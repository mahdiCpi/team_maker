import path from "node:path";

import { describe, expect, it } from "vitest";

import {
  collectScanTargets,
  scanContentForColorLiterals,
  scanForColorLiterals,
  stripNonColorContexts,
} from "./color-scan";

/**
 * Story 2.1, AC 6 / Guard test A.
 *
 * A scan regex that matches nothing passes exactly like clean code does, so
 * the matcher is proved against known-bad fixtures before any zero-hit result
 * on the real tree is trusted — and against known-GOOD fixtures too, because
 * a scanner that flags innocent code gets disabled by the next person who
 * trips over it. Review found both failure modes in the first version.
 */

const bad = (src: string) => scanContentForColorLiterals("fixture.tsx", src);

describe("matcher catches every colour form a developer could write", () => {
  it.each([
    ["6-digit hex", 'const c = "#2DD4BF"'],
    ["3-digit hex", 'const c = "#fff"'],
    ["8-digit hex with alpha", 'const c = "#2DD4BFCC"'],
    ["rgb()", ".x { color: rgb(45, 212, 191); }"],
    ["rgba()", ".x { color: rgba(45, 212, 191, 0.5); }"],
    ["hsl()", ".x { color: hsl(174 66% 50%); }"],
    ["oklch()", ".x { color: oklch(0.7 0.1 180); }"],
    ["oklab()", ".x { color: oklab(0.7 0.1 0.1); }"],
    ["lab()", ".x { color: lab(70% 20 30); }"],
    ["lch()", ".x { color: lch(70% 40 180); }"],
    ["hwb()", ".x { color: hwb(180 20% 10%); }"],
    ["color()", ".x { color: color(display-p3 1 0 0); }"],
    ["color-mix()", ".x { color: color-mix(in oklch, white, black); }"],
    ["numbered palette class", '<div className="bg-teal-500" />'],
    ["bg-white", '<div className="bg-white" />'],
    ["text-black", '<div className="text-black" />'],
    ["border-white", '<div className="border-white" />'],
    ["arbitrary hex value", '<div className="bg-[#2DD4BF]" />'],
    ["arbitrary named value", '<div className="text-[red]" />'],
    ["CSS named colour", ".x { color: rebeccapurple; }"],
    ["CSS named colour on fill", ".x { fill: red; }"],
    ["JSX fill attribute", '<circle fill="black" />'],
    ["JSX stroke attribute", '<path stroke="white" />'],
  ])("flags %s", (_label, source) => {
    expect(bad(source)).not.toEqual([]);
  });

  it("reports every offence rather than stopping at the first", () => {
    const hits = bad('<div className="bg-teal-500 text-slate-900 bg-white" />');
    expect(hits.length).toBe(3);
  });
});

describe("matcher leaves legitimate token-based code alone", () => {
  it.each([
    ["semantic utilities", '<div className="bg-signal text-muted-foreground" />'],
    ["currentColor", '<svg stroke="currentColor" fill="none" />'],
    ["fill none", '<path fill="none" />'],
    ["var() reference", ".x { color: var(--primary); }"],
    ["issue reference in a line comment", "// fixes #1234 — see tracker"],
    ["issue reference in a block comment", "/* see #abc123 for context */"],
    ["in-page anchor", '<a href="#add">jump</a>'],
    ["hash in a src attribute", '<img src="/x.svg#icon" />'],
    ["colour word in prose", "<p>The red team ships on Friday.</p>"],
    ["non-colour arbitrary value", '<div className="w-[42px]" />'],
    ["transparent keyword", '<div className="border-transparent" />'],
  ])("does not flag %s", (_label, source) => {
    expect(bad(source)).toEqual([]);
  });

  it("blanks comments without shifting line numbers", () => {
    const stripped = stripNonColorContexts("a\n/* #fff */\nb");
    expect(stripped.split("\n")).toHaveLength(3);
  });
});

describe("scan traversal reaches the directories it claims to", () => {
  const webRoot = process.cwd();
  const targets = collectScanTargets(webRoot).map((f) =>
    path.relative(webRoot, f).replace(/\\/g, "/")
  );

  it.each([
    "app/page.tsx",
    "app/layout.tsx",
    "app/settings/page.tsx",
    "components/app-sidebar.tsx",
    "components/brand-wordmark.tsx",
    "lib/nav-items.ts",
  ])("walks to %s", (file) => {
    // Named files, not a bare count: breaking the recursion or dropping a
    // scan root now fails here instead of passing vacuously.
    expect(targets).toContain(file);
  });

  it("descends into nested route directories", () => {
    expect(targets.filter((f) => f.split("/").length > 2).length).toBeGreaterThan(0);
  });

  it("excludes vendored shadcn output and the token file", () => {
    expect(targets.filter((f) => f.startsWith("components/ui/"))).toEqual([]);
    expect(targets).not.toContain("hooks/use-mobile.ts");
    expect(targets).not.toContain("lib/utils.ts");
    expect(targets).not.toContain("app/globals.css");
  });
});

describe("guard A — no stray colour literals in authored source", () => {
  it("finds zero colour literals across app/, components/, lib/ and hooks/", () => {
    const files = collectScanTargets(process.cwd());
    expect(files.length).toBeGreaterThan(0);
    expect(scanForColorLiterals(files)).toEqual([]);
  });
});
