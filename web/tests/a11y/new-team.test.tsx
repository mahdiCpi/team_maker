import { render } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ComposerSurface } from "@/components/composer/composer-surface";

import { completeFirstTurn, createFetchQueue, type FetchQueue } from "../composer/harness";

/**
 * New Team surface accessibility smoke tests (AC 9)
 *
 * Tests that the New Team route (ComposerSurface) has no axe violations in
 * both its empty state and a real mid-conversation state. `fetch` is stubbed
 * via the same harness `tests/composer/` uses (CLAUDE.md test transparency:
 * this is a mocked integration, not proof the API works) — the point is
 * reaching the actual mid-conversation DOM the composer renders, not the
 * empty state twice under a different name.
 */

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  usePathname: () => "/",
  // Story 3-2's `StarterSeedEffect` is mounted unconditionally inside
  // `ComposerSurface` and calls this on every render; without it this suite
  // throws "invariant expected app router to be mounted" (there is no
  // `?starter=` param in either test here, so it is otherwise a no-op).
  useSearchParams: () => new URLSearchParams(),
}));

let queue: FetchQueue;

beforeEach(() => {
  queue = createFetchQueue();
  queue.install();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("New Team surface accessibility", () => {
  it("should have no axe violations in empty state", async () => {
    const { container } = render(<ComposerSurface />);
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it("should have no axe violations in mid-conversation state", async () => {
    const user = userEvent.setup();
    const { container } = render(<ComposerSurface />);
    await completeFirstTurn(user, queue);

    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});
