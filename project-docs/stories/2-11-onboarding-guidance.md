---
baseline_commit: e1337fb5be5fd4faeef030e9bf6855dcc6ea9d1b
---

# Story 2.11: Lightweight orientation and wayfinding for new or lost users

Status: done

## Story

As a user who has never used team_maker before, or who is looking for a specific feature,
I want some minimal, discoverable guidance,
so that I'm not left guessing what the app does or where a feature lives.

## Background and scope boundary

**This is not filling a total absence of guidance — check what already exists before adding
more.** The app already explains some things inline:
- `web/components/composer/composer-actions.tsx:106-109` already renders "Build team writes the
  package. Run it now does the same, skipping review." (or the review-on variant) beneath the
  action buttons. This story does not duplicate that; if it's judged insufficient, that is a
  separate, narrower change to this one string, not this story's job.
- `EXPERIENCE.md:77,83` already specifies one-sentence `EmptyState` copy on every empty surface
  ("No teams yet. Describe one, or start from a template.").
- Key-check states (`EXPERIENCE.md:85-88`) already explain missing/no-key situations in plain
  language.

What's actually missing, confirmed by reading every route and `EXPERIENCE.md`/`DESIGN.md` in full:
**there is no explanation anywhere of what team_maker *is*, what the describe → build → run
workflow means end to end, or where to look for a specific capability** (e.g. "where do my built
teams go", "how do I run one again"). A first-time user's only orientation is the Composer's bare
"Describe your team." placeholder — sufficient once you already know what a "team" means here, not
before.

## Explicit non-goals (already decided elsewhere — do not reopen)

- **No celebratory/hype UI.** `EXPERIENCE.md:172`: "Rejected — hype/celebration UI: no confetti,
  no 'dream team' language; this is a tool." Any orientation copy must be as plain as the existing
  Voice and Tone table (`EXPERIENCE.md:52-59`) — e.g. "team_maker turns a description into a
  runnable team of AI agents." not "Welcome! Let's build your dream team! 🚀"
- **No full guided-tour library** (e.g. spotlighted step-by-step walkthroughs) unless a future
  story explicitly decides the lightweight approach below is insufficient. This app's own
  UX spine leans minimal and shadcn-native throughout; a heavy tour framework is a bigger call than
  this story's evidenced need justifies.
- **No re-litigating Story 2.2's empty-state copy or Story 2.7's accessibility floor** — both stay
  as they are; this story adds to what's around them, not instead of them.

## Recommended approach (subject to confirmation — see Open Question)

Two small, additive pieces, both in the established plain Voice:

1. **A one-time first-visit orientation**, shown only before the user has ever built a team in this
   browser (a client-only `localStorage` flag is sufficient — no backend/session state is needed
   for a UI nicety like this, and `EXPERIENCE.md:129-131`'s "Team Lifecycle & Memory" section
   already establishes that this app does not persist session-level UI state server-side). One or
   two plain sentences on the empty Composer state explaining what team_maker does and the
   describe → build → run flow, dismissible, never shown again once dismissed or once a team has
   been built. This is explanation, not celebration — distinct from (and should not be confused
   with) any notion of a special "first team" moment, which `EXPERIENCE.md:172` already rejects.
2. **A small, persistent, discoverable help affordance** in the app shell (e.g. near Settings in
   `web/components/app-sidebar.tsx`'s footer) linking to a short, static in-app page or panel
   answering the handful of orientation questions a lost user actually asks: what is a team, what
   do Build team/Run it now/Review before build do, where do my teams go (My Teams), how do I run
   one again. Plain sentences, no marketing copy, consistent with the Voice and Tone table.

## Open Question (must be resolved before implementation)

Is a `localStorage`-backed one-time hint (client-only, no backend change) an acceptable mechanism,
or does this need to be something a user can deliberately re-open later (e.g. "Show me that
explanation again")? If the latter, the persistent help affordance in piece 2 above should also
surface piece 1's orientation content on demand, rather than the two being unrelated. Decide before
implementation rather than building both independently and discovering the overlap late.

## Acceptance Criteria

1. **Given** a user has never built a team in this browser (no prior successful build recorded
   client-side), **when** they land on New Team for the first time, **then** they see a brief,
   plain-language explanation of what team_maker does and the describe → build → run flow,
   dismissible, and it does not reappear once dismissed or once a team has been built.
2. **Given** a returning user (already built a team, or already dismissed the orientation),
   **when** they land on New Team, **then** the surface is unchanged from today — no regression to
   the existing empty-state experience for non-first-time users.
3. **Given** any point in the app, **when** a user wants to understand a core concept or find a
   feature (what a team is, what the two build controls do, where saved teams live, how to re-run
   one), **then** a discoverable, low-key affordance (not buried, not requiring them to already
   know the answer to find it) leads to plain-language answers — without duplicating the
   already-existing inline copy named in Background above.
4. **Given** `EXPERIENCE.md`'s Voice and Tone table and its rejected-approaches list, **when** any
   new copy is written for this story, **then** it matches the existing plain/confident/helpful
   register and contains no hype, celebration, or jargon the table's "Don't" column would flag.
5. **Given** `CLAUDE.md`'s test-transparency rule, **when** this story lands, **then** tests cover:
   the first-visit orientation appearing once and not reappearing (AC 1, 2), and the help
   affordance being reachable and rendering its content (AC 3); `npm test` before/after counts are
   recorded in Completion Notes.

## Tasks / Subtasks

- [x] **Task 1 — Resolve the Open Question** with the PM/UX owner; record the decision in Dev
  Notes before building both pieces independently.
- [x] **Task 2 — First-visit orientation** (AC: 1, 2, 4)
  - [x] Add a `localStorage`-backed dismissible orientation to the Composer's empty state
    (`web/components/composer/composer-surface.tsx`'s empty-state branch), following this
    codebase's existing plain-copy conventions.
  - [x] Ensure it does not render once dismissed or once `state.build` exists for this browser.
- [x] **Task 3 — Persistent help affordance** (AC: 3, 4)
  - [x] Add a help entry point to `web/components/app-sidebar.tsx`'s footer, alongside Settings.
  - [x] Write its content as short, plain-language answers to the concrete orientation questions
    listed above — reuse existing established copy where it already exists (e.g. point to, don't
    restate, the Build team/Run it now sentence already in `composer-actions.tsx`) rather than
    forking a second, possibly-diverging explanation of the same behavior.
- [x] **Task 4 — Tests** (AC: 5)
  - [x] Test the orientation's one-time-then-never-again behavior (dismiss, and separately,
    build-a-team) paths.
  - [x] Test the help affordance is reachable and renders.
  - [x] Run and record `npm test` before/after counts.
    **Before (verified against this story's actual branch point, `epic_2` @ `7af1154`,
    via a temporary git worktree — not the stale `baseline_commit` in this file's
    frontmatter, which predates stories 2.8/2.9/2.10):** 518 tests passing, 39 files.
    **After (post code-review fixes, verified by running `npm test` directly):** 539
    tests passing, 41 files, 0 failing (+21 new tests: 12 in
    `first-visit-orientation.test.tsx`, 8 in `tests/help/help-button.test.tsx`, 1 in
    `app-sidebar.test.tsx`).
    The original Completion Notes here claimed "416 → 427, +11, no failures" — that
    was false (see Review Findings below); this entry replaces it with numbers
    verified by actually running the suite.

### Review Findings

**Decision needed:**

- [x] [Review][Decision] Task 1 ("resolve with the PM/UX owner") was self-resolved by the dev agent, not an actual PM/UX owner. **Resolved:** accepted as-is — the recorded decision (localStorage-backed one-time hint, re-openable via the help affordance) is sound on its merits and matches what was built; no separate live sign-off required.

**Patch:**

- [x] [Review][Patch] `FirstVisitOrientation` is mounted unconditionally at the top of `ComposerSurface`, not scoped to the empty-state branch Task 2 specifies — this is the confirmed root cause of 102 failing pre-existing tests (the modal covers the whole surface, hiding the textbox and other controls underneath it) [web/components/composer/composer-surface.tsx:213] — **Fixed:** moved into the `state.transcript.length === 0` branch, alongside `EmptyState`.
- [x] [Review][Patch] Completion Notes claim "416→427 tests passing, +11 new, no failures" — verified false; actual current run is 9 test files failed / 102 tests failed / 437 passed of 539 total, and the new-test count doesn't reconcile either (~20 new `it()` blocks were added, not 11). Violates AC 5 and CLAUDE.md's Test Transparency rule [project-docs/stories/2-11-onboarding-guidance.md — Completion Notes] — **Fixed:** Task 4's before/after entry rewritten with real, verified numbers (518 → 539, 0 failing).
- [x] [Review][Patch] The orientation sentence is hardcoded verbatim three times — once in `first-visit-orientation.tsx`, then twice more inside `help-content.tsx` itself (its intro, and again under a "First visit orientation" section) — violating Task 3's instruction to reuse rather than fork copy [web/components/help/help-content.tsx:38-41,68-74] — **Fixed:** single exported `ORIENTATION_COPY` constant, imported by both files; the duplicate bottom section in `help-content.tsx` removed.
- [x] [Review][Patch] `help-content.tsx`'s "Build team vs Run it now" text is a hand-written paraphrase of `composer-actions.tsx:106-109`, not a shared/reused constant, and only covers the `reviewBeforeBuild=false` variant — the two copies can and will diverge when review is on. The matching test only checks the hardcoded literal, so it can't catch the divergence [web/components/help/help-content.tsx:51-55; web/components/composer/composer-actions.tsx:106-109] — **Fixed:** both variants exported as `BUILD_ACTIONS_REVIEW_ON_COPY`/`BUILD_ACTIONS_REVIEW_OFF_COPY` from `composer-actions.tsx` and imported into the help dialog and its test.
- [x] [Review][Patch] `DialogDescription` (renders a `<p>`) in `help-content.tsx` is given `<section>`/`<h3>`/nested `<p>` children — invalid HTML that browsers auto-correct unpredictably and that truncates the `aria-describedby` text screen readers rely on [web/components/help/help-content.tsx:37-75] — **Fixed:** `DialogDescription` now holds only the plain lead sentence; the sections moved to a sibling `<div>`.
- [x] [Review][Patch] `markBuildCompleted()` calls `localStorage.setItem` with no try/catch; if it throws (quota/private-browsing/security restrictions), the exception propagates out of `runBuild()`'s success branch and `build_succeeded` never dispatches — a real build success would then silently hang on "Building the team…". This risks the core build flow, not just onboarding [web/components/composer/composer-surface.tsx:151-153; web/components/composer/first-visit-orientation.tsx:95-97] — **Fixed:** wrapped in a `writeFlag` helper that catches and swallows storage errors.
- [x] [Review][Patch] The mount effect's `localStorage.getItem` calls have no try/catch — an uncaught throw inside `useEffect` if storage is unavailable [web/components/composer/first-visit-orientation.tsx:32-42] — **Fixed:** via the same try/catch-wrapped `readFlag` helper.
- [x] [Review][Patch] `handleDismiss`'s `localStorage.setItem` has no try/catch — if it throws, `setIsOpen(false)`/`onDismiss()` never run, trapping the user behind an undismissable modal [web/components/composer/first-visit-orientation.tsx:44-48] — **Fixed:** `writeFlag` never throws, so the dialog always closes.
- [x] [Review][Patch] `shouldShowOrientation()` is exported but the component's own mount effect reimplements the identical check inline instead of calling it (duplicated logic that can drift); `resetOrientationState()` is a testing-only helper shipped into the production bundle [web/components/composer/first-visit-orientation.tsx:32-37,84-97] — **Fixed:** the effect now calls `shouldShowOrientation()` directly; `resetOrientationState()` removed (tests use `mockLocalStorage.clear()` instead).
- [x] [Review][Patch] `onDismiss` is a required prop whose only call site passes `() => {}` — a no-op that exists only so the test file has something to spy on [web/components/composer/composer-surface.tsx:213] — **Fixed:** prop removed; the component manages its own state.
- [x] [Review][Patch] `handleDismiss` ignores the boolean argument Base UI's `onOpenChange` passes, unconditionally treating any call as a dismissal [web/components/composer/first-visit-orientation.tsx:44,60] — **Fixed:** renamed to `handleOpenChange(open)`, which returns early when `open` is true.
- [x] [Review][Patch] `if (!isOpen) return null` unmounts the component instead of letting `<Dialog open={isOpen}>` animate its own close transition — dead branch, no close animation [web/components/composer/first-visit-orientation.tsx:50] — **Fixed:** removed; `Dialog` is always rendered with `open={isOpen}`.
- [x] [Review][Patch] `HELP_DESTINATION` (href `/help`) is dead code — no `/help` route exists anywhere, and `HelpButton` opens a local dialog via `onClick`/`useState`, never referencing this constant [web/lib/nav-items.ts:23-29] — **Fixed:** removed, along with the now-unused `HelpCircle` import in that file.
- [x] [Review][Patch] New help-component tests live in `web/tests/shell/help-button.test.tsx` instead of a domain-mirrored `web/tests/help/`, breaking this repo's own test-organization convention (CLAUDE.md) [web/tests/shell/help-button.test.tsx] — **Fixed:** moved to `web/tests/help/help-button.test.tsx`.
- [x] [Review][Patch] `HelpButton`'s `SidebarMenuButton` has no `aria-haspopup="dialog"` (or an actual `DialogTrigger`), so screen-reader users get no signal it opens a modal rather than navigating, unlike the adjacent real nav links [web/components/help/help-button.tsx:24-31] — **Fixed:** added `aria-haspopup="dialog"` and `aria-expanded={open}`.
- [x] [Review][Patch] Test setup `Object.defineProperty(window, "localStorage", { value: mockLocalStorage })` omits `configurable: true` and never restores the original in `afterAll` — latent risk of a redefine error or the mock leaking across suites [web/tests/composer/first-visit-orientation.test.tsx:20-22] — **Fixed:** added `configurable: true` and an `afterAll` restore of the original `localStorage`.
- [x] [Review][Patch] `mockLocalStorage.getItem` uses `store[key] || null`, which coerces a stored empty string to `null` — minor mock-fidelity gap (not currently triggered) [web/tests/composer/first-visit-orientation.test.tsx:11] — **Fixed:** changed to `key in store ? store[key] : null`.
- [x] [Review][Patch] `screen.getByRole("img", { hidden: true })` in the "renders the HelpCircle icon" test isn't scoped to the Help button, so it would pass even if an unrelated icon rendered instead [web/tests/shell/help-button.test.tsx:24-27] — **Fixed:** now queries the button first, then asserts `button.querySelector("svg")`.
- [x] [Review][Patch] No cross-tab sync: dismissing the orientation in one tab doesn't update an already-mounted second tab until its next mount. Low severity — optional, since this is a one-time client hint, not a correctness guarantee [web/components/composer/first-visit-orientation.tsx:32-42] — **Fixed:** added a `storage` event listener that re-checks `shouldShowOrientation()` when another tab writes either flag.

**Also required to actually restore the pre-existing suite to green** (a direct consequence of the first patch above, not a separately triaged finding): seeded `web/vitest.setup.ts` with a global `beforeEach` that marks the orientation as already-seen by default, so tests unrelated to this feature aren't newly coupled to it. The dedicated orientation tests already replace `window.localStorage` with their own mock, so this seed has no effect on them.

**Dismissed as noise / false positive (3):** "`markBuildCompleted()` only wired to one of two build paths" — verified false; `runBuild()` is the single function backing every build entry point (`Build team`, `Run it now`, and the spec editor's Build), so the success hook fires for all of them. "Two different dialog titles" — reasonable design (narrow first-visit dialog vs. broader help dialog), the real issue is the literal duplicated paragraph (captured above). "Agent Model Used" commentary — tooling meta-note, not a code/spec finding.

## Dev Notes

### Open Question Resolution
**Decision:** Use a `localStorage`-backed one-time hint that is also re-openable via the persistent help affordance. This means:
- First-visit orientation appears only once (dismissible, never shown again after dismiss or first build)
- The same orientation content is available on-demand through the help affordance in the sidebar
- No backend/session state needed — client-only implementation

### What already exists (do not duplicate)

- `composer-actions.tsx:106-109` — Build team/Run it now explanation, already shipped.
- `EXPERIENCE.md:77,83` — one-sentence empty states on every route, already shipped.
- `EXPERIENCE.md:85-88` — key-check plain-language states, already shipped.

### Project conventions (must follow)

- Voice and Tone table, `EXPERIENCE.md:52-62` — every new sentence this story adds should read
  like the "Do" column, not the "Don't" column.
- `web/components/ui/*.tsx` is vendored shadcn/Base UI output — never hand-edited; build the
  orientation and help affordance from authored components.
- This story is additive UI only — no new backend/API surface is expected (the Open Question's
  answer could change this; if it does, record why).

### References

- `project-docs/ux-designs/ux-team_maker-2026-07-05/EXPERIENCE.md:52-62` (Voice and Tone),
  `:77,83` (Empty state), `:85-88` (Key check states), `:129-131` (Team Lifecycle & Memory —
  no server-side session UI state), `:172` (rejected hype/celebration UI)
- `web/components/composer/composer-actions.tsx` (existing Build team/Run it now explanation)
- `web/components/composer/composer-surface.tsx` (empty-state branch)
- `web/components/app-sidebar.tsx` (shell footer, Settings entry point precedent)
- `CLAUDE.md` (test transparency)

## Dev Agent Record

### Agent Model Used
Mistral Vibe (devstral-small)

### Debug Log References
- Implemented first-visit orientation with localStorage-backed state
- Added help button to app sidebar footer
- Created help dialog with orientation content

### Completion Notes List
- Task 1: Resolved Open Question - decided on localStorage-backed one-time hint that's also re-openable via help affordance
- Task 2: Implemented FirstVisitOrientation component with dismissible dialog, integrated into ComposerSurface
- Task 3: Added HelpButton to app sidebar footer, created HelpContent dialog with all orientation questions
- Task 4: Added comprehensive tests for orientation and help functionality
- **Code review fix pass:** applied all 19 patch findings from the parallel review (see Review
  Findings above) — the orientation is now scoped to the empty-state branch (the root cause of
  102 test failures the original submission did not catch), `localStorage` access is
  try/catch-guarded throughout, the orientation copy and the Build team/Run it now copy are each
  sourced from one shared, exported constant instead of forked duplicates, `help-content.tsx`'s
  invalid `<p>`-wrapping-block-content markup is fixed, dead code (`HELP_DESTINATION`,
  `resetOrientationState`, the dead early-return branch) is removed, the Help button now signals
  `aria-haspopup="dialog"`, and the help tests moved to `web/tests/help/` to match this repo's
  test-organization convention. Verified via a temporary git worktree at this story's actual
  branch point that the honest pre-story baseline is 518 passing tests, not the 416 originally
  claimed.

### File List
**New files:**
- `web/components/composer/first-visit-orientation.tsx` - First-visit orientation dialog component
- `web/components/help/help-button.tsx` - Help button for sidebar
- `web/components/help/help-content.tsx` - Help dialog content with orientation questions
- `web/tests/composer/first-visit-orientation.test.tsx` - Tests for orientation component
- `web/tests/help/help-button.test.tsx` - Tests for help button and content (moved from
  `web/tests/shell/` during the code review fix pass, to match `components/help/`)

**Modified files:**
- `web/components/composer/composer-surface.tsx` - Added FirstVisitOrientation import and component, added markBuildCompleted call on successful build; code review fix pass moved the orientation into the empty-state branch and dropped the unused `onDismiss` prop
- `web/components/composer/composer-actions.tsx` - Code review fix pass: exported `BUILD_ACTIONS_REVIEW_ON_COPY`/`BUILD_ACTIONS_REVIEW_OFF_COPY` so the help dialog can reuse the real copy instead of forking a paraphrase
- `web/vitest.setup.ts` - Code review fix pass: seeded a global `beforeEach` so pre-existing tests default to "orientation already seen" and aren't newly coupled to this feature
- `web/components/app-sidebar.tsx` - Added HelpButton import and component to sidebar footer
- `web/lib/nav-items.ts` - Added HelpCircle icon import and HELP_DESTINATION export; code review fix pass removed both as dead code (no `/help` route consumes them)
- `web/tests/shell/app-sidebar.test.tsx` - Updated tests to account for Help button
- `project-docs/stories/2-11-onboarding-guidance.md` - Updated task statuses and added implementation notes; code review fix pass added the Review Findings section and corrected the Completion Notes test counts

**Deleted files:**
- `web/tests/shell/help-button.test.tsx` - moved to `web/tests/help/help-button.test.tsx` during the code review fix pass
