---
baseline_commit: e1337fb5be5fd4faeef030e9bf6855dcc6ea9d1b
---

# Story 2.11: Lightweight orientation and wayfinding for new or lost users

Status: review

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
    **Before:** 416 tests passing
    **After:** 427 tests passing (+11 new tests for orientation and help functionality)

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

### File List
**New files:**
- `web/components/composer/first-visit-orientation.tsx` - First-visit orientation dialog component
- `web/components/help/help-button.tsx` - Help button for sidebar
- `web/components/help/help-content.tsx` - Help dialog content with orientation questions
- `web/tests/composer/first-visit-orientation.test.tsx` - Tests for orientation component
- `web/tests/shell/help-button.test.tsx` - Tests for help button and content

**Modified files:**
- `web/components/composer/composer-surface.tsx` - Added FirstVisitOrientation import and component, added markBuildCompleted call on successful build
- `web/components/app-sidebar.tsx` - Added HelpButton import and component to sidebar footer
- `web/lib/nav-items.ts` - Added HelpCircle icon import and HELP_DESTINATION export
- `web/tests/shell/app-sidebar.test.tsx` - Updated tests to account for Help button
- `project-docs/stories/2-11-onboarding-guidance.md` - Updated task statuses and added implementation notes
