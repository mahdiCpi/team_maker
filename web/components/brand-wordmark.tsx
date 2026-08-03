function RobotGlyph({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      className={className}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      data-testid="robot-glyph"
    >
      <line x1="12" y1="2" x2="12" y2="4.5" />
      <circle cx="12" cy="1.5" r="0.75" fill="currentColor" stroke="none" />
      <rect x="4" y="4.5" width="16" height="14" rx="4" />
      <circle cx="9" cy="11.5" r="1.25" fill="currentColor" stroke="none" />
      <circle cx="15" cy="11.5" r="1.25" fill="currentColor" stroke="none" />
      <line x1="8.5" y1="16" x2="15.5" y2="16" />
    </svg>
  )
}

/**
 * Monochrome robot wordmark (Story 2.1, AC 4).
 *
 * `text-foreground` is deliberate: DESIGN.md:120-121 — the clause AC 4 cites —
 * specifies the glyph inherits `foreground`, which is also why it must be
 * inline SVG on `currentColor` rather than the raster `assets/cpi_logo.jpg`.
 *
 * The accessible name lives on a single sr-only element rather than on the
 * SVG: with the visible wordmark alongside, an `aria-label` on the glyph made
 * screen readers announce "team_maker" twice. This way the name survives the
 * icon-collapsed state, where the visible text is hidden.
 */
export function BrandWordmark() {
  return (
    <div className="flex items-center gap-2 px-1 py-1">
      <RobotGlyph className="size-6 shrink-0 text-foreground" />
      <span className="sr-only">team_maker — Coinpela R&amp;D</span>
      <div
        aria-hidden="true"
        className="flex min-w-0 flex-col leading-none group-data-[collapsible=icon]:hidden"
      >
        <span className="truncate text-sm font-semibold tracking-tight">
          team_maker
        </span>
        <span className="truncate text-[0.6875rem] text-muted-foreground">
          Coinpela R&amp;D
        </span>
      </div>
    </div>
  )
}
