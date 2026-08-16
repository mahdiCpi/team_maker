---
baseline_commit: e1337fb5be5fd4faeef030e9bf6855dcc6ea9d1b
---

# Story 2.8: My Teams — browse, reopen, re-run, rename, delete

Status: done

## Story

As a user,
I want to see the teams I've saved and act on them from My Teams,
so that building a team is not a dead end — I can come back to it later.

## Dependency and scope boundary

**This story is frontend-only.** Story 2.5 ("Named teams — save, browse, rename, delete") shipped
the complete backend — `api/routers/teams.py` with `GET /api/teams/browse`, `POST
/api/teams/save`, `PUT /api/teams/rename`, `DELETE /api/teams/delete`, `GET /api/teams/recent`,
and `POST /api/teams/{team_name}/record-run` — confirmed via `git show --stat 936340c`: zero
files under `web/`. Story 2.7 (Accessibility floor) explicitly declared it would not build this UI
(`project-docs/stories/2-7-accessibility-floor.md` AC 8) and added a `deferred-work.md` entry
naming this exact gap. `web/app/my-teams/page.tsx` today is still the Story 2.1 `EmptyState` stub:
hard-coded "No teams yet. Describe one, or start from a template." with a single "New Team"
button, and no data fetching of any kind (confirmed by reading the file — no `fetch`, no
`useEffect`, no import from `lib/api-client`).

No frontend API client or types exist yet for the teams endpoints either — `web/lib/api-client/`
currently has only `compose.ts`, `keys.ts`, `run.ts`, `transport.ts`, `index.ts`; `web/lib/api-types/`
has only `compose.ts`, `errors.ts`, `keys.ts`, `primitives.ts`, `index.ts`. This story adds both,
following the same pattern `run.ts`/`api-types/run.ts` already establish.

**Read before writing code**, in this order:
1. `project-docs/stories/2-5-named-teams.md` — the full backend contract (endpoints, request/
   response shapes, edge cases already handled server-side: case-insensitive uniqueness, reserved
   names, path-traversal containment, the `record-run` endpoint added specifically for this
   story's re-run flow).
2. `project-docs/stories/2-7-accessibility-floor.md` AC 8 and its `deferred-work.md` entry — this
   story inherits Story 2.7's accessibility floor (headings, landmarks, focus ring, color+label
   pairing, keyboard operability) as a baseline, not a fresh audit.
3. `api/routers/teams.py` (whole file) and `api/schemas.py`'s `TeamView`/`TeamListView`/
   `TeamSaveRequest`/`TeamRenameRequest`/`TeamRecordRunRequest`/`MessageView` — the real response
   shapes.
4. `api/routers/run.py:67-88,186-210` and `api/output.py` — **read this before assuming "reopen a
   team's Workspace" is a one-line link.** See the open technical question below; it is the single
   biggest risk in this story.
5. `web/lib/api-client/run.ts` and `web/lib/api-types/run.ts` — the pattern to mirror for a new
   `web/lib/api-client/teams.ts` / `web/lib/api-types/teams.ts` pair (typed `request()` calls,
   `parseX` validators, bounds mirrored from `api/schemas.py`).
6. `web/components/composer/build-result.tsx` — the existing "Open in workspace" link pattern
   (`Link` + `buttonVariants()`, not the Base UI `Button` `render` prop — see this repo's own
   accessibility regression history with that pattern) this story's row actions should follow.

### Open technical question — saved-team storage vs. Workspace storage are different roots

**This is not a detail; it changes what "reopen a team's Workspace" and "re-run a saved team" can
mean, and must be resolved (not assumed) before implementation.**

- Story 2.5's save flow (`api/routers/teams.py:_team_storage_path`) stores a saved team under
  `SAVED_TEAMS_ROOT/<team_name>` (verbatim `team_name`, not slugified).
- The Team Workspace route (`web/app/teams/[slug]/page.tsx`, Story 2.4) loads a team via `GET
  /api/runs/teams/{team_slug}`, which resolves **only** against `output_root()` — the Factory's
  build-output directory (`api/routers/run.py:83-88,186-210`) — a completely different root from
  `SAVED_TEAMS_ROOT`.
