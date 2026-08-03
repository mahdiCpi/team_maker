import { describe, expect, it } from "vitest";

import { readGlobalsCss, tokenValue } from "./read-tokens";

/**
 * Story 2.1, AC 10 — measured contrast, not asserted-by-assumption.
 *
 * The pairs are read out of the SHIPPED `globals.css`. The first version read
 * a hand-maintained copy in `lib/brand-tokens.ts` that nothing compared to the
 * stylesheet, so changing `--primary` to any low-contrast value left this test
 * reporting the old ratio and passing.
 */

const HEX_RE = /^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/;

export function hexToRgb(hex: string): [number, number, number] {
  const value = hex.trim();
  // Without this, "teal" / "" / "#GGGGGG" all parse to black via NaN→0 and
  // silently return a guaranteed-passing 21:1.
  if (!HEX_RE.test(value)) {
    throw new Error(
      `Expected a 3- or 6-digit hex colour, got "${hex}". ` +
        `Alpha and named colours are not comparable with WCAG contrast.`
    );
  }
  const digits = value.slice(1);
  const full =
    digits.length === 3
      ? digits
          .split("")
          .map((d) => d + d)
          .join("")
      : digits;
  const int = parseInt(full, 16);
  return [(int >> 16) & 255, (int >> 8) & 255, int & 255];
}

function srgbChannelToLinear(channel255: number): number {
  const c = channel255 / 255;
  return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
}

export function relativeLuminance(hex: string): number {
  const [r, g, b] = hexToRgb(hex);
  return (
    0.2126 * srgbChannelToLinear(r) +
    0.7152 * srgbChannelToLinear(g) +
    0.0722 * srgbChannelToLinear(b)
  );
}

export function contrastRatio(hexA: string, hexB: string): number {
  const lA = relativeLuminance(hexA);
  const lB = relativeLuminance(hexB);
  return (Math.max(lA, lB) + 0.05) / (Math.min(lA, lB) + 0.05);
}

/** WCAG 2.2 SC 1.4.11 non-text floor — the bar AC 10 sets. */
const NON_TEXT_FLOOR = 3.0;

describe("hex parsing rejects everything it cannot honestly measure", () => {
  it.each(["teal", "", "#GGGGGG", "#0E8C8", "0E8C82", "#0E8C82FF", "#12345"])(
    "throws on %o instead of silently computing a wrong ratio",
    (input) => {
      expect(() => hexToRgb(input)).toThrow();
    }
  );

  it("expands 3-digit shorthand correctly", () => {
    expect(hexToRgb("#fff")).toEqual([255, 255, 255]);
    expect(hexToRgb("#0f8")).toEqual([0, 255, 136]);
  });

  it("accepts lowercase", () => {
    expect(hexToRgb("#0e8c82")).toEqual(hexToRgb("#0E8C82"));
  });
});

describe("luminance formula, checked against known anchors", () => {
  it("computes 1.0 for white and 0.0 for black", () => {
    expect(relativeLuminance("#FFFFFF")).toBeCloseTo(1, 5);
    expect(relativeLuminance("#000000")).toBeCloseTo(0, 5);
  });

  it("computes the maximum possible 21:1 for black on white", () => {
    expect(contrastRatio("#000000", "#FFFFFF")).toBeCloseTo(21, 1);
  });

  it("is symmetric in its arguments", () => {
    expect(contrastRatio("#0E8C82", "#FFFFFF")).toBeCloseTo(
      contrastRatio("#FFFFFF", "#0E8C82"),
      10
    );
  });
});

describe("brand token contrast, measured from the shipped stylesheet (AC 10)", () => {
  const css = readGlobalsCss();

  const pairs = [
    {
      label: "light: primary-foreground on primary",
      fg: tokenValue(css, ":root", "--primary-foreground"),
      bg: tokenValue(css, ":root", "--primary"),
    },
    {
      label: "dark: primary-foreground on primary",
      fg: tokenValue(css, ".dark", "--primary-foreground"),
      bg: tokenValue(css, ".dark", "--primary"),
    },
    {
      label: "signal-foreground on signal",
      fg: tokenValue(css, ":root", "--signal-foreground"),
      bg: tokenValue(css, ":root", "--signal"),
    },
  ];

  it.each(pairs)("$label clears the 3:1 non-text floor", ({ label, fg, bg }) => {
    const ratio = contrastRatio(fg, bg);
    console.info(`[contrast] ${label}: ${fg} on ${bg} = ${ratio.toFixed(2)}:1`);
    expect(ratio).toBeGreaterThanOrEqual(NON_TEXT_FLOOR);
  });

  it("reads the DESIGN.md brand values, not a stale copy", () => {
    expect(tokenValue(css, ":root", "--primary").toUpperCase()).toBe("#0E8C82");
    expect(tokenValue(css, ".dark", "--primary").toUpperCase()).toBe("#17B3A6");
  });
});
