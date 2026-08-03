import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { BrandWordmark } from "@/components/brand-wordmark";

function glyph() {
  return screen.getByTestId("robot-glyph");
}

describe("BrandWordmark glyph", () => {
  it("is an inline SVG", () => {
    render(<BrandWordmark />);
    expect(glyph().tagName.toLowerCase()).toBe("svg");
  });

  it("takes its colour from the foreground token, per DESIGN.md:120-121", () => {
    render(<BrandWordmark />);
    // Pinned explicitly: the glyph shipped as `text-primary` (brand teal),
    // contradicting the DESIGN.md clause AC 4 cites.
    // getAttribute, not .className: on an SVG element that is an
    // SVGAnimatedString object rather than a string.
    expect(glyph()).toHaveClass("text-foreground");
    expect(glyph().getAttribute("class")).not.toMatch(/text-primary/);
  });

  it("strokes with currentColor rather than a literal", () => {
    render(<BrandWordmark />);
    expect(glyph().getAttribute("stroke")).toBe("currentColor");
  });

  it("uses no hard-coded fill on the glyph or any of its shapes", () => {
    render(<BrandWordmark />);
    expect(["none", "currentColor", null]).toContain(
      glyph().getAttribute("fill")
    );

    const filled = Array.from(glyph().querySelectorAll("[fill]"));
    expect(filled.length).toBeGreaterThan(0);
    for (const node of filled) {
      expect(["none", "currentColor"]).toContain(node.getAttribute("fill"));
    }
  });
});

describe("BrandWordmark accessible name", () => {
  it("carries a name that survives the icon-collapsed state", () => {
    render(<BrandWordmark />);
    // sr-only, so it is announced whether or not the visible text is hidden
    // by group-data-[collapsible=icon]:hidden.
    expect(screen.getByText("team_maker — Coinpela R&D")).toHaveClass("sr-only");
  });

  it("hides the visible wordmark from assistive tech to avoid announcing it twice", () => {
    const { container } = render(<BrandWordmark />);
    // div, not [aria-hidden] alone — the decorative glyph is aria-hidden too.
    const visible = container.querySelector('div[aria-hidden="true"]');
    expect(visible).not.toBeNull();
    expect(visible?.textContent).toContain("team_maker");
  });

  it("marks the decorative glyph aria-hidden", () => {
    render(<BrandWordmark />);
    expect(glyph()).toHaveAttribute("aria-hidden", "true");
  });
});

describe("BrandWordmark visible content", () => {
  it("renders the wordmark and the Coinpela R&D tag", () => {
    const { container } = render(<BrandWordmark />);
    // div, not [aria-hidden] alone — the decorative glyph is aria-hidden too.
    const visible = container.querySelector('div[aria-hidden="true"]');
    expect(visible?.textContent).toBe("team_makerCoinpela R&D");
  });
});
