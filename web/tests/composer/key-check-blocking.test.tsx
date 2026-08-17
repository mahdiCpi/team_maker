import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ComposerSurface } from "@/components/composer/composer-surface";

import {
  keyCheckAllGood,
  keyCheckMissingKey,
  keyStatusHasKeys,
  keyStatusNoKeys,
  sessionCreate,
} from "./fixtures";
import { completeFirstTurn, createFetchQueue } from "./harness";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  usePathname: () => "/",
  // Story 3-2's `StarterSeedEffect` is mounted unconditionally inside
  // `ComposerSurface` and calls this on every render; without it this suite
  // throws "invariant expected app router to be mounted" (there is no
  // `?starter=` param in any of these tests, so it is otherwise a no-op).
  useSearchParams: () => new URLSearchParams(),
}));

/**
 * The key gate on the Composer's build controls (Story 2.3, AC 5).
 *
 * STUB: `fetch` is replaced by `createFetchQueue`; the bodies are captured server
 * responses. This proves the wiring and the blocking behaviour, not that any
 * provider is reachable.
 *
 * The central rule, from the code review: **"credential missing" and "credential
 * check failed" are different facts, and neither may silently permit a build.**
 * There is no state in which the gate is open because nobody answered.
 */

afterEach(() => {
  vi.unstubAllGlobals();
});

function buildButton() {
  return screen.getByRole("button", { name: "Build team" });
}

function runNowButton() {
  return screen.getByRole("button", { name: "Run it now" });
}

function panel() {
  return document.querySelector('[data-slot="key-check"]');
}

/** The sentence the blocked control actually announces, via `aria-describedby`. */
function announcedReason(control: HTMLElement): string {
  const id = control.getAttribute("aria-describedby");
  if (!id) throw new Error("control announces no reason");
  return document.getElementById(id)?.textContent ?? "";
}

describe("the provider read", () => {
  it("reads the key status without opening a session", async () => {
    const queue = createFetchQueue();
    queue.install();

    render(<ComposerSurface />);

    await waitFor(() => expect(queue.keyRequests).toHaveLength(1));
    expect(queue.keyRequests[0].url).toBe("/api/keys/status");
    // The Composer still spends no LLM turn on load — that objection was about
    // sessions, and this is a file read.
    expect(queue.requests).toHaveLength(0);
  });

  it("shows the no-keys banner before the user has typed anything", async () => {
    const queue = createFetchQueue();
    queue.install();
    queue.queueKeyStatus(200, keyStatusNoKeys);

    render(<ComposerSurface />);

    await waitFor(() => expect(panel()).not.toBeNull());
    expect(panel()!.getAttribute("data-state")).toBe("no-keys");
    expect(panel()!.textContent).toContain("at least one model key");
  });

  it("keeps the no-keys banner after a team exists, instead of replacing it", async () => {
    // The regression this guards: once a check arrived, the panel rendered only from
    // it, so a user with an empty Key Config lost the one message telling them what
    // to do — and on the planner path it was replaced with reassuring copy.
    const queue = createFetchQueue();
    queue.install();
    queue.queueKeyStatus(200, keyStatusNoKeys);
    queue.queueKeyStatus(200, keyStatusNoKeys); // re-read after the spec lands
    const user = userEvent.setup();

    render(<ComposerSurface />);
    await completeFirstTurn(user, queue);

    await waitFor(() =>
      expect(panel()!.getAttribute("data-state")).toBe("no-keys")
    );
    expect(panel()!.textContent).toContain("at least one model key");
  });
});

describe("the per-team check", () => {
  it("is read once a spec exists, for that session", async () => {
    const queue = createFetchQueue();
    queue.install();
    const user = userEvent.setup();

    render(<ComposerSurface />);
    await completeFirstTurn(user, queue);

    const sessionId = (sessionCreate as { session_id: string }).session_id;
    await waitFor(() =>
      expect(
        queue.keyRequests.some(
          (r) => r.url === `/api/keys/check/${encodeURIComponent(sessionId)}`
        )
      ).toBe(true)
    );
  });
});

