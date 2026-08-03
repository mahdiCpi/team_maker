---
baseline_commit: a489334
---

# Story 2.1: App shell, sidebar nav, and theming

Status: done

## Story

As a semi-technical user,
I want a clean app with clear navigation,
so that I can use team_maker without the CLI.

## Acceptance Criteria

1. **Given** the repo has no JavaScript toolchain today, **When** this story lands, **Then** a Next.js App Router project exists at repo-root **`web/`** (per the Structural Seed, `ARCHITECTURE-SPINE.md:193`) on the pinned stack — **Next.js 16.2.x · React 19 · TypeScript · Tailwind v4 · shadcn/ui** (`ARCHITECTURE-SPINE.md:174-175`) — with a committed `package-lock.json`, and both `npm run build` and `npm run dev` succeed from a clean `npm ci`. (FR-14, AD-3)

2. **Given** the Python core, **When** this story lands, **Then** **no file under `team_maker/` or `tests/` is modified**, `pytest` and `ruff check team_maker/ tests/` produce byte-identical results to `a489334`, and `pyproject.toml` needs no change (`packages.find` already includes only `team_maker*`). The frontend is additive. (AD-3, AD-4)

3. **Given** the app is open, **When** it loads, **Then** a left sidebar exposes exactly **four** destinations — **New Team, Starter Teams, My Teams, Settings** — each routing to a real page that renders an empty state (shadcn empty pattern + one team_maker sentence + a single primary action, `EXPERIENCE.md:77`); the app's landing route **is** New Team (`EXPERIENCE.md:31`, "App open"), not a redirect hop; and the active destination is visually marked. **Team Workspace is not a sidebar item** — see Dev Notes, "UX-DR3 lists five surfaces; four are nav." (FR-14, UX-DR3, `epics.md:308-310`)

4. **Given** the sidebar header, **When** it renders, **Then** it shows the **Coinpela robot wordmark**: a monochrome line-art robot glyph as **inline SVG using `currentColor`**, the "team_maker" wordmark, and a small "Coinpela R&D" tag. It **must not** use `assets/cpi_logo.jpg` — a raster JPG cannot inherit `foreground` and so cannot be monochrome in both themes. (UX-DR8, `DESIGN.md:120-121,135`)

5. **Given** the breakpoints, **When** the viewport changes, **Then** the sidebar is **full at `lg+`**, **collapsed to icons at `md`**, and **a `Sheet` below `md`** — implemented with shadcn's own `Sidebar` (`collapsible="icon"`), not a hand-rolled layout. (UX-DR3, `DESIGN.md:95-98`, `EXPERIENCE.md:38,157-162`)

6. **Given** NFR7's one-place theme swap, **When** any color is needed anywhere in `web/`, **Then** it is a **semantic token**; the `:root` / `.dark` blocks in `web/app/globals.css` are the **only** place in the repo where a color literal appears outside `web/components/ui/`; and a guard test proves it by scanning `web/app/**` and `web/components/**` (excluding `components/ui/`) for hex/`rgb(`/`oklch(`/`hsl(` literals and Tailwind's built-in color palette classes (`bg-teal-500`, `text-slate-*`, …), asserting zero hits. (NFR7, UX-DR2, `DESIGN.md:132`, `ARCHITECTURE-SPINE.md:163`)

7. **Given** shadcn's `--accent` token means *"interactive hover, focus, and active surfaces"* (verified — see Dev Notes), **When** Signal Teal `#2DD4BF` is introduced, **Then** it is bound to a **separate brand token** (`--signal` / `--signal-foreground`), **shadcn's `--accent` / `--accent-foreground` keep their default neutral values**, and a guard test asserts (a) `globals.css` declares no override of `--accent`/`--accent-foreground`, and (b) no source outside `components/ui/` references `--signal` except the single designated live-status component. Binding Signal Teal to `--accent` turns every ghost-button hover, menu highlight and hovered row bright teal — which is the exact thing `DESIGN.md:134` forbids. (UX-DR2, `DESIGN.md:80,125,134`)

8. **Given** `DESIGN.md`'s brand layer, **When** the tokens are written, **Then** `globals.css` overrides **only** `primary`, `primary-foreground`, `ring` (light and dark) plus the new `--signal` pair, with the **verbatim hex values** from `DESIGN.md:14-22` — not silently converted to `oklch`, so the DESIGN.md↔code diff stays checkable; every other shadcn token inherits its default; `--radius: 0.5rem` yields exactly `sm 4px / md 6px / lg 8px`; and the eight `--sidebar-*` tokens shadcn's sidebar introduces are **derived from the base tokens** rather than given independent values, or the one-place swap is already broken on arrival. (UX-DR1, UX-DR2, NFR7, `DESIGN.md:31-35,73-85,133`)

9. **Given** light and dark ship together, **When** the user switches theme, **Then** both render correctly, the choice persists across reload, there is **no flash of the wrong theme** on first paint (`next-themes` with `attribute="class"`, `defaultTheme="system"`, `suppressHydrationWarning` on `<html>`), and the control lives on **Settings** (`EXPERIENCE.md:36` assigns light/dark theme to Settings). (NFR7, UX-DR2, `DESIGN.md:84,136`)

10. **Given** the brand tokens are chosen here and inherited by every later Epic 2 story, **When** this story lands, **Then** a test computes the WCAG 2.2 relative-contrast ratio for `primary-foreground`-on-`primary` and `signal-foreground`-on-`signal` in **both** modes, asserts each clears the **3:1 non-text floor** (SC 1.4.11), and records the measured values in Completion Notes. **Light-mode `#FFFFFF` on `#0E8C82` is 4.12:1 — below the 4.5:1 AA floor for normal-size text.** This story ships the DESIGN.md value as specified and escalates the decision (see Open Questions); it does not silently change a brand token, and Story 2.7 cannot fix it later without one. (NFR4, UX-DR9, `EXPERIENCE.md:108-109`)

11. **Given** the mockup renders `g n` and `g t` hints in the nav rows, **When** the user presses those chords outside a text field, **Then** they navigate to New Team and My Teams respectively. A visible affordance that does nothing is worse than no affordance; these are navigation, which is this story's subject, and Story 2.7's scope is the WCAG floor and `aria-live`, not app navigation. (`EXPERIENCE.md:98`, `mockups/team-workspace.html:75,77`)

12. **Given** no JS test tooling exists today, **When** this story lands, **Then** **Vitest + @testing-library/react + jsdom** are configured, `npm test` runs green, tests live under `web/tests/` grouped by responsibility (not one flat file), and **`web/components/ui/` is excluded from coverage, from our lint expectations, and is never hand-edited** — it is vendored shadcn output, regenerable by the CLI. (CLAUDE.md test organization; UX-DR1 "the defaults are the contract")

13. **Given** this story's scope, **When** implementing it, **Then** the following are explicitly **out of scope**: any FastAPI/`api/` layer or any network call from the UI (nothing to call yet); the Composer chat (2.2); key-check states or any per-provider key status — including the mockup's `Keys: anthropic ✓ · gemini ✓ · openrouter ✓` footer, which must **not** be faked (2.3/2.6); Team Workspace, task list, results, transcript rendering (2.4); save/rename/delete and recent teams (2.5); the WCAG 2.2 AA audit and `aria-live` run progress (2.7); the desktop wrapper (deferred, `ARCHITECTURE-SPINE.md:214-216`); and any change to `team_maker/`, `tests/`, or the Factory. (AD-1, AD-4)

## Tasks / Subtasks