- Nothing in the codebase today copies a saved team back into `output_root()`, and nothing makes
  `GET /api/runs/teams/{team_slug}` aware of `SAVED_TEAMS_ROOT`. So "reopen a saved team's
  Workspace" as literally described in `epics.md`'s Story 2.5 AC cannot work by just linking to
  `/teams/<team_name>` today — that route will 404 unless the original build's output directory
  still exists under `output_root()` with a matching slug, which is not guaranteed (a different
  build session, a cleaned-up output directory, or a team-name-vs.-slug mismatch from
  `slugify_team_name` would all break it).

Whoever implements this story must resolve this explicitly — options include (not prescribed):
(a) have `_load_team_or_404` (or a new lookup) also check `SAVED_TEAMS_ROOT` as a fallback root,
(b) re-copy/re-register a saved team's package into `output_root()` on "reopen", or (c) something
else. This is a legitimate backend change riding along with this otherwise-frontend story, and
should be called out as such rather than silently worked around in the UI. If it turns out the
existing build output is expected to simply still be present in the common case, that assumption
must be stated and tested, not left implicit.

## Acceptance Criteria

1. **Given** `GET /api/teams/browse` returns a `TeamListView` (`{ teams: TeamView[] }`, each with
   `name`, `created_at`, `last_run_at`, `run_count`), **when** a user opens My Teams, **then** the
   page fetches and renders every saved team by name, showing its last-run time (or "never run")
   and run count, replacing the current hard-coded `EmptyState` copy; the empty state ("No teams
   yet. Describe one, or start from a template.") is shown only when the list is genuinely empty,
   not while it is loading.
2. **Given** a team in the list, **when** the user chooses to reopen it, **then** they are taken to
   that team's Workspace — resolving the open technical question above so the link actually loads
   the right team rather than 404ing.
3. **Given** a team in the list, **when** the user chooses to re-run it, **then** the app calls
   `POST /api/teams/{team_name}/record-run` per Story 2.5's contract (updating `last_run_at`/
   `run_count`) as part of that re-run flow, and the updated metadata is reflected in the list
   without a full page reload.
4. **Given** a team in the list, **when** the user renames it, **then** the app calls `PUT
   /api/teams/rename` with `old_name`/`new_name`, surfaces the server's case-insensitive-uniqueness
   and reserved-name rejections in plain language inline (not a raw error), and the list reflects
   the new name immediately on success.
