import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import NewTeamPage, { metadata as newTeamMeta } from "@/app/page";

/**
 * The `/` route's own assertions, migrated out of `web/tests/shell/routes.test.tsx`
 * where they described the Story 2.1 placeholder this story replaced.
 *
 * No `fetch` stub and no `next/navigation` mock: rendering the page performs no
 * request and calls no router, and asserting that is part of the point — the old
 * suite does not mock `next/navigation`, so a page that reached for `useRouter`
 * would have broken it.
 */

describe("the / route", () => {
  it("keeps its distinct document title", () => {
    // Unchanged from Story 2.1: the *route* is still New Team even though the
    // page's heading is now the Composer's.
    expect(newTeamMeta.title).toBe("New Team · team_maker");
  });

  it("renders without a router, so it cannot break the shell suite", () => {
    // `page.tsx` stays a server component and `ComposerSurface` calls no
    // navigation hook. If either changed, this throws.
    expect(() => render(<NewTeamPage />)).not.toThrow();
  });

  it("issues no request on first render", () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    try {
      render(<NewTeamPage />);
      // The Composer waits for the user; it does not open a session on mount,
      // which would spend an LLM turn on every page load.
      expect(fetchMock).not.toHaveBeenCalled();
    } finally {
      vi.unstubAllGlobals();
    }
  });

  it("heads the surface `Describe your team.`, replacing the placeholder", () => {
    const { container } = render(<NewTeamPage />);
    expect(
      container.querySelector('[data-slot="empty-title"]')?.textContent
    ).toBe("Describe your team.");
    // The Story 2.1 copy that appeared in no spine is gone.
    expect(container.textContent).not.toMatch(
      /Describe the team you need, or begin from a starter team\./
    );
  });

  it("no longer ships a `New Team` button linking to /starter-teams", () => {
    render(<NewTeamPage />);
    // The old assertion was `getByRole("link")` with href="/starter-teams" — a
    // New Team button, on the New Team page, that went somewhere else.
    expect(screen.queryAllByRole("link")).toHaveLength(0);
  });

  it("ships no `disabled` control", () => {
    const { container } = render(<NewTeamPage />);
    // Story 2.1's review found a permanently disabled button used as the
    // "single primary action". Unavailable actions here carry `aria-disabled`
    // plus a stated reason instead.
    expect(container.querySelector("[disabled]")).toBeNull();
  });

  it("borrows no copy that belongs to another surface", () => {
    const { container } = render(<NewTeamPage />);
    const text = container.textContent ?? "";
    for (const borrowed of [
      // My Teams (2.5)
      "No teams yet. Describe one, or start from a template.",
      // Team Workspace chat (2.4) — dangerously close to a Composer placeholder
      "Ask a follow-up or refine the goal…",
      // Run status (2.4)
      "Running · 2 of 4 tasks",
      // Post-run prompt (2.5)
      "Save this team and its results?",
      // Key check (2.3) — renders on the Composer, but is 2.3's copy and data
      "All models reachable.",
      "Keys: anthropic",
    ]) {
      expect(text).not.toContain(borrowed);
    }
    // Proof the haystack is real: the assertions above are not passing on an
    // empty string.
    expect(text).toContain("Describe your team.");
  });

  it("fakes none of Story 2.3's key-check states", () => {
    const { container } = render(<NewTeamPage />);
    // The seam is left; the states are not invented. Story 2.1 refused the
    // mockup's `Keys: anthropic ✓ …` footer for the same reason.
    expect(container.textContent).not.toMatch(
      /key|anthropic|openai|gemini|openrouter|via OpenRouter/i
    );
  });

  it("anticipates no Story 2.4/2.5 surface", () => {
    const { container } = render(<NewTeamPage />);
    expect(container.textContent).not.toMatch(/My Teams|workspace|Adapt with/i);
  });
});
