import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AppSidebar } from "@/components/app-sidebar";
import { SidebarProvider } from "@/components/ui/sidebar";
import { NAV_DESTINATIONS, SETTINGS_DESTINATION } from "@/lib/nav-items";

vi.mock("next/navigation", () => ({
  usePathname: () => "/my-teams",
}));

const ALL_DESTINATIONS = [...NAV_DESTINATIONS, SETTINGS_DESTINATION];

function renderSidebar() {
  return render(
    <SidebarProvider>
      <AppSidebar />
    </SidebarProvider>
  );
}

describe("AppSidebar destinations", () => {
  it("renders exactly four links and no more", () => {
    renderSidebar();
    // A count, not a probe for one absent string: asserting that
    // "Team Workspace" is missing also passed on a component rendering null.
    expect(screen.getAllByRole("link")).toHaveLength(4);
  });

  it.each(ALL_DESTINATIONS)("links $title to $href", ({ title, href }) => {
    renderSidebar();
    expect(screen.getByRole("link", { name: title })).toHaveAttribute(
      "href",
      href
    );
  });

  it("renders the four destinations in order, Settings last", () => {
    renderSidebar();
    const hrefs = screen
      .getAllByRole("link")
      .map((el) => el.getAttribute("href"));
    expect(hrefs).toEqual(["/", "/starter-teams", "/my-teams", "/settings"]);
  });
});

describe("AppSidebar active state", () => {
  it("marks the destination matching the current pathname", () => {
    renderSidebar();
    expect(screen.getByRole("link", { name: "My Teams" })).toHaveAttribute(
      "data-active"
    );
  });

  it("marks exactly one destination active", () => {
    renderSidebar();
    const active = screen
      .getAllByRole("link")
      .filter((el) => el.hasAttribute("data-active"));
    expect(active).toHaveLength(1);
  });
});

describe("AppSidebar keyboard shortcut hints", () => {
  it("keeps chord hints out of the link's accessible name", () => {
    renderSidebar();
    // Exact match: with the kbd exposed, the name was "New Team g n".
    const link = screen.getByRole("link", { name: "New Team" });
    expect(link).toBeInTheDocument();
  });

  it("advertises the chord through aria-keyshortcuts instead", () => {
    renderSidebar();
    expect(screen.getByRole("link", { name: "New Team" })).toHaveAttribute(
      "aria-keyshortcuts",
      "g n"
    );
    expect(screen.getByRole("link", { name: "My Teams" })).toHaveAttribute(
      "aria-keyshortcuts",
      "g t"
    );
  });

  it("sets no aria-keyshortcuts on destinations without a chord", () => {
    renderSidebar();
    expect(
      screen.getByRole("link", { name: "Starter Teams" })
    ).not.toHaveAttribute("aria-keyshortcuts");
  });
});

describe("AppSidebar branding", () => {
  it("renders the wordmark's accessible name once", () => {
    renderSidebar();
    expect(screen.getAllByText(/Coinpela R&D/)).toHaveLength(2); // sr-only + visible
    expect(
      screen.getByText("team_maker — Coinpela R&D")
    ).toHaveClass("sr-only");
  });
});
