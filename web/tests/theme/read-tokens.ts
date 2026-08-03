import fs from "node:fs";
import path from "node:path";

/**
 * Reads design tokens out of the SHIPPED stylesheet.
 *
 * Story 2.1's first cut kept a hand-maintained copy of the brand hexes in
 * `lib/brand-tokens.ts` and asserted against that. The copy was never
 * compared to `globals.css`, so the contrast guard measured the mirror and
 * stayed green no matter what the browser actually loaded. Every theme test
 * now parses the real file instead — there is no second source to drift.
 */

export const GLOBALS_CSS_PATH = path.join(process.cwd(), "app/globals.css");

export function readGlobalsCss(): string {
  return fs.readFileSync(GLOBALS_CSS_PATH, "utf8");
}

/** Comments can contain braces and marker text; remove them before parsing. */
export function stripCssComments(css: string): string {
  return css.replace(/\/\*[\s\S]*?\*\//g, "");
}

export type Declaration = { prop: string; value: string };

const DECLARATION_RE = /(--[\w-]+)\s*:\s*([^;{}]+);/g;

function declarationsIn(source: string): Declaration[] {
  const out: Declaration[] = [];
  DECLARATION_RE.lastIndex = 0;
  let match: RegExpExecArray | null;
  while ((match = DECLARATION_RE.exec(source))) {
    out.push({ prop: match[1], value: match[2].trim() });
  }
  return out;
}

/** Every custom-property declaration in the file, regardless of selector. */
export function allDeclarations(css: string): Declaration[] {
  return declarationsIn(stripCssComments(css));
}

/**
 * Bodies of every top-level block with this exact selector. Brace-counted,
 * so a nested at-rule cannot truncate the block, and unbalanced braces throw
 * rather than silently yielding a short (and therefore vacuously clean) slice.
 */
export function extractBlocks(css: string, selector: string): string[] {
  const clean = stripCssComments(css);
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const opener = new RegExp(`(?:^|[};])\\s*${escaped}\\s*\\{`, "g");
  const blocks: string[] = [];

  let match: RegExpExecArray | null;
  while ((match = opener.exec(clean))) {
    const start = match.index + match[0].length;
    let depth = 1;
    let i = start;
    while (i < clean.length && depth > 0) {
      if (clean[i] === "{") depth++;
      else if (clean[i] === "}") depth--;
      i++;
    }
    if (depth !== 0) {
      throw new Error(`Unbalanced braces after "${selector}" in globals.css`);
    }
    blocks.push(clean.slice(start, i - 1));
  }

  if (blocks.length === 0) {
    throw new Error(`Selector "${selector}" not found in globals.css`);
  }
  return blocks;
}

/** All declarations under a selector, across every block using it. */
export function blockDeclarations(css: string, selector: string): Declaration[] {
  return extractBlocks(css, selector).flatMap(declarationsIn);
}

/**
 * The value a browser would use for `prop` under `selector` — the LAST
 * declaration wins, matching the cascade. Throws when absent, so a renamed
 * or deleted token fails loudly instead of comparing against `undefined`.
 */
export function tokenValue(css: string, selector: string, prop: string): string {
  const matches = blockDeclarations(css, selector).filter((d) => d.prop === prop);
  if (matches.length === 0) {
    throw new Error(`"${prop}" is not declared in "${selector}"`);
  }
  return matches[matches.length - 1].value;
}
