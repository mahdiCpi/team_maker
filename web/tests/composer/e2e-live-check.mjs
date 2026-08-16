/**
 * A one-off, real end-to-end check of the Story 2.2 Composer.
 *
 * Not part of any test lane and not wired into CI — Story 2.2 adds no browser
 * test framework (that would be a new dependency, which the story does not
 * authorise). This is a manual verification harness: it drives a real Chromium
 * against a real `next dev` server proxying to a real `uvicorn api.main:app`,
 * with real Anthropic authoring turns, so the run costs real LLM calls.
 *
 * **Not collected by vitest** — the filename carries no `.test.`/`.spec.`
 * segment, so `npm test` ignores it. It sits here rather than in `scripts/`
 * because the story's Project Structure Notes list `scripts/` as untouched, and
 * `web/tests/` is already outside Guard A's `SCAN_ROOTS` so this adds no newly
 * unguarded directory.
 *
 * `playwright` is deliberately NOT a dependency of this project. Run it from a
 * throwaway install so `web/package.json` stays unchanged:
 *
 *   # terminal 1
 *   make api-dev
 *   # terminal 2
 *   npm --prefix web run dev -- --port 3100
 *   # terminal 3
 *   mkdir /tmp/pwrun && cd /tmp/pwrun && npm init -y && npm install playwright
 *   cp <repo>/web/tests/composer/e2e-live-check.mjs run.mjs
 *   CHROME_PATH=<an existing chromium> COMPOSER_URL=http://localhost:3100/ node run.mjs
 *
 * Env: COMPOSER_URL (default http://localhost:3100/), CHROME_PATH (optional).
 */
import { chromium } from "playwright";

// Not named `URL`: that shadows the global constructor used below.
const COMPOSER_URL = process.env.COMPOSER_URL ?? "http://localhost:3100/";

const consoleErrors = [];
const pageErrors = [];
const apiCalls = [];

function log(step, detail = "") {
  console.log(`[e2e] ${step}${detail ? ` — ${detail}` : ""}`);
}

// `CHROME_PATH` lets the run reuse an already-downloaded Chromium instead of
// requiring `npx playwright install` for an exact build number.
const browser = await chromium.launch({
  executablePath: process.env.CHROME_PATH || undefined,
});
const page = await browser.newPage();

page.on("console", (message) => {
  if (message.type() === "error") consoleErrors.push(message.text());
});
page.on("pageerror", (error) => pageErrors.push(String(error)));
page.on("response", (response) => {
  const url = new URL(response.url());
  if (url.pathname.startsWith("/api/")) {
    apiCalls.push(`${response.request().method()} ${url.pathname} -> ${response.status()}`);
  }
});

let failures = 0;
let total = 0;
function check(label, condition) {
  total += 1;
  if (condition) log(`PASS ${label}`);
  else {
    failures += 1;
    log(`FAIL ${label}`);
  }
}

