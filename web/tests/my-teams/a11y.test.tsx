import { render, screen, waitFor } from "@testing-library/react";
import { axe } from "jest-axe";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import MyTeamsPage from "@/app/my-teams/page";
import { createTeamsFetchQueue, type TeamsFetchQueue } from "./harness";

/**
 * Story 2.8 AC 6: My Teams is no longer the Story 2.1 stub `tests/a11y/
 * stub-routes.test.tsx` covered, so its axe coverage moved here — both the
 * empty state (inherited from the stub) and the newly-added populated state.
 */
describe("My Teams accessibility", () => {
  let queue: TeamsFetchQueue;

  beforeEach(() => {
    queue = createTeamsFetchQueue();
    queue.install();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("has no axe violations with no saved teams", async () => {
    queue.queueBrowse(200, { teams: [] });

    const { container } = render(<MyTeamsPage />);
    await waitFor(() => expect(screen.getByRole("link", { name: "New Team" })).toBeInTheDocument());

    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it("has no axe violations with saved teams listed", async () => {
    queue.queueBrowse(200, {
      teams: [
        { name: "Article Team", created_at: "2026-08-01T00:00:00Z", last_run_at: null, run_count: 0 },
        {
          name: "Research Team",
          created_at: "2026-08-01T00:00:00Z",
          last_run_at: "2026-08-10T00:00:00Z",
          run_count: 3,
        },
      ],
    });

    const { container } = render(<MyTeamsPage />);
    await waitFor(() =>
      expect(screen.getAllByRole("listitem")).toHaveLength(2)
    );

    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});