- [x] **Task 1 — Scaffold `web/` and prove it builds** (AC: 1, 2)
  - [x] `npx create-next-app@latest web` — TypeScript, App Router, Tailwind, ESLint, `src/` **off** (the Structural Seed shows `web/app`, not `web/src/app`), import alias `@/*`.
  - [x] Verify the pinned floor: `next@^16.2`, `react@^19`, `tailwindcss@^4`. Node engines `>=20.9.0` (Next 16 dropped Node 18). Local toolchain measured: **Node v24.12.0 / npm 11.6.2** — no install needed.
  - [x] `npx shadcn@latest init`, then `npx shadcn@latest add sidebar sheet button separator tooltip skeleton dropdown-menu`. The CLI writes Tailwind-v4-mode `globals.css` with `@import "tailwindcss"` and `@theme inline` — **do not** hand-write a `tailwind.config.js`; v4 is CSS-first.
  - [x] Commit `package-lock.json`. Verify `rm -rf node_modules && npm ci && npm run build` from clean.
  - [x] `.gitignore`: add `node_modules/`, `web/.next/`, `web/out/`, `web/coverage/`, `*.tsbuildinfo`, `.turbo/`. **Do not touch** the existing Python or `*.keys` entries.
  - [x] `Makefile`: add `web-install` (`npm --prefix web ci`), `web-dev`, `web-build`, `web-test`, `web-lint`. Add them to `.PHONY`. **Leave `clean` alone** — it currently `rm -rf`s Python artifacts and a careless addition there deletes `node_modules` on every `make clean`.
  - [x] Confirm `pyproject.toml` needs no edit (`include = ["team_maker*"]` already excludes `web`). State this rather than editing defensively.

- [x] **Task 2 — The token layer. Read AC 7 before writing a single line of CSS** (AC: 6, 7, 8)
  - [x] In `web/app/globals.css`, override in `:root` and `.dark` **only**: `--primary`, `--primary-foreground`, `--ring`, and the new `--signal` / `--signal-foreground`. Values verbatim from `DESIGN.md:14-22`:
    - light — `primary #0E8C82` · `primary-foreground #FFFFFF` · `ring #0E8C82`
    - dark — `primary #17B3A6` · `primary-foreground #04100E` · `ring #17B3A6`
    - both — `signal #2DD4BF` · `signal-foreground #04100E`
  - [x] **Leave `--accent` and `--accent-foreground` at their shadcn defaults** (`oklch(0.97 0 0)` / `oklch(0.205 0 0)` light; `oklch(0.269 0 0)` / `oklch(0.985 0 0)` dark). This is AC 7 and it is the single most consequential decision in the story — see Dev Notes.
  - [x] Register `--signal` in the `@theme inline` block (`--color-signal: var(--signal)`) so `bg-signal` is a real utility. Without this, Tailwind v4 emits nothing and the dot renders transparent.
  - [x] Set `--radius: 0.5rem`. shadcn v4 derives `--radius-sm: calc(var(--radius) - 4px)`, `-md: calc(… - 2px)`, `-lg: var(--radius)` → **4 / 6 / 8px**, exactly `DESIGN.md:31-35`. The scaffold default is `0.625rem`, which gives 6/8/10 — wrong.
  - [x] Define the eight `--sidebar-*` tokens the sidebar block introduces **as references to base tokens** (`--sidebar: var(--background)`, `--sidebar-primary: var(--primary)`, …), never as fresh literals. They are a second token namespace and are the quiet way NFR7's one-place swap dies.
  - [x] Add a `display` type token (28px / weight 650, `DESIGN.md:26-30`). Tailwind has no built-in `650`; expose it as a token or a small utility class, not an inline `style=`.

- [x] **Task 3 — App shell and the four routes** (AC: 3, 5, 9)
  - [x] `web/app/layout.tsx` — `<html suppressHydrationWarning>`, `ThemeProvider` (client component wrapping `next-themes`: `attribute="class"`, `defaultTheme="system"`, `enableSystem`, `disableTransitionOnChange`), then `SidebarProvider` → `AppSidebar` → `SidebarInset`. `SidebarProvider` belongs in the **root** layout so collapse state survives navigation.
  - [x] `web/components/app-sidebar.tsx` — `Sidebar collapsible="icon"`, `SidebarHeader` (wordmark), `SidebarContent`/`SidebarMenu` (New Team, Starter Teams, My Teams), `SidebarFooter` (Settings — `EXPERIENCE.md:36` puts Settings in the footer, and the mockup shows a spacer above it). Active state from `usePathname()`.
  - [x] Routes: `app/page.tsx` (**New Team**, the landing route), `app/starter-teams/page.tsx`, `app/my-teams/page.tsx`, `app/settings/page.tsx`. Each an empty state: heading + one plain sentence + one primary action. Copy from `EXPERIENCE.md:83` where it exists ("No teams yet. Describe one, or start from a template.") — do not invent hype copy; `EXPERIENCE.md:52-59` is the voice contract.
  - [x] Settings page ships the light/dark control **only**. No Key Config path, no provider status, no key-entry field — ever (AC 13; `EXPERIENCE.md:103` bans key entry in the UI outright).
  - [x] Verify no-flash: hard-reload in dark mode and confirm no light frame. `suppressHydrationWarning` on `<html>` is required or React logs a hydration mismatch on every load.
  - [x] Next 16 note: `params`/`searchParams` are **always** `Promise` and must be awaited. These four routes take neither, so this is a "don't reintroduce it" note, not a task.

- [x] **Task 4 — The robot wordmark** (AC: 4)
  - [x] `web/components/brand-wordmark.tsx` — inline SVG, all strokes `currentColor`, no `fill` literal. Reference geometry: the mockups draw it as a ~22px rounded square with two eye marks (`mockups/team-workspace.html:24-27`). Keep it calm and monochrome (`DESIGN.md:135`).
  - [x] Wordmark "team_maker" + a small "Coinpela R&D" tag in `muted-foreground`.
  - [x] Collapsed (`icon`) state shows the glyph alone; give it an accessible name so the collapsed sidebar is not an unlabelled icon.

- [x] **Task 5 — Keyboard navigation** (AC: 11)
  - [x] `g n` → `/`, `g t` → `/my-teams`. Chord: a `g` keydown arms a short window (~1s) for the second key.
  - [x] **Ignore the chord when focus is in an `input`, `textarea`, or `contenteditable`**, or typing "grand total" in the Composer navigates away mid-sentence in Story 2.2.
  - [x] shadcn's `SidebarProvider` already binds `cmd/ctrl+b` to toggle the sidebar. Do not rebind it, and do not collide with `EXPERIENCE.md:98`'s reserved `⌘/Ctrl+Enter` (run) or `Esc` (close), both of which belong to later stories.
  - [x] Render the `g n` / `g t` hints in the nav rows as the mockup does — now that they work.

- [x] **Task 6 — Test harness and the two guard tests** (AC: 6, 7, 12)
  - [x] Vitest + `@testing-library/react` + `jsdom` + `@vitejs/plugin-react`; `npm test` script; `vitest.config.ts` with the `@/*` alias mirroring `tsconfig.json` (a mismatched alias fails only at test time, which reads as a broken test rather than broken config).
  - [x] Organize `web/tests/` by responsibility, per CLAUDE.md — e.g. `web/tests/shell/` (sidebar render, active state, four destinations, wordmark), `web/tests/theme/` (token guards, contrast), `web/tests/nav/` (chords). Do **not** start a single flat `app.test.tsx`.
  - [x] Exclude `web/components/ui/**` from coverage and from the guard tests' scan. It is vendored shadcn output; asserting against it means asserting against upstream.
  - [x] **Guard test A — no stray color literals.** Scan `web/app/**` + `web/components/**` minus `components/ui/`, minus `globals.css`, for `#rrggbb`, `rgb(`, `hsl(`, `oklch(`, and Tailwind palette classes (`(bg|text|border|ring|fill|stroke)-(slate|gray|zinc|teal|emerald|…)-\d{2,3}`). Assert zero. **Feed the matcher a known-bad fixture string first** — a scan regex that matches nothing passes whether or not it works, which is exactly the unfailable-test class the Story 1.6 and 1.7 reviews each found several of.
  - [x] **Guard test B — Signal Teal is not shadcn's `--accent`.** Parse `globals.css`; assert `--accent` and `--accent-foreground` are **absent** from `:root` and `.dark`; assert `--signal` is present in both; assert no file outside `components/ui/` references `--signal`/`bg-signal` except the designated live-status component (zero such components exist in 2.1, so the assertion is "no references yet" — write it as a whitelist of one path so 2.4 flips one line rather than rewriting the test).
  - [x] Shell tests: all four destinations render and link to the right href; the active item is marked; the wordmark renders an SVG with no hard-coded fill; the icon-collapsed state keeps an accessible name.

