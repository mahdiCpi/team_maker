import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ComposerSurface } from "@/components/composer/composer-surface";

import {
  build,
  buildWithSubstitution,
  errorSpecInvalid,
  messageTurn2,
} from "./fixtures";
import {
  box,
  buildPanel,
  completeFirstTurn,
  createFetchQueue,
  openSpecEditor,
  transcript,
} from "./harness";

/**
 * AC 3, AC 4 and AC 5 — `Run it now`, `Build team`, the review editor, and the
 * outcome reported inline.
 *
 * `fetch` and `next/navigation` are stubbed (see `harness.tsx`); the bodies are
 * live captures. This is a mocked integration, not proof the API works.
 */

const pushMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
  usePathname: () => "/",
}));

let queue: ReturnType<typeof createFetchQueue>;

beforeEach(() => {
  queue = createFetchQueue();
  queue.install();
  pushMock.mockClear();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("AC 3 — Run it now", () => {
  it("appears from the first proposal onward and builds immediately", async () => {
    const user = userEvent.setup();
    render(<ComposerSurface />);
    expect(
      screen.queryByRole("button", { name: "Run it now" })
    ).not.toBeInTheDocument();

    await completeFirstTurn(user, queue);
    queue.queueResponse(200, build);
    await user.click(screen.getByRole("button", { name: "Run it now" }));

    await waitFor(() => expect(queue.buildRequests()).toHaveLength(1));
    expect(queue.buildRequests()[0].method).toBe("POST");
  });

  it("bypasses the review toggle even when review is on", async () => {
    const user = userEvent.setup();
    render(<ComposerSurface />);
    await completeFirstTurn(user, queue);

    await user.click(screen.getByRole("switch", { name: "Review before build" }));
    queue.queueResponse(200, build);
    await user.click(screen.getByRole("button", { name: "Run it now" }));

    await waitFor(() => expect(queue.buildRequests()).toHaveLength(1));
    // No editor interposed — that is what "skips further tuning" means.
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("builds; it does not start a run", async () => {
    const user = userEvent.setup();
    render(<ComposerSurface />);
    await completeFirstTurn(user, queue);
    queue.queueResponse(200, build);
    await user.click(screen.getByRole("button", { name: "Run it now" }));
    await waitFor(() => expect(buildPanel()).toBeInTheDocument());

    // A run needs a goal, and the goal is entered in the Workspace (2.4).
    expect(queue.requests.map((r) => r.url)).toEqual([
      "/api/compose/sessions",
      expect.stringMatching(/\/build$/),
    ]);
    expect(document.body.textContent).not.toMatch(/Running ·|run started/i);
  });

  it("states why it cannot run instead of being a silent dead control", async () => {
    const user = userEvent.setup();
    render(<ComposerSurface />);
    await completeFirstTurn(user, queue);

    queue.queueHeld(build);
    await user.click(screen.getByRole("button", { name: "Run it now" }));

    const runNow = screen.getByRole("button", { name: "Run it now" });
    await waitFor(() => expect(runNow).toHaveAttribute("aria-disabled", "true"));
    expect(
      document.querySelector('[data-slot="composer-actions-reason"]')?.textContent?.trim()
        .length
    ).toBeGreaterThan(0);
    // `aria-disabled`, not `disabled`: the reason stays reachable by keyboard.
    expect(runNow).not.toBeDisabled();
    queue.releaseHeld();
  });
});

describe("AC 4 — Build team and the review toggle", () => {
  it("defaults review off and builds with no interstitial screen", async () => {
    const user = userEvent.setup();
    render(<ComposerSurface />);
    await completeFirstTurn(user, queue);

    expect(
      screen.getByRole("switch", { name: "Review before build" })
    ).toHaveAttribute("aria-checked", "false");

    queue.queueResponse(200, build);
    await user.click(screen.getByRole("button", { name: "Build team" }));
    await waitFor(() => expect(queue.buildRequests()).toHaveLength(1));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("never auto-builds after a turn, so a second turn stays possible", async () => {
    const user = userEvent.setup();
    const { container } = render(<ComposerSurface />);
    await completeFirstTurn(user, queue);

    // Counted, not asserted absent: a component rendering nothing would also
    // have "no build request".
    expect(queue.requests).toHaveLength(1);
    expect(queue.buildRequests()).toHaveLength(0);

    queue.queueResponse(200, messageTurn2);
    await user.type(box(), "add a fact-checker");
    await user.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() =>
      expect(
        container.querySelectorAll('[data-slot="composer-message"]')
      ).toHaveLength(4)
    );
    expect(queue.buildRequests()).toHaveLength(0);
  });

  it("opens the editor instead of building when review is on", async () => {
    const user = userEvent.setup();
    render(<ComposerSurface />);
    await completeFirstTurn(user, queue);

    await user.click(screen.getByRole("switch", { name: "Review before build" }));
    await user.click(screen.getByRole("button", { name: "Build team" }));

    // Queried by role: "Review before build" is also the toggle's label, so an
    // unscoped text match finds two nodes.
    const dialog = await screen.findByRole("dialog");
    expect(
      within(dialog).getByRole("heading", { name: "Review before build" })
    ).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Role 1 name" })).toHaveValue(
      "researcher"
    );
    expect(queue.buildRequests()).toHaveLength(0);
  });
});

describe("AC 4 — the spec editor", () => {
  it("exposes roles, tasks and a per-agent provider/model control", async () => {
    const user = userEvent.setup();
    render(<ComposerSurface />);
    await openSpecEditor(user, queue);

    expect(screen.getByRole("textbox", { name: "Role 1 name" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Task 1 name" })).toBeInTheDocument();
    expect(
      screen.getByRole("combobox", { name: "Role 1 provider" })
    ).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Role 1 model" })).toBeInTheDocument();
  });

  it("offers no model catalogue — the model is free text", async () => {
    const user = userEvent.setup();
    render(<ComposerSurface />);
    await openSpecEditor(user, queue);

    const model = screen.getByRole("textbox", { name: "Role 1 model" });
    expect(model.tagName).toBe("INPUT");
    await user.type(model, "some-unreleased-model");
    expect(model).toHaveValue("some-unreleased-model");

    const options = within(
      screen.getByRole("combobox", { name: "Role 1 provider" })
    ).getAllByRole("option");
    expect(options.map((option) => option.getAttribute("value"))).toEqual([
      "",
      "anthropic",
      "openai",
      "xai",
      "google",
      "ollama",
      "openrouter",
    ]);
  });

  it("saves through PUT .../spec and never sends output_path", async () => {
    const user = userEvent.setup();
    render(<ComposerSurface />);
    await openSpecEditor(user, queue);

    const description = screen.getByRole("textbox", { name: "Role 1 description" });
    await user.clear(description);
    await user.type(description, "Researches deeply.");
    queue.queueResponse(200, messageTurn2);
    await user.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(queue.requests).toHaveLength(2));
    expect(queue.requests[1].url).toMatch(/\/spec$/);
    expect(queue.requests[1].method).toBe("PUT");
    expect(Object.keys(queue.requests[1].body as object).sort()).toEqual([
      "desired_roles",
      "desired_tasks",
      "purpose",
      "team_name",
    ]);
    expect(JSON.stringify(queue.requests[1].body)).not.toMatch(/output_path/);
  });

  it("re-renders from the response, not from the local edit", async () => {
    const user = userEvent.setup();
    render(<ComposerSurface />);
    await openSpecEditor(user, queue);

    const name = screen.getByRole("textbox", { name: "Team name" });
    await user.clear(name);
    await user.type(name, "local_only_value");

    // The server answers with its own re-serialisation: four roles including
    // fact_checker, a shape the local edit never asked for.
    queue.queueResponse(200, messageTurn2);
    await user.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() =>
      expect(screen.getByRole("textbox", { name: "Team name" })).toHaveValue(
        "article_team"
      )
    );
    expect(screen.getByRole("textbox", { name: "Role 3 name" })).toHaveValue(
      "fact_checker"
    );
    expect(screen.getByRole("textbox", { name: "Role 4 name" })).toHaveValue("critic");
    expect(screen.queryByDisplayValue("local_only_value")).toBeNull();
    // And the save is confirmed rather than silently succeeding.
    expect(screen.getByText(/what the server stored/)).toBeInTheDocument();
  });

  it("blocks the build with inline reasons from fields[] and keeps the good spec", async () => {
    const user = userEvent.setup();
    render(<ComposerSurface />);
    await openSpecEditor(user, queue);

    // Rename a role so the captured 422 (orphaned tasks) is the honest answer,
    // and repoint every task so the client pre-flight passes and the SERVER's
    // rejection is what gets rendered.
    const roleName = screen.getByRole("textbox", { name: "Role 1 name" });
    await user.clear(roleName);
    await user.type(roleName, "renamed_role");
    for (const index of [1, 2, 3]) {
      await user.selectOptions(
        screen.getByRole("combobox", { name: `Task ${index} role` }),
        "renamed_role"
      );
    }
    queue.queueResponse(422, errorSpecInvalid);
    await user.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() =>
      expect(
        screen.getByText(
          /is assigned to 'writer', which is not one of the team's roles/
        )
      ).toBeInTheDocument()
    );
    // Rendered once, inside the editor — not duplicated into the alert behind
    // the dialog, where it would be invisible anyway.
    expect(
      document.querySelectorAll('[data-slot="composer-failure"]')
    ).toHaveLength(0);
    // The editor keeps the draft; the previous good spec is untouched.
    expect(screen.getByRole("textbox", { name: "Role 1 name" })).toHaveValue(
      "renamed_role"
    );
    expect(
      screen.getAllByRole("button", { name: "Build team" }).at(-1)
    ).toHaveAttribute("aria-disabled", "true");
    expect(queue.buildRequests()).toHaveLength(0);
  });

  it("refuses an unnamed role before the request leaves the browser", async () => {
    const user = userEvent.setup();
    render(<ComposerSurface />);
    await openSpecEditor(user, queue);

    for (const index of [1, 2, 3]) {
      await user.clear(screen.getByRole("textbox", { name: `Role ${index} name` }));
    }
    await user.click(screen.getByRole("button", { name: "Save" }));

    // One reason per blanked role — asserted as a count, because `getByText`
    // throws on three matches and `queryByText` would pass on none.
    expect(await screen.findAllByText(/Give the role a name/)).toHaveLength(3);
    expect(queue.requests).toHaveLength(1);
  });

  it("caps modal depth at one — no dialog inside the dialog", async () => {
    const user = userEvent.setup();
    render(<ComposerSurface />);
    await openSpecEditor(user, queue);
    // The provider control is a native select, not a second overlay.
    expect(screen.getAllByRole("dialog")).toHaveLength(1);
  });
});

describe("AC 5 — the build outcome", () => {
  async function buildWith(
    user: ReturnType<typeof userEvent.setup>,
    body: unknown
  ) {
    render(<ComposerSurface />);
    await completeFirstTurn(user, queue);
    queue.queueResponse(200, body);
    await user.click(screen.getByRole("button", { name: "Run it now" }));
    await waitFor(() => expect(buildPanel()).toBeInTheDocument());
  }

  it("reports name, path, counts and validation on this surface", async () => {
    const user = userEvent.setup();
    await buildWith(user, build);

    const scoped = within(buildPanel() as HTMLElement);
    expect(scoped.getByText("article_team")).toBeInTheDocument();
    expect(
      scoped.getByText(/3 agents and 3 tasks across 17 files/)
    ).toBeInTheDocument();
    expect(scoped.getByText("Passed")).toBeInTheDocument();
    expect(
      buildPanel()?.querySelector('[data-slot="build-output-path"]')?.textContent
    ).toMatch(/generated_teams/);
  });

  it("renders output_path as text only — no link, no input, no picker", async () => {
    const user = userEvent.setup();
    await buildWith(user, build);

    const panel = buildPanel() as HTMLElement;
    expect(panel.querySelector('[data-slot="build-output-path"]')?.tagName).toBe("P");
    expect(panel.querySelector("a")).toBeNull();
    expect(panel.querySelector("input")).toBeNull();
    expect(panel.querySelector("button")).toBeNull();
    // And nothing on the surface ever sends it back.
    expect(
      queue.requests.some((r) => JSON.stringify(r.body ?? {}).includes("output_path"))
    ).toBe(false);
  });

  it("surfaces a model substitution rather than claiming the requested model", async () => {
    const user = userEvent.setup();
    await buildWith(user, buildWithSubstitution);

    const rows = (buildPanel() as HTMLElement).querySelectorAll(
      '[data-slot="build-substitution"]'
    );
    expect(rows).toHaveLength(1);
    expect(rows[0].textContent).toContain("critic");
    expect(rows[0].textContent).toContain("openai/gpt-4o-min");
    expect(rows[0].textContent).toContain("openai/gpt-4o-mini");
  });

  it("does not navigate to a surface that cannot show the outcome", async () => {
    const user = userEvent.setup();
    await buildWith(user, build);
    // My Teams (2.5) and the Workspace (2.4) do not exist yet.
    expect(pushMock).not.toHaveBeenCalled();
    expect(document.body.textContent).not.toMatch(/My Teams|workspace/i);
  });

  it("keeps the conversation alive after a build", async () => {
    const user = userEvent.setup();
    await buildWith(user, build);
    expect(box()).not.toBeDisabled();
    expect(within(transcript()).getByText("You")).toBeInTheDocument();
  });

  it("replaces a stale result when a second build starts", async () => {
    const user = userEvent.setup();
    await buildWith(user, build);

    queue.queueHeld(buildWithSubstitution);
    await user.click(screen.getByRole("button", { name: "Run it now" }));
    // Otherwise a success panel from the previous attempt sits next to a
    // spinner, claiming a build this attempt has not made.
    await waitFor(() => expect(buildPanel()).toBeNull());
    queue.releaseHeld();
    await waitFor(() => expect(buildPanel()).toBeInTheDocument());
  });
});
