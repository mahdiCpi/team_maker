import fs from "node:fs";
import path from "node:path";

export type ScanHit = { file: string; line: number; match: string };

/**
 * Story 2.1, AC 6 — semantic tokens only. Every colour in the product comes
 * from `app/globals.css`; nothing else may hard-code one.
 *
 * Two failure modes this scanner is written against, both found in review:
 *   - Too narrow: the first version walked only `app/` and `components/`, so
 *     `lib/` and `hooks/` were unguarded, and it matched only hex/rgb/oklch
 *     plus numbered Tailwind palette classes — missing `bg-white`,
 *     `text-black`, CSS named colours and every modern colour function.
 *   - Too eager: it scanned raw text, so `// fixes #1234` and `href="#add"`
 *     were reported as colour literals.
 * Both directions are pinned by fixtures in color-literals.test.ts.
 */

/** Values that name no colour of their own — these must never be flagged. */
const NON_LITERAL_VALUES =
  /^(?:currentcolor|none|transparent|inherit|initial|unset|revert|revert-layer|auto)$/i;

const NAMED_COLORS = [
  "white", "black", "red", "green", "blue", "yellow", "orange", "purple",
  "pink", "brown", "gray", "grey", "cyan", "magenta", "teal", "navy", "olive",
  "maroon", "lime", "aqua", "fuchsia", "silver", "gold", "beige", "coral",
  "crimson", "indigo", "ivory", "khaki", "lavender", "salmon", "tan",
  "turquoise", "violet", "wheat", "azure", "plum", "orchid", "tomato",
  "rebeccapurple", "aliceblue", "antiquewhite", "chartreuse", "chocolate",
  "darkblue", "darkgreen", "darkred", "deeppink", "dodgerblue", "firebrick",
  "forestgreen", "hotpink", "lightblue", "lightgreen", "midnightblue",
  "seagreen", "skyblue", "slateblue", "springgreen", "steelblue",
].join("|");

const TAILWIND_PALETTE_FAMILIES = [
  "slate", "gray", "zinc", "neutral", "stone", "red", "orange", "amber",
  "yellow", "lime", "green", "emerald", "teal", "cyan", "sky", "blue",
  "indigo", "violet", "purple", "fuchsia", "pink", "rose",
].join("|");

/** Tailwind utilities that take a colour. */
const COLOR_UTILITIES =
  "bg|text|border|ring|fill|stroke|from|via|to|outline|decoration|caret|divide|shadow|accent|placeholder";

/** CSS properties whose value is a colour. */
const COLOR_PROPERTIES =
  "color|background|background-color|border-color|border-top-color|border-right-color|border-bottom-color|border-left-color|outline-color|fill|stroke|stop-color|flood-color|lighting-color|caret-color|text-decoration-color|column-rule-color|accent-color|box-shadow|text-shadow";

/** JSX/SVG attributes whose value is a colour. */
const COLOR_ATTRIBUTES =
  "fill|stroke|color|stopColor|floodColor|lightingColor|bgcolor";

type Matcher = { name: string; re: RegExp; reject?: (m: RegExpExecArray) => boolean };

