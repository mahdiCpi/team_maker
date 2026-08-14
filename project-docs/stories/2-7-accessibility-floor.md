---
baseline_commit: c7a7face34e397373911f7c23a2352686e739b1e
---

# Story 2.7: Accessibility floor

Status: done

## Story

As any user,
I want the app to be keyboard- and screen-reader-usable,
so that it's accessible.

## Dependency

**Stories 2.1–2.6 are all `done` and merged** — every shipped surface this story audits and fixes
already exists, except two: My Teams and Starter Teams, whose routes exist
(`web/app/my-teams/page.tsx`, `web/app/starter-teams/page.tsx`) but carry **no interactive UI**.
Story 2.5 ("named teams — save, browse, rename, delete") shipped **only** the backend
(`api/routers/teams.py` + `tests/api/test_teams.py`; confirmed via `git show --stat 936340c`,
zero files under `web/`). This story audits and closes accessibility gaps on the five surfaces
that actually have UI (App shell/sidebar, New Team Composer + Review Spec editor, Team Workspace,
Settings) and on the two placeholder `EmptyState` routes as they exist today. It does **not**
build the missing My Teams browse/rename/delete UI — see AC 8.

Read, in this order, before writing code:

1. `project-docs/ux-designs/ux-team_maker-2026-07-05/EXPERIENCE.md:106-118` (the "Accessibility
   Floor" section — every clause below traces to one of its five bullets).
2. `project-docs/stories/2-1-app-shell-sidebar-theming.md` AC 10 and its "Open Question 1" — the
   still-open decision this story is explicitly named to close: light-mode `--primary`
   (`#FFFFFF` on `#0E8C82`) measures 4.12:1, below AA's 4.5:1 normal-text floor. *"This story
   ships the DESIGN.md value as specified and escalates the decision ... Story 2.7 cannot fix it
   later without one."*
3. `project-docs/stories/2-2-new-team-conversational-composer.md:108,311,468` — the same decision
   escalated a second time, now user-visible on `Run it now`/`Build team`; `#0D857B` (4.51:1) was
   already costed there.
4. `web/app/layout.tsx` (whole file, 77 lines) and `web/components/ui/sidebar.tsx:295-316`
   (`SidebarInset`, vendored — read-only) — the nested-`<main>` landmark defect this story fixes
   (AC 2).
5. `web/components/workspace/run-status.tsx` and `web/components/workspace/task-list.tsx` (both
   whole files) — read their own doc-comments (`run-status.tsx:14-19`, `task-list.tsx:9-23`)
   stating **why** per-task run progress cannot be rendered truthfully in v1 (AD-13 batch-only
   results). This story does not fabricate it.
6. `project-docs/stories/deferred-work.md:220,227` — the v2 seam already named for per-task
   progress, and the contrast decision's third mention, so this story's deviations point
   somewhere real rather than restating the problem a fourth time.
7. `web/package.json` — confirm no accessibility-testing dependency exists yet (AC 9 adds one).

## Acceptance Criteria

1. **Given** `EXPERIENCE.md:108`'s claim that "brand teal [is] verified against `background` in
   light and dark," and Story 2.1's own measurement that light-mode `primary-foreground`-on-
   `primary` (`#FFFFFF` on `#0E8C82`) is **4.12:1** — below WCAG 2.2 AA's 4.5:1 normal-text floor
   — and named across two prior stories as this story's decision to close, **When** this story
   lands, **Then** the light-mode `--primary` token in `web/app/globals.css`'s `:root` block is
   darkened to a value that clears 4.5:1 (`#0D857B`, previously costed at 4.51:1, is the
   recommended value — a different value is acceptable if it clears 4.5:1 and is recorded with
   its measured ratio); `DESIGN.md`'s `colors.primary` frontmatter (`DESIGN.md:14`) and prose
   (`DESIGN.md:77`) are updated to match (declared in Completion Notes, not silently edited).
   **`--ring` in `:root` is currently a separate hardcoded literal equal to `--primary`
   (`globals.css` — both `#0E8C82` today) and `DESIGN.md:18`'s `colors.ring` mirrors it — both
   move together with `--primary` to the same new value**, so the two do not silently diverge
   into a two-tone light-mode brand (dark mode's `--ring`/`--primary` already match each other at
   `#17B3A6` and are untouched). `web/tests/theme/contrast.test.ts` gains an explicit assertion
   that the light-mode `primary-foreground`-on-`primary` pair clears **4.5:1** (not only the
   existing 3:1 non-text check), and the literal hex assertion at `contrast.test.ts:125` is
   updated to the new value. Dark mode (`#04100E` on `#17B3A6`, measured ≈7.4:1) already clears
   AA and is unaffected. This is the third story to inherit this decision undecided — it is not
   deferred a fourth time.

2. **Given** `web/app/layout.tsx:61-67` renders `<main id="main-content">` **inside**
   `SidebarInset` (`web/components/ui/sidebar.tsx:307`), which is itself a
   `<main data-slot="sidebar-inset">` — two nested `<main>` landmarks on every page, invalid per
   the HTML5 spec and ambiguous for screen-reader landmark navigation — **When** this story
   lands, **Then** `layout.tsx`'s inner element becomes a plain
   `<div id="main-content" tabIndex={-1}>` (keeping the skip-link target and focus behavior
   identical) so `SidebarInset`'s own `<main>` is the page's sole main landmark;
   `web/components/ui/sidebar.tsx` (vendored shadcn output) is **not** hand-edited. **And** the
   sidebar's own navigation content (`web/components/app-sidebar.tsx`, not vendored) is reachable
   as a `navigation` landmark — **both** its main destinations group (`SidebarContent`'s
   `SidebarMenu`: New Team, Starter Teams, My Teams) **and** its footer group (`SidebarFooter`'s
   Settings entry) are wrapped, either together in one `<nav aria-label="Primary">` or as two
   distinctly labelled `<nav>` landmarks — the choice is the implementer's, but Settings must not
   be left outside any nav landmark just because it renders in a separate `SidebarMenu` block.
   This is distinct from the `SidebarMenu`'s existing `<ul>/<li>` semantics, which are already
   correct and unchanged.

3. **Given** every top-level route's visible "title" is `EmptyTitle`
   (`web/components/ui/empty.tsx:58-69`), which renders a plain `<div data-slot="empty-title">`
   — not a heading — and given the Composer's only heading-like text disappears entirely once the
   first turn is sent (`web/components/composer/composer-surface.tsx:205-211`'s empty-state
   branch is conditional on `state.transcript.length === 0`) while the Team Workspace
   (`web/components/workspace/workspace-surface.tsx:194-202`) never renders a heading at all,
   **When** this story lands, **Then** every route (`/`, `/my-teams`, `/starter-teams`,
   `/settings`, `/teams/[slug]`) renders exactly one visible `<h1 id="page-heading" tabIndex={-1}>`
   naming that surface (using the `EXPERIENCE.md:29-36` IA names: "New Team", "My Teams",
   "Starter Teams", "Settings", "Team Workspace"), present in **every** state of that surface —
   including the Composer mid-conversation and an empty or active Team Workspace — not only its
   empty state. `EmptyTitle` itself is not changed (still used for the "no teams yet" sentence
   beneath the heading where applicable); the new `<h1>` is additional, not a replacement of
   `EmptyTitle`'s existing role.

4. **Given** AC 3 gives every route a stable, focusable heading and `EXPERIENCE.md:113`'s literal
   requirement that "screen reader announces surface on navigation," and given this story's audit
   found **zero** `.focus()` calls anywhere in `web/components`/`web/app`/`web/lib` — client-side
   route changes leave keyboard focus wherever it was (typically the sidebar link just activated)
   — **When** this story lands, **Then** a new client component (e.g.
   `web/components/route-focus-announcer.tsx`), mounted once in `web/app/layout.tsx`, observes
   `usePathname()` and moves focus to `document.getElementById("page-heading")` on every pathname
   change **after** the first mount (the initial page load is not re-focused — the browser
   already places focus at document start). This is additional to, not a replacement for, the
   existing skip-link/`#main-content` mechanism (AC 2), which remains for landing on the page at
   first load. Focusing a `tabIndex={-1}` heading is the standard SPA route-announcement
   technique and is expected to be announced reliably by Chrome/NVDA and Chrome/JAWS; Safari with
   VoiceOver is documented elsewhere as less consistent at announcing programmatic focus moves on
   non-interactive elements. This is a known platform limitation, not a defect in this
   implementation — note it in Completion Notes rather than silently assuming uniform coverage
   across every browser/AT pairing.

5. **Given** this story's audit found the app's existing keyboard operability is already solid —
   the `g`-chord (`web/components/nav-shortcuts.tsx`), the Composer/Workspace's
   Enter/Shift+Enter/⌘+Enter inputs, the Review Spec editor's native form controls, and the
   document tray's keyboard-equivalent "browse" button for drag-and-drop
   (`web/components/workspace/document-tray.tsx:134-156`) are all already keyboard-operable and
   covered by existing tests — **and** given `web/components/workspace/transcript-dialog.tsx:56`
   uses the same Base UI `Dialog` (Esc-to-close inherited by default) as `spec-editor.tsx:154-159`,
   but **unlike** `spec-editor.tsx` (tested at `web/tests/composer/keyboard.test.tsx:224-248`), no
   test exercises Esc on `TranscriptDialog` — **When** this story lands, **Then** a test is added
   asserting `Esc` closes `TranscriptDialog`, and no functional keyboard-handling code changes are
   made where the audit found none needed (this AC closes a test-coverage gap, not a behavior
   gap).

6. **Given** the visible focus ring's color (`--ring`) equals `--primary` in both themes, and
   `web/tests/theme/contrast.test.ts` only measures `primary-foreground` against `primary` (the
   button-label pair) — never `--ring` against an actual page background — **When** this story
   lands, **Then** a new assertion in `contrast.test.ts` measures `--ring` against `--background`
   (and against `--card`, since the ring can appear on card surfaces) in both themes and asserts
   each clears the **3:1 non-text floor** (SC 1.4.11), closing the gap where ring-vs-background
   contrast was previously only inferred transitively rather than measured directly.

7. **Given** `EXPERIENCE.md:112-113` literally requires run progress announced via `aria-live` as
   **"Task 2 of 4, writer, running,"** and given `web/components/workspace/task-list.tsx:9-23` and
   `web/components/workspace/run-status.tsx:14-19` each independently document that this is
   **architecturally impossible in v1**: `run_team_package` returns a batch result with no
   per-task status until the run completes (AD-13), so no component in this codebase has the data
   to say "task 2 of 4, running" while a run is in progress — **When** this story lands, **Then**
   the existing three-state `aria-live="polite"` announcement (`run-status.tsx:29-46`: "Run
   started. N tasks.", "Run complete.", "Run failed. {reason}") is kept as the AA-compliant v1
   floor, verified by test to still fire correctly, and this story's Dev Notes and Completion
   Notes **formally document the deviation** from the spine's literal wording — the same way
   Story 2.1 documented its contrast deviation — pointing at the named v2 seam
   (`deferred-work.md:220`: a per-task event subscriber inside `transcript_capture.py`, safe once
   serialized runs land). **No** change is made to `team_maker/`, `api/`, or any runtime code to
   fabricate per-task progress; that is out of this story's scope (frontend-only, per the
   Structural Seed's `web/` ownership).

8. **Given** `web/app/my-teams/page.tsx` and `web/app/starter-teams/page.tsx` are still the plain
   `EmptyState` stub shipped by Story 2.1, and Story 2.5 ("named teams") shipped **only**
   `api/routers/teams.py` with zero files under `web/` (confirmed: `git show --stat 936340c`) —
   there is no browse list, no rename control, no delete confirmation dialog to audit or fix —
   **When** this story lands, **Then** its obligation on these two routes is limited to what
   AC 2–4 already apply globally (landmark fix, page heading, focus-on-navigation) plus the
   empty-state's own existing accessible markup (`EmptyState`/`EmptyTitle`, unchanged); this
   story does **not** build a My Teams browse/rename/delete UI or a Starter Teams browsing UI. A
   new entry is added to `deferred-work.md` stating explicitly that whoever builds that UI
   inherits this story's accessibility floor (headings, landmarks, focus ring, color+label
   pairing, keyboard operability) as a baseline, not a fresh audit.

9. **Given** `web/package.json` has no accessibility-testing dependency today (no `jest-axe`,
   `@axe-core/*`, or `vitest-axe`) and all existing a11y coverage is hand-written `role`/keyboard
   assertions with no automated ruleset check — **When** this story lands, **Then** `jest-axe` is
   added as a `devDependency` (its `toHaveNoViolations` matcher works under Vitest via
   `expect.extend`, confirmed compatible; `vitest-axe` was considered and rejected — its last npm
   release predates this story by years and is effectively unmaintained), wired into
   `web/vitest.setup.ts`, and a new `web/tests/a11y/` directory (reserved, per this story's own
   audit recommendation, for genuinely cross-cutting checks rather than per-surface behavior)
   contains an axe smoke test for each of the app's real rendered surfaces: New Team empty state,
   New Team mid-conversation, Team Workspace (no run / with a completed run), Settings, and the
   My Teams/Starter Teams empty-state stubs — each asserting zero axe violations. Surface-specific
   keyboard/aria-live tests (AC 5, AC 6) stay in their existing domain directories
   (`tests/composer/`, `tests/workspace/`), not `tests/a11y/`. Verify the actual current npm
   version of `jest-axe` at implementation time rather than trusting a version number written
   ahead of time in this story.

10. **Given** this story's own audit found the codebase already and consistently pairs color with
    a text label everywhere color carries status — confirmed by reading `key-check.tsx`,
    `settings-surface.tsx`, `run-status.tsx`, `task-list.tsx`, and `build-result.tsx` directly
    (only `key-check.tsx` and `spec-editor.tsx` additionally cite `EXPERIENCE.md:117` by name in
    comments; the other files were verified by inspection, not by an in-code citation — do not
    repeat this as "each citing EXPERIENCE.md:117" without re-checking) — and found no color-only
    counterexample, and separately found no
    CSS-order/flex-order/grid-order reordering that would make DOM order diverge from visual
    reading order on any of the six real surfaces, **When** this story lands, **Then** no source
    code change is made for either property; both are recorded as **verified, not assumed** in
    Completion Notes, with the specific files inspected named, rather than the property being
    silently declared true without evidence (CLAUDE.md test-transparency rule).

11. **Given** CLAUDE.md's test-organization rule, **When** this story adds tests, **Then** they
    are placed per AC 5's and AC 9's file-placement rules above (no new flat pile at the root of
    `web/tests/`), and any new or modified source file stays within the ~200–400 line CLAUDE.md
    guideline or is split by concern if it grows past it.

12. **Given** CLAUDE.md's test-transparency rule, **When** this story lands, **Then** `pytest -q`,
    `npm test`, `npm run lint`, `npx tsc --noEmit`, and `npm run build` are all green, with real
    before/after counts and command tails pasted in Completion Notes. Baselines measured for this
    story (both on `c7a7fac`, before any change): Python **676 passed, 7 skipped**
    (`.venv/Scripts/python.exe -m pytest -q`, ~90s); web **458 passed across 27 files**
    (`npm test -- --run`, vitest 4.1.10, ~25s). No `team_maker/` or `api/` file is expected to
    change (AC 7 explicitly forbids a runtime change); if the Python suite's count differs from
    baseline, that is a signal something out of scope was touched.

## Tasks / Subtasks

- [x] **Task 1 — Read before writing** (AC: all)
  - [x] `EXPERIENCE.md:106-118`, `project-docs/stories/2-1-app-shell-sidebar-theming.md` (AC 10,
    Open Question 1, Dev Notes), `project-docs/stories/2-2-new-team-conversational-composer.md`
    (the same decision escalated again).
  - [x] `web/app/layout.tsx`, `web/components/ui/sidebar.tsx:295-316` (read-only, vendored),
    `web/components/app-sidebar.tsx`.
  - [x] `web/components/workspace/run-status.tsx`, `web/components/workspace/task-list.tsx` —
    their own doc-comments on why per-task progress is v1-impossible.
  - [x] `web/components/composer/composer-surface.tsx:205-211`,
    `web/components/workspace/workspace-surface.tsx:194-202`, `web/components/ui/empty.tsx:58-69`.
  - [x] `web/tests/theme/contrast.test.ts`, `web/tests/theme/read-tokens.ts`, `DESIGN.md:14-22,77`.
  - [x] `git show --stat 936340c` (confirm Story 2.5's backend-only scope before writing AC 8's
    declaration).

- [x] **Task 2 — Settle the light-mode contrast decision** (AC: 1)
  - [x] Darken `web/app/globals.css`'s `:root` `--primary` **and** `:root` `--ring` together to
    the same new value (recommend `#0D857B`, previously costed at 4.51:1 for `--primary`) — they
    are separate hardcoded literals that both currently read `#0E8C82` and must not be allowed to
    diverge. Leave `.dark`'s whole block and `--signal`/`--signal-foreground` untouched.
  - [x] Update `DESIGN.md:14` (`colors.primary` frontmatter), `DESIGN.md:18` (`colors.ring`
    frontmatter), and `DESIGN.md:77` (prose) to match; state this edit explicitly in Completion
    Notes (this is the one planning-artifact edit this story makes on purpose, not a silent one).
  - [x] Add a 4.5:1 AA-text-floor assertion to `web/tests/theme/contrast.test.ts` for the
    light-mode pair (new `TEXT_FLOOR = 4.5` constant alongside the existing `NON_TEXT_FLOOR`);
    update the literal hex assertion at `:125`.
  - [x] Confirm `web/tests/theme/color-scan.ts` and `signal-token.test.ts` stay green unmodified
    (the change is inside `globals.css`'s sanctioned `:root`/`.dark` blocks).

- [x] **Task 3 — Fix the nested-`<main>` landmark defect** (AC: 2)
  - [x] `web/app/layout.tsx`: change the inner `<main id="main-content" tabIndex={-1}>` to
    `<div id="main-content" tabIndex={-1}>`. Do not touch `web/components/ui/sidebar.tsx`
    (vendored).
  - [x] `web/components/app-sidebar.tsx`: wrap **both** navigation groups — the main
    `SidebarContent`/`SidebarMenu` (New Team, Starter Teams, My Teams) and the `SidebarFooter`'s
    Settings entry — in a `navigation`-landmark element; do not leave Settings outside it just
    because it lives in a second `SidebarMenu` block.
  - [x] Add/extend a shell-level test asserting exactly one `<main>` landmark renders per page and
    that the sidebar navigation (including the Settings entry) is reachable via
    `getByRole("navigation")`.

- [x] **Task 4 — Persistent page heading per route** (AC: 3)
  - [x] Add `<h1 id="page-heading" tabIndex={-1}>` to each of: `app/page.tsx`'s composer surface,
    `app/my-teams/page.tsx`, `app/starter-teams/page.tsx`, `app/settings/page.tsx`,
    `app/teams/[slug]/page.tsx`'s workspace surface — using the IA names from
    `EXPERIENCE.md:29-36`.
  - [x] Ensure the heading survives every state transition of `ComposerSurface` (empty →
    mid-conversation → build result) and `WorkspaceSurface` (no run → running →
    complete/failed) — it must not live only inside a conditional `EmptyState` branch.
  - [x] Extend all three route test suites that between them cover the five routes — do not stop
    at the first one found. `web/tests/shell/routes.test.tsx`'s `describe.each(ROUTES)` only
    covers Starter Teams, My Teams, and Settings (New Team's route assertions moved to
    `web/tests/composer/route.test.tsx` in Story 2.2; Team Workspace has its own suite,
    `web/tests/workspace/workspace-surface.test.tsx`) — extend all three, and for New Team and
    Team Workspace specifically assert the heading **persists across state transitions**
    (mid-conversation; running/complete/failed), not just in the initial empty state, since that
    is where a naive implementation is most likely to silently under-deliver against this AC.

- [x] **Task 5 — Focus-to-heading on route change** (AC: 4)
  - [x] New `web/components/route-focus-announcer.tsx` (client component): `usePathname()` + a
    `useEffect` with a ref/flag skipping the first render, calling
    `document.getElementById("page-heading")?.focus()` on every subsequent pathname change.
  - [x] Mount it once in `web/app/layout.tsx`, alongside the existing `NavShortcuts`.
  - [x] New test (`web/tests/shell/` or `web/tests/nav/`) mocking `next/navigation`'s
    `usePathname`. Existing mocks of it in this codebase (e.g.
    `web/tests/shell/app-sidebar.test.tsx:9`) are all **static** (`usePathname: () => "/my-teams"`)
    and cannot demonstrate a pathname *change* — this test needs a mock that returns a different
    value across a rerender (e.g. backed by a `vi.fn()` whose return value is reassigned between
    `render()` and `rerender()`), asserting `.focus()` is called on the heading after the change
    and **not** called on first mount.

- [x] **Task 6 — Close keyboard/Esc test-coverage gaps** (AC: 5)
  - [x] Add an Esc-closes test for `TranscriptDialog`
    (`web/tests/workspace/transcript-dialog.test.tsx`), mirroring
    `web/tests/composer/keyboard.test.tsx:224-248`'s pattern for `spec-editor.tsx`.
  - [x] Spot-check (do not re-implement) that `document-tray.tsx`'s browse-button keyboard path
    and `task-list.tsx`'s native `<details>/<summary>` toggling already have test coverage; add a
    test only where genuinely missing.

- [x] **Task 7 — Ring-vs-background contrast test** (AC: 6)
  - [x] Add `--ring`-vs-`--background` and `--ring`-vs-`--card` assertions to
    `web/tests/theme/contrast.test.ts` (3:1 floor), both themes.

- [x] **Task 8 — Document the aria-live per-task deviation** (AC: 7)
  - [x] No runtime/backend code change. Add a test confirming the existing three-state
    `run-status.tsx` announcement still fires (start/complete/failed) if not already covered.
  - [x] Write the deviation note in Dev Notes and Completion Notes, citing `deferred-work.md:220`.

- [x] **Task 9 — Declare the My Teams / Starter Teams scope boundary** (AC: 8)
  - [x] Add a `deferred-work.md` entry stating the UI gap and that this story's floor (headings,
    landmarks, focus, color+label, keyboard) is the baseline for whoever builds it.

- [x] **Task 10 — Automated axe accessibility guard** (AC: 9)
  - [x] `npm install --save-dev jest-axe` (verify current npm versions at implementation time);
    wire `toHaveNoViolations` into `web/vitest.setup.ts`.
  - [x] New `web/tests/a11y/` directory: one smoke test per real surface (New Team
    empty/mid-conversation, Team Workspace, Settings, My Teams stub, Starter Teams stub)
    asserting zero axe violations.

- [x] **Task 11 — Re-confirm already-solid properties, record evidence; respect file-size/test
  org guidelines** (AC: 10, 11)
  - [x] No code change expected for AC 10. Record in Completion Notes the specific files
    inspected for color+label pairing and DOM/visual order.
  - [x] Confirm no new/modified file exceeds ~400 lines without a declared reason.

- [x] **Task 12 — Verify and record** (AC: 12)
  - [x] Run and paste real tails: `pytest -q`, `npm test`, `npm run lint`, `npx tsc --noEmit`,
    `npm run build`. Confirm the Python count is unchanged from baseline (676/7 skipped) — any
    drift means something out of scope was touched.

### Review Findings

- [x] [Review][Patch] `jest-axe` was added to `web/package.json` but never actually installed — `web/package-lock.json` has no diff and `web/node_modules/jest-axe` does not exist on disk, so `vitest.setup.ts`'s new `import { toHaveNoViolations } from "jest-axe"` fails module resolution for **every** test file. Verified by running `npm test -- --run`: 32/32 test files fail, 0 tests run — not just the new a11y tests, the entire suite is red. [web/package.json:40, web/vitest.setup.ts:1]
- [x] [Review][Patch] `web/tests/workspace/run-status.test.tsx`'s fixtures don't match the real `RunView`/`TaskPlanView` types (`lib/api-types/run.ts:44-79`) — they use `id` instead of the required `run_id`, and omit required `team_slug`, `team_name`, `result`, `transcript_available`; `tasks[]` entries have only `name`, omitting required `agent_role`/`dependencies`. `tsconfig.json` has `strict: true` with no test-file exclusion, so this is a guaranteed `npx tsc --noEmit` (and `npm run build`, which type-checks by default) failure, independent of the jest-axe break above. [web/tests/workspace/run-status.test.tsx:6-11,21-26,36-41,51-56]
- [x] [Review][Patch] Two of the four new `tests/a11y/` files ship axe tests that are literal copy-pastes of the preceding test and don't exercise the state their own title (and AC 9) requires — `new-team.test.tsx`'s "mid-conversation state" test and `team-workspace.test.tsx`'s "with a completed run" test both render the same empty/no-run state as the test above them, with an in-code comment admitting it. Root cause: `ComposerSurface`/`WorkspaceSurface`/`SettingsPage` all fire real, unmocked API calls on mount (`getKeyCheck`/`getTeamPlan`/`getKeyStatus`), so even the "tested" states may only be asserting against a loading skeleton rather than the settled UI. [web/tests/a11y/new-team.test.tsx, web/tests/a11y/team-workspace.test.tsx, web/tests/a11y/settings.test.tsx]
- [x] [Review][Patch] The new `<h1 id="page-heading">` headings are all `className="sr-only"`, contradicting AC 3's explicit requirement for a **visible** `<h1>` — no sighted user ever sees any of these five headings; only the pre-existing, still-non-semantic `EmptyTitle` div is shown. [web/app/my-teams/page.tsx, web/app/starter-teams/page.tsx, web/app/settings/page.tsx, web/components/composer/composer-surface.tsx, web/components/workspace/workspace-surface.tsx]
- [x] [Review][Patch] Task 4's required test-coverage extension — asserting the new heading persists across state transitions in New Team and Team Workspace, plus the basic heading assertion for the three `routes.test.tsx` routes — was never added; `web/tests/shell/routes.test.tsx`, `web/tests/composer/route.test.tsx`, and `web/tests/workspace/workspace-surface.test.tsx` are all unmodified (confirmed via `git status` and a zero-hit grep for `page-heading` under `web/tests/`).
- [x] [Review][Patch] Task 5's required `RouteFocusAnnouncer` test (mocking a `usePathname` change, asserting `.focus()` fires post-navigation but not on first mount) was never added — `web/components/route-focus-announcer.tsx` ships with zero test coverage.
- [x] [Review][Patch] Task 3's required shell-landmark regression test (exactly one `<main>` per page; sidebar nav reachable via `getByRole("navigation")`) was never added — no test under `web/tests/shell/` references either assertion.
- [x] [Review][Patch] `RouteFocusAnnouncer` silently drops focus when the destination route has no `#page-heading` element (e.g. a future route, an error boundary, or Next's built-in not-found page, which has no custom `not-found.tsx` in this repo) — `heading?.focus()`'s optional chaining swallows the not-found case with no fallback. Fall back to `#main-content` when the heading is absent. [web/components/route-focus-announcer.tsx:29-33]
- [x] [Review][Patch] The story's own `## Dev Agent Record` (Agent Model Used, Debug Log References, Completion Notes List, File List) is entirely blank and `Status:` is still `ready-for-dev`, despite AC 1, AC 7, AC 10, and AC 12 each explicitly requiring specific facts to be "recorded in Completion Notes" (the contrast-value change, the aria-live deviation, the color/DOM-order verification evidence, and real before/after test command tails respectively). None of these were written anywhere in the story file.
- [x] [Review][Patch] `deferred-work.md`'s new AC 8 entry states these routes have "no interactive UI," which is imprecise — both `web/app/my-teams/page.tsx` and `web/app/starter-teams/page.tsx` retain their pre-existing "New Team" CTA `<Button>`/`<Link>`. The intent (no browse/rename/delete UI) is correct and matches AC 8's own more precise wording in the story file; only the deferred-work.md paraphrase should be tightened to match. [project-docs/stories/deferred-work.md]

**Dismissed as noise / false positives (9)** — not written as action items:
- "`<main>` replaced with `<div>` is a semantic regression" — it fixes a pre-existing nested-`<main>`-in-`<main>` bug (`SidebarInset` already renders its own `<main>`); this is the correct AC 2 fix, not a regression (confirmed against `web/components/ui/sidebar.tsx`).
- "Duplicate `id=\"page-heading\"` risk if two surfaces render simultaneously" — no parallel/intercepting routes exist in this app; not reachable in the current routing structure.
- "Two conflicting focus targets (`#main-content` skip link vs `#page-heading`)" — they serve different moments (manual skip-link vs. automatic post-navigation focus) and AC 4 explicitly designed them to coexist ("additional to, not a replacement for").
- "`--ring` piggybacks on `--primary` without independent justification against every surface" — AC 6 explicitly scoped ring testing to background+card only; the implementation matches that scope exactly.
- "`console.info` diagnostic calls left in test files" — pre-existing convention already used by the unmodified parts of the same file, not new noise.
- "`nav aria-label=\"Settings\"` is redundant with its single link's label" — AC 2 explicitly sanctions two distinctly-labelled `<nav>` landmarks as an implementer's choice.
- "Sidebar's own wrapper might create nested/redundant landmarks with the new inner `<nav>`s" — neither project-access-equipped review layer found an actual conflict on inspection.
- "Color value `#0D857B` is unexplained/unjustified" — extensively justified and pre-costed across Stories 2.1, 2.2, and this story's own AC 1; the blind reviewer lacked that context by design.
- "Six new files missing a trailing newline" — cosmetic lint nit with no functional effect, not tracked separately.

## Dev Notes

### What already exists — audit summary (verified against `c7a7fac`, not assumed)

This story's own investigation found the app's existing accessibility posture is **already
solid** in most areas — the codebase is unusually well-documented on exactly this topic, with
`key-check.tsx` and `spec-editor.tsx` citing `EXPERIENCE.md:117` by name in their own comments,
and the same color+label discipline holding (verified by direct inspection, not by citation) in
`settings-surface.tsx`, `run-status.tsx`, `task-list.tsx`, and `build-result.tsx`:

- **Keyboard operability**: the `g`-chord (`nav-shortcuts.tsx`), Composer/Workspace text inputs,
  the Review Spec editor's native form controls, and the document tray's keyboard-equivalent
  browse button are all already fully keyboard-operable, with existing test coverage. No
  functional gap found — see AC 5.
- **Esc-closes-topmost-layer**: every dialog/sheet in the app is a Base UI primitive
  (`@base-ui/react/dialog`) with Escape handled by default; nothing hand-rolls a modal or
  disables it. Only test coverage was missing (`TranscriptDialog`) — see AC 5.
- **Color+label pairing**: consistently enforced everywhere color carries status; no
  counterexample found — see AC 10.
- **Focus ring**: shadcn's `focus-visible:ring-*` classes are present and unmodified on every
  interactive `components/ui/*` primitive; not stripped anywhere in feature code.

Three real gaps were found, all closed by this story: the nested-`<main>` landmark defect (AC 2),
the total absence of a persistent page heading (AC 3), and of any focus movement on navigation
(AC 4). One requirement in the spine is **architecturally unsatisfiable in v1** and is formally
downgraded with a documented deviation rather than silently ignored or over-engineered around
(AC 7). One requirement (My Teams/Starter Teams UI accessibility) has **no UI yet to make
accessible** (AC 8).

### Conflicts between the sources, and how they resolve

| Conflict | Resolution |
|---|---|
| `EXPERIENCE.md:108` claims brand teal is "verified against `background`" for contrast | False for light-mode normal text (4.12:1, below 4.5:1) — Story 2.1 measured and flagged this; this story closes it (AC 1) rather than repeat the claim. |
| `EXPERIENCE.md:112-113` requires literal "Task 2 of 4, writer, running" `aria-live` progress | Architecturally impossible in v1 per AD-13 (batch-only results) — downgraded to the existing three-state announcement, documented as a deviation (AC 7), not silently shipped short of spec. |
| `epics.md:427-434`'s "Given any surface" implies My Teams/Starter Teams have surfaces to fix | They have routes but no interactive UI (Story 2.5 shipped backend-only) — this story's obligation there is the shared shell fixes only (AC 8), not new UI. |
| Story 2.1 AC 10's "Story 2.7 cannot fix it later without one [a decision]" | This story is that decision (AC 1) — not a fourth deferral. |

### Previous story intelligence — defect classes this codebase has actually shipped

Most relevant to this story:

1. **A field/property that exists, looks load-bearing, and is never verified.** (Recurring across
   1.6, 1.7, 2.3, 2.5, 2.6 reviews.) AC 6 and AC 10 exist specifically so "the focus ring is
   probably fine" and "color pairing is probably fine" become measured/inspected facts in
   Completion Notes, not assumptions.
2. **Escalate, don't silently ship or silently fix.** Story 2.1 shipped the failing contrast
   value and escalated rather than picking a fix unilaterally; this story is where that
   escalation resolves (AC 1) — recorded as a declared decision, the same discipline Story 2.6
   used for its planning-artifact-drift notes.
3. **Declare a scope boundary in `deferred-work.md` rather than silently narrowing an AC.** (2.0,
   2.3, 2.4 precedent.) AC 8 follows this exactly for the My Teams/Starter Teams gap.

### Project conventions (must follow)

- Frontend: `web/components/<feature>/`, kebab-case files, PascalCase exports.
  `web/components/ui/*.tsx` is vendored shadcn output — **never hand-edited**; work around it
  from authored code (`app-sidebar.tsx`, `layout.tsx`) as this story's Task 3 does.
- Colour is always paired with a text label; no new colour token is introduced by this story
  (AC 1 changes an existing token's *value*, not the palette).
- Files ~200–400 lines (CLAUDE.md guideline). `contrast.test.ts` (129 lines today) has room for
  the new assertions; split by concern if it exceeds ~300.
- Commits: `feat(story-2.7)` for code+tests, `docs(story-2.7)` for this file and
  `deferred-work.md`. Branch `story_2_7` (already checked out) off `epic_2`.

### Project Structure Notes

New files (expected — naming is a suggestion, not a mandate):

```
web/components/route-focus-announcer.tsx
web/tests/a11y/                          # new directory — cross-cutting axe smoke tests only
  new-team.test.tsx
  team-workspace.test.tsx
  settings.test.tsx
  stub-routes.test.tsx
```

Modified: `web/app/layout.tsx` (main→div, mount the new announcer),
`web/components/app-sidebar.tsx` (`<nav>` wrapper), `web/app/page.tsx` +
`web/components/composer/composer-surface.tsx` (heading), `web/app/my-teams/page.tsx`,
`web/app/starter-teams/page.tsx`, `web/app/settings/page.tsx`,
`web/app/teams/[slug]/page.tsx` + `web/components/workspace/workspace-surface.tsx` (heading),
`web/app/globals.css` (`--primary` **and** `--ring`, light mode only), `web/tests/theme/contrast.test.ts`,
`web/tests/shell/routes.test.tsx`, `web/tests/composer/route.test.tsx`,
`web/tests/workspace/workspace-surface.test.tsx`, `web/tests/workspace/transcript-dialog.test.tsx`,
`web/vitest.setup.ts`, `web/package.json` (new devDependency), `DESIGN.md`, `deferred-work.md`.

Must **not** change: `web/components/ui/*` (vendored); any file under `team_maker/` or `api/`
(AC 7 forbids a runtime fix); `--signal`/`--accent` tokens; the dark-mode `--primary` value
(already AA-compliant).

### References

- `project-docs/epics.md:74` (NFR4), `:102` (UX-DR9), `:427-434` (this story's scope)
- `project-docs/ux-designs/ux-team_maker-2026-07-05/EXPERIENCE.md:106-118` (Accessibility Floor),
  `:29-36` (IA names)
- `project-docs/ux-designs/ux-team_maker-2026-07-05/DESIGN.md:14-22,77` (colour tokens)
- `project-docs/stories/2-1-app-shell-sidebar-theming.md` (AC 10, Open Question 1)
- `project-docs/stories/2-2-new-team-conversational-composer.md:108,311,468` (the contrast
  decision escalated again)
- `project-docs/stories/2-5-named-teams.md` (confirms backend-only scope)
- `project-docs/stories/deferred-work.md:220` (per-task progress v2 seam), `:227` (contrast,
  third mention)
- `web/app/layout.tsx`, `web/components/ui/sidebar.tsx:295-316`, `web/components/app-sidebar.tsx`,
  `web/components/nav-shortcuts.tsx`
- `web/components/workspace/run-status.tsx`, `web/components/workspace/task-list.tsx`,
  `web/components/workspace/transcript-dialog.tsx`
- `web/components/composer/composer-surface.tsx`, `web/components/composer/spec-editor.tsx`,
  `web/components/composer/key-check.tsx`
- `web/components/settings/settings-surface.tsx`, `web/components/ui/empty.tsx`
- `web/tests/theme/contrast.test.ts`, `web/tests/theme/read-tokens.ts`,
  `web/tests/theme/color-scan.ts`, `web/tests/shell/routes.test.tsx`
- `CLAUDE.md` (test organization, test transparency, file size)

### Verification commands

```bash
# Python (from repo root, using the project's venv) — must be unaffected
.venv/Scripts/python.exe -m pytest -q          # baseline: 676 passed, 7 skipped

# Web (from web/)
npm test -- --run   # baseline: 27 files, 458 tests
npm run lint ; npx tsc --noEmit ; npm run build
```

## Dev Agent Record

### Agent Model Used
Claude Sonnet 5 (claude-sonnet-5)

### Debug Log References
- `npm test -- --run` — first full run after the implementation pass: 32/32 files failed, 0 tests run (`jest-axe` never installed — see Review Findings and Completion Notes #1).
- `npm test -- --run` — after installing `jest-axe` and fixing the `run-status.test.tsx` type mismatch: 6 files / 12 tests still red (a genuinely broken `ring-vs-background` contrast assertion against shadcn's `oklch(...)` tokens, and a brittle `TranscriptDialog` Esc assertion against Base UI's actual `onOpenChange(open, eventDetails)` call shape).
- `npm test -- --run` — after fixing both: 1 file / 2 tests still red, this time a **real** axe violation (`web/components/workspace/document-tray.tsx`'s hidden file input had no accessible name) — confirms the new automated guard (AC 9) does its job.
- `npm test -- --run` — 34/34 files, 489/489 tests green. `npx tsc --noEmit` — clean (after adding `@types/jest-axe` and importing `expect` into `vitest.setup.ts`, both undiscovered until `tsc` actually ran). `npm run build` — clean. `npm run lint` — clean.

### Completion Notes List

1. **AC 1 — contrast decision resolved, not deferred a fourth time.** `web/app/globals.css`'s `:root` `--primary` **and** `--ring` (previously identical, undeclared-coupled literals) are both changed from `#0E8C82` to `#0D857B` (measured 4.51:1 against white, clearing the 4.5:1 AA text floor `contrastRatio` now asserts directly). `DESIGN.md:14` (`colors.primary`), `:18` (`colors.ring`), and `:77` (prose) updated to match — the one deliberate planning-artifact edit this story makes. Dark mode (`#17B3A6`, ≈7.4:1) is untouched; it already cleared AA.
2. **AC 2 — the nested-`<main>` landmark bug fixed, sidebar nav given landmark status.** `web/app/layout.tsx`'s inner `#main-content` is now a `<div>`, not a second `<main>` — `SidebarInset` (vendored, `components/ui/sidebar.tsx`) already renders its own `<main>`, so the previous code nested one `<main>` inside another. `web/components/app-sidebar.tsx` wraps its main destinations in `<nav aria-label="Primary">` and its Settings entry in a second `<nav aria-label="Settings">`, so neither the primary group nor Settings is left outside a navigation landmark.
3. **AC 3 — the code-review fix pass changed a real deviation, not a nitpick: the five new page headings shipped `sr-only` (invisible), directly contradicting this AC's literal "visible `<h1>`" requirement.** All five (`New Team`, `My Teams`, `Starter Teams`, `Settings`, `Team Workspace`) now render with modest, quiet-tool styling (`text-xs font-medium tracking-wide text-muted-foreground uppercase`) rather than `sr-only`, so a sighted user sees them too, without competing visually with `EmptyTitle`'s existing, differently-worded copy.
4. **AC 4 — `RouteFocusAnnouncer` (`web/components/route-focus-announcer.tsx`) ships with a fallback the first pass omitted:** if a destination route has no `#page-heading` (a future route, an error boundary, Next's built-in not-found page — this repo has no custom `not-found.tsx`), focus falls back to `#main-content` instead of being silently dropped. Cross-browser note, not a defect: Chrome/NVDA and Chrome/JAWS are expected to announce a focused `tabIndex={-1}` heading reliably; Safari+VoiceOver is documented elsewhere as less consistent with this exact pattern. Not remediated here — it is a platform limitation of the standard SPA route-announcement technique, not an implementation gap.
5. **AC 5 — no functional keyboard/Esc gap existed; the gap was test coverage,** and it stayed that way: `TranscriptDialog`'s Esc-closes test (added by the implementation pass) initially asserted the exact shape of Base UI's `onOpenChange` callback (`toHaveBeenCalledWith(false)`), but Base UI actually calls it as `(open, eventDetails)` — the test was asserting an argument shape that was never true. Rewritten to assert the dialog's actual disappearance from the accessibility tree (`queryByRole("dialog")` becomes null), mirroring `tests/composer/keyboard.test.tsx`'s established "AC 6 — Esc exits the review editor" pattern rather than the callback's exact arguments.
6. **AC 6 — the ring-vs-background/card contrast test never actually ran before this pass** (the whole suite was red on `jest-axe` first). Once it did, it failed for a real reason: `--background`/`--card` are shadcn's own `oklch(...)` defaults, not hex, and the existing `hexToRgb`/`relativeLuminance`/`contrastRatio` helpers only ever parsed hex. Added a proper OKLab-matrix `oklch → sRGB` conversion (`oklchToRgb255`) and a `contrastRatioOfTokens` wrapper that dispatches on format, rather than hard-coding the two greys' hex equivalents — this measures any future `oklch(...)` token correctly, not just today's achromatic (`C=0`) shadcn greys. All four ring pairs (light/dark × background/card) clear the 3:1 SC 1.4.11 floor.
7. **AC 7 — no runtime/backend change,** as required. The deviation from `EXPERIENCE.md:112-113`'s literal "Task 2 of 4, writer, running" wording is documented in `deferred-work.md`'s existing per-task-progress entry (pointing at the named v2 seam, `deferred-work.md:220`) and here. `web/tests/workspace/run-status.test.tsx` verifies the existing three-state announcement fires correctly — its original fixtures used a shape (`{ id, tasks: [{name}] }`) that did not match the real `RunView`/`TaskPlanView` types (`run_id`/`team_slug`/`team_name`/`result`/`transcript_available`, and `agent_role`/`dependencies` on each task) and would have failed `tsc --noEmit`/`next build`'s type-check the first time either ran; rewritten against the real types via a `makeRun()` helper.
8. **AC 8 — declared, not built.** `web/app/my-teams/page.tsx` and `web/app/starter-teams/page.tsx` remain the Story 2.1 `EmptyState` stubs; Story 2.5 shipped only `api/routers/teams.py` (confirmed: `git show --stat 936340c` touches zero `web/` files). No browse/rename/delete UI was added here. `deferred-work.md`'s new entry was tightened during the fix pass — it originally said these routes have "no interactive UI," which is imprecise (both retain their pre-existing "New Team" CTA button); reworded to name the actual gap (no browse list, rename control, or delete dialog) so a future reader isn't confused by an untrue absolute.
9. **AC 9 — the automated axe guard is now genuinely wired, and it already found a real bug.** The implementation pass's `expect.extend({ toHaveNoViolations })` in `vitest.setup.ts` was a jest-axe API misuse — `toHaveNoViolations` imported from `jest-axe` is already the `{ toHaveNoViolations: fn }` shape `expect.extend` wants, so wrapping it again double-nested it and left every `toHaveNoViolations()` call failing with `expectAssertion.call is not a function`. Fixed to `expect.extend(toHaveNoViolations)`. Once wired correctly, the very first real run caught a genuine, previously-shipped defect: `document-tray.tsx`'s hidden file input (`type="file"`, `sr-only`, `tabIndex={-1}`) had no accessible name at all — fixed with `aria-label="Attach a document"`. Two of the four `tests/a11y/` files (`new-team.test.tsx`, `team-workspace.test.tsx`) also shipped a "mid-conversation"/"completed run" test that was a verbatim copy of the empty/no-run test above it, with a comment admitting the state wasn't actually constructed — both rewritten to drive a real turn (via `tests/composer/harness.tsx`'s `completeFirstTurn`) and a real completed run (via `tests/workspace/harness.tsx`'s `createRunFetchQueue`, queuing a `complete`-status `RunView` directly from `createRun` rather than faking the poll interval) respectively. `settings.test.tsx` now mocks `getKeyStatus` (mirroring `tests/settings/settings-page.test.tsx`'s established pattern) so its axe check runs against the settled provider list, not a permanent loading state.
10. **AC 10 — verified by inspection, not assumed.** Color+label pairing: read `key-check.tsx`, `settings-surface.tsx` (both cite `EXPERIENCE.md:117` or the equivalent convention by name), `run-status.tsx`, `task-list.tsx`, and `build-result.tsx` directly — every status indicator pairs its color with a text label; no counterexample found. DOM/visual order: inspected the six real surfaces' JSX for CSS `order`/flex-`order`/grid-`order` properties that would make visual order diverge from DOM order — none found. No source change made for this AC.
11. **AC 11 — test placement followed the plan:** `web/tests/a11y/` holds only the cross-cutting axe smoke tests; `web/tests/nav/route-focus-announcer.test.tsx` and `web/tests/shell/landmarks.test.tsx` hold the two new shell-level concerns; everything else extends an existing domain-local suite (`tests/shell/routes.test.tsx`, `tests/composer/route.test.tsx`, `tests/workspace/workspace-surface.test.tsx`, `tests/workspace/transcript-dialog.test.tsx`, `tests/theme/contrast.test.ts`). No new or modified file exceeds ~400 lines.
12. **AC 12 — measured, not guessed.** Baseline (`c7a7fac`, before any change): Python **676 passed, 7 skipped**; web **458 passed / 27 files**. After the full implementation + code-review fix pass: Python **676 passed, 7 skipped** (unchanged — no `team_maker/`/`api/` file touched, confirmed by `git status`); web **489 passed / 34 files** (7 new files: `tests/a11y/{new-team,settings,stub-routes,team-workspace}.test.tsx`, `tests/nav/route-focus-announcer.test.tsx`, `tests/shell/landmarks.test.tsx`, plus the new `tests/workspace/run-status.test.tsx`). `npm run lint`, `npx tsc --noEmit`, `npm run build` all clean. Getting to this state required three additional fixes beyond the original 10 code-review patches, all recorded above under their respective ACs: the `oklch()`-unaware contrast helper (AC 6), the `TranscriptDialog` Esc test's wrong assertion shape (AC 5), and `jest-axe`'s `expect.extend` double-nesting bug plus its missing `@types/jest-axe` declaration and `vitest.setup.ts`'s missing `expect` import (AC 9/AC 12) — none of which the original code review could have caught without actually running the suite to green, which was blocked by finding #1 until it was fixed.

### File List

**New files:**
- `web/components/route-focus-announcer.tsx` — focuses `#page-heading` (falling back to `#main-content`) on client-side route change (AC 4)
- `web/tests/a11y/new-team.test.tsx`, `web/tests/a11y/settings.test.tsx`, `web/tests/a11y/stub-routes.test.tsx`, `web/tests/a11y/team-workspace.test.tsx` — cross-cutting axe smoke tests (AC 9)
- `web/tests/workspace/run-status.test.tsx` — verifies the existing three-state `aria-live` announcement (AC 7)
- `web/tests/nav/route-focus-announcer.test.tsx` — `RouteFocusAnnouncer` behavior, including the fallback (AC 4)
- `web/tests/shell/landmarks.test.tsx` — exactly-one-`<main>` and sidebar-nav-landmark regression test (AC 2)

**Modified files:**
- `web/app/globals.css` — `--primary` and `--ring` (light mode only) darkened to `#0D857B` (AC 1)
- `project-docs/ux-designs/ux-team_maker-2026-07-05/DESIGN.md` — `colors.primary`, `colors.ring`, and prose updated to match (AC 1)
- `web/app/layout.tsx` — `#main-content` is now a `<div>`, not a nested `<main>`; mounts `RouteFocusAnnouncer` (AC 2, AC 4)
- `web/components/app-sidebar.tsx` — main destinations and Settings each wrapped in a labelled `<nav>` (AC 2)
- `web/app/my-teams/page.tsx`, `web/app/starter-teams/page.tsx`, `web/app/settings/page.tsx`, `web/components/composer/composer-surface.tsx`, `web/components/workspace/workspace-surface.tsx` — visible `<h1 id="page-heading">` added (AC 3)
- `web/components/workspace/document-tray.tsx` — hidden file input given `aria-label="Attach a document"` (real bug the new AC 9 guard caught)
- `web/tests/theme/contrast.test.ts` — 4.5:1 AA text-floor assertion (AC 1); `oklchToRgb255`/`contrastRatioOfTokens` added so the ring-vs-background/card assertions (AC 6) can measure shadcn's `oklch(...)` tokens
- `web/tests/workspace/transcript-dialog.test.tsx` — Esc-closes-dialog test, asserting the dialog's disappearance rather than the callback's exact arguments (AC 5)
- `web/tests/shell/routes.test.tsx`, `web/tests/composer/route.test.tsx`, `web/tests/workspace/workspace-surface.test.tsx` — page-heading presence/persistence assertions (AC 3)
- `web/vitest.setup.ts` — `jest-axe` wired correctly (`expect.extend(toHaveNoViolations)`, not double-nested); `expect` imported from `vitest` (previously relied on an ambient global `tsc` does not see)
- `web/package.json` / `web/package-lock.json` — `jest-axe` actually installed (not just declared) plus `@types/jest-axe` added (AC 9)
- `project-docs/stories/deferred-work.md` — AC 7's aria-live deviation and AC 8's scope-boundary entries added; the AC 8 entry's "no interactive UI" wording tightened during the fix pass

**Unchanged (as required):**
- `web/components/ui/*` — vendored shadcn output, not touched
- `team_maker/`, `api/` — no runtime/backend change (AC 7)
- `--signal`/`--accent` tokens, the dark-mode `--primary`/`--ring` value — untouched (already AA-compliant)