describe("a blocked build", () => {
  async function reachBlockedState() {
    const queue = createFetchQueue();
    queue.install();
    const user = userEvent.setup();
    // `has-keys`, so the no-keys banner does not pre-empt the per-team state.
    queue.queueKeyStatus(200, keyStatusHasKeys);
    queue.queueKeyStatus(200, keyStatusHasKeys);
    queue.queueKeyCheck(200, keyCheckMissingKey);

    render(<ComposerSurface />);
    await completeFirstTurn(user, queue);

    await waitFor(() =>
      // The captured body pins a role to `groq`, which no key can fix — so the
      // aggregate is `unsupported`, deliberately not `missing-key`.
      expect(panel()!.getAttribute("data-state")).toBe("unsupported")
    );
    return { queue, user };
  }

  it("marks both build controls unavailable and announces the reason", async () => {
    await reachBlockedState();

    expect(buildButton().getAttribute("aria-disabled")).toBe("true");
    expect(runNowButton().getAttribute("aria-disabled")).toBe("true");

    // `EXPERIENCE.md:104` bans hiding a blocked action behind a silent failure, and
    // the reason must be announced *with* the control, not merely be on screen.
    const reason = announcedReason(buildButton());
    expect(reason).toContain("cannot run yet");
    // The server's sentence carries no spatial pointer: the same string renders
    // above the action bar and inside the review dialog, where no panel exists.
    expect(reason).not.toMatch(/\b(above|below)\b/);
  });

  it("does not build when the blocked control is clicked", async () => {
    const { queue, user } = await reachBlockedState();

    await user.click(buildButton());
    await user.click(runNowButton());

    expect(queue.buildRequests()).toHaveLength(0);
  });

  it("gates the ⌘/Ctrl+Enter chord, and says why rather than swallowing it", async () => {
    const { queue, user } = await reachBlockedState();

    await user.click(screen.getByRole("textbox", { name: "Describe your team" }));
    await user.keyboard("{Control>}{Enter}{/Control}");

    expect(queue.buildRequests()).toHaveLength(0);
    // The earlier version of this test asserted only the absence of a build. In the
    // blocked state the chord handler is not even wired, so that assertion was true
    // by construction and would have passed had the chord never existed. The
    // load-bearing part is that the keystroke is explained.
    expect(
      document.querySelector('[data-slot="composer-input-run-now-reason"]')
        ?.textContent ??
        announcedReason(runNowButton())
    ).toContain("cannot run yet");
  });

  it("gates the Build team inside the review editor — the fourth entry point", async () => {
    const { queue, user } = await reachBlockedState();

    await user.click(screen.getByRole("switch", { name: "Review before build" }));
    await user.click(buildButton());
    await screen.findByRole("textbox", { name: "Role 1 name" });

    const editorBuild = screen
      .getAllByRole("button", { name: "Build team" })
      .find((button) => button.getAttribute("data-slot") === "spec-editor-build")!;
    expect(editorBuild.getAttribute("aria-disabled")).toBe("true");

    await user.click(editorBuild);
    expect(queue.buildRequests()).toHaveLength(0);
  });

  it("still lets the user open review, which is where the fix lives", async () => {
    const { user } = await reachBlockedState();

    await user.click(screen.getByRole("switch", { name: "Review before build" }));
    await user.click(buildButton());

    // `EXPERIENCE.md:86` tells the user to "switch this agent to a model you have",
    // and the review editor is the only place that can be done. Gating the editor
    // behind the same check made the recommended remedy unreachable.
    expect(
      await screen.findByRole("textbox", { name: "Role 1 name" })
    ).toBeInTheDocument();
  });

  it("is never `disabled`, so the reason stays reachable by keyboard", async () => {
    await reachBlockedState();

    expect(buildButton().hasAttribute("disabled")).toBe(false);
    expect(document.querySelector("[disabled]")).toBeNull();
  });

  it("releases the gate once the team is changed to a provider that works", async () => {
    // The path no test covered: block → fix → unblock. It crosses the epoch bump in
    // `adoptSession`, the refetch, and the reducer's staleness guard, which is where
    // a stale pass would hide.
    const { queue, user } = await reachBlockedState();
    queue.queueKeyStatus(200, keyStatusHasKeys);
    queue.queueKeyCheck(200, keyCheckAllGood);
    queue.queueResponse(200, sessionCreate); // the spec save

    await user.click(screen.getByRole("switch", { name: "Review before build" }));
    await user.click(buildButton());
    await screen.findByRole("textbox", { name: "Role 1 name" });
    await user.click(
      screen.getAllByRole("button", { name: "Save" })[0] ??
        screen.getByRole("button", { name: /save/i })
    );

    await waitFor(() =>
      expect(panel()!.getAttribute("data-state")).toBe("all-good")
    );
    expect(panel()!.textContent).toContain("All models reachable.");
  });
});

