import { render, screen, waitFor } from "@testing-library/react";
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

  it("opens no compose session on first render", () => {
    // Typed parameter, not `async () => …`: an empty parameter list makes
    // `mock.calls[n][0]` a type error, and the URL is the whole point here.
    const fetchMock = vi.fn(async (url: string | URL) => {
      throw new TypeError(`Failed to fetch ${String(url)}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    try {
      render(<NewTeamPage />);
      // The original assertion was "no request at all". Story 2.3 narrowed it
      // rather than deleting it, because the reason it existed is intact: the
      // Composer waits for the user and does not spend an LLM turn on page load.
      // A key-status read is a file read on the server — no model, no cost — so it
      // is not the thing this guard was protecting against.
      const paths = fetchMock.mock.calls.map((call) => String(call[0]));
      expect(paths.filter((path) => path.startsWith("/api/compose/"))).toEqual([]);
      // Proof the guard is still looking at something: the mount read did happen,
      // so an implementation that stopped calling the API entirely cannot pass this
      // by making the haystack empty.
      expect(paths).toEqual(["/api/keys/status"]);
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
      // The mockup's fabricated key footer (`team-workspace.html:80`). Story 2.3
      // shipped the real key check, and this is still not it: it is invented data,
      // refused by 2.1 and 2.2 and not resurrected by 2.3.
      "Keys: anthropic",
    ]) {
      expect(text).not.toContain(borrowed);
    }
    // Proof the haystack is real: the assertions above are not passing on an
    // empty string.
    expect(text).toContain("Describe your team.");
  });

  it("states nothing about keys until the server has said something", async () => {
    // Story 2.3 built the key check, so this no longer asserts that the seam is
    // empty — it asserts the states are *server-derived*. With no usable response the
    // surface must still say nothing rather than fall back to a cheerful default,
    // which is how the fabricated `Keys: anthropic ✓ …` footer got into the mockup in
    // the first place.
    //
    // `fetch` is stubbed even though the assertion is about absence: the Composer now
    // reads `/api/keys/status` on mount, and leaving it unstubbed made this suite
    // attempt a real request against the jsdom origin. It also has to be *awaited* —
    // asserting synchronously after `render` passed before any state could arrive, so
    // it could not have failed either way.
    const fetchMock = vi.fn(async (url: string | URL) => {
      throw new TypeError(`Failed to fetch ${String(url)}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    try {
      const { container } = render(<NewTeamPage />);
      await waitFor(() => expect(fetchMock).toHaveBeenCalled());

      expect(container.querySelector('[data-slot="key-check"]')).toBeNull();
      expect(container.textContent).not.toMatch(
        /key missing|key found|All models reachable|via OpenRouter|✓/i
      );
    } finally {
      vi.unstubAllGlobals();
    }
  });

  it("anticipates no Story 2.4/2.5 surface", () => {
    const { container } = render(<NewTeamPage />);
    expect(container.textContent).not.toMatch(/My Teams|workspace|Adapt with/i);
  });

  // Story 2.7 AC 3 — a real, visible `<h1 id="page-heading">` naming the
  // surface, present even in the empty state where `EmptyTitle` shows the
  // Composer's own "Describe your team." sentence instead of the route name.
  it("renders a visible 'New Team' page heading distinct from EmptyTitle", () => {
    render(<NewTeamPage />);
    const heading = screen.getByRole("heading", { level: 1, name: "New Team" });
    expect(heading).toHaveAttribute("id", "page-heading");
    expect(heading).not.toHaveClass("sr-only");
  });
});

describe("the copy guards hold AFTER a conversation starts, not just before it", () => {
  it("borrows no other surface's copy once a turn has landed", async () => {
    // The pre-conversation checks above run on an empty state where none of the
    // banned strings could appear anyway. This drives a real turn first, so the
    // haystack actually contains the assistant's proposal, the action bar and the
    // review toggle.
    const { render: rtlRender } = await import("@testing-library/react");
    const userEvent = (await import("@testing-library/user-event")).default;
    const { ComposerSurface } = await import(
      "@/components/composer/composer-surface"
    );
    const { createFetchQueue, completeFirstTurn } = await import("./harness");

    vi.doMock("next/navigation", () => ({
      useRouter: () => ({ push: vi.fn() }),
      usePathname: () => "/",
    }));

    const queue = createFetchQueue();
    queue.install();
    try {
      const user = userEvent.setup();
      rtlRender(<ComposerSurface />);
      await completeFirstTurn(user, queue);

      const text = document.body.textContent ?? "";
      // Proof the haystack is real and post-turn.
      expect(text).toMatch(/researcher/);
      expect(text).toMatch(/Run it now/);

      // Story 2.7 AC 3 — the page heading persists once the empty state is
      // replaced by the transcript; it must not have been rendered only
      // inside the now-gone `EmptyState` branch.
      expect(
        screen.getByRole("heading", { level: 1, name: "New Team" })
      ).toBeInTheDocument();

      for (const borrowed of [
        "No teams yet. Describe one, or start from a template.",
        "Ask a follow-up or refine the goal…",
        "Running · 2 of 4 tasks",
        "Save this team and its results?",
        // Still fabricated data, still not ours (see the pre-conversation guard).
        "Keys: anthropic",
      ]) {
        expect(text).not.toContain(borrowed);
      }
      // Story 2.3's key-check copy is no longer banned here — it is this surface's
      // own, and the harness answers the key routes with a captured all-good body,
      // so it legitimately appears. Asserted positively instead, which also proves
      // the wiring survives a real turn.
      expect(text).toContain("All models reachable.");
      // The check-mark glyph stays banned. It belongs to the mockup's fabricated
      // `Keys: anthropic ✓ · gemini ✓` footer, which 2.1 and 2.2 both refused and
      // 2.3 did not resurrect — the real states are words, not ticks. An earlier
      // version of this story deleted this assertion along with 2.3's own copy,
      // taking a tooth off the guard rather than narrowing it.
      expect(text).not.toMatch(/✓/);
    } finally {
      vi.unstubAllGlobals();
    }
  });
});
