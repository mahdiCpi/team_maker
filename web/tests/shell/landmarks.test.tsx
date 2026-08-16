import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AppSidebar } from "@/components/app-sidebar";
import { SidebarInset, SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";

/**
 * Shell landmark structure (Story 2.7 AC 2).
 *
 * Reconstructs the relevant slice of `app/layout.tsx`'s JSX — `AppSidebar` +
 * `SidebarInset` wrapping a header and the `#main-content` region — rather
 * than rendering `RootLayout` itself, since that pulls in `next/font/google`
 * (Geist), which needs Next's own compiler and does not resolve under a
 * plain Vitest/jsdom render. `SidebarInset` already renders a `<main>`
 * (`components/ui/sidebar.tsx`, vendored); the inner region must be a plain
 * `<div>`, not a second `<main>`, or the page carries two nested main
 * landmarks — invalid HTML and ambiguous for landmark navigation.
 */

vi.mock("next/navigation", () => ({
  usePathname: () => "/",
}));

function renderShell() {
  return render(
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset>
        <header>
          <SidebarTrigger />
        </header>
        <div id="main-content" tabIndex={-1}>
          Page content
        </div>
      </SidebarInset>
    </SidebarProvider>
  );
}

describe("shell landmark structure", () => {
  it("renders exactly one main landmark per page", () => {
    renderShell();
    expect(screen.getAllByRole("main")).toHaveLength(1);
  });

  it("exposes the sidebar navigation as a navigation landmark", () => {
    renderShell();
    const nav = screen.getAllByRole("navigation");
    expect(nav.length).toBeGreaterThan(0);
  });

  it("keeps every sidebar destination reachable inside a navigation landmark", () => {
    renderShell();
    const navs = screen.getAllByRole("navigation");
    const linksInNavs = navs.flatMap((nav) =>
      Array.from(nav.querySelectorAll("a"))
    );
    expect(linksInNavs).toHaveLength(4);
  });
});
