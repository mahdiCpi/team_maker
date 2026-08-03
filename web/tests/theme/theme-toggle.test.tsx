import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const setThemeMock = vi.fn();
let currentTheme: string | undefined = "system";

vi.mock("next-themes", () => ({
  useTheme: () => ({ theme: currentTheme, setTheme: setThemeMock }),
}));

import { ThemeToggle } from "@/components/theme-toggle";

beforeEach(() => {
  setThemeMock.mockClear();
  currentTheme = "system";
});

/**
 * AC 9. The control shipped as a two-way Light/Dark toggle, which made the
 * provider's own `defaultTheme="system"` unreachable after the first click —
 * the app stopped following the OS with no route back.
 *
 * `next-themes` is mocked here (labelled per CLAUDE.md's test-transparency
 * rule); this covers the control's behaviour, not next-themes' persistence.
 */
describe("ThemeToggle", () => {
  it("offers all three modes, including System", () => {
    render(<ThemeToggle />);
    expect(
      screen.getAllByRole("button").map((b) => b.textContent)
    ).toEqual(["Light", "Dark", "System"]);
  });

  it.each([
    ["Light", "light"],
    ["Dark", "dark"],
    ["System", "system"],
  ])("selects %s", (label, value) => {
    currentTheme = "light";
    render(<ThemeToggle />);
    fireEvent.click(screen.getByRole("button", { name: label }));
    expect(setThemeMock).toHaveBeenCalledWith(value);
  });

  it("can return to System after an explicit light/dark choice", () => {
    currentTheme = "dark";
    render(<ThemeToggle />);
    fireEvent.click(screen.getByRole("button", { name: "System" }));
    expect(setThemeMock).toHaveBeenCalledWith("system");
  });

  it("marks the current mode pressed, and only that one", () => {
    currentTheme = "dark";
    render(<ThemeToggle />);
    const pressed = screen
      .getAllByRole("button")
      .filter((b) => b.getAttribute("aria-pressed") === "true");
    expect(pressed.map((b) => b.textContent)).toEqual(["Dark"]);
  });

  it("renders a disabled placeholder before next-themes reports a value", () => {
    currentTheme = undefined;
    render(<ThemeToggle />);
    for (const button of screen.getAllByRole("button")) {
      expect(button).toBeDisabled();
    }
  });
});
