import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { StarterTeamCard } from "@/components/starter-teams/starter-team-card";
import { createStartersFetchQueue, type StartersFetchQueue } from "./harness";

const educationTeam = {
  id: "baseline_education_team",
  name: "Baseline Education Team",
  purpose: "Create educational content that explains complex topics clearly.",
  template_id: "baseline_education_team",
  agent_count: 3,
};

let queue: StartersFetchQueue;

beforeEach(() => {
  queue = createStartersFetchQueue();
  queue.install();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

// Mock useRouter — the one thing that genuinely needs mocking here. Every
// starter-run request below goes through the REAL `runStarterTeam` client and
// the harness's stubbed `fetch` (`queue.queueRun`), not a second, separate
// mock of `@/lib/api-client` — a prior version of this file mocked the API
// client too, whose lookup logic read from `queue.requests` without anything
// ever writing to it (the client itself was replaced, so it never reached the
// stubbed fetch), so every "Run" click threw "Unexpected runStarterTeam call".
const mockPush = vi.fn();
vi.mock("next/navigation", async () => {
  const actual = await vi.importActual("next/navigation");
  return {
    ...actual,
    useRouter: () => ({ push: mockPush }),
  };
});

describe("StarterTeamCard display", () => {
  it("shows the starter's name", () => {
    render(<StarterTeamCard starter={educationTeam} />);

    expect(screen.getByText("Baseline Education Team")).toBeInTheDocument();
  });

  it("shows the starter's purpose", () => {
    render(<StarterTeamCard starter={educationTeam} />);

    expect(screen.getByText(/Create educational content/)).toBeInTheDocument();
  });

  it("shows the agent count", () => {
    render(<StarterTeamCard starter={educationTeam} />);

    expect(screen.getByText("3 agents")).toBeInTheDocument();
  });

  it("has data-slot attributes for testing", () => {
    render(<StarterTeamCard starter={educationTeam} />);

    expect(document.querySelector('[data-slot="starter-team-card"]')).toBeInTheDocument();
  });
});

describe("StarterTeamCard actions (Story 3-2)", () => {
  beforeEach(() => {
    mockPush.mockClear();
  });

  describe("Run button", () => {
    it("has a Run button", () => {
      render(<StarterTeamCard starter={educationTeam} />);

      expect(screen.getByText("Run")).toBeInTheDocument();
    });

    it("has data-slot attribute for Run button", () => {
      render(<StarterTeamCard starter={educationTeam} />);

      expect(document.querySelector('[data-slot="starter-team-card-run"]')).toBeInTheDocument();
    });

    it("calls the run endpoint when clicked", async () => {
      queue.queueRun(200, {
        status: "complete",
        team_slug: "baseline_education_team",
        team_name: educationTeam.name,
      });
      const user = userEvent.setup();
      render(<StarterTeamCard starter={educationTeam} />);

      await user.click(screen.getByText("Run"));

      await waitFor(() => {
        expect(queue.requests).toHaveLength(1);
      });

      expect(queue.requests[0].method).toBe("POST");
      expect(queue.requests[0].url).toBe("/api/starters/baseline_education_team/run");
    });

    it("navigates to the team workspace on success", async () => {
      queue.queueRun(200, {
        status: "complete",
        team_slug: "baseline_education_team",
        team_name: educationTeam.name,
      });
      const user = userEvent.setup();
      render(<StarterTeamCard starter={educationTeam} />);

      await user.click(screen.getByText("Run"));

      await waitFor(() => {
        expect(mockPush).toHaveBeenCalledWith("/teams/baseline_education_team");
      });
    });

    it("shows loading state while building", () => {
      queue.queueRun(200, {
        status: "complete",
        team_slug: "baseline_education_team",
        team_name: educationTeam.name,
      });
      render(<StarterTeamCard starter={educationTeam} />);

      // `setRunPending(true)` runs synchronously, before the `await
      // runStarterTeam(...)` inside `handleRun` — so the pending label is
      // already on screen the instant the click handler returns, with no
      // need to wait for the queued response to resolve.
      fireEvent.click(screen.getByText("Run"));

      expect(screen.getByText("Building...")).toBeInTheDocument();
    });

    it("shows error message on failure", async () => {
      queue.queueRun(500, {
        error: { code: "build_failed", message: "Build failed due to missing dependencies" },
      });

      const user = userEvent.setup();
      render(<StarterTeamCard starter={educationTeam} />);

      await user.click(screen.getByText("Run"));

      await waitFor(() => {
        expect(screen.getByRole("alert")).toBeInTheDocument();
      });

      expect(screen.getByText(/Build failed/)).toBeInTheDocument();
    });
  });

  describe("Adapt with Composer link", () => {
    it("has an Adapt with Composer link", () => {
      render(<StarterTeamCard starter={educationTeam} />);

      expect(screen.getByText("Adapt with Composer")).toBeInTheDocument();
    });

    it("has data-slot attribute for Adapt link", () => {
      render(<StarterTeamCard starter={educationTeam} />);

      expect(document.querySelector('[data-slot="starter-team-card-adapt"]')).toBeInTheDocument();
    });

    it("navigates to Composer with starter query param", async () => {
      render(<StarterTeamCard starter={educationTeam} />);

      const adaptLink = screen.getByText("Adapt with Composer");

      // Check the href
      expect(adaptLink).toHaveAttribute(
        "href",
        "/?starter=baseline_education_team"
      );
    });

    it("uses button styling for consistency", () => {
      render(<StarterTeamCard starter={educationTeam} />);

      const adaptLink = screen.getByText("Adapt with Composer");
      // Should have button-like styling
      expect(adaptLink).toHaveClass("inline-flex");
    });
  });

  describe("Accessibility (Story 2.7 floor)", () => {
    it("Run button is keyboard operable", () => {
      render(<StarterTeamCard starter={educationTeam} />);

      const runButton = screen.getByText("Run");
      // Button should be focusable
      runButton.focus();
      expect(document.activeElement).toBe(runButton);
    });

    it("Adapt link is keyboard operable", () => {
      render(<StarterTeamCard starter={educationTeam} />);

      const adaptLink = screen.getByText("Adapt with Composer");
      // A native `<a>` with an `href` is focusable by default — asserting an
      // explicit `tabindex="0"` (which this element never sets) is not what
      // "keyboard operable" requires; asserting real focusability is.
      adaptLink.focus();
      expect(document.activeElement).toBe(adaptLink);
    });

    it("buttons are in a logical tab order", () => {
      render(<StarterTeamCard starter={educationTeam} />);

      const runButton = screen.getByText("Run");
      const adaptLink = screen.getByText("Adapt with Composer");

      // Both should be focusable elements
      expect(runButton).toBeInTheDocument();
      expect(adaptLink).toBeInTheDocument();
    });
  });

  describe("Both actions together", () => {
    it("shows both Run and Adapt with Composer actions", () => {
      render(<StarterTeamCard starter={educationTeam} />);

      expect(screen.getByText("Run")).toBeInTheDocument();
      expect(screen.getByText("Adapt with Composer")).toBeInTheDocument();
    });

    it("actions are in a flex container", () => {
      render(<StarterTeamCard starter={educationTeam} />);

      const actionsContainer = screen.getByRole("button", { name: "Run" }).parentElement;
      expect(actionsContainer).toHaveClass("flex");
      expect(actionsContainer).toHaveClass("gap-2");
    });
  });
});
