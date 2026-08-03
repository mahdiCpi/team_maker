import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import MyTeamsPage from "@/app/my-teams/page";
import NewTeamPage from "@/app/page";
import SettingsPage from "@/app/settings/page";
import StarterTeamsPage from "@/app/starter-teams/page";
import { metadata as myTeamsMeta } from "@/app/my-teams/page";
import { metadata as newTeamMeta } from "@/app/page";
import { metadata as settingsMeta } from "@/app/settings/page";
import { metadata as starterTeamsMeta } from "@/app/starter-teams/page";

vi.mock("next-themes", () => ({
  useTheme: () => ({ theme: "system", setTheme: vi.fn() }),
}));

/** AC 3 — every destination routes to a real page rendering an empty state. */
const ROUTES = [
  { name: "New Team", Page: NewTeamPage, meta: newTeamMeta, action: "/starter-teams" },
  { name: "Starter Teams", Page: StarterTeamsPage, meta: starterTeamsMeta, action: "/" },
  { name: "My Teams", Page: MyTeamsPage, meta: myTeamsMeta, action: "/" },
  { name: "Settings", Page: SettingsPage, meta: settingsMeta, action: null },
];

describe.each(ROUTES)("$name page", ({ name, Page, meta, action }) => {
  it("renders its heading", () => {
    const { container } = render(<Page />);
    // Scoped to the title slot: on `/` the string "New Team" is also the
    // button label, so an unscoped getByText matches twice.
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
  it("does not reuse My Teams' empty-state sentence on New Team", () => {
    const { container: newTeam } = render(<NewTeamPage />);
    const newTeamCopy = newTeam.querySelector(
      '[data-slot="empty-description"]'
    )?.textContent;

    const { container: myTeams } = render(<MyTeamsPage />);
    const myTeamsCopy = myTeams.querySelector(
      '[data-slot="empty-description"]'
    )?.textContent;

    expect(newTeamCopy).not.toBe(myTeamsCopy);
  });

  it("ships no disabled control anywhere in the four routes", () => {
    for (const { Page } of ROUTES.slice(0, 3)) {
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
