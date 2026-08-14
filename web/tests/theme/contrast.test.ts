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

const OKLCH_RE = /^oklch\(\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)/;

/**
 * shadcn's own defaults (`--background`, `--card`, …) ship as `oklch(...)`,
 * not hex — unlike the brand layer's hand-written hex literals, which is all
 * `hexToRgb` above ever had to parse. Converts via the standard OKLab
 * matrices (Björn Ottosson's, the same ones the CSS Color 4 spec uses) so an
 * arbitrary oklch token — not just the achromatic (`C=0`) greys shadcn ships
 * — measures correctly.
 */
function oklchToRgb255(value: string): [number, number, number] {
  const match = OKLCH_RE.exec(value.trim());
  if (!match) {
    throw new Error(`Expected an oklch(...) colour, got "${value}".`);
  }
  const L = Number(match[1]);
  const C = Number(match[2]);
  const hRad = (Number(match[3]) * Math.PI) / 180;
  const a = C * Math.cos(hRad);
  const b = C * Math.sin(hRad);

  const l_ = L + 0.3963377774 * a + 0.2158037573 * b;
  const m_ = L - 0.1055613458 * a - 0.0638541728 * b;
  const s_ = L - 0.0894841775 * a - 1.2914855480 * b;

  const l = l_ ** 3;
  const m = m_ ** 3;
  const s = s_ ** 3;

  const rLin = 4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s;
  const gLin = -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s;
  const bLin = -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s;

  const encode = (channel: number) => {
    const clamped = Math.min(1, Math.max(0, channel));
    return clamped <= 0.0031308
      ? 12.92 * clamped
      : 1.055 * Math.pow(clamped, 1 / 2.4) - 0.055;
  };

  return [
    Math.round(encode(rLin) * 255),
    Math.round(encode(gLin) * 255),
    Math.round(encode(bLin) * 255),
  ];
}

function relativeLuminanceOfToken(value: string): number {
  const trimmed = value.trim();
  if (HEX_RE.test(trimmed)) return relativeLuminance(trimmed);
  if (trimmed.startsWith("oklch(")) {
    const [r, g, b] = oklchToRgb255(trimmed);
    return (
      0.2126 * srgbChannelToLinear(r) +
      0.7152 * srgbChannelToLinear(g) +
      0.0722 * srgbChannelToLinear(b)
    );
  }
  throw new Error(`Cannot measure contrast for "${value}" — expected hex or oklch().`);
}

/** Like `contrastRatio`, but accepts either the brand layer's hex literals
 *  or shadcn's own `oklch(...)` defaults — needed once a pair spans both,
 *  as the ring-vs-background/card pairs below do. */
function contrastRatioOfTokens(a: string, b: string): number {
  const lA = relativeLuminanceOfToken(a);
  const lB = relativeLuminanceOfToken(b);
  return (Math.max(lA, lB) + 0.05) / (Math.min(lA, lB) + 0.05);
}

/** WCAG 2.2 SC 1.4.11 non-text floor — the bar AC 10 sets. */
const NON_TEXT_FLOOR = 3.0;

/** WCAG 2.2 SC 1.4.3 normal text floor for AA compliance. */
const TEXT_FLOOR = 4.5;

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

  it("light: primary-foreground on primary clears the 4.5:1 AA text floor", () => {
    const fg = tokenValue(css, ":root", "--primary-foreground");
    const bg = tokenValue(css, ":root", "--primary");
    const ratio = contrastRatio(fg, bg);
    console.info(`[contrast] light AA text: ${fg} on ${bg} = ${ratio.toFixed(2)}:1`);
    expect(ratio).toBeGreaterThanOrEqual(TEXT_FLOOR);
  });

  it("reads the DESIGN.md brand values, not a stale copy", () => {
    expect(tokenValue(css, ":root", "--primary").toUpperCase()).toBe("#0D857B");
    expect(tokenValue(css, ".dark", "--primary").toUpperCase()).toBe("#17B3A6");
  });

  describe("ring-vs-background contrast (AC 6)", () => {
    const ringVsBackgroundPairs = [
      {
        label: "light: ring on background",
        fg: tokenValue(css, ":root", "--ring"),
        bg: tokenValue(css, ":root", "--background"),
      },
      {
        label: "light: ring on card",
        fg: tokenValue(css, ":root", "--ring"),
        bg: tokenValue(css, ":root", "--card"),
      },
      {
        label: "dark: ring on background",
        fg: tokenValue(css, ".dark", "--ring"),
        bg: tokenValue(css, ".dark", "--background"),
      },
      {
        label: "dark: ring on card",
        fg: tokenValue(css, ".dark", "--ring"),
        bg: tokenValue(css, ".dark", "--card"),
      },
    ];

    it.each(ringVsBackgroundPairs)(
      "$label clears the 3:1 non-text floor",
      ({ label, fg, bg }) => {
        // `fg` (`--ring`) is always hex; `bg` (`--background`/`--card`) is
        // shadcn's own `oklch(...)` default — `contrastRatioOfTokens` reads
        // either format rather than assuming hex.
        const ratio = contrastRatioOfTokens(fg, bg);
        console.info(`[contrast] ${label}: ${fg} on ${bg} = ${ratio.toFixed(2)}:1`);
        expect(ratio).toBeGreaterThanOrEqual(NON_TEXT_FLOOR);
      }
    );
  });
});
