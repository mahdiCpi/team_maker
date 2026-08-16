import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { WorkspaceSurface } from "@/components/workspace/workspace-surface";

import { createRunFetchQueue, type RunFetchQueue } from "./harness";
import { runComplete, runRunning, teamPlan } from "./fixtures";

/**
 * Story 2.8 AC 3: a saved team's `last_run_at`/`run_count` update on re-run.
 * A new file rather than an addition to `workspace-surface.test.tsx`
 * (already 560 lines, over CLAUDE.md's ~400-line guideline) — this is a
 * self-contained new behavior, not an extension of an existing describe
 * block there.
 */

let queue: RunFetchQueue;

beforeEach(() => {
  queue = createRunFetchQueue();
  queue.install();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

async function driveRunToCompletion(user: ReturnType<typeof userEvent.setup>) {
  queue.queuePlan(200, teamPlan);
  render(<WorkspaceSurface teamSlug="haiku_team" />);
  await screen.findByRole("textbox", { name: "Describe the goal for this run" });

  queue.queueCreateRun(200, runRunning);
  await user.type(
    screen.getByRole("textbox", { name: "Describe the goal for this run" }),
    "ship it"
  );
  await user.click(screen.getByRole("button", { name: "Run" }));
  await screen.findByText("ship it");

  queue.queueGetRun(200, runComplete);
  await waitFor(
    () => {
      expect(
        document.querySelector('[data-slot="run-status"]')?.getAttribute("data-status")
      ).toBe("complete");
    },
    { timeout: 5000 }
  );
}

describe("recording a run against My Teams on completion", () => {
  it(
    "calls record-run for the team once the run completes",
    async () => {
      const user = userEvent.setup();
      queue.queueRecordRun(200, {
        name: "haiku_team",
        created_at: "2026-08-01T00:00:00Z",
        last_run_at: "2026-08-14T00:00:00Z",
        run_count: 1,
      });

      await driveRunToCompletion(user);

      await waitFor(() => {
        expect(
          queue.requests.some(
            (r) => r.url === "/api/teams/haiku_team/record-run" && r.method === "POST"
          )
        ).toBe(true);
      });
    },
    10000
  );

  it(
    "does not call record-run twice for the same completed run",
    async () => {
      const user = userEvent.setup();
      queue.queueRecordRun(200, {
        name: "haiku_team",
        created_at: "2026-08-01T00:00:00Z",
        last_run_at: "2026-08-14T00:00:00Z",
        run_count: 1,
      });

      await driveRunToCompletion(user);
      await waitFor(() => {
        expect(
          queue.requests.filter((r) => r.url === "/api/teams/haiku_team/record-run").length
        ).toBe(1);
      });

      // A poll tick lands after the run is already complete (a plausible race
      // between the last in-flight interval tick and its own cancellation) —
      // it must not fire a second record-run for the same run id.
      queue.queueGetRun(200, runComplete);
      await new Promise((resolve) => setTimeout(resolve, 50));

      expect(
        queue.requests.filter((r) => r.url === "/api/teams/haiku_team/record-run").length
      ).toBe(1);
    },
    10000
  );

  it(
    "does not surface an error when the team was never saved (record-run 404s)",
    async () => {
      const user = userEvent.setup();
      queue.queueRecordRun(404, {
        error: { code: "not_found", message: "Team 'haiku_team' not found." },
      });

      await driveRunToCompletion(user);

      await waitFor(() => {
        expect(
          queue.requests.some((r) => r.url === "/api/teams/haiku_team/record-run")
        ).toBe(true);
      });
      // The run's own success state is unaffected by record-run's outcome.
      expect(
        document.querySelector('[data-slot="run-status"]')?.getAttribute("data-status")
      ).toBe("complete");
      expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    },
    10000
  );
});
