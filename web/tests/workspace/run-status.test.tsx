import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { RunStatus } from "@/components/workspace/run-status";
import type { RunView } from "@/lib/api-types";

/**
 * RunStatus aria-live announcements (AC 7)
 *
 * Tests that the existing three-state aria-live announcement still fires correctly.
 * Per-task progress announcements are architecturally impossible in v1 (AD-13)
 * and are formally documented as a deviation from EXPERIENCE.md:112-113.
 */
function makeRun(overrides: Partial<RunView>): RunView {
  return {
    status: "running",
    run_id: "run-1",
    team_slug: "test-team",
    team_name: "Test Team",
    tasks: [],
    result: null,
    transcript_available: false,
    failure_reason: null,
    ...overrides,
  };
}

describe("RunStatus aria-live announcements", () => {
  it("announces 'Run started' when a run begins", () => {
    const run = makeRun({
      status: "running",
      tasks: [
        { name: "task-1", agent_role: "researcher", dependencies: [] },
        { name: "task-2", agent_role: "writer", dependencies: ["task-1"] },
        { name: "task-3", agent_role: "editor", dependencies: ["task-2"] },
      ],
    });

    render(<RunStatus run={run} />);

    // The live region should contain the started announcement
    const liveRegion = document.querySelector('[aria-live="polite"]');
    expect(liveRegion).toBeInTheDocument();
    expect(liveRegion?.textContent).toContain("Run started");
    expect(liveRegion?.textContent).toContain("3 tasks");
  });

  it("announces 'Run complete' when a run finishes successfully", () => {
    const run = makeRun({
      status: "complete",
      tasks: [{ name: "task-1", agent_role: "researcher", dependencies: [] }],
      result: { final_output: "Done.", task_results: [] },
      transcript_available: true,
    });

    render(<RunStatus run={run} />);

    const liveRegion = document.querySelector('[aria-live="polite"]');
    expect(liveRegion).toBeInTheDocument();
    expect(liveRegion?.textContent).toContain("Run complete");
  });

  it("announces 'Run failed' with reason when a run fails", () => {
    const run = makeRun({
      status: "failed",
      tasks: [{ name: "task-1", agent_role: "researcher", dependencies: [] }],
      failure_reason: "No usable models for the selected providers",
    });

    render(<RunStatus run={run} />);

    const liveRegion = document.querySelector('[aria-live="polite"]');
    expect(liveRegion).toBeInTheDocument();
    expect(liveRegion?.textContent).toContain("Run failed");
    expect(liveRegion?.textContent).toContain("No usable models for the selected providers");
  });

  it("renders an empty live region when there is no run", () => {
    render(<RunStatus run={null} />);

    const liveRegion = document.querySelector('[aria-live="polite"]');
    expect(liveRegion).toBeInTheDocument();
    // Should be empty but present in the DOM
    expect(liveRegion?.textContent).toBe("");
  });
});