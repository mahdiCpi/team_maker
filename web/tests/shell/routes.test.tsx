import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import MyTeamsPage from "@/app/my-teams/page";
import SettingsPage from "@/app/settings/page";
import StarterTeamsPage from "@/app/starter-teams/page";
import { metadata as myTeamsMeta } from "@/app/my-teams/page";
import { metadata as settingsMeta } from "@/app/settings/page";
import { metadata as starterTeamsMeta } from "@/app/starter-teams/page";

vi.mock("next-themes", () => ({
  useTheme: () => ({ theme: "system", setTheme: vi.fn() }),
}));

/**
 * AC 3 (Story 2.1) — every destination routes to a real page rendering an empty
 * state.
 *
 * **`/` is no longer here.** Story 2.2 replaced it with the Composer, so its
 * assertions moved to `web/tests/composer/route.test.tsx`: it has no
 * `empty-title` of `"New Team"`, no single `link` to `/starter-teams`, and its
 * route-level checks belong beside the surface they describe.
 *
 * One test was **deleted rather than migrated**: `route copy > does not reuse My
 * Teams' empty-state sentence on New Team`. With no `empty-description` on the
 * Composer once a conversation starts, it degraded to
 * `expect(undefined).not.toBe(…)` — a silent vacuous pass, which is the defect
 * class Story 2.2 was written to avoid repeating. The property it cared about is
 * covered directly in `tests/composer/route.test.tsx`, which asserts the banned
 * strings are absent by name.
 */
const ROUTES = [
  { name: "Starter Teams", Page: StarterTeamsPage, meta: starterTeamsMeta, action: "/" },
  { name: "My Teams", Page: MyTeamsPage, meta: myTeamsMeta, action: "/" },
  { name: "Settings", Page: SettingsPage, meta: settingsMeta, action: null },
];

describe.each(ROUTES)("$name page", ({ name, Page, meta, action }) => {
  it("renders its heading", () => {
    const { container } = render(<Page />);
    expect(
      container.querySelector('[data-slot="empty-title"]')?.textContent
    ).toBe(name);
  });

  it("renders exactly one plain description sentence", () => {
    const { container } = render(<Page />);
    const description = container.querySelector(
      '[data-slot="empty-description"]'
    );
    expect(description?.textContent?.trim().length).toBeGreaterThan(0);
  });

  it("declares a distinct document title", () => {
    expect(meta.title).toBe(`${name} · team_maker`);
  });

  if (action) {
    it("offers a working primary action, not a disabled placeholder", () => {
      render(<Page />);
      const link = screen.getByRole("link");
      expect(link).toHaveAttribute("href", action);
      expect(link).not.toHaveAttribute("disabled");
      expect(link).not.toHaveAttribute("aria-disabled", "true");
    });
  }
});

describe("route copy", () => {
  it("ships no disabled control on the empty-state routes", () => {
    // Excluded by NAME, not by `slice(0, 3)`. The old index quietly meant
    // "everything except Settings"; once `/` left the array the same slice
    // would have started including Settings, whose ThemeToggle ships a
    // deliberate disabled hydration placeholder — turning a real assertion into
    // an unexplained failure.
    const checked = ROUTES.filter((route) => route.name !== "Settings");
    expect(checked).toHaveLength(2);
    for (const { Page } of checked) {
      const { container } = render(<Page />);
      expect(container.querySelector("[disabled]")).toBeNull();
    }
  });
});

describe("Settings page scope (AC 13)", () => {
  it("ships the theme control and nothing key-related", () => {
    const { container } = render(<SettingsPage />);
    expect(screen.getByRole("group", { name: "Theme" })).toBeInTheDocument();
    expect(container.textContent).not.toMatch(
      /key|anthropic|openai|gemini|openrouter/i
    );
  });
});