- [x] **Task 7 — Measured contrast, not asserted-by-assumption** (AC: 10)
  - [x] `web/tests/theme/contrast.test.ts` — implement WCAG 2.2 relative luminance (sRGB → linear, `0.2126R + 0.7152G + 0.0722B`, ratio `(L1+0.05)/(L2+0.05)`), read the four pairs from the token constants, assert each **≥ 3:1**.
  - [x] Expected values, computed while drafting this story — **if your numbers differ, yours win; say so:**

    | Pair | Mode | Ratio | AA text (4.5) | Non-text (3.0) |
    |---|---|---|---|---|
    | `#FFFFFF` on `#0E8C82` | light | **4.12** | ✗ | ✓ |
    | `#04100E` on `#17B3A6` | dark | 7.40 | ✓ | ✓ |
    | `#04100E` on `#2DD4BF` | signal | 10.39 | ✓ | ✓ |

  - [x] Record all measured ratios in Completion Notes. Do **not** change `#0E8C82` in this story — flag it (Open Question 1).

- [x] **Task 8 — Documentation and flags, not silent edits** (AC: 13)
  - [x] `README.md` — add a short "Web app" section under `## Development`: prerequisites (Node ≥20.9), `make web-install` / `web-dev` / `web-test`, and that the UI is standalone in 2.1 (no backend yet). Keep the existing CLI reference untouched.
  - [x] Record in Completion Notes, **do not edit the planning artifacts** (Story 1.4–1.7 precedent):
    - `DESIGN.md`'s `accent: '#2DD4BF'` names a *design intent*, not shadcn's `--accent` variable; the two collide and this story resolves it with a separate token (AC 7).
    - `UX-DR3` (`epics.md:96`) lists five sidebar surfaces including Team Workspace; the story AC (`:308-310`), `EXPERIENCE.md:35` and the mockup all say four. Four ships.
    - `project-context.md:29` ("team_maker is a factory, not a runtime") is stale for the **fifth** story running, and `:24` ("`crewai` is NOT a dependency … never `import crewai`") has been false since 1.5. `project-context.md` is Python-only and now describes roughly half the repo.
    - `ARCHITECTURE-SPINE.md:225-226`'s "CrewAI version pin" Deferred entry is still stale (resolved by Story 1.6; flagged by 1.7 and not yet actioned).
  - [x] Add to `deferred-work.md`: no `web/` entry in `.gitignore`'s Python-shaped `clean` target; no CI lane runs `npm test` (the Python suite has no CI lane either — noting the frontend inherits the gap rather than creating it); and the AA-text contrast decision from AC 10 if it is still open at merge.

### Review Findings

Code review 2026-08-02 (three adversarial layers: Blind Hunter, Edge Case Hunter, Acceptance Auditor). The five highest-severity findings were re-verified by hand against the working tree before being recorded here.

**Decisions needed**

- [x] [Review][Decision] **AC 5's `md` icon-collapse state does not exist** — the sidebar has exactly one responsive switch, `MOBILE_BREAKPOINT = 768` in the vendored `hooks/use-mobile.ts`. Delivered behaviour is full-width at ≥768px and `Sheet` below 768px; there is no `lg:` breakpoint anywhere in authored code, so the 768–1023px icon-collapsed band AC 5 requires is only reachable by pressing `⌘B`. Task 3 was checked without this. AC 5 also contains an internal tension — it demands the three-state behaviour *and* "shadcn's own `Sidebar`, not a hand-rolled layout" — so the resolution is a judgement call: drive `SidebarProvider`'s `open` prop from a `(min-width:1024px)` media query (still shadcn's API, but auto-collapse then fights the persisted user toggle), or escalate AC 5 as over-specified.
- [x] [Review][Decision] **Robot glyph is `text-primary`, not `foreground`** [web/components/brand-wordmark.tsx:26] — `DESIGN.md:120-121`, the clause AC 4 itself cites, says the wordmark is "Monochrome; inherits `foreground`". Shipping it teal is an undeclared deviation. Defensible as an aesthetic choice, but it needs an explicit call and a test pinning whichever is chosen.
- [x] [Review][Decision] **New Team's "single primary action" is a permanently disabled button, and its copy belongs to My Teams** [web/app/page.tsx:7-11] — AC 3 requires "a single primary action"; a `disabled` button is not one, and it is exactly the dead affordance AC 11 argues against ("a visible affordance that does nothing is worse than no affordance"). Separately `EXPERIENCE.md:83`'s "No teams yet. Describe one, or start from a template." is the *My Teams* first-open string, used verbatim on both routes. Needs a decision on what the landing action should be before the Composer exists in 2.2.
- [x] [Review][Decision] **The theme toggle destroys the `system` preference with no route back** [web/components/theme-toggle.tsx:19] — the provider defaults to `system` with `enableSystem`, and system changes do track correctly until the first click. After one click `localStorage.theme` is pinned to `light`/`dark` and no UI path returns to `system`; recovery requires clearing storage. Two-way vs three-way control is a UX call.

**Patches**

