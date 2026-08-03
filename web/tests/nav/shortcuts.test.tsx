import { fireEvent, render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const pushMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
}));

import { CHORD_WINDOW_MS, NavShortcuts } from "@/components/nav-shortcuts";

beforeEach(() => {
  pushMock.mockClear();
});

afterEach(() => {
  vi.useRealTimers();
});

function renderWith(extra?: React.ReactNode) {
  return render(
    <div>
      <NavShortcuts />
      {extra}
    </div>
  );
}

describe("chord navigation", () => {
  it("navigates to New Team on g then n", () => {
    renderWith();
    fireEvent.keyDown(window, { key: "g" });
    fireEvent.keyDown(window, { key: "n" });
    expect(pushMock).toHaveBeenCalledWith("/");
  });

  it("navigates to My Teams on g then t", () => {
    renderWith();
    fireEvent.keyDown(window, { key: "g" });
    fireEvent.keyDown(window, { key: "t" });
    expect(pushMock).toHaveBeenCalledWith("/my-teams");
  });

  it("calls preventDefault on a completed chord", () => {
    renderWith();
    fireEvent.keyDown(window, { key: "g" });
    const event = new KeyboardEvent("keydown", { key: "n", cancelable: true });
    window.dispatchEvent(event);
    expect(event.defaultPrevented).toBe(true);
  });

  it("is case-insensitive, so Caps Lock does not silently break it", () => {
    renderWith();
    fireEvent.keyDown(window, { key: "G" });
    fireEvent.keyDown(window, { key: "N" });
    expect(pushMock).toHaveBeenCalledWith("/");
  });

  it("does nothing for g followed by an unmapped key", () => {
    renderWith();
    fireEvent.keyDown(window, { key: "g" });
    fireEvent.keyDown(window, { key: "x" });
    expect(pushMock).not.toHaveBeenCalled();
  });

  it("does nothing for a lone destination key with no leader", () => {
    renderWith();
    fireEvent.keyDown(window, { key: "n" });
    expect(pushMock).not.toHaveBeenCalled();
  });
});

describe("chord expiry", () => {
  it("stops responding once the window has elapsed", () => {
    vi.useFakeTimers();
    renderWith();
    fireEvent.keyDown(window, { key: "g" });
    vi.advanceTimersByTime(CHORD_WINDOW_MS + 1);
    fireEvent.keyDown(window, { key: "n" });
    // Deleting the setTimeout that disarms the chord must turn this red;
    // without it the arm lives forever and the window is decorative.
    expect(pushMock).not.toHaveBeenCalled();
  });

  it("still fires just inside the window", () => {
    vi.useFakeTimers();
    renderWith();
    fireEvent.keyDown(window, { key: "g" });
    vi.advanceTimersByTime(CHORD_WINDOW_MS - 1);
    fireEvent.keyDown(window, { key: "n" });
    expect(pushMock).toHaveBeenCalledWith("/");
  });

  it("a second leader press restarts the window instead of cancelling it", () => {
    vi.useFakeTimers();
    renderWith();
    fireEvent.keyDown(window, { key: "g" });
    vi.advanceTimersByTime(CHORD_WINDOW_MS - 10);
    fireEvent.keyDown(window, { key: "g" });
    vi.advanceTimersByTime(CHORD_WINDOW_MS - 10);
    fireEvent.keyDown(window, { key: "t" });
    expect(pushMock).toHaveBeenCalledWith("/my-teams");
  });
});

describe("keys that belong to something else", () => {
  it("ignores auto-repeat, so holding the leader is not a coin flip", () => {
    renderWith();
    fireEvent.keyDown(window, { key: "g" });
    for (let i = 0; i < 5; i++) {
      fireEvent.keyDown(window, { key: "g", repeat: true });
    }
    fireEvent.keyDown(window, { key: "n" });
    expect(pushMock).toHaveBeenCalledWith("/");
  });

  it.each([
    ["input", <input aria-label="team-name" key="i" />, "input"],
    ["textarea", <textarea aria-label="notes" key="t" />, "textarea"],
    ["select", <select aria-label="pick" key="s" />, "select"],
    [
      "contenteditable",
      <div contentEditable aria-label="rich" key="c" />,
      "[contenteditable]",
    ],
  ])("ignores the chord while focus is in a %s", (_label, node, selector) => {
    const { container } = renderWith(node);
    const el = container.querySelector(selector) as HTMLElement;
    fireEvent.keyDown(el, { key: "g" });
    fireEvent.keyDown(el, { key: "n" });
    expect(pushMock).not.toHaveBeenCalled();
  });

  it('ignores contenteditable="plaintext-only" (the Story 2.2 composer case)', () => {
    const { container } = renderWith(
      <div contentEditable="plaintext-only" suppressContentEditableWarning />
    );
    const el = container.querySelector("[contenteditable]") as HTMLElement;
    fireEvent.keyDown(el, { key: "g" });
    fireEvent.keyDown(el, { key: "n" });
    expect(pushMock).not.toHaveBeenCalled();
  });

  it("ignores a keystroke on a child of a contenteditable region", () => {
    const { container } = renderWith(
      <div contentEditable suppressContentEditableWarning>
        <span data-testid="child">text</span>
      </div>
    );
    const child = container.querySelector('[data-testid="child"]') as HTMLElement;
    fireEvent.keyDown(child, { key: "g" });
    fireEvent.keyDown(child, { key: "n" });
    expect(pushMock).not.toHaveBeenCalled();
  });

  it("cancels a pending chord when focus moves into a text field", () => {
    const { container } = renderWith(<input aria-label="team-name" />);
    const input = container.querySelector("input") as HTMLInputElement;
    fireEvent.keyDown(window, { key: "g" });
    fireEvent.keyDown(input, { key: "n" });
    fireEvent.keyDown(window, { key: "t" });
    // The arm must not survive the excursion and fire on the next page key.
    expect(pushMock).not.toHaveBeenCalled();
  });

  it("ignores the chord when a modifier is held (no cmd/ctrl+b collision)", () => {
    renderWith();
    fireEvent.keyDown(window, { key: "g", metaKey: true });
    fireEvent.keyDown(window, { key: "n" });
    expect(pushMock).not.toHaveBeenCalled();
  });
});

describe("teardown", () => {
  it("stops listening after unmount", () => {
    const { unmount } = renderWith();
    unmount();
    fireEvent.keyDown(window, { key: "g" });
    fireEvent.keyDown(window, { key: "n" });
    expect(pushMock).not.toHaveBeenCalled();
  });
});