const MATCHERS: Matcher[] = [
  {
    name: "hex",
    // 3/4/6/8 digits only — the lengths CSS actually accepts.
    re: /#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{4}|[0-9a-fA-F]{3})\b/g,
  },
  {
    name: "color-function",
    re: /\b(?:rgba?|hsla?|hwb|lab|lch|oklab|oklch|color|color-mix)\s*\(/g,
  },
  {
    name: "tailwind-palette",
    re: new RegExp(
      `\\b(?:${COLOR_UTILITIES})-(?:${TAILWIND_PALETTE_FAMILIES})-\\d{2,3}\\b`,
      "g"
    ),
  },
  {
    name: "tailwind-fixed-color",
    // bg-white / text-black / border-white — no numeric shade, so the
    // palette matcher above can never see them.
    re: new RegExp(`\\b(?:${COLOR_UTILITIES})-(?:white|black)\\b`, "g"),
  },
  {
    name: "tailwind-arbitrary-color",
    // bg-[#fff], text-[red], border-[rgb(0,0,0)]
    re: new RegExp(`\\b(?:${COLOR_UTILITIES})-\\[[^\\]]*\\]`, "g"),
    reject: (m) => !/#|\brgb|\bhsl|\bokl|\blab|\blch|\bhwb|\bcolor\(/i.test(m[0])
      && !new RegExp(`\\[(?:${NAMED_COLORS})\\]`, "i").test(m[0]),
  },
  {
    name: "css-named-color",
    re: new RegExp(`\\b(?:${COLOR_PROPERTIES})\\s*:\\s*(${NAMED_COLORS})\\b`, "gi"),
  },
  {
    name: "jsx-color-attribute",
    re: new RegExp(`\\b(?:${COLOR_ATTRIBUTES})\\s*=\\s*["']([^"']+)["']`, "g"),
    reject: (m) => NON_LITERAL_VALUES.test(m[1].trim()),
  },
];

const SCANNED_EXTENSIONS = /\.(tsx?|jsx?|mts|mjs|css)$/;

/** Roots that hold authored source. `lib/` and `hooks/` were the blind spot. */
const SCAN_ROOTS = ["app", "components", "lib", "hooks"];

/** Vendored shadcn CLI output — upstream code, never hand-edited (AC 12). */
const VENDORED = [
  "components/ui/",
  "hooks/use-mobile.ts",
  "lib/utils.ts",
];

/** The one file where colour literals belong. */
const TOKEN_FILE = "app/globals.css";

/**
 * Remove text that legitimately contains `#` or colour words but names no
 * colour: comments, and URL/anchor fragments. Replaced with equal-length
 * blanks so reported line numbers stay accurate.
 */
export function stripNonColorContexts(content: string): string {
  const blank = (s: string) => s.replace(/[^\n]/g, " ");
  return content
    .replace(/\/\*[\s\S]*?\*\//g, blank)
    .replace(/(^|[^:])\/\/[^\n]*/g, (m, p1) => p1 + blank(m.slice(p1.length)))
    .replace(/\b(?:href|src|id|action|xlinkHref)\s*=\s*["'][^"']*["']/g, blank);
}

export function scanContentForColorLiterals(
  file: string,
  content: string
): ScanHit[] {
  const hits: ScanHit[] = [];
  stripNonColorContexts(content)
    .split("\n")
    .forEach((line, index) => {
      for (const matcher of MATCHERS) {
        matcher.re.lastIndex = 0;
        let match: RegExpExecArray | null;
        while ((match = matcher.re.exec(line))) {
          if (matcher.reject?.(match)) continue;
          hits.push({ file, line: index + 1, match: match[0] });
        }
      }
    });
  return hits;
}

function walk(dir: string, files: string[] = []): string[] {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    // statSync follows symlinks, so a linked directory is still traversed.
    if (fs.statSync(full).isDirectory()) walk(full, files);
    else if (SCANNED_EXTENSIONS.test(entry.name)) files.push(full);
  }
  return files;
}

export function collectScanTargets(webRoot: string): string[] {
  const targets: string[] = [];
  for (const base of SCAN_ROOTS) {
    const dir = path.join(webRoot, base);
    if (!fs.existsSync(dir)) continue;
    for (const file of walk(dir)) {
      const rel = path.relative(webRoot, file).replace(/\\/g, "/");
      if (rel === TOKEN_FILE) continue;
      if (VENDORED.some((v) => rel === v || rel.startsWith(v))) continue;
      targets.push(file);
    }
  }
  return targets;
}

/** Collects every offence — never short-circuits on the first. */
export function scanForColorLiterals(files: string[]): ScanHit[] {
  return files.flatMap((file) =>
    scanContentForColorLiterals(file, fs.readFileSync(file, "utf8"))
  );
}
