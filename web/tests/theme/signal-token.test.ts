import fs from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

import { collectScanTargets } from "./color-scan";
import {
  allDeclarations,
  blockDeclarations,
  readGlobalsCss,
  tokenValue,
} from "./read-tokens";

/**
 * Story 2.1, AC 7 — Signal Teal must never be bound to shadcn's `--accent`.
 *
 * The first version of this guard extracted a comment-delimited "Brand
 * tokens" region and asserted `--accent:` did not appear inside it. That
 * caught nothing real: editing the `--accent` declaration the scaffold
 * already ships — the single most likely way this regresses — left the whole
 * suite green while every hover surface in the app turned teal. The guard now
 * pins the accent family by VALUE, wherever in the file it is declared, and
 * each assertion below is validated against a fixture reproducing a real
 * bypass.
 */

// shadcn's defaults (story:59). Signal Teal must never appear here.
const ACCENT_DEFAULTS: Record<string, Record<string, string>> = {
  ":root": {
    "--accent": "oklch(0.97 0 0)",
    "--accent-foreground": "oklch(0.205 0 0)",
  },
  ".dark": {
    "--accent": "oklch(0.269 0 0)",
    "--accent-foreground": "oklch(0.985 0 0)",
  },
};

const SIGNAL_VALUES = {
  "--signal": "#2DD4BF",
  "--signal-foreground": "#04100E",
};

/** Any token whose name puts it in the hover/focus/active surface family. */
const ACCENT_FAMILY_RE = /^--(?:color-)?(?:sidebar-)?accent(?:-foreground)?$/;

/** A value that routes back to Signal Teal, literally or by reference. */
const BINDS_SIGNAL_RE = /#2dd4bf\b|var\(\s*--signal\b|var\(\s*--color-signal\b/i;

function accentFamilyBoundToSignal(css: string): string[] {
  return allDeclarations(css)
    .filter((d) => ACCENT_FAMILY_RE.test(d.prop) && BINDS_SIGNAL_RE.test(d.value))
    .map((d) => `${d.prop}: ${d.value}`);
}

// ---------------------------------------------------------------------------
// Fixture validation. Each fixture is a bypass that the PREVIOUS guard passed.
// A guard that cannot fail is worse than no guard (story Dev Notes, rule 1).
// ---------------------------------------------------------------------------

describe("guard B matchers, validated against real bypasses", () => {
  it("catches Signal Teal bound to the scaffold's own --accent declaration", () => {
    const bad = ":root { --accent: #2DD4BF; }";
    expect(accentFamilyBoundToSignal(bad)).not.toEqual([]);
  });

  it("catches --sidebar-accent pointed at var(--signal)", () => {
    const bad = ":root { --sidebar-accent: var(--signal); }";
    expect(accentFamilyBoundToSignal(bad)).not.toEqual([]);
  });

  it("catches --color-accent rebound in @theme inline", () => {
    const bad = "@theme inline { --color-accent: var(--signal); }";
    expect(accentFamilyBoundToSignal(bad)).not.toEqual([]);
  });

  it("catches a lowercase hex spelling", () => {
    expect(accentFamilyBoundToSignal(":root{--accent:#2dd4bf;}")).not.toEqual([]);
  });

  it("does not flag the legitimate --signal token itself", () => {
    const good = ":root { --signal: #2DD4BF; --accent: oklch(0.97 0 0); }";
    expect(accentFamilyBoundToSignal(good)).toEqual([]);
  });

  it("does not confuse var(--accent) usage with an accent declaration", () => {
    const good = ":root { --ring: var(--accent); --signal: #2DD4BF; }";
    expect(accentFamilyBoundToSignal(good)).toEqual([]);
  });

  it("value pinning fails when a default is changed", () => {
    const bad = ":root { --accent: #2DD4BF; }";
    expect(tokenValue(bad, ":root", "--accent")).not.toBe("oklch(0.97 0 0)");
  });

  it("reports the LAST declaration, so a later override cannot hide behind an earlier default", () => {
    const bad = ":root { --accent: oklch(0.97 0 0); --accent: #2DD4BF; }";
    expect(tokenValue(bad, ":root", "--accent")).toBe("#2DD4BF");
  });
});

// ---------------------------------------------------------------------------
// The real assertions, against the shipped stylesheet.
// ---------------------------------------------------------------------------

describe("guard B — shadcn's accent family keeps its default values", () => {
  const css = readGlobalsCss();

  it.each(Object.keys(ACCENT_DEFAULTS))(
    "%s declares the untouched shadcn accent defaults",
    (selector) => {
      for (const [prop, expected] of Object.entries(ACCENT_DEFAULTS[selector])) {
        expect(tokenValue(css, selector, prop)).toBe(expected);
      }
    }
  );

  it("no token in the accent family resolves to Signal Teal, anywhere in the file", () => {
    expect(accentFamilyBoundToSignal(css)).toEqual([]);
  });
});

describe("guard B — the --signal pair exists and carries the DESIGN.md values", () => {
  const css = readGlobalsCss();

  it.each([":root", ".dark"])("%s declares --signal and --signal-foreground", (selector) => {
    for (const [prop, expected] of Object.entries(SIGNAL_VALUES)) {
      expect(tokenValue(css, selector, prop).toUpperCase()).toBe(expected);
    }
  });

  it("registers --color-signal so `bg-signal` is a real utility", () => {
    const themeBlock = blockDeclarations(css, "@theme inline");
    const registered = themeBlock.find((d) => d.prop === "--color-signal");
    expect(registered?.value).toBe("var(--signal)");
  });
});

// Story 2.1 shipped `--signal` with an empty consumer whitelist, naming
// Story 2.4 as its first consumer. `run-status.tsx` is that consumer — the
// run-level accent pulse, confined to exactly this one file (AC 12).
const SIGNAL_CONSUMER_WHITELIST: string[] = ["components/workspace/run-status.tsx"];

describe("guard B — no consumer of --signal outside the whitelist", () => {
  // Story 2.4 flipped the whitelist from empty to one entry — the title
  // "finds no source referencing --signal or bg-signal yet" would now be a
  // false sentence while the assertion still passed (defect class 5: a test
  // title is a testable assertion). Renamed to what it still guards.
  it("finds no consumer of --signal or bg-signal outside the whitelist", () => {
    const files = collectScanTargets(process.cwd());
    expect(files.length).toBeGreaterThan(0);

    const offenders = files.filter((file) => {
      const rel = path.relative(process.cwd(), file).replace(/\\/g, "/");
      if (SIGNAL_CONSUMER_WHITELIST.includes(rel)) return false;
      return /--signal\b|bg-signal\b/.test(fs.readFileSync(file, "utf8"));
    });

    expect(offenders).toEqual([]);
  });
});