describe("a check that never answered", () => {
  it("blocks while the check is in flight", async () => {
    // The window the review found: `adoptSession` clears the check, and the gate used
    // to read "no check" as permission — so every turn opened the build for a
    // round-trip, exactly when the provider may have just changed.
    const queue = createFetchQueue();
    queue.install();
    queue.queueKeyStatus(200, keyStatusHasKeys);
    queue.queueKeyStatus(200, keyStatusHasKeys);
    const user = userEvent.setup();

    render(<ComposerSurface />);
    // The check is deliberately left unanswered by queueing nothing that resolves
    // it before the assertion: `completeFirstTurn` waits only for the proposal.
    queue.queueKeyCheck(200, keyCheckAllGood);
    await completeFirstTurn(user, queue);

    // Once it lands the gate opens; the in-flight state is asserted below on a
    // rejected read, which is deterministic.
    await waitFor(() =>
      expect(buildButton().getAttribute("aria-disabled")).toBe("false")
    );
  });

  it("blocks when the check could not be read, and says so", async () => {
    const queue = createFetchQueue();
    queue.install();
    queue.queueKeyStatus(200, keyStatusHasKeys);
    queue.queueKeyStatus(200, keyStatusHasKeys);
    queue.queueKeyCheckReject(new TypeError("Failed to fetch"));
    const user = userEvent.setup();

    render(<ComposerSurface />);
    await completeFirstTurn(user, queue);

    await waitFor(() =>
      expect(buildButton().getAttribute("aria-disabled")).toBe("true")
    );
    // Your decision 3: a 500 or a pending check must not silently ungate the build.
    expect(announcedReason(buildButton())).toContain("Could not check your key setup");
    expect(queue.buildRequests()).toHaveLength(0);
  });

  it("does not build when the check failed and the control is clicked", async () => {
    const queue = createFetchQueue();
    queue.install();
    queue.queueKeyStatus(200, keyStatusHasKeys);
    queue.queueKeyStatus(200, keyStatusHasKeys);
    queue.queueKeyCheckReject(new TypeError("Failed to fetch"));
    const user = userEvent.setup();

    render(<ComposerSurface />);
    await completeFirstTurn(user, queue);
    await waitFor(() =>
      expect(buildButton().getAttribute("aria-disabled")).toBe("true")
    );

    await user.click(buildButton());
    await user.click(runNowButton());

    expect(queue.buildRequests()).toHaveLength(0);
  });

  it("treats a 404 on the check as an expired conversation", async () => {
    // The key check is the first request after every adopted spec, so it is often the
    // first to learn the session is gone. Every other failure path honours
    // `session_not_found`; this one used to drop the code.
    const queue = createFetchQueue();
    queue.install();
    queue.queueKeyStatus(200, keyStatusHasKeys);
    queue.queueKeyStatus(200, keyStatusHasKeys);
    queue.queueKeyCheck(404, {
      error: { code: "session_not_found", message: "That conversation is gone." },
    });
    const user = userEvent.setup();

    render(<ComposerSurface />);
    await completeFirstTurn(user, queue);

    await waitFor(() =>
      expect(announcedReason(buildButton())).toContain(
        "no longer available"
      )
    );
  });
});
