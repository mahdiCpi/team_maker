import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AppShellProvider } from "@/components/app-shell-provider";
import { Sidebar, SidebarTrigger, useSidebar } from "@/components/ui/sidebar";
import { DEFAULT_VIEWPORT_WIDTH, setViewportWidth } from "../../vitest.setup";

vi.mock("next/navigation", () => ({
  usePathname: () => "/",
}));

function StateProbe() {
  const { state } = useSidebar();
  return <span data-testid="sidebar-state">{state}</span>;
}

function renderAt(width: number) {
  setViewportWidth(width);
  return render(
    <AppShellProvider>
      <Sidebar collapsible="icon" />
      <SidebarTrigger />
      <StateProbe />
    </AppShellProvider>
  );
}

afterEach(() => {
  setViewportWidth(DEFAULT_VIEWPORT_WIDTH);
});

/**
 * AC 5: full at `lg+`, collapsed to icons at `md`, `Sheet` below `md`.
 *
 * shadcn's `collapsible="icon"` only governs what a user toggle does — its
 * single automatic breakpoint is the 768px switch to the mobile Sheet. The
 * md band is supplied by AppShellProvider, so it is pinned here.
 */
describe("sidebar responsive states (AC 5)", () => {
  it("is expanded at lg (1024px)", () => {
    renderAt(1024);
    expect(screen.getByTestId("sidebar-state")).toHaveTextContent("expanded");
  });

  it("is expanded above lg", () => {
    renderAt(1440);
    expect(screen.getByTestId("sidebar-state")).toHaveTextContent("expanded");
  });

  it("collapses to icons in the md band (768–1023px)", () => {
    renderAt(900);
    expect(screen.getByTestId("sidebar-state")).toHaveTextContent("collapsed");
  });

  it("collapses to icons at the lower edge of md", () => {
    renderAt(768);
    expect(screen.getByTestId("sidebar-state")).toHaveTextContent("collapsed");
  });

  it("is collapsed one pixel below lg", () => {
    renderAt(1023);
    expect(screen.getByTestId("sidebar-state")).toHaveTextContent("collapsed");
  });
});

describe("an explicit user toggle wins over the viewport", () => {
  it("stays expanded in the md band once the user opens it", () => {
    renderAt(900);
    expect(screen.getByTestId("sidebar-state")).toHaveTextContent("collapsed");

    fireEvent.click(screen.getByRole("button", { name: /toggle sidebar/i }));
    expect(screen.getByTestId("sidebar-state")).toHaveTextContent("expanded");
  });

  it("stays collapsed at lg once the user closes it", () => {
    renderAt(1280);
    expect(screen.getByTestId("sidebar-state")).toHaveTextContent("expanded");

    fireEvent.click(screen.getByRole("button", { name: /toggle sidebar/i }));
    expect(screen.getByTestId("sidebar-state")).toHaveTextContent("collapsed");
  });
});