5. **Given** a team in the list, **when** the user deletes it, **then** an explicit confirmation
   dialog names what will be deleted (the team and its saved runs/results, per Story 2.5's AC),
   `DELETE /api/teams/delete?team_name=...` is called only after that confirmation, and the team
   disappears from the list on success.
6. **Given** this project's accessibility floor (Story 2.7), **when** this story lands, **then**
   the new page keeps the existing `<h1 id="page-heading">` (already added by Story 2.7) as the
   sole heading, every new interactive control (row actions, rename input, delete confirmation) is
   fully keyboard-operable, the delete confirmation is a proper dialog (Esc closes it, per this
   codebase's existing Base UI `Dialog` convention), and no new automated axe check
   (`web/tests/a11y/`) regresses — extend or add one for the populated (non-empty) My Teams state,
   since the existing `stub-routes.test.tsx` only covers the empty stub.
7. **Given** `CLAUDE.md`'s test-organization and file-size guidelines, **when** this story adds
   code, **then** new frontend tests live under a feature-appropriate directory (e.g.
   `web/tests/my-teams/`, not a flat addition to `web/tests/shell/`), and no new/modified file
   exceeds ~400 lines without a stated reason for the split.
8. **Given** `CLAUDE.md`'s test-transparency rule, **when** this story is implemented, **then**
   `npm test`, `npm run lint`, `npx tsc --noEmit`, and `npm run build` are all run and their real
   tails recorded in Completion Notes, alongside `pytest -q` if the open technical question above
   required a backend change.

## Tasks / Subtasks

- [x] **Task 1 — Resolve the storage-root question** (AC: 2)
  - [x] Decide and document how a saved team (`SAVED_TEAMS_ROOT`) becomes loadable by
    `GET /api/runs/teams/{team_slug}` (which only reads `output_root()`), or propose the
    alternative the story actually implements.
  - [x] If a backend change is needed, scope it precisely and add/extend `tests/api/`.
- [x] **Task 2 — Add the frontend teams API client** (AC: 1, 3, 4, 5)
  - [x] `web/lib/api-types/teams.ts`: `TeamView`, `TeamListView` types + `parseTeamList`/`parseTeam`
    validators, mirroring `api-types/run.ts`'s pattern (open `string` fields where the server's
    field is intentionally open, explicit bounds mirrored from `api/schemas.py`'s `_MAX_NAME`).
  - [x] `web/lib/api-client/teams.ts`: `listTeams()`, `renameTeam()`, `deleteTeam()`,
    `recordTeamRun()` (and `recentTeams()` if used), each a typed `request()` call per
    `api-client/run.ts`'s pattern; wire into `web/lib/api-client/index.ts`.
- [x] **Task 3 — Build the My Teams list UI** (AC: 1)
  - [x] Replace the static `EmptyState` render in `web/app/my-teams/page.tsx` with a client
    component (`web/components/my-teams/my-teams-surface.tsx`) that fetches
    `listTeams()` on mount, shows a loading state, and falls back to the existing `EmptyState`
    copy only when the list is empty.
  - [x] Each row shows name, last-run (or "never run"), run count.
- [x] **Task 4 — Reopen, re-run, rename, delete actions** (AC: 2, 3, 4, 5)
  - [x] Reopen: link to the team's Workspace using whatever Task 1 decided resolves correctly.
  - [x] Re-run: trigger the existing run flow for that team, then call `recordTeamRun()` and
    refresh that row's metadata in place. **Design refinement recorded in Dev Notes**: "reopen"
    and "re-run" collapse into the same "Open workspace" link — a run needs a goal, which can only
    be entered in the Workspace (unchanged Story 2.4 design) — so `recordTeamRun()` is called from
    `WorkspaceSurface` on run completion, not from a My Teams row.
  - [x] Rename: inline control or dialog; call `renameTeam()`; surface `409`/validation errors in
    plain language (reuse this codebase's existing error-copy conventions, not raw server text).
  - [x] Delete: a confirmation dialog naming exactly what is deleted; call `deleteTeam()` only on
    confirm; remove the row from the list on success.
- [x] **Task 5 — Accessibility** (AC: 6)
  - [x] Verify/extend keyboard operability and dialog Esc-close for every new control.
  - [x] Add an axe smoke test for the populated My Teams state (`web/tests/my-teams/a11y.test.tsx`
    — moved out of `web/tests/a11y/stub-routes.test.tsx` since My Teams is no longer a stub).
- [x] **Task 6 — Tests and verification** (AC: 7, 8)
  - [x] New tests under `web/tests/my-teams/` covering list rendering, reopen, re-run, rename
    (success + rejection), delete (with and without confirmation).
  - [x] Run and record `npm test`, `npm run lint`, `npx tsc --noEmit`, `npm run build` (and
    `pytest -q` if Task 1 touched the backend).

### Review Findings

- [x] [Review][Patch] Memory leak in workspace-surface.tsx — `recordedRunIds` Set grows indefinitely without cleanup [web/components/workspace/workspace-surface.tsx:144-155]
- [x] [Review][Patch] Loading skeleton count mismatch — Shows exactly 2 skeleton items regardless of actual team count [web/components/my-teams/my-teams-surface.tsx:60-63]
- [x] [Review][Defer] No error boundaries — New components lack error boundaries [web/components/my-teams/*.tsx] — deferred, pre-existing pattern in codebase
- [x] [Review][Defer] Type name inconsistency — Frontend uses `TeamMessageView` but backend uses `MessageView` [web/lib/api-types/teams.ts:48] — deferred, pre-existing

## Dev Notes

### What already exists (verified, not assumed)

- Backend: fully shipped, done, tested (`api/routers/teams.py`, `tests/api/test_teams.py`) —
  save/browse/rename/delete/recent/record-run all work today, including path-traversal
  containment, case-insensitive uniqueness (DB-enforced via `PRIMARY KEY COLLATE NOCASE`), WAL
  mode + busy timeout, and reserved-name checks against Epic 3's guessed starter-team names.
- Frontend: nothing. `web/app/my-teams/page.tsx` is the unmodified Story 2.1 stub plus Story 2.7's
  added `<h1 id="page-heading">` and `nativeButton={false}`-style Link-as-button fix (see this
  repo's own commit history around the console-warning fix this story's sibling work applied).
- The Workspace route and its data loader (Story 2.4) are keyed by a build-output slug, not a
  saved-team name — see the Open Technical Question above. Do not assume these two are
  interchangeable without checking.

### Project conventions (must follow)

- `web/lib/api-client/` and `web/lib/api-types/` are split by domain (`compose`, `keys`, `run`);
  add `teams` as a sibling, not folded into an existing file.
- `web/components/ui/*.tsx` is vendored shadcn/Base UI output — never hand-edited.
- A control that navigates (not one that performs an in-place action) should be a real `Link`
  styled with `buttonVariants()`, not the `Button` component's `render` prop — the latter changes
  the accessible role to `button` via Base UI's `nativeButton` ARIA shim, which is wrong for
  something that is semantically a link (confirmed by this codebase's own
  `web/tests/shell/routes.test.tsx` asserting `getByRole("link")` on exactly this kind of control).
- Files ~200–400 lines (CLAUDE.md guideline); split `my-teams-surface.tsx` by row-vs-list concern
  if it grows past that.
- Error copy: plain language, never a raw server exception string — mirror
  `web/lib/api-client/transport.ts`'s `FALLBACK_MESSAGE` pattern for any new error code this story
  introduces.

### Project Structure Notes

Expected new files (naming is a suggestion, not a mandate):
```
web/lib/api-types/teams.ts
web/lib/api-client/teams.ts
web/components/my-teams/my-teams-surface.tsx
web/tests/my-teams/*.test.tsx
```
Modified: `web/app/my-teams/page.tsx`, `web/lib/api-client/index.ts`, `web/tests/a11y/stub-routes.test.tsx`
(or its replacement once My Teams is no longer a stub), `project-docs/stories/deferred-work.md`
(close the gap Story 2.7 opened there).

### References

- `project-docs/epics.md` Story 2.5's AC ("My Teams lists built teams by name so I can reopen a
  Workspace, re-run, or rename a team")
- `project-docs/stories/2-5-named-teams.md` (full backend contract, already done)
- `project-docs/stories/2-7-accessibility-floor.md` AC 8 (scope boundary this story closes)
- `api/routers/teams.py`, `api/routers/run.py:67-88,186-210`, `api/output.py`, `api/schemas.py`
- `web/lib/api-client/run.ts`, `web/lib/api-types/run.ts`, `web/lib/api-client/transport.ts`
- `web/components/composer/build-result.tsx` (Link-as-button pattern)
- `CLAUDE.md` (test organization, test transparency, file size)

## Dev Agent Record

### Agent Model Used
Claude Sonnet 5 (claude-sonnet-5)

### Debug Log References
- `pytest tests/api/test_run.py -k team_plan -q` — 5 passed (2 new fallback tests + 3 existing),
  first run after Task 1's implementation.
- `pytest -q` (full suite) — 678 passed, 7 skipped, both before Task 1 (baseline, matching Story
  2.7's recorded 676 + this story's own +2) and after every later task (unchanged; no `team_maker/`
  or `api/` file touched again after Task 1).
- `npx vitest run` (full web suite) — 3 failures the first time it ran after Task 3
  (`tests/shell/routes.test.tsx`'s three My Teams assertions, all because the route now fetches on
  mount and nothing mocked `listTeams`) — fixed by mocking `@/lib/api-client/teams` in that file
  and making its "offers a working primary action" test async (`await waitFor`), matching the
  Settings row's existing precedent in the same file. 514 passed, 0 failed after.
- Two self-authored test bugs caught and fixed before considering Task 3 done: (1) a test asserted
  the `internal_error` fallback copy ("Something went wrong…") where the server's own authored
  message ("boom") is what actually renders — `transport.ts`'s `toFailure` keeps the server message
  verbatim unless it looks like a leaked internal, which "boom" does not; fixed the test to assert
  the real (correct) behavior instead of guessing wrong. (2) A rename-rejection test asserted the
  plain text "Article Team" was still visible after a failed rename — it is not, because a failed
  rename leaves the row in edit mode (by design, so the user can fix and retry), putting the name
  only inside an `sr-only` label and the rejected draft's input value, not as plain text. Fixed to
  assert the input's value and the *other*, untouched row's name instead.
- `npm run lint`, `npx tsc --noEmit`, `npm run build` — all clean on the final pass.
- **Live, unmocked verification** (not just automated tests) against the actual running
  `uvicorn api.main:app --port 8000` dev process, restarted mid-story to pick up the Task 1
  backend change (it was running without `--reload`): built a real Team Package via
  `PipelineRunner`, saved it (`POST /api/teams/save`), deleted its original build-output directory
  entirely, and confirmed `GET /api/runs/teams/Live%20Check%20Team` still resolved it via the new
  `SAVED_TEAMS_ROOT` fallback (verified the response body, not just a 200). Also exercised
  `record-run`, `rename`, and `delete` for real against the live SQLite DB and filesystem, then
  cleaned up (`browse` confirmed empty again, `git status` confirmed no residue — `data/` and
  `generated_teams/` are gitignored anyway). No live browser click-through was performed — the
  available browser-automation tooling (`playwright-cli`) was not installed in this environment
  (`npx playwright-cli` failed with "could not determine executable to run") and no working
  alternative was found; the populated-list, rename, and delete flows are verified instead by the
  component-level tests in `web/tests/my-teams/` (real components, real API client code, mocked
  `fetch`) plus the live curl-based API verification above, not by a rendered browser session.

### Completion Notes List

1. **AC 2's "open technical question" was real and is now resolved.** `SAVED_TEAMS_ROOT` (Story
   2.5) and `output_root()` (Story 2.4/2.0) are different directory roots, keyed differently
   (verbatim team name vs. a slug) — a saved team's original build output is not guaranteed to
   still exist. Fixed by adding `api/routers/teams.py::resolve_saved_team_path` (a public,
   containment-checked accessor mirroring the existing `_team_storage_path`) and consulting it as a
   fallback from `api/routers/run.py::_load_team_or_404` when the primary `output_root()` lookup's
   `load_team_package` raises `TeamPackageError`. The fallback resolves against the client's raw,
   un-slugged value (matching how `SAVED_TEAMS_ROOT` actually stores directories), and the resolved
   identifier returned in that case is that same raw value, so a later lookup (e.g. `record-run`)
   for the same team resolves the same way again. A fresh build always takes precedence over a
   same-named saved copy (verified by a dedicated test), since the fallback is only consulted after
   the primary lookup fails.
2. **"Re-run" and "reopen" are the same action, by design, not an oversight.** A run needs a goal,
   which can only be entered in the Workspace (Story 2.4, unchanged) — there is no way to
   meaningfully "re-run" a team from a My Teams list row without navigating there. AC 3's actual
   requirement (a re-run updates `last_run_at`/`run_count`) is satisfied by calling
   `recordTeamRun()` from `WorkspaceSurface` itself, once, when a run reaches `status: "complete"`
   — not from My Teams. This call is best-effort and silent: a team reached via a fresh, unsaved
   build 404s (`not_found`) harmlessly, since `recordTeamRun` never rejects
   (`transport.ts`'s `request()` contract) and nothing is surfaced to the user either way. Verified
   with three dedicated tests (`web/tests/workspace/record-run-on-complete.test.tsx`): the call
   fires once on completion, does not fire a second time for the same run id on a later poll tick,
   and a 404 does not disturb the run's own success state or surface a spurious error.
3. **A gap this story's own research flagged as new turned out to already be documented — re-verified,
   not re-discovered.** Story 2.5's "prompted to save" UI (the actual way a team would get into the
   `teams` DB from a completed run in the Workspace) does not exist anywhere in `web/` — confirmed
   by grepping the whole frontend for `teams/save`/`saveTeam`/`TeamSaveRequest`, which found
   nothing except the literal string "Save this team and its results?" inside
   `tests/composer/route.test.tsx`'s "borrows no copy that belongs to another surface" test. This
   is exactly `deferred-work.md:223`'s story-2.4 entry ("omitted, not built... building the prompt
   without the persistence would be a dead affordance"), written 2026-08-09 and still true today —
   Story 2.5 shipped the persistence it was waiting on, but the prompt itself was never
   subsequently built. Not re-recorded as a new entry; this note exists so the next reader
   confirms `:223` is still accurate rather than assuming it was closed once 2.5 landed. This
   story does not build that flow (not in any of its Tasks, and doing so unasked would be scope
   creep) — My Teams' browse/reopen/rename/delete UI is fully built and tested against the
   existing, already-functional backend, verified live via direct `POST /api/teams/save` calls
   rather than a UI that does not yet exist.
4. **`TeamPlanView`'s `status: "complete"` field** (`api/schemas.py:340`) is not modeled in
   `web/lib/api-types/run.ts`'s `TeamPlanView` type — discovered during the live verification above
   (the real response includes it, the frontend type does not). Pre-existing, not introduced by
   this story, and harmless (the frontend parser ignores unknown fields) — noted rather than fixed,
   since `run.ts` is outside this story's stated file list and the omission causes no defect.
5. **File-size guideline**: no new/modified file exceeds ~200 lines (all of
   `my-teams-surface.tsx`, `team-row.tsx`, `delete-team-dialog.tsx`, `api-types/teams.ts`,
   `api-client/teams.ts` are well under CLAUDE.md's ~400-line ceiling). New tests were placed under
   a dedicated `web/tests/my-teams/` directory per AC 7, and the one workspace-side addition
   (`record-run-on-complete.test.tsx`) was deliberately kept as a new, separate file rather than
   added to the already-560-line `workspace-surface.test.tsx`.
6. **Verification tail**: Python `pytest -q` — 678 passed, 7 skipped (baseline 676 + 2 new).
   Web `npx vitest run` — 514 passed, 39 files (0 regressions; +16 net new test files/cases across
   `web/tests/my-teams/` and the one new `web/tests/workspace/record-run-on-complete.test.tsx`).
   `npm run lint` — clean. `npx tsc --noEmit` — clean. `npm run build` — clean, `/my-teams` still
   builds as a static route. Live API verification per the Debug Log above.

### File List

**New files:**
- `web/lib/api-types/teams.ts` — `TeamView`/`TeamListView`/`TeamMessageView` + parsers
- `web/lib/api-client/teams.ts` — `listTeams`/`renameTeam`/`deleteTeam`/`recordTeamRun`
- `web/components/my-teams/my-teams-surface.tsx` — loading/error/empty/populated states
- `web/components/my-teams/team-row.tsx` — one row: open workspace link, rename, delete
- `web/components/my-teams/delete-team-dialog.tsx` — delete confirmation dialog
- `web/tests/my-teams/harness.tsx` — fetch-queue test harness for the teams routes
- `web/tests/my-teams/teams-client.test.ts` — API client tests
- `web/tests/my-teams/my-teams-surface.test.tsx` — component tests (all states + actions)
- `web/tests/my-teams/delete-team-dialog.test.tsx` — dialog behavior + Esc-close
- `web/tests/my-teams/a11y.test.tsx` — axe smoke tests, empty and populated states
- `web/tests/workspace/record-run-on-complete.test.tsx` — record-run-on-completion wiring

**Modified files:**
- `api/routers/teams.py` — added `resolve_saved_team_path`
- `api/routers/run.py` — `_load_team_or_404` falls back to `resolve_saved_team_path`
- `tests/api/test_run.py` — 2 new tests for the fallback (and the "build output still wins" case)
- `web/app/my-teams/page.tsx` — renders `MyTeamsSurface` instead of a static `EmptyState`
- `web/app/starter-teams/page.tsx`, `web/components/composer/build-result.tsx` — `nativeButton`
  console-warning fix (sibling fix requested alongside this story; see git history for the commit
  that introduced it, immediately before this story's work)
- `web/lib/api-client/transport.ts` — `RequestSpec.method` gained `"DELETE"`
- `web/lib/api-types/index.ts`, `web/lib/api-client/index.ts` — wired in the new `teams` module
- `web/components/workspace/workspace-surface.tsx` — calls `recordTeamRun` on run completion
- `web/tests/workspace/harness.tsx` — added `queueRecordRun`
- `web/tests/shell/routes.test.tsx` — mocked `@/lib/api-client/teams`; made the primary-action test
  async
- `web/tests/a11y/stub-routes.test.tsx` — removed the My Teams block (moved to
  `web/tests/my-teams/a11y.test.tsx`)
- `project-docs/epics.md` — Stories 2.8–2.11 added to the Epic 2 roadmap (prior to this story's
  implementation)
