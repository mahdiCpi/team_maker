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

    // Edited via `Purpose`, not a role name: renaming a role orphans the tasks
    // that point at it, which the client-side referential check now refuses
    // before any request — so the save would never reach the server and this
    // test would prove nothing.
    const purpose = screen.getByRole("textbox", { name: "Purpose" });
    await user.clear(purpose);
    await user.type(purpose, "local_only_value");

    // The server answers with its own re-serialisation: four roles including
    // fact_checker, and its own purpose — a shape the local edit never asked for.
    queue.queueResponse(200, messageTurn2);
    await user.click(screen.getByRole("button", { name: "Save" }));

    // The captured turn-2 order is researcher, writer, fact_checker, critic.
    await waitFor(() =>
      expect(screen.getByRole("textbox", { name: "Role 3 name" })).toHaveValue(
        "fact_checker"
      )
    );
    expect(screen.getByRole("textbox", { name: "Role 1 name" })).toHaveValue(
      "researcher"
    );
    expect(screen.getByRole("textbox", { name: "Role 4 name" })).toHaveValue("critic");
    // The local edit is gone: the form re-seeded from the response.
    expect(screen.queryByDisplayValue("local_only_value")).toBeNull();
    expect(screen.getByRole("textbox", { name: "Purpose" })).not.toHaveValue(
      "local_only_value"
    );
    // And the save is confirmed rather than silently succeeding.
    expect(screen.getByText(/what the server stored/)).toBeInTheDocument();
  });

  it("shows the team name but does not offer to edit it", async () => {
    const user = userEvent.setup();
    render(<ComposerSurface />);
    await openSpecEditor(user, queue);

    // AC 4 names exactly three editable dimensions; renaming is Story 2.5's, and
    // `output_path` is pinned from the first spec so a rename would desync the
    // path shown on the build panel.
    expect(
      document.querySelector('[data-slot="spec-editor-team-name"]')?.textContent
    ).toBe("article_team");
    expect(screen.queryByRole("textbox", { name: "Team name" })).toBeNull();
    // `purpose` stays editable — it is the one other accepted field with no
    // such side effect.
    expect(screen.getByRole("textbox", { name: "Purpose" })).toBeInTheDocument();
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
    const pathNode = panel.querySelector('[data-slot="build-output-path"]');
    expect(pathNode?.tagName).toBe("P");
    // Scoped to output_path's own container, not the whole panel: Story 2.4
    // added a legitimate "Open in workspace" link elsewhere in this card,
    // and this guard's job is output_path specifically, never having been
    // about the panel containing no control at all.
    const container = pathNode?.parentElement as HTMLElement;
    expect(container.querySelector("a")).toBeNull();
    expect(container.querySelector("input")).toBeNull();
    expect(container.querySelector("button")).toBeNull();
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

  it("does not automatically navigate to the Workspace", async () => {
    // Renamed: this test's title asserted "does not navigate to a surface
    // that cannot show the outcome", which went false the moment the
    // Workspace shipped (Story 2.4) — a test title is a testable assertion
    // (defect class 5). What it still guards is that reaching the Workspace
    // is a link the user clicks, never an automatic redirect: Story 2.2
    // already proved `router.push` is never called from this surface, and
    // auto-navigating away would destroy the conversation that produced the
    // team.
    const user = userEvent.setup();
    await buildWith(user, build);
    // My Teams (2.5) still does not exist.
    expect(pushMock).not.toHaveBeenCalled();
    expect(document.body.textContent).not.toMatch(/My Teams/i);
    // "workspace" is now legitimate: the build result links to it.
    expect(document.body.textContent).toMatch(/workspace/i);
    expect(screen.getByRole("link", { name: "Open in workspace" })).toBeInTheDocument();
  });

  it("keeps the conversation alive after a build", async () => {
    const user = userEvent.setup();
    await buildWith(user, build);
    expect(box()).not.toBeDisabled();
    expect(within(transcript()).getByText("You")).toBeInTheDocument();
  });

  it("blocks a second build, which could only ever 409, and offers a way out", async () => {
    const user = userEvent.setup();
    await buildWith(user, build);

    // `output_path` is derived from the first spec and pinned for the session's
    // life (`api/output.py`), so a second build in this conversation cannot
    // succeed. Offering the button anyway meant the only way to learn that was
    // to press it — and the resulting error wiped the success panel, the one
    // place the output path was ever shown.
    for (const name of ["Run it now", "Build team"]) {
      expect(screen.getByRole("button", { name })).toHaveAttribute(
        "aria-disabled",
        "true"
      );
    }
    expect(
      document.querySelector('[data-slot="composer-actions-reason"]')?.textContent
    ).toMatch(/has been built/i);

    // Clicking anyway issues no request, and the panel survives.
    await user.click(screen.getByRole("button", { name: "Run it now" }));
    expect(queue.buildRequests()).toHaveLength(1);
    expect(buildPanel()).toBeInTheDocument();

    // And there is a real control out of the dead end, not just an error.
    const restart = screen.getByRole("button", {
      name: "Start a new conversation",
    });
    await user.click(restart);
    await waitFor(() =>
      expect(screen.getByText("Describe your team.")).toBeInTheDocument()
    );
    expect(buildPanel()).toBeNull();
  });

  it("clears a stale build panel when the next turn changes the team", async () => {
    const user = userEvent.setup();
    await buildWith(user, build);
    expect(buildPanel()).toBeInTheDocument();

    queue.queueResponse(200, messageTurn2);
    await user.type(box(), "add a fact-checker");
    await user.click(screen.getByRole("button", { name: "Send" }));

    // The panel described a 3-role team; the conversation now has 4. Leaving it
    // rendered — as the newest entry in the transcript, no less — claimed the
    // team on disk matched the team on screen.
    await waitFor(() => expect(buildPanel()).toBeNull());
    expect(within(transcript()).getByText(/fact_checker/)).toBeInTheDocument();
  });
});

describe("the build outcome is scrolled into view", () => {
  it("scrolls when the panel appears, though it appends no transcript entry", async () => {
    // jsdom implements no `scrollIntoView` at all, which is why the production
    // code guards on `typeof`. That absence is also why this needed an explicit
    // stub: without one, removing the effect's dependency on the build signal
    // left the whole suite green while the outcome of the primary action
    // rendered below the fold.
    const scrollIntoView = vi.fn();
    Object.defineProperty(Element.prototype, "scrollIntoView", {
      configurable: true,
      writable: true,
      value: scrollIntoView,
    });
    try {
      const user = userEvent.setup();
      render(<ComposerSurface />);
      await completeFirstTurn(user, queue);

      const beforeBuild = scrollIntoView.mock.calls.length;
      expect(beforeBuild).toBeGreaterThan(0); // the turn itself scrolled

      queue.queueResponse(200, build);
      await user.click(screen.getByRole("button", { name: "Run it now" }));
      await waitFor(() => expect(buildPanel()).toBeInTheDocument());

      // `entries.length` and `thinking` are both unchanged by a build, so this
      // call can only come from the build signal being a dependency.
      expect(scrollIntoView.mock.calls.length).toBeGreaterThan(beforeBuild);
    } finally {
      delete (Element.prototype as unknown as Record<string, unknown>)
        .scrollIntoView;
    }
  });
});
