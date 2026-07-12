---
name: team_maker
description: Coinpela R&D product — conversational multi-agent team builder. shadcn/ui on Next.js + Tailwind; this DESIGN.md specifies the Coinpela brand-layer delta only. Colors are semantic tokens so the theme is swappable in one place.
status: final
sources:
  - project-docs/prds/prd-team_maker-2026-07-05/prd.md
  - project-docs/briefs/brief-team_maker-2026-07-04/brief.md
updated: 2026-07-05
colors:
  # Brand overrides on top of shadcn defaults ("Fintech Teal" direction).
  # All unlisted tokens inherit from shadcn (background, foreground, muted,
  # muted-foreground, popover, card, border, input, destructive, and their
  # -foreground pairs). Swapping the theme later = change primary/accent here only.
  primary: '#0E8C82'
  primary-foreground: '#FFFFFF'
  accent: '#2DD4BF'
  accent-foreground: '#04100E'
  ring: '#0E8C82'
  primary-dark: '#17B3A6'
  primary-foreground-dark: '#04100E'
  accent-dark: '#2DD4BF'
  ring-dark: '#17B3A6'
typography:
  # Inherit shadcn's default sans ramp for body/label/caption. No serif display
  # role — this is a tool, not an editorial product.
  display:
    fontFamily: 'inherit (shadcn sans)'
    fontSize: 28px
    fontWeight: '650'
    lineHeight: '1.2'
rounded:
  # shadcn defaults, very slightly tightened to read "tool".
  sm: 4px
  md: 6px
  lg: 8px
spacing:
  # shadcn / Tailwind 4-based scale inherited as-is. No overrides.
components:
  button-primary:
    background: '{colors.primary}'
    foreground: '{colors.primary-foreground}'
    radius: '{rounded.md}'
  agent-provider-badge:
    background: '{colors.muted}'
    foreground: '{colors.foreground}'
    radius: '{rounded.sm}'
  run-status-live:
    dot: '{colors.accent}'
    radius: '{rounded.full}'
---

## Brand & Style

team_maker is an open-source R&D product from **Coinpela**: describe a team of AI "thinkers" in
plain language and it builds and runs a multi-provider team for you. The personality is
**friendly + technical** — approachable and legible for semi-technical users, but unmistakably a
capable tool. The Coinpela mark (a friendly line-art robot cradling a bowl of ¢ coins) sets the
tone: clean, high-contrast, a little warm, never toy-like.

The product inherits **shadcn/ui wholesale** and adds only the Coinpela brand layer: the
Fintech-Teal `primary`/`accent`, the robot wordmark, and a handful of product-specific
components. Everything else (Button variants, Card, Dialog, Sheet, Command, Toast, Tabs,
Popover, Input, Textarea) uses shadcn's visual specs as-is. **Customizing shadcn defaults
beyond the brand layer is against the discipline** — the defaults are the contract, and they
keep the surface accessible and consistent across web, macOS, and Windows.

**Voice** (brand-level; microcopy specifics live in EXPERIENCE.md.Voice and Tone): plain,
confident, and helpful. We explain, we don't hype. "Which model should the critic use?" not
"Let's supercharge your AI dream team! 🚀".

## Colors

Two brand-layer colors plus shadcn defaults for everything else. **All color is expressed as
semantic tokens** (shadcn CSS variables) so re-theming is a single-place change — a hard product
requirement (the final Coinpela palette isn't locked yet).

- **Primary Teal (`#0E8C82` light / `#17B3A6` dark)** — brand color. Primary buttons, active nav,
  links, selected states. Replaces shadcn's default `primary`.
- **Signal Teal (`#2DD4BF`)** — accent. Reserved for **"live / running / now"**: the pulse on a
  running team, the active task in a run. Not for chrome, not decorative.
- **All other tokens** (`background`, `foreground`, `muted`, `muted-foreground`, `border`,
  `input`, `card`, `popover`, `destructive`) inherit shadcn defaults, light and dark.

Both **light and dark** themes are in scope and ship together (shadcn's dark mode + the teal
above). Avoid: a second brand hue, gradients, custom destructive colors (use shadcn's).

## Typography

Inherit shadcn's default sans ramp for body, label, and caption. `display` (28px/650) is used
for surface headings ("Describe your team", "Research & Content") — same family, heavier weight,
not a separate serif. This is a tool; typography stays quiet.

## Layout & Spacing

shadcn / Tailwind spacing scale inherited as-is. **Left sidebar** navigation on `lg+`
(New Team, Starter Teams, My Teams, Settings); collapses to icons on `md`; becomes a `Sheet` on
`sm`. Primary content column is comfortable-width, not full-bleed — reading and chat, not wide
tables. The desktop (macOS/Windows) builds use the same layout as web (shared codebase).

## Elevation & Depth

Inherited from shadcn — subtle shadow on hover/active, no elevation as hierarchy device. The
brand adds nothing on top.

## Shapes

Slightly tighter than shadcn: `rounded/sm` 4px inputs, `rounded/md` 6px cards/buttons,
`rounded/lg` 8px dialogs. Pills (`rounded/full`) only for status/provider badges.

## Components

Used as-is from shadcn (do not customize): `Button` (non-primary variants), `Card`, `Dialog`,
`Sheet`, `Command`, `Popover`, `DropdownMenu`, `Toast`, `Tabs`, `Avatar`, `Input`, `Textarea`,
`Skeleton`, `Badge`, `Separator`, `ScrollArea`.

Brand-layer / product components:

- **Button (primary variant)** — `{colors.primary}` fill, `{rounded.md}`. Other variants inherit
  shadcn.
- **Robot wordmark** — the Coinpela robot glyph + "team_maker" + a small "Coinpela R&D" tag.
  Sidebar header. Monochrome; inherits `foreground`.
- **Agent/provider badge** — small pill on an agent showing its Provider/model (e.g. `claude`,
  `gemini`, `openrouter`). `{colors.muted}` fill; the key-check state may tint it (see
  EXPERIENCE.md.State Patterns).
- **Run status (live)** — the `{colors.accent}` pulse dot meaning a team/task is running.
  Accent appears *here* and on the active task row, nowhere decorative.

## Do's and Don'ts

| Do | Don't |
|---|---|
| Express all color as semantic tokens (one-place theme swap) | Hard-code hex in components |
| Inherit shadcn defaults for everything outside the brand layer | Override shadcn tokens beyond `primary`/`accent` |
| Use `{colors.accent}` only for "live / running / now" | Use accent for chrome, hover, or decoration |
| Keep the robot mark monochrome and calm | Make it a bouncing mascot or add emoji energy |
| Ship light and dark together | Treat dark mode as an afterthought |