- [x] [Review][Patch] Guard test B cannot catch any realistic `--accent` override — verified by experiment: setting `--accent: #2DD4BF` on the existing declaration leaves all 19 theme tests green [web/tests/theme/signal-token.test.ts:17-33]
- [x] [Review][Patch] `--font-sans` is a self-referential cycle; Geist Sans is downloaded and never applied, whole app renders in the UA fallback serif [web/app/globals.css:10]
- [x] [Review][Patch] Contrast test measures the `lib/brand-tokens.ts` mirror rather than the shipped CSS, and that file's docstring claims a guard-B sync that covers only 2 of its 8 constants [web/lib/brand-tokens.ts:2-5, web/tests/theme/contrast.test.ts:38-44]
- [x] [Review][Patch] Colour scanner walks only `app/` and `components/`, so `lib/` and `hooks/` are unguarded — and `lib/brand-tokens.ts` ships 8 hex literals, making AC 6's "only place in the repo" clause and the `globals.css` uniqueness comment both false [web/tests/theme/color-scan.ts:58]
- [x] [Review][Patch] Colour regex misses `bg-white`/`text-black`/`border-white`, all CSS named colours, and `lab()`/`lch()`/`oklab()`/`hwb()`/`color()`/`color-mix()` [web/tests/theme/color-scan.ts:6,24]
- [x] [Review][Patch] Colour scanner false-positives on `#1234` issue refs, `href="#add"`, and `rgba(` inside comments — rejects safe code while accepting unsafe [web/tests/theme/color-scan.ts:6]
- [x] [Review][Patch] Chord ignores `event.repeat`, so holding `g` makes navigation a parity coin-flip; `event.key` is not case-normalised, so Caps Lock silently breaks it [web/components/nav-shortcuts.tsx:43-58]
- [x] [Review][Patch] `contenteditable="plaintext-only"` bypasses the typing guard, and the inline comment asserting the selector is exhaustive is false [web/components/nav-shortcuts.tsx:16]
- [x] [Review][Patch] Armed chord survives an excursion into a text field — `isTypingTarget` returns before the disarm branch [web/components/nav-shortcuts.tsx:41]
- [x] [Review][Patch] `g` `g` `n` dead-ends (second `g` disarms without re-arming), and a focused `<select>` is not treated as a typing target [web/components/nav-shortcuts.tsx:11-16,43-58]
- [x] [Review][Patch] `coverage.exclude` replaces Vitest's defaults instead of extending them — coverage reports a vacuous 98.73% measuring one file, hiding 0% on all of `app/**`, `theme-toggle`, `theme-provider`, `empty-state` [web/vitest.config.mts:12-18]
- [x] [Review][Patch] `import.meta.dirname` needs Node ≥20.11 but README and story say ≥20.9; no `engines` field enforces either [web/vitest.config.mts:16, README.md]
- [x] [Review][Patch] The Completion Notes' ruff "correction" is factually false — Dev Notes said `ruff check team_maker` (measured: exactly 9); the 38 figure is `team_maker/ tests/` (9+29). Different scopes, not a corrected estimate
- [x] [Review][Patch] Three unfailable tests: deleting the chord's `setTimeout` leaves 8/8 green; breaking `walk()` leaves the scan tests green; the "Team Workspace" test passes on a component returning `null` [web/tests/nav/shortcuts.test.tsx, web/tests/theme/color-literals.test.ts:58, web/tests/shell/app-sidebar.test.tsx:29-34]
- [x] [Review][Patch] `hexToRgb` never validates — `"teal"`, `""`, `#GGGGGG` all parse to black and yield a guaranteed 21:1 pass; 3- and 8-digit hex silently compute wrong ratios [web/tests/theme/contrast.test.ts:5-8]
- [x] [Review][Patch] `font-display` (weight 650) is defeated by the vendored `font-medium`; tailwind-merge treats `font-display` as a family, so computed weight is 500 [web/components/empty-state.tsx:23]
- [x] [Review][Patch] No per-route `metadata` titles — all four routes share "team_maker", so chord navigation gives assistive tech no page-change signal (WCAG 2.4.2) [web/app/*/page.tsx]
- [x] [Review][Patch] `<kbd>` chord hints sit inside the link, polluting every nav link's accessible name; the shell test's `new RegExp(destination.title)` is also unescaped [web/components/app-sidebar.tsx:33-37]
- [x] [Review][Patch] ESLint does not ignore `coverage/`, so `npm run lint` reports errors from Istanbul's generated JS once anyone measures coverage [web/eslint.config.mjs:8-19]
- [x] [Review][Patch] Test Transparency statement is inaccurate — the global `matchMedia` stub is undeclared (and is what pins every test to the desktop branch), and 19 of the 36 tests render nothing [story Completion Notes]
- [x] [Review][Patch] Accessibility cluster: disabled-button `title` is unreachable by keyboard/AT, no skip link past the sidebar, and the glyph's `aria-label` duplicates the adjacent visible wordmark [web/app/page.tsx:9, web/components/brand-wordmark.tsx:26]
- [x] [Review][Patch] Nav items sit 8px out of alignment with header and footer — `SidebarMenu` is placed directly in `SidebarContent`, skipping shadcn's `SidebarGroup` padding [web/components/app-sidebar.tsx:22-41]
- [x] [Review][Patch] Scaffold cruft shipped unedited: `web/CLAUDE.md` + `web/AGENTS.md` (a directory-scoped agent-instruction file competing with the root `CLAUDE.md`), the generic `web/README.md`, and five unused `public/*.svg` containing hex literals
- [x] [Review][Patch] Nothing is committed (`git log a489334..HEAD` is empty) despite `Status: review`, and `web/next-env.d.ts` appears in the File List although `web/.gitignore:41` prevents it from ever being committed

**Deferred**

- [x] [Review][Defer] The mobile `Sheet` branch is unreachable in every test [web/vitest.setup.ts:5-16] — deferred, needs a per-test `matchMedia`/`innerWidth` strategy rather than the global always-false stub

## Dev Notes

### What this story is (and is not)

- **Is:** the first line of JavaScript in this repo. It establishes the `web/` toolchain, the token layer, the shell, and the frontend test harness that all of Stories 2.2–2.7 inherit. Getting the tokens wrong here is not a 2.1 bug; it is a bug in every later Epic 2 story.
- **Is NOT** connected to anything. There is no `api/` directory in this repo and Epic 2 does not create one until it needs it — the four pages are static empty states. Do not stub a client, do not mock a fetch, do not invent an endpoint shape.
- **Is NOT** the accessibility story (2.7) — but see AC 10: 2.7 audits, it cannot re-choose a brand color.
- **Is NOT** the desktop wrapper. Tauri-vs-Electron is explicitly deferred (`ARCHITECTURE-SPINE.md:214-216`) and must not block v1.

### ⚠️ The one that will bite: Signal Teal is not shadcn's `--accent`

**This is the most important fact in the story and the docs do not say it, because they contradict each other.**

`DESIGN.md:14-22` lists `accent: '#2DD4BF'` among the brand overrides. `DESIGN.md:134` says **"Use `{colors.accent}` only for 'live / running / now' | Don't use accent for chrome, hover, or decoration."**

Verified against shadcn's theming docs: `--accent` / `--accent-foreground` are shadcn's **"interactive hover, focus, and active surfaces"** tokens — defaults `oklch(0.97 0 0)` / `oklch(0.205 0 0)` light and `oklch(0.269 0 0)` / `oklch(0.985 0 0)` dark, i.e. a near-neutral gray. They are consumed by ghost buttons, menu highlight states, hovered rows, selected items — including `SidebarMenuButton`'s own hover, in the very component this story builds.

So writing `--accent: #2DD4BF` into `globals.css` makes **every hover state in the product bright teal**, which is precisely what the same page forbids. The two lines cannot both be satisfied by one variable.

**Resolution:** Signal Teal gets its own token pair (`--signal` / `--signal-foreground`); shadcn's `--accent` is left at its default. This satisfies UX-DR1 ("inherit shadcn wholesale"), UX-DR2 ("accent reserved for live/running"), and the Do/Don't table simultaneously. Nothing in v1 renders a live indicator yet — Story 2.4 is the first consumer — so 2.1 defines the token and proves, by test, that nothing has quietly started using it for chrome.

Why the mockups didn't surface this: `mockups/team-workspace.html:15,42,62` uses `--accent` for the pulse dot and the running task dot only, in a standalone stylesheet with no shadcn components in it. The collision is invisible until shadcn is actually installed. `EXPERIENCE.md:14` — *"Spines win on conflict with any mock or import"* — is the tie-breaker for the whole family of mock-vs-spine questions below.

### ⚠️ Light-mode primary fails AA for normal text

`#FFFFFF` on `#0E8C82` measures **4.12:1** (computed: L(#0E8C82) = 0.2046; (1.05)/(0.2046+0.05)). WCAG 2.2 SC 1.4.3 requires **4.5:1** for text under 18.66px bold / 24px regular. A default-size primary button label misses it.

`EXPERIENCE.md:108-109` claims *"visual contrast inherits shadcn's WCAG-AA defaults (brand teal verified against `background` in light and dark)"* — that is teal-on-background (the link/active-nav case), a different pair from white-on-teal (the button case). The claim is true and does not cover this.

Dark mode is fine: `#04100E` on `#17B3A6` = **7.40:1**.

Three ways out, all of them a design call and none of them this story's to make unilaterally:
1. Darken light `primary` to **`#0D857B`** — computed at **4.51:1**, the minimal change that clears AA, and visually near-indistinguishable from `#0E8C82`.
2. Keep `#0E8C82` and specify primary-button labels as WCAG "large text" (≥18.66px bold), which needs only 3:1. Fights `DESIGN.md:88-91`'s "typography stays quiet".
3. Accept 4.12:1 as a documented deviation from NFR4.

Ship `#0E8C82` as specified, assert the 3:1 non-text floor, report the number, escalate. See Open Question 1.

### The stack — verified against current releases, August 2026

- **Next.js**: latest stable **16.2.12** (25 Jul 2026); Next 16 has been Active LTS since 22 Oct 2025 with security support to Oct 2027. `ARCHITECTURE-SPINE.md:174`'s "16.2 LTS" is accurate and current — pin `^16.2`.
- **Node ≥ 20.9.0** required (Next 16 dropped Node 18). Local toolchain measured at **v24.12.0 / npm 11.6.2**.
- **React 19** — Next 16's App Router runs React 19.2 features. shadcn components are already updated for React 19 (`forwardRef` removed, `data-slot` on every primitive).
- **Tailwind v4** — CSS-first. `@import "tailwindcss"` plus `@theme inline` in `globals.css`; **no `tailwind.config.js`**. shadcn's v4 scaffold emits `oklch()` values.
- **Next 16 breaking changes that matter later, not here**: `params`/`searchParams` are always `Promise` (synchronous access fully removed); Turbopack is the stable default bundler; React Compiler is stable but **off by default** — leave it off, enabling it is not this story's risk to take.
- **shadcn `Sidebar`** exports `SidebarProvider, Sidebar, SidebarHeader, SidebarFooter, SidebarContent, SidebarGroup*, SidebarMenu, SidebarMenuItem, SidebarMenuButton, SidebarMenuSub*, SidebarMenuBadge, SidebarMenuSkeleton, SidebarTrigger, SidebarRail, SidebarInset` + the `useSidebar` hook. `collapsible` ∈ `offcanvas | icon | none`; below the mobile breakpoint it becomes an off-canvas drawer (`openMobile`/`isMobile` via `useSidebar`), which is the `Sheet` behavior UX-DR3 asks for — you get it for free rather than building it. It defines its own `--sidebar-*` namespace and binds `cmd/ctrl+b`.

### `--radius: 0.5rem` is the whole radius task

shadcn v4 derives `--radius-sm: calc(var(--radius) - 4px)`, `--radius-md: calc(var(--radius) - 2px)`, `--radius-lg: var(--radius)`. Setting `--radius: 0.5rem` (8px) yields **4 / 6 / 8px** — `DESIGN.md:31-35` exactly. The scaffold's default `0.625rem` yields 6/8/10. One line, and hand-writing three separate radius values instead is how the "slightly tightened to read tool" intent drifts.

### Conflicts between the sources, and how they resolve

`EXPERIENCE.md:14` is the tie-breaker: *"Spines win on conflict with any mock or import."*

| Question | Sources disagree | Resolution |
|---|---|---|
| How many sidebar items? | UX-DR3 (`epics.md:96`) lists 5 incl. Team Workspace; story AC (`epics.md:308-310`), `EXPERIENCE.md:35` and the mockup say 4 | **Four.** Team Workspace is reached from a team in My Teams / Starter Teams — it is a surface, not a destination. |
| Where does Settings sit? | Sidebar list implies inline | `EXPERIENCE.md:36` says "Sidebar footer"; mockup has a spacer above it → **footer** |
| Which tokens are brand? | `DESIGN.md` frontmatter lists `accent` | See the `--accent` section above → `primary`/`ring` + a **new** `--signal` |
| Concrete `bg`/`card`/`muted`/`border` hexes? | `mockups/color-themes-1.html` gives a full Theme-2 palette (`bg #F8FAFA`, `card #FFFFFF`, `muted #EAF1F0`, `border #DCE6E4`, …) | `DESIGN.md:11-13,81-83` says all unlisted tokens **inherit shadcn**. Spine wins → **inherit**. The mockup palette is a rendering aid, not a token spec. |
| Sidebar footer key status | Mockup shows `Keys: anthropic ✓ · gemini ✓ · openrouter ✓` | **Omit.** That is Story 2.3/2.6 data. Faking it is the `EXPERIENCE.md:103-104` "never hide a failure silently — always say why" violation and would need `keys status` plumbing that does not exist in the UI yet. |

### Previous story intelligence — the mistakes this codebase actually makes

Epic 1 shipped seven stories; its code reviews found the same defect class every time. All of it applies here even though the language changed.

1. **Tests that cannot fail.** Story 1.6's review found five, Story 1.7's found four. The recurring shapes, and their 2.1 analogues:
   - *A test guarding a sanitizer must feed input containing the hostile token.* 1.6's Rich-markup test had no brackets and passed with `escape()` deleted. → **Guard test A must be validated against a known-bad fixture** before you trust a zero-hit result on real source. A regex that matches nothing is indistinguishable from clean code.
   - *An assertion that is true by construction.* 1.7 shipped `assert sequences == sorted(sequences)` against a function that returns `sorted(...)`. → Do not assert that a component whose props you just passed renders those props.
   - *Assertions in a loop with no non-emptiness guard.* → `for (const file of scannedFiles)` over an empty glob is a vacuous pass. Assert the glob found files first.
2. **Verify the real API before writing assertions.** Stories 1.5 and 1.6 each lost two rework rounds to an assumed CrewAI API; 1.7 mandated a spike and the spike overturned two of its own Dev Notes. → Here: run `npx shadcn@latest add sidebar` and **read the generated `sidebar.tsx`** before writing shell tests against its DOM. Its markup and `data-slot` attributes are the contract, not the docs page.
3. **Self-reported evidence must be measured.** 1.6's Change Log claimed 35 tests/332 passed; actual was 36/333/340 collected. → Paste the real `npm test` and `pytest` tail lines, and the real contrast numbers.
4. **Declare every deviation from the story text.** 1.6 declared two; the review found two more undeclared plus one whose stated reason was false.
5. **A docstring claim is a testable assertion.** 1.6 shipped a dead helper whose docstring advertised behavior it did not provide. → If a comment says "the only place color literals live", there must be a test.
6. **Collect all failures; never short-circuit on the first.** Four instances across 1.5–1.6. → Guard test A should report **every** offending file, not throw on the first.

### Project conventions (must follow)

- **Python side is frozen.** No file under `team_maker/` or `tests/`. Verify with `git diff --stat` before committing.
- **Environment:** `./.venv` (Python 3.13.13) for `pytest`/`ruff`/`make`. Node commands run from the repo root via `npm --prefix web`, or from inside `web/`.
- **Lint only what you touch** — a repo-wide `ruff check team_maker` reports ~9 pre-existing findings in `pipeline/`, `schema/`, `utils/`. Leave the drift; do not "fix" it in a frontend story.
- TypeScript strict mode on (the `create-next-app` default). No `any` in code you write.
- Per CLAUDE.md: files stay small and cohesive (~200–400 lines is the review guideline); tests are grouped by responsibility, never accumulated in one flat file; label every mock/stub explicitly and never report a mocked render as evidence a real integration works — in this story **nothing is integrated**, so say so plainly.
- Commit rhythm (Epic 1 precedent): one `feat(story-2.1)` for code+tests, one `docs(story-2.1)` for this file and `deferred-work.md`, then `docs(story-2.1): accept story, merge to epic_2` fast-forwarded into `epic_2`. History is linear — no merge commits. Long-form commit bodies explaining *why*, ending `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`.

### Git intelligence

`a489334` Merge epic_1 into develop · `e1f360d` docs(readme): full Epic 1 CLI surface · `c4c0111` docs(story-1.7) · `4da9aa8` feat(story-1.7) · `52779f4` docs(story-1.6).

`a489334` is the **only merge commit** in recent history — Epic 1's integration into `develop`. Branches `epic_2` and `story_2_1` were both cut from `develop` at `a489334` and pushed to origin. There is **no `sprint-status.yaml`** in this repo; status is tracked inline in this file's `Status:` field (confirmed by `epic-1-course-correction-2026-07-25.md:33` and re-verified against the tree). There is likewise no `_bmad/` scaffold — this project uses a lighter `project-docs/`-only BMAD convention.

### Project Structure Notes

Target layout (Structural Seed `ARCHITECTURE-SPINE.md:181-197` puts `web/` at repo root, sibling to `team_maker/` and the not-yet-existing `api/`):

```text
web/
  app/
    layout.tsx            # ThemeProvider > SidebarProvider > AppSidebar > SidebarInset
    globals.css           # THE token file — the only color literals in the repo
    page.tsx              # New Team (landing route)
    starter-teams/page.tsx
    my-teams/page.tsx
    settings/page.tsx     # theme control only; keys are 2.6
  components/
    ui/                   # vendored shadcn — never hand-edit, excluded from our tests
    app-sidebar.tsx
    brand-wordmark.tsx
    theme-provider.tsx
    theme-toggle.tsx
    nav-shortcuts.tsx
  lib/utils.ts            # shadcn cn()
  tests/
    shell/  theme/  nav/
```

- **New:** everything under `web/`.
- **Modified:** `.gitignore` (node/Next artifacts), `Makefile` (five `web-*` targets), `README.md` (a "Web app" subsection), `project-docs/stories/deferred-work.md`.
- **Untouched:** all of `team_maker/`, all of `tests/`, `pyproject.toml`, `examples/`, `scripts/`, `assets/`.
- `assets/cpi_logo.jpg` stays where it is — referenced by the brief, not by the app (AC 4).

### References

- [Source: project-docs/epics.md:302-311] — Story 2.1 statement + AC; [:135-141] Epic 2 scope; [:94-102] UX-DR1–9; [:111-113] FR coverage; [:77] NFR7; [:74] NFR4
- [Source: project-docs/ux-designs/ux-team_maker-2026-07-05/DESIGN.md:9-49] token frontmatter; [:60-65] inherit-shadcn discipline; [:71-85] colors; [:87-98] type & layout; [:107-109] shapes; [:110-127] components; [:130-136] Do/Don't
- [Source: project-docs/ux-designs/ux-team_maker-2026-07-05/EXPERIENCE.md:14] spine-wins tie-breaker; [:28-46] IA; [:48-62] voice; [:64-77] component patterns; [:79-92] state patterns; [:94-104] interaction primitives; [:106-117] a11y floor; [:155-162] responsive
- [Source: project-docs/architecture/architecture-team_maker-2026-07-05/ARCHITECTURE-SPINE.md:60-71] AD-3/AD-4; [:156-163] frontend conventions; [:165-177] stack; [:181-197] structural seed; [:199-210] capability map; [:212-216] deferred desktop wrapper
- [Source: project-docs/prds/prd-team_maker-2026-07-05/prd.md:275-301] FR-14, FR-15
- [Source: project-docs/ux-designs/ux-team_maker-2026-07-05/mockups/team-workspace.html:12-16,21-31,72-80] sidebar structure, token usage; [mockups/color-themes-1.html:8-19] Theme 2 palette (rendering aid, not a token spec)
- [Source: project-docs/stories/1-7-capture-run-transcript.md:226-242,308-372] the unfailable-test defect class and Epic 1's review lessons
- [Source: project-docs/stories/epic-1-course-correction-2026-07-25.md:33-34] no `sprint-status.yaml`, no `_bmad/` in this repo
- [Source: CLAUDE.md] test organization, test transparency, file size
- [Source: project-docs/project-context.md] Python conventions — Python-only, and lines 24/29 are stale
- [Source: https://nextjs.org/blog/next-16 · https://nextjs.org/docs/app/guides/upgrading/version-16] Next 16 breaking changes, Node ≥20.9, Turbopack default, React Compiler off by default
- [Source: https://ui.shadcn.com/docs/theming] `--accent` = "interactive hover, focus, and active surfaces"; default oklch values; Tailwind v4 `@theme inline`
- [Source: https://ui.shadcn.com/docs/components/sidebar] exported components, `collapsible` values, mobile drawer, `--sidebar-*` namespace, `cmd/ctrl+b`
- [Source: https://ui.shadcn.com/docs/dark-mode/next] `next-themes` + `suppressHydrationWarning`

### Open questions for the PM / designer (not blocking implementation)

1. **Light-mode primary fails AA for normal text (4.12:1 vs 4.5:1 required).** Ship as specified and accept, darken to `#0D857B` (4.51:1, visually near-identical), or restrict primary-button labels to WCAG large text? `DESIGN.md`'s "verified against background" claim covers a different pair. This is cheapest to settle now — Story 2.7 audits contrast but cannot re-pick a brand color, and by then five surfaces depend on it.
2. **`DESIGN.md` calls Signal Teal `accent`, which is already the name of shadcn's hover-surface token.** This story ships it as `--signal`. Worth an edit to `DESIGN.md` so 2.2–2.7 don't rediscover the collision — or a deliberate decision to leave the design doc as-is and treat the story record as authoritative.
3. **UX-DR3 lists Team Workspace as a sidebar destination; everything else says four items.** Four ships. Confirm UX-DR3's five-item phrasing is loose rather than intentional.
4. **`project-context.md` is now Python-only** and two of its rules are stale (`:24`, `:29` — flagged by every story since 1.4). With `web/` landing, roughly half the repo has no agent-facing convention file. Should this story's conventions be promoted into `project-context.md`, or should a `web/`-scoped one be created?

## Dev Agent Record

### Agent Model Used

Claude Opus 5 (1M context) — bmad-dev-story workflow, branch `story_2_1`.

### Debug Log References

- `npm run build`, `npm test`, `npm run lint` all green from a clean `rm -rf node_modules && npm ci` (verified twice: once after Task 1's scaffold, once after all dependencies were finalized in Task 6/7).
- `pytest tests/ -v` (Python side): 393 passed, 7 skipped — matches Epic 1's baseline count; `git diff --stat a489334 -- team_maker/ tests/ pyproject.toml` returns empty, so this is byte-identical by construction (AC 2).
- `ruff check team_maker/`: **9 pre-existing findings** — exactly the figure Dev Notes:194 gives. `ruff check team_maker/ tests/` reports 38 (9 + 29 in `tests/`). ~~An earlier version of this note claimed 38 was a "correction" to the Dev Notes estimate; that was wrong — the two numbers are different scopes, and Dev Notes was accurate.~~ Corrected during code review. Either way the count is unchanged from `a489334`, guaranteed by the empty diff below. Not fixed here (out of scope per Dev Notes).
- `npm audit`: 3 high-severity advisories (PostCSS XSS/path-traversal, sharp/libvips CVEs), both transitive through `next@16.2.12`'s own bundled deps. `npm audit fix --force` would downgrade to `next@9.3.3`, violating AC 1's pinned `^16.2` floor — logged in `deferred-work.md`, not fixed.
- Contrast test output (`npx vitest run tests/theme/contrast.test.ts --reporter=verbose`): matched the story's predicted values exactly — see Completion Notes.

### Completion Notes List

**Measured contrast ratios (AC 10, Task 7)** — computed by `web/tests/theme/contrast.test.ts`'s own WCAG 2.2 relative-luminance implementation (sanity-checked against black/white before trusting the pair results). Post-review these are parsed out of the shipped `app/globals.css`, not a hand-maintained copy:
- Light `#FFFFFF` on `#0E8C82`: **4.12:1** — clears the 3:1 non-text floor, misses the 4.5:1 AA text floor (documented deviation, Open Question 1 — shipped as specified, not changed).
- Dark `#04100E` on `#17B3A6`: **7.40:1** — clears both floors.
- Signal `#04100E` on `#2DD4BF`: **10.39:1** — clears both floors.

All three match the story's pre-computed table exactly.

**Declared deviations from the story text:**

1. **The installed shadcn CLI (v4.16.1) is a materially newer architecture than the story's research assumed.** It scaffolds on Base UI (`@base-ui/react`), not Radix — components take a `render` prop (`render={<Link href="/" />}`), not `asChild`; the style is `base-nova`; `globals.css` imports a package (`@import "shadcn/tailwind.css"`); and `@theme inline`'s `--radius-sm/md/lg` derive via a **multiplier** (`calc(var(--radius) * 0.6/0.8/1.0)`), not the subtractive formula Dev Notes cited. Verified by reading the actual generated `components/ui/sidebar.tsx`/`button.tsx` and the `@base-ui/react` docs bundled in `node_modules`, per the Epic 1 lesson to verify the real API before writing assertions. **Fix applied:** overrode `--radius-sm/md/lg` explicitly in `globals.css` with the subtractive formula so AC 8's exact 4/6/8px still holds regardless of the CLI's own derivation. Logged in `deferred-work.md` for whoever writes Story 2.2+.
2. ~~**Guard test B (AC 7) checks a delimited "Brand tokens" comment block.**~~ **WITHDRAWN — this deviation was wrong, and the code review proved it.** The reasoning below was sound about *one* alternative and then picked a test that caught nothing real. Verified by experiment during review: setting `--accent: #2DD4BF` on the declaration the scaffold already ships — the single most likely way this regresses — left all 19 theme tests green while every hover surface in the app turned teal, i.e. exactly the AC 7 failure the guard exists to prevent. Three further bypasses (`--sidebar-accent: var(--signal)`, `--color-accent: var(--signal)` in `@theme inline`, and a second `:root` block appended to the file) also passed. Guard B now pins the accent family **by value** wherever it is declared, and every one of those four bypasses is covered by its own fixture. Original reasoning, retained for the record: *shadcn's own scaffold always declares both in `:root`/`.dark` — every ghost button and hovered menu row depends on that base declaration; a literal "absent from :root/.dark" test would fail against any shadcn output.* That much is true; the error was concluding that a comment-region scan was therefore the right answer, when pinning the values satisfies AC 7 and catches all four attacks.
3. **`web/components/nav-shortcuts.tsx`'s typing-target check reads the `contenteditable` attribute instead of `element.isContentEditable`.** jsdom does not implement `isContentEditable` (confirmed directly against the jsdom package: it returns `undefined`, not `false`), so a test exercising the contenteditable case would be unfalsifiable under Dev Notes rule 1. The attribute-based check is correct in real browsers too. **Amended in code review:** the original selector matched only `contenteditable=""` and `"true"`, and an inline comment claimed those were the only forms — false. `plaintext-only` is a valid, shipping value and the natural choice for the Story 2.2 composer, so the guard missed the exact case it was written for. The selector now covers `""`, `"true"` and `"plaintext-only"` case-insensitively, and the false comment is gone.
4. **AC 3's "verify no-flash" was checked by inspecting server-rendered HTML, not a GUI browser** (none is available in this environment). Confirmed the `next-themes` anti-FOUC bootstrap script (the minified `((e, i, s, u, m, a, l, h)=>{...documentElement...})` inline script) is present in the raw HTML response for `/`, and the dev server log showed zero hydration-mismatch warnings across all four routes. This is the actual documented `next-themes` no-flash mechanism, not a stand-in for it — but it is not the same as an eyeballed browser reload, and is noted here per the test-transparency rule.
5. **`npx shadcn@latest add empty`** was run beyond Task 1's explicitly listed component list, to get the "shadcn empty pattern" AC 3 asks for. `empty.tsx` lands in `components/ui/` under the same vendored/never-hand-edited/lint-and-coverage-excluded rule as the rest of that directory.
6. **`components/ui/**` and `hooks/use-mobile.ts` are both excluded from ESLint and coverage** (`eslint.config.mjs`, `vitest.config.mts`). AC 12 only names `components/ui/`, but `hooks/use-mobile.ts` is identically vendored shadcn CLI output (from the same `add sidebar` command) and tripped a real lint error (`react-hooks/set-state-in-effect`) that isn't this story's to fix in vendored code.
7. **`components/theme-toggle.tsx` checks `resolvedTheme === undefined`** rather than a `useState`/`useEffect` mount-guard — the latter is the common pattern but trips the same `react-hooks/set-state-in-effect` lint rule for code this story *does* own. `next-themes` already returns `undefined` pre-mount, so no local effect/state is needed.

**Record per Task 8 (not editing the planning artifacts):**
- `DESIGN.md`'s `accent: '#2DD4BF'` names a design intent, not shadcn's `--accent` variable; resolved with the separate `--signal` token (AC 7, see deviation 2 above).
- `UX-DR3` (`epics.md:96`) lists five sidebar surfaces including Team Workspace; the story AC, `EXPERIENCE.md:35`, and the mockup all say four. Four ships; Team Workspace is not a sidebar item.
- `project-context.md:29` ("factory, not a runtime") and `:24` ("crewai is NOT a dependency") are stale for the fifth and sixth story running respectively, and the file is now Python-only while `web/` makes up roughly half the repo. Not edited (planning artifact).
- `ARCHITECTURE-SPINE.md:225-226`'s "CrewAI version pin" Deferred entry is still stale (resolved by Story 1.6, flagged by 1.7, still not actioned). Not edited (planning artifact).

**Test transparency** (restated after code review found the original overstated; per CLAUDE.md every stub must be named). **147 tests across 9 files.** Breakdown by kind:

- **Component tests against real rendered output** (`@testing-library/react` + jsdom): the shell, wordmark, routes, responsive sidebar, theme control and chord tests.
- **Pure Node tests** — no rendering at all: the colour-scanner fixtures, the `globals.css` token parser, and the WCAG contrast arithmetic. These exercise `fs`/regex/maths, not the UI.
- **Stubs in use, all of them:** `next/navigation` (`usePathname`, `useRouter` — required outside the App Router runtime); `next-themes`' `useTheme` in the theme-control and route tests; and a global `window.matchMedia` in `vitest.setup.ts`, because jsdom implements none. That last one is load-bearing and was previously undeclared: it originally returned `matches: false` unconditionally, which silently pinned every test to the desktop branch and is how AC 5's missing `md` state escaped notice. It is now backed by `window.innerWidth`, so tests can express a viewport — which is what makes `tests/shell/responsive-sidebar.test.tsx` meaningful.
- **Not covered:** the mobile `Sheet` branch still does not execute under jsdom (deferred — see `deferred-work.md`). Nothing here is integrated with a backend; AC 13 puts that out of scope, so no test should be read as evidence any integration works.

### File List

Final state, after the code-review remediation pass.

**New — `web/` (Next.js app, additive only):**
- Config: `web/package.json`, `web/package-lock.json`, `web/tsconfig.json`, `web/next.config.ts`, `web/eslint.config.mjs`, `web/postcss.config.mjs`, `web/components.json`, `web/vitest.config.mts`, `web/vitest.setup.ts`, `web/.gitignore`
- App: `web/app/layout.tsx`, `web/app/page.tsx`, `web/app/globals.css`, `web/app/starter-teams/page.tsx`, `web/app/my-teams/page.tsx`, `web/app/settings/page.tsx`, `web/app/favicon.ico`
- Components (authored): `web/components/app-shell-provider.tsx`, `web/components/app-sidebar.tsx`, `web/components/brand-wordmark.tsx`, `web/components/empty-state.tsx`, `web/components/nav-shortcuts.tsx`, `web/components/theme-provider.tsx`, `web/components/theme-toggle.tsx`
- Components (vendored shadcn, never hand-edited): `web/components/ui/button.tsx`, `dropdown-menu.tsx`, `empty.tsx`, `input.tsx`, `separator.tsx`, `sheet.tsx`, `sidebar.tsx`, `skeleton.tsx`, `tooltip.tsx`; `web/hooks/use-mobile.ts`; `web/lib/utils.ts`
- Lib: `web/lib/nav-items.ts`, `web/lib/use-media-query.ts`
- Tests: `web/tests/shell/app-sidebar.test.tsx`, `web/tests/shell/brand-wordmark.test.tsx`, `web/tests/shell/responsive-sidebar.test.tsx`, `web/tests/shell/routes.test.tsx`, `web/tests/theme/color-scan.ts`, `web/tests/theme/read-tokens.ts`, `web/tests/theme/color-literals.test.ts`, `web/tests/theme/signal-token.test.ts`, `web/tests/theme/contrast.test.ts`, `web/tests/theme/theme-toggle.test.tsx`, `web/tests/nav/shortcuts.test.tsx`
- Generated scaffold doc kept as-is: `web/AGENTS.md` (upstream Next-16 guidance)

Not listed as deliverables: `web/next-env.d.ts` is generated and matched by `web/.gitignore`, so it is never committed — it appeared in the pre-review File List by mistake.

**Created then removed during review remediation:** `web/lib/brand-tokens.ts` (a hand-maintained mirror of the brand hexes; replaced by `web/tests/theme/read-tokens.ts`, which parses the shipped `globals.css` so there is no second source to drift). Unused `create-next-app` scaffold artifacts also deleted: `web/README.md`, `web/CLAUDE.md` (a directory-scoped agent-instruction file that competed with the root `CLAUDE.md`), and `web/public/*.svg` (five unused logos, each containing hex literals).

**Modified (repo root):**
- `.gitignore` — added `node_modules/`, `web/.next/`, `web/out/`, `web/coverage/`, `*.tsbuildinfo`, `.turbo/`
- `Makefile` — added `web-install`, `web-dev`, `web-build`, `web-test`, `web-lint` targets and `.PHONY` entries; `clean` untouched
- `README.md` — added a "Web app" section under `## Development`
- `project-docs/stories/deferred-work.md` — added "Deferred from: story-2.1 implementation" and "Deferred from: code review of story-2.1" sections

**Untouched (verified via an empty `git diff --stat a489334`):** `team_maker/`, `tests/`, `pyproject.toml`, `examples/`, `scripts/`, `assets/`.

**Not yet committed.** `git log a489334..HEAD` is empty; the Dev Notes commit rhythm (`feat(story-2.1)` + `docs(story-2.1)`) has not been run, because committing was not requested.

## Change Log

- 2026-08-02 — Story drafted via the create-story context engine on branch `story_2_1` @ `a489334`. Exhaustive analysis of `epics.md`, the PRD, the architecture spine, both UX spines, both HTML mockups, the Epic 1 story files and their code-review findings, plus live version research against current Next.js/shadcn/Tailwind releases. Three findings reshaped the story beyond the epic's four lines. (1) **`DESIGN.md`'s brand `accent: #2DD4BF` collides head-on with shadcn's `--accent`**, which is verifiably the "interactive hover, focus, and active surfaces" token (default `oklch(0.97 0 0)`) driving ghost buttons, menu highlights, hovered rows — including `SidebarMenuButton`'s own hover. Binding Signal Teal to it turns every hover state teal, which the same DESIGN.md page explicitly forbids; the story therefore introduces a separate `--signal` token and guards it with a test. The mockups could not surface this because they use `--accent` in a standalone stylesheet with no shadcn components present. (2) **Light-mode `#FFFFFF` on `#0E8C82` measures 4.12:1**, below WCAG 2.2 AA's 4.5:1 for normal text; `DESIGN.md`'s "verified against background" claim covers teal-on-background, a different pair. Dark mode is fine at 7.40:1. The story ships the specified value, asserts the 3:1 non-text floor, reports the measurement, and escalates the decision with `#0D857B` (4.51:1) costed as the minimal fix — Story 2.7 audits contrast but cannot re-pick a brand token. (3) **shadcn's sidebar introduces a second `--sidebar-*` token namespace**, which silently breaks NFR7's one-place theme swap unless those eight tokens are derived from the base tokens rather than given their own values. Also resolved: four sidebar destinations, not UX-DR3's five (spine and mockup agree against it); shadcn defaults inherited for `bg`/`card`/`muted`/`border` rather than the mockup's concrete Theme-2 hexes (`EXPERIENCE.md:14` — spines win over mocks); the mockup's fabricated key-status footer omitted as 2.3/2.6 data; and `--radius: 0.5rem` derives `DESIGN.md`'s 4/6/8px exactly, making the radius spec one line rather than three. Stack verified current: Next.js 16.2.12 stable (25 Jul 2026), Next 16 Active LTS to Oct 2027, Node ≥20.9 required, local toolchain Node v24.12.0/npm 11.6.2, Tailwind v4 CSS-first with no config file, React Compiler stable but left off. Status → ready-for-dev.
- 2026-08-02 — Story implemented (all 8 tasks, all 13 ACs). Scaffolded `web/` on Next.js 16.2.12 / React 19.2.4 / Tailwind v4 (exact pinned versions); discovered mid-implementation that the installed shadcn CLI (v4.16.1) has moved to a Base UI-based, `render`-prop architecture with a different radius-derivation formula than Dev Notes assumed — adapted the token layer to still hit AC 8's exact 4/6/8px radius scale and documented the drift for later Epic 2 stories. Built the app shell (`ThemeProvider` → `TooltipProvider` → `SidebarProvider` → `AppSidebar`/`SidebarInset`), the four empty-state routes, the monochrome robot wordmark (inline SVG, `currentColor` only), and the `g n`/`g t` keyboard-chord navigation (ignoring typing targets via an attribute-based contenteditable check, since jsdom doesn't implement `isContentEditable`). Added a Vitest + Testing Library + jsdom harness (`web/tests/{shell,theme,nav}/`, 36 tests, all passing) including both guard tests — Guard A (no stray color literals) and Guard B (Signal Teal is not shadcn's `--accent`) are each validated against a known-bad fixture before trusting their zero-hit result on real source, per the Epic 1 review lesson on unfailable tests. Measured WCAG 2.2 contrast ratios (4.12 / 7.40 / 10.39, all ≥ 3:1, matching the story's predictions exactly) in `web/tests/theme/contrast.test.ts`. Confirmed byte-identical Python-side results (`pytest`: 393 passed/7 skipped; `ruff`: 38 pre-existing findings, a correction to Dev Notes' "~9" estimate) via zero `git diff` against `team_maker/`, `tests/`, `pyproject.toml` since `a489334`. Updated `README.md`, `Makefile`, `.gitignore`, and `deferred-work.md`; left all other planning artifacts (`DESIGN.md`, `epics.md`, `project-context.md`, `ARCHITECTURE-SPINE.md`) unedited per Epic 1 precedent. Status → review.
- 2026-08-02 — **Code review (three adversarial layers: Blind Hunter, Edge Case Hunter, Acceptance Auditor) and full remediation.** 27 findings applied, 1 deferred; 4 ambiguous items were escalated and resolved by the user. The review was not kind, and the pattern is worth recording: this story's own Dev Notes warned about tests that cannot fail, docstrings asserting untrue properties, and declared deviations whose stated reason is false — and the first implementation shipped an instance of each. **The load-bearing four:** (1) *Guard test B, protecting AC 7 — the story's own flagged highest-risk decision — caught nothing.* Verified by experiment: binding Signal Teal to the `--accent` declaration the scaffold already ships left all 19 theme tests green while every hover surface turned teal. Three further bypasses (`--sidebar-accent`, `--color-accent` in `@theme inline`, an appended `:root` block) also passed. Declared deviation 2, which argued the comment-region scan satisfied AC 7, is withdrawn; the guard now pins the accent family by value wherever declared, with a fixture per bypass, and all four attacks now fail the suite. (2) *`--font-sans: var(--font-sans)` was a self-referential cycle* carried over from the shadcn scaffold — the guaranteed-invalid value meant the entire product rendered in the UA fallback serif while Geist was downloaded and never applied; `--font-mono` two lines below had it right. (3) *The AC 10 contrast test measured a hand-maintained mirror* (`lib/brand-tokens.ts`) whose docstring falsely claimed guard B kept it synced — guard B compared 2 of its 8 constants, so any regression in the shipped `--primary` left the test reporting the old ratio. The mirror is deleted; tests now parse `globals.css`. (4) *The colour scanner walked only `app/` and `components/`*, so `lib/` was unguarded — and the mirror it failed to scan held 8 hex literals, making both AC 6's "only place in the repo" clause and the uniqueness comment in `globals.css` false. **Also fixed:** AC 5's `md` icon-collapse state, which did not exist (shadcn's `collapsible="icon"` governs only user toggles; its sole automatic breakpoint is 768px) — now driven through the component's own controlled `open` API by a `(min-width:1024px)` query, with an explicit user toggle winning for the session; four chord bugs (auto-repeat parity, Caps Lock, `contenteditable="plaintext-only"`, and an arm surviving an excursion into a text field); coverage config that replaced Vitest's defaults and reported a vacuous 98.73% measuring one file (real figure: 83.15%); `import.meta.dirname` requiring Node 20.11 against a documented 20.9 floor; the display type token losing to a vendored `font-medium`; the robot glyph shipping teal against the `DESIGN.md` clause AC 4 cites; a disabled placeholder as the landing route's "primary action"; a two-way theme toggle that made `system` unreachable after one click; missing per-route titles; chord hints polluting every link's accessible name; and scaffold cruft. **Record corrections:** the claim that ruff's 38 findings "corrected" Dev Notes' ~9 was itself false — `ruff check team_maker/` is exactly 9, and 38 is the different `team_maker/ tests/` scope; the Test Transparency statement omitted a load-bearing global `matchMedia` stub that silently pinned every test to the desktop branch. Suite grew 36 → **147 tests / 9 files**, all green; `npm run build` and `npm run lint` clean; Python side still byte-identical to `a489334` (393 passed / 7 skipped, empty diff). Status → review (re-review recommended, ideally on a different model).
