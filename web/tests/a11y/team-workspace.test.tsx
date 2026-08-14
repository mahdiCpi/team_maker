import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { WorkspaceSurface } from "@/components/workspace/workspace-surface";

import { createRunFetchQueue, type RunFetchQueue } from "../workspace/harness";
import { runComplete, teamPlan, transcriptAvailable } from "../workspace/fixtures";

/**
 * Team Workspace surface accessibility smoke tests (AC 9)
 *
 * Tests that the Team Workspace route has no axe violations with no run in
 * progress, and with a genuinely completed run rendered (results panel,
 * transcript button, run-status card) — not the no-run state asserted twice
 * under a different name. `fetch` is stubbed via the same harness
 * `tests/workspace/` uses; this is a mocked integration (CLAUDE.md test
 * transparency), not proof the API works.
 */

let queue: RunFetchQueue;

beforeEach(() => {
  queue = createRunFetchQueue();
  queue.install();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("Team Workspace surface accessibility", () => {
  it("should have no axe violations with no run", async () => {
    queue.queuePlan(200, teamPlan);
    const { container } = render(<WorkspaceSurface teamSlug="haiku_team" />);
    await screen.findByRole("textbox", { name: "Describe the goal for this run" });

    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it("should have no axe violations with a completed run", async () => {
    const user = userEvent.setup();
    queue.queuePlan(200, teamPlan);
    const { container } = render(<WorkspaceSurface teamSlug="haiku_team" />);
    await screen.findByRole("textbox", { name: "Describe the goal for this run" });

    // `createRun` answering with a `complete` RunView (rather than
    // `running`) lets the surface land on the completed state directly,
    // without needing to fake the poll interval.
    queue.queueCreateRun(200, runComplete);
    queue.queueTranscript(200, transcriptAvailable);
    await user.type(
      screen.getByRole("textbox", { name: "Describe the goal for this run" }),
      "write a haiku about autumn"
    );
    await user.click(screen.getByRole("button", { name: "Run" }));
    await screen.findByRole("button", { name: "View transcript" });

    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});
