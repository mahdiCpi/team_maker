import { render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { RouteFocusAnnouncer } from "@/components/route-focus-announcer";

/**
 * Route Focus Announcer (Story 2.7 AC 4).
 *
 * `next/navigation`'s `usePathname` is mocked through a `vi.fn()` whose
 * return value is reassigned between `render` and `rerender` — a *mutable*
 * mock, unlike every other `usePathname` mock in this codebase (e.g.
 * `tests/shell/app-sidebar.test.tsx:9`), which are static and cannot
 * demonstrate a pathname *change*.
 */

const mockUsePathname = vi.fn<() => string>();

vi.mock("next/navigation", () => ({
  usePathname: () => mockUsePathname(),
}));

beforeEach(() => {
  mockUsePathname.mockReset();
  document.body.innerHTML = "";
});

afterEach(() => {
  document.body.innerHTML = "";
});

function addHeading() {
  const heading = document.createElement("h1");
  heading.id = "page-heading";
  heading.tabIndex = -1;
  document.body.appendChild(heading);
  return heading;
}

function addMainContent() {
  const main = document.createElement("div");
  main.id = "main-content";
  main.tabIndex = -1;
  document.body.appendChild(main);
  return main;
}

describe("RouteFocusAnnouncer", () => {
  it("does not move focus on the initial mount", () => {
    mockUsePathname.mockReturnValue("/");
    const heading = addHeading();
    const focusSpy = vi.spyOn(heading, "focus");

    render(<RouteFocusAnnouncer />);

    expect(focusSpy).not.toHaveBeenCalled();
  });

  it("moves focus to the page heading after a route change", () => {
    mockUsePathname.mockReturnValue("/");
    const heading = addHeading();
    const focusSpy = vi.spyOn(heading, "focus");

    const { rerender } = render(<RouteFocusAnnouncer />);
    expect(focusSpy).not.toHaveBeenCalled();

    mockUsePathname.mockReturnValue("/my-teams");
    rerender(<RouteFocusAnnouncer />);

    expect(focusSpy).toHaveBeenCalledTimes(1);
  });

  it("does not re-focus on a re-render with the same pathname", () => {
    mockUsePathname.mockReturnValue("/");
    const heading = addHeading();
    const focusSpy = vi.spyOn(heading, "focus");

    const { rerender } = render(<RouteFocusAnnouncer />);
    mockUsePathname.mockReturnValue("/my-teams");
    rerender(<RouteFocusAnnouncer />);
    expect(focusSpy).toHaveBeenCalledTimes(1);

    // Same pathname again — no further focus call.
    rerender(<RouteFocusAnnouncer />);
    expect(focusSpy).toHaveBeenCalledTimes(1);
  });

  it("falls back to #main-content when the destination has no page heading", () => {
    mockUsePathname.mockReturnValue("/");
    const main = addMainContent();
    const focusSpy = vi.spyOn(main, "focus");

    const { rerender } = render(<RouteFocusAnnouncer />);
    mockUsePathname.mockReturnValue("/some-route-with-no-heading");
    rerender(<RouteFocusAnnouncer />);

    expect(focusSpy).toHaveBeenCalledTimes(1);
  });

  it("silently does nothing when neither target exists", () => {
    mockUsePathname.mockReturnValue("/");
    const { rerender } = render(<RouteFocusAnnouncer />);

    mockUsePathname.mockReturnValue("/gone");
    expect(() => rerender(<RouteFocusAnnouncer />)).not.toThrow();
  });
});
