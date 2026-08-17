import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { StarterTeamsSurface } from "@/components/starter-teams/starter-teams-surface";
import { createStartersFetchQueue, type StartersFetchQueue } from "./harness";

// A populated list renders `StarterTeamCard` per starter (Story 3-2), and
// that component calls `useRouter()` unconditionally — without this mock
// (matching `starter-team-card.test.tsx`'s own) every populated-list test
// below throws "invariant expected app router to be mounted", since this
// file predates Story 3-2 and never needed a router context before.
vi.mock("next/navigation", async () => {
  const actual = await vi.importActual("next/navigation");
  return {
    ...actual,
    useRouter: () => ({ push: vi.fn() }),
  };
});

const educationTeam = {
  id: "baseline_education_team",
  name: "Baseline Education Team",
  purpose: "Create educational content that explains complex topics clearly.",
  template_id: "baseline_education_team",
  agent_count: 3,
};
const researchTeam = {
  id: "research_content_team",
  name: "Research Content Team",
  purpose: "Create well-researched, high-quality content.",
  template_id: "research_content_team",
  agent_count: 4,
};

let queue: StartersFetchQueue;

beforeEach(() => {
  queue = createStartersFetchQueue();
  queue.install();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("loading and empty states", () => {
  it("shows a loading state before the fetch resolves, not the empty-state copy", () => {
    // Never resolved within this test, deliberately: proves the loading
    // frame is distinct from "no starter teams" (AC 4), not merely a fast flash.
    render(<StarterTeamsSurface />);

    expect(document.querySelector('[data-slot="starter-teams-loading"]')).toBeInTheDocument();
    expect(screen.queryByText("No starter teams available. Check your installation.")).toBeNull();
  });

  it("shows the empty-state copy only once the list resolves empty", async () => {
    queue.queueList(200, { starters: [] });
    render(<StarterTeamsSurface />);

    await waitFor(() =>
      expect(screen.getByText("No starter teams available. Check your installation.")).toBeInTheDocument()
    );
  });

  it("shows a plain-language message, not a crash, when the list fails to load", async () => {
    // The client shows the server's own authored message verbatim when it
    // does not look like a leaked internal (`transport.ts`'s `toFailure`) —
    // this proves the failure renders as text and never crashes the surface,
    // not that any particular wording is chosen.
    queue.queueList(500, {
      error: { code: "internal_error", message: "The starter team list could not be loaded." },
    });
    render(<StarterTeamsSurface />);

    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toBe("The starter team list could not be loaded.");
  });
});

describe("a populated list", () => {
  async function renderPopulated() {
    queue.queueList(200, { starters: [educationTeam, researchTeam] });
    render(<StarterTeamsSurface />);
    await waitFor(() => expect(screen.getAllByRole("listitem")).toHaveLength(2));
  }

  it("shows each starter's name and agent count", async () => {
    await renderPopulated();

    expect(screen.getByText("Baseline Education Team")).toBeInTheDocument();
    expect(screen.getByText("3 agents")).toBeInTheDocument();

    expect(screen.getByText("Research Content Team")).toBeInTheDocument();
    expect(screen.getByText("4 agents")).toBeInTheDocument();
  });

  it("shows each starter's purpose", async () => {
    await renderPopulated();

    expect(screen.getByText(/Create educational content/)).toBeInTheDocument();
    expect(screen.getByText(/Create well-researched/)).toBeInTheDocument();
  });

  it("renders the correct number of list items", async () => {
    await renderPopulated();

    const items = screen.getAllByRole("listitem");
    expect(items).toHaveLength(2);
  });

  it("includes data-slot attributes for testing", async () => {
    await renderPopulated();

    expect(document.querySelector('[data-slot="starter-teams-list"]')).toBeInTheDocument();
    expect(document.querySelector('[data-slot="starter-team-card"]')).toBeInTheDocument();
  });
});
