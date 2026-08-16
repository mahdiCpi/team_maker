import { toHaveNoViolations } from "jest-axe";
import { beforeEach, expect } from "vitest";
import "@testing-library/jest-dom/vitest";

// `jest-axe`'s `toHaveNoViolations` export is already the matcher-map shape
// `expect.extend` wants (`{ toHaveNoViolations: fn }`) — passing it directly,
// not re-wrapped in `{ toHaveNoViolations }`, which double-nests it and
// leaves `expect(...).toHaveNoViolations` bound to an object instead of a
// function.
expect.extend(toHaveNoViolations);

/**
 * jsdom implements no `matchMedia` at all (the property is absent, not
 * stubbed), and shadcn's vendored `use-mobile` hook plus our own
 * `useMediaQuery` both call it unconditionally.
 *
 * This stub is backed by `window.innerWidth` rather than hard-coded to
 * `false`. An always-false stub silently pinned every test to the desktop
 * branch, which is how the responsive behaviour AC 5 specifies went untested.
 * Tests set a viewport with `setViewportWidth` below.
 */

const listeners = new Set<() => void>();

function matches(query: string): boolean {
  const min = /\(min-width:\s*(\d+)px\)/.exec(query);
  if (min) return window.innerWidth >= Number(min[1]);
  const max = /\(max-width:\s*(\d+)px\)/.exec(query);
  if (max) return window.innerWidth <= Number(max[1]);
  return false;
}

if (typeof window !== "undefined") {
  window.matchMedia = ((query: string) => ({
    get matches() {
      return matches(query);
    },
    media: query,
    onchange: null,
    addListener: (cb: () => void) => listeners.add(cb),
    removeListener: (cb: () => void) => listeners.delete(cb),
    addEventListener: (_: string, cb: () => void) => listeners.add(cb),
    removeEventListener: (_: string, cb: () => void) => listeners.delete(cb),
    dispatchEvent: () => false,
  })) as unknown as typeof window.matchMedia;
}

/** jsdom's default. Restored between tests by the helper's caller. */
export const DEFAULT_VIEWPORT_WIDTH = 1024;

export function setViewportWidth(width: number): void {
  Object.defineProperty(window, "innerWidth", {
    configurable: true,
    writable: true,
    value: width,
  });
  listeners.forEach((cb) => cb());
}

/**
 * Story 2.11's first-visit orientation reads real `localStorage` and opens a
 * modal over the whole Composer whenever it's empty. Suites that aren't
 * exercising that feature are testing an established, already-seen surface —
 * so default every test to "already seen" here. `first-visit-orientation.test.tsx`
 * replaces `window.localStorage` with its own mock before this hook runs, so
 * this seed is a no-op there and has no effect on that suite's own scenarios.
 */
beforeEach(() => {
  try {
    localStorage.setItem("team_maker_orientation_shown", "true");
  } catch {
    // Storage may be unavailable in some environments — not this hook's job to fix.
  }
});