try {
  await page.goto(COMPOSER_URL, { waitUntil: "networkidle" });

  // AC 1 — the initial state.
  const heading = await page
    .locator('[data-slot="empty-title"]')
    .first()
    .textContent();
  check(`heading is "Describe your team."`, heading?.trim() === "Describe your team.");

  const box = page.getByRole("textbox", { name: "Describe your team" });
  check("the input is a real textarea", (await box.evaluate((el) => el.tagName)) === "TEXTAREA");
  check(
    "placeholder is the mockup's",
    (await box.getAttribute("placeholder"))?.startsWith("e.g. a team that researches")
  );

  // AC 1 / AC 2 — a real turn, driven by Enter.
  await box.click();
  await box.fill("a team that researches a topic and writes a short brief");
  log("submitting the first turn (real LLM call, may take a while)");
  await page.keyboard.press("Enter");

  // AC 2 — the input must stay usable while the turn is in flight.
  const thinking = page.locator('[data-slot="composer-thinking"]');
  await thinking.waitFor({ state: "visible", timeout: 10_000 });
  check("a thinking indicator appears", await thinking.isVisible());
  check("the input is NOT disabled mid-turn", !(await box.isDisabled()));
  await box.type("typed during the turn");
  check(
    "typing during the turn is kept",
    (await box.inputValue()).includes("typed during the turn")
  );

  const runNow = page.getByRole("button", { name: "Run it now" });
  await runNow.waitFor({ state: "visible", timeout: 240_000 });
  log("first proposal received");

  const messages = page.locator('[data-slot="composer-message"]');
  check("two messages after one turn", (await messages.count()) === 2);
  const reply = (await messages.nth(1).textContent()) ?? "";
  check("the reply asks exactly one question", (reply.match(/\?/g) ?? []).length === 1);
  check("Run it now is present from the first proposal", await runNow.isVisible());

  // AC 3 / AC 5 — build, and report inline.
  await box.fill("");
  log("building (real generation + per-provider model calls)");
  await runNow.click();

  const panel = page.locator('[data-slot="build-result"]');
  const alert = page.locator('[data-slot="composer-failure"]');
  // Raced against the failure alert rather than waited for blindly. A build that
  // 409s on `output_exists` — routine, because `output_path` is derived from the
  // LLM-chosen team name and pinned, so a leftover directory from a previous run
  // of this very harness triggers it — otherwise surfaced as a bare 240s timeout
  // with no indication of the cause.
  await Promise.race([
    panel.waitFor({ state: "visible", timeout: 240_000 }),
    alert.waitFor({ state: "visible", timeout: 240_000 }),
  ]);
  if (!(await panel.isVisible())) {
    const why = (await alert.textContent()) ?? "(no message rendered)";
    log(`build did not succeed — the surface says: ${why.trim()}`);
    log(
      "if that is `output_exists`, clear the matching directory under generated_teams/ and re-run"
    );
  }
  check("the build result panel renders on this surface", await panel.isVisible());

  const outputPath = await panel
    .locator('[data-slot="build-output-path"]')
    .textContent();
  check("output_path is shown", Boolean(outputPath && outputPath.length > 0));
  check(
    "output_path is text, not a link or an input",
    (await panel.locator("a").count()) === 0 &&
      (await panel.locator("input").count()) === 0
  );
  check("we did not navigate away", new URL(page.url()).pathname === "/");
  check("the conversation is still usable", !(await box.isDisabled()));

  // Added after the first code review, which found that a second build could
  // only ever 409 (the output path is pinned per session) while both controls
  // stayed enabled, and that the doomed attempt wiped the success panel.
  check(
    "a second build is blocked rather than offered",
    (await runNow.getAttribute("aria-disabled")) === "true"
  );
  const reason = await page
    .locator('[data-slot="composer-actions-reason"]')
    .textContent();
  check(
    "the block states why",
    Boolean(reason && /has been built/i.test(reason))
  );
  check(
    "a restart control is offered instead of a dead end",
    await page.getByRole("button", { name: "Start a new conversation" }).isVisible()
  );
  const beforeSecond = apiCalls.length;
  // `force` because Playwright's actionability check treats `aria-disabled` as
  // not-enabled and would wait forever — which is itself evidence the attribute
  // is real. The point of the click is to prove the handler does nothing.
  await runNow.click({ force: true });
  await page.waitForTimeout(300);
  check("clicking the blocked control issues no request", apiCalls.length === beforeSecond);
  check("the success panel survives the click", await panel.isVisible());

  log("api calls observed", JSON.stringify(apiCalls));
} finally {
  await browser.close();
}

if (consoleErrors.length > 0) console.log("[e2e] console errors:", consoleErrors);
if (pageErrors.length > 0) console.log("[e2e] page errors:", pageErrors);
check("no uncaught page errors", pageErrors.length === 0);
check("no console errors", consoleErrors.length === 0);

// Prints the count. The first run of this harness reported "17/17" in the story
// file when the script had 16 checks and the pasted log showed 14 — a figure
// asserted rather than measured. Now the number comes from the run itself.
console.log(
  failures === 0
    ? `[e2e] ALL CHECKS PASSED (${total - failures}/${total})`
    : `[e2e] ${failures} of ${total} CHECK(S) FAILED`
);
process.exit(failures === 0 ? 0 : 1);
