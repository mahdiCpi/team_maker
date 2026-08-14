---
baseline_commit: 936340c06ffa348b9ef82bd63d4b47c737a2760e
---

# Story 2.6: Settings — keys and providers

Status: done

## Story

As a user,
I want a place to understand my key setup,
so that I can configure providers safely.

## Dependency

**Stories 2.0, 2.1, and 2.3 are all `done` and merged.** This story fills a scope that has been *deliberately left empty* twice already:

1. `project-docs/stories/2-1-app-shell-sidebar-theming.md:69` — Story 2.1's task list states the Settings page ships "the light/dark control **only**. No Key Config path, no provider status, no key-entry field — ever (AC 13)" and backs that with a regression test.
2. `project-docs/stories/2-3-key-check-states-plain-language-errors.md` AC 9 — Story 2.3 built the entire key-status data layer (`GET /api/keys/status`) but explicitly refused to put any of it on Settings, declaring: *"Settings' key-status list, the Key Config path display, and safe-key guidance"* are out of scope and *"`web/tests/shell/routes.test.tsx:85-93` asserts Settings contains nothing key-related and must stay green"* — until now.

Read, in this order, before writing code:

1. `api/routers/keys.py` and `api/keystatus.py` in full — the data this story renders, already built and already correct. **Do not re-derive any of it.**
2. `web/components/composer/key-check.tsx` in full — the established rendering conventions (badge colour/label pairing, `role="status"`, `data-slot` test hooks) and its own doc-comment naming the exact gap this story closes (`key-check.tsx:28-33`).
3. `web/tests/shell/routes.test.tsx:85-93` — the test that currently forbids this story's own content and must be inverted, not deleted.
4. `project-docs/stories/deferred-work.md:187,189,203` — three explicit forward-pointers from Story 2.3's review, each written for whoever picked up this story.

### The core already answers this question. Do not build a second answer.

`GET /api/keys/status` (Story 2.3, `api/routers/keys.py:72-82`) already returns exactly what FR-14 asks Settings to show: `key_config_path`, one `ProviderKeyView` per catalog provider (`name`, `status`, `detail`, `usable`, `env_var`, `fix_hint`, `credential_source`), `load_warnings`, `any_key_present`, and `needs_restart_to_author`. `web/lib/api-client/keys.ts` already exports `getKeyStatus()` wired to it. `deferred-work.md:187` says this outright: *"Story 2.6's Settings surface will want the per-provider list this route already returns, not an aggregate."*

`epics.md:337`'s ownership table row — *"settings (provider + Key Config status, never values) → Story 2.6"* — reads as if a new `api/` group is expected. It is satisfied by **reusing** the existing `/api/keys/status` route. Inventing a parallel `/api/settings/status` endpoint that re-projects the same `registry.classify()` data would be the "measuring a mirror" / second-source-of-truth defect class this codebase has already named and rejected twice (2.3 Dev Notes, "Previous story intelligence" #3). If, after reading the code, a genuine gap is found that the existing route cannot cover, **declare it** rather than quietly adding a route — and if one is added, it must be added to `tests/api/test_secret_containment.py`'s route sweep and `tests/api/test_health.py`'s route count (AC 8).

## Acceptance Criteria

1. **Given** `epics.md:415-422` (UX-DR7, AD-9) and FR-14's consequence line (`prd.md:293-294`) — *"Settings shows the Key Config path, per-Provider key status, the OpenRouter option, and plain guidance on keeping keys safe"* — and given `GET /api/keys/status` already returns every field this requires, **When** this story lands, **Then** `web/app/settings/page.tsx` (currently 17 lines, `ThemeToggle` only) renders, in addition to the existing theme control: the `key_config_path` value, and one row per entry in `providers[]` (provider name, a status word, and `fix_hint` when present) fetched via the existing `getKeyStatus()` (`web/lib/api-client/keys.ts`) — with **zero new backend code** and **zero re-derivation** of availability rules; every word rendered must trace to a field already on `KeyStatusView` (`api/schemas.py:221-239`). (AD-4, AD-9, FR-14)

2. **Given** this route's `overall`/`any_key_present` aggregate is documented as team-less and therefore meaningless as a pass/fail verdict (`api/keystatus.py:48-52`: *"any whole-catalog verdict is meaningless"*), **When** the page renders, **Then** it does **not** show a "you have no keys" / "all good" style banner derived from `overall` or `any_key_present` — a user running only the keyless-local `ollama` provider must not see a false warning. `load_warnings` (problems the server hit *reading* the Key Config file) and `needs_restart_to_author` (a provider whose key changed after the API started and needs a restart before *composing* can use it) **are** surfaced — dropping either at the render boundary is the exact "field that exists, looks load-bearing, and is never read" defect this codebase's own review has already caught twice (`key-check.tsx`'s `Warnings`/`RestartNote` components are the shipped precedent for the copy). (`deferred-work.md:187`)

3. **Given** FR-14/UX-DR7 name "the OpenRouter option" as a thing distinct from the plain per-provider list, and given OpenRouter is an ordinary catalog row (`team_maker/adapters/providers/registry.py`, name `"openrouter"`) that other providers opt into via `openrouter_reachable` — **When** the provider list renders, **Then** the `openrouter` row carries a short explanatory sentence describing the gateway model (one key unlocks many models — `EXPERIENCE.md:127-128`), in addition to its ordinary status badge. This is informational only: **no toggle, no "connect", no affordance that implies the UI can add, edit, or manage a key** — AD-9 and `EXPERIENCE.md:103` ban key entry in the UI outright, with no exception for a single-key gateway.

4. **Given** no plain-language "keeping keys safe" copy exists anywhere in this codebase yet (`EXPERIENCE.md:131` names the requirement but authors no copy for it), **When** Settings renders, **Then** it includes new, authored guidance text in the established Voice register (`EXPERIENCE.md:50-57` — plain, confident, helpful; no hype, no "Configure agent LLM routing parameters"-style jargon) covering at minimum: keep the Key Config file out of version control, never paste or share its contents (chat, tickets, screenshots), and rotate a key at the provider if it may have leaked. This copy has no server source — the dev agent owns its exact wording the same way Story 2.3 owned error copy.

5. **Given** AD-9 and `EXPERIENCE.md:103` ban key entry in the UI outright, and this is the one property a future edit could most easily violate by accident (e.g. adding a "paste your key to verify" convenience field), **When** this story lands, **Then** no `<input>`, `<textarea>`, or other editable control capable of accepting a key value exists anywhere on the Settings page, and this is asserted **by a test**, not left as something merely true by inspection.

6. **Given** `web/tests/shell/routes.test.tsx:85-93` ("Settings page scope (AC 13)") currently asserts `container.textContent` does **not** match `/key|anthropic|openai|gemini|openrouter/i` — the exact property this story's purpose contradicts — **When** this story lands, **Then** that test is **inverted, not deleted**, following the precedent `web/tests/composer/route.test.tsx:91-98`'s inversion set in Story 2.3: assert the real per-provider content renders from a mocked `getKeyStatus()` response, rather than asserting its absence. The rest of that file's shared assertions — `describe.each(ROUTES)`'s "renders its heading" (`data-slot="empty-title"` still equals `"Settings"`, so Settings keeps its `EmptyState` header) and "ships no disabled control on the empty-state routes" (already excludes Settings by name for `ThemeToggle`'s hydration placeholder) — continue to pass unmodified.

7. **Given** CLAUDE.md's test-organization rule — reorganize rather than pile into an existing flat area once a story adds meaningfully new coverage — and given no `web/tests/settings/` directory exists yet, **When** this story adds tests for the new content, **Then** they live in a new `web/tests/settings/` directory (e.g. `settings-page.test.tsx`), leaving `web/tests/shell/routes.test.tsx` scoped to the generic cross-page assertions it already owns.

8. **Given** AC 1 adds no backend route, **When** this story lands, **Then** `tests/api/test_secret_containment.py`'s route sweep, `tests/api/test_health.py`'s authored-route count, and the full Python suite are unaffected — measured baseline on `936340c` (this story's `baseline_commit`): **676 passed, 7 skipped** (`.venv` interpreter, `python -m pytest -q`). If implementation reveals a genuine need for a new `api/` route, that is a scope change to be **declared explicitly** in Completion Notes, not made silently, and it must then be added to the containment sweep and the health-route count.

9. **Given** `DESIGN.md:78-85` bans a second brand hue and custom destructive colours, and the accent (`--signal`/`bg-signal`) is reserved for "live/running" — nothing on Settings runs — **When** implementing, **Then** this story references `--signal`/`bg-signal` zero times (including in comments — Guard B greps raw file text) and introduces no new colour token; `web/tests/theme/signal-token.test.ts:142`'s `SIGNAL_CONSUMER_WHITELIST` stays exactly `["components/workspace/run-status.tsx"]`, and `web/tests/theme/color-scan.ts` stays green unmodified. Status is distinguished by text plus the existing neutral/destructive convention `key-check.tsx` already established — usable renders neutral (`bg-muted`/`text-foreground`), unusable renders `border-destructive/40 text-destructive`, and colour is always paired with a label (`EXPERIENCE.md:117`).

10. **Given** CLAUDE.md's test-transparency rule, **When** this story lands, **Then** `pytest -q`, `npm test`, `npm run lint`, `npx tsc --noEmit`, and `npm run build` are all green, with real before/after counts and command tails pasted in Completion Notes rather than guessed ones. Baselines measured for this story (both on `936340c`, before any change): Python **676 passed, 7 skipped** (`.venv/Scripts/python.exe -m pytest -q`, ~132s); web **439 passed across 26 files** (`npm test -- --run`, vitest 4.1.10, ~53s). Note these are marginally different from Story 2.3's cited baseline (525/7 Python, 339 web tests) because Stories 2.4 and 2.5 landed in between — **use the numbers in this AC**, not 2.3's, as the pre-change reference.

## Tasks / Subtasks

- [x] **Task 1 — Read before writing** (AC: all)
  - [x] `web/app/settings/page.tsx`, `web/components/theme-toggle.tsx`, `web/components/empty-state.tsx` — the current Settings surface, to be extended, not replaced.
  - [x] `web/lib/api-client/keys.ts` + `web/lib/api-types/keys.ts` — the already-shipped client function (`getKeyStatus()`) and types (`KeyStatusView`, `ProviderKeyView`). No new client code should be needed for fetching.
  - [x] `api/routers/keys.py`, `api/keystatus.py`, `api/schemas.py:174-239` in full — the projection this story renders and must not re-derive.
  - [x] `web/components/composer/key-check.tsx` in full — badge/panel/copy conventions to reuse visually (`Panel`, `Message`, `Warnings`, `RestartNote`, `ConfigPath` sub-components; `role="status"`; `data-slot` test hooks), and its doc-comment (`:28-33`) naming this exact gap.
  - [x] `web/tests/shell/routes.test.tsx` in full, especially `:32-36` (the `ROUTES` array) and `:85-93` (the AC-13 guard to invert).
  - [x] `project-docs/stories/2-1-app-shell-sidebar-theming.md:69` and `project-docs/stories/deferred-work.md:187,189,203`.

- [x] **Task 2 — Settings surface: per-provider status + Key Config path** (AC: 1, 2)
  - [x] Follow the New Team / Team Workspace page-shape convention: keep `web/app/settings/page.tsx` a server component exporting `metadata`, delegating interactivity to a new client component (e.g. `web/components/settings/settings-surface.tsx`).
  - [x] Fetch `getKeyStatus()` on mount, following `composer-surface.tsx`'s cancelled-flag guard against a stale response.
  - [x] Render `key_config_path`, the theme control (unchanged), and one row per `providers[]` entry (name, status word via a table/mapping similar to `key-check.tsx`'s `STATUS_WORD`, `fix_hint` when present), reusing the established badge colour/label convention.
  - [x] Do **not** render `overall`/`any_key_present` as a pass/fail verdict (AC 2). Surface `load_warnings` and `needs_restart_to_author` using copy consistent with `key-check.tsx`'s `Warnings`/`RestartNote`.

- [x] **Task 3 — OpenRouter callout** (AC: 3)
  - [x] Add a short explanatory sentence near (or on) the `openrouter` row describing the gateway model, sourced from that same `providers[]` entry — no new data, no entry/toggle affordance.

- [x] **Task 4 — Safe-key guidance copy** (AC: 4)
  - [x] Author new plain-language guidance text (Voice register) covering: keep the file out of version control, never share/paste it, rotate at the provider if leaked.

- [x] **Task 5 — Enforce the no-key-entry invariant** (AC: 5)
  - [x] Confirm no editable control capable of holding a key value exists on the page; add a direct test for it (not an absence-of-text assertion).

- [x] **Task 6 — Tests** (AC: 6, 7, 9, 10)
  - [x] New `web/tests/settings/settings-page.test.tsx`: per-provider rows render from a mocked `getKeyStatus()`; OpenRouter callout renders; guidance copy renders; `load_warnings`/`needs_restart_to_author` render when present and are absent when empty; no-input-field assertion (AC 5); no verdict banner renders from `overall`/`any_key_present` (AC 2) — prove this one by feeding a mocked `no-keys` + all-`ollama` payload and asserting no warning text appears.
  - [x] Invert `web/tests/shell/routes.test.tsx:85-93` per AC 6; confirm the shared `describe.each(ROUTES)` assertions still pass unmodified.
  - [x] Confirm `web/tests/theme/color-scan.ts` and `signal-token.test.ts` stay green unmodified (AC 9).
  - [x] Run and record: `pytest -q`, `pytest tests/api/ -v --tb=short`, `npm test`, `npm run lint`, `npx tsc --noEmit`, `npm run build` — paste real tails and before/after counts (AC 10).

- [x] **Task 7 — Declare, do not silently edit** (AC: 1, 8)
  - [x] Record in Completion Notes: the `epics.md:337` ownership row is satisfied by reusing `GET /api/keys/status`, not a new route — state this reconciliation explicitly.
  - [x] Record whether `key-check.tsx`'s `NO_KEYS` banner (Composer surface, not this story's own) was additionally updated to link to the now-real Settings guidance (`deferred-work.md:189,203` flag this as a natural but **optional** follow-on, not required by this story's ACs) — if touched, say so and why; if left, say so and why.
  - [x] Note any other stale planning-artifact drift found rather than silently fixing it (established precedent, e.g. Story 2.3's Completion Notes) — for example, `team_maker/providers/registry.py` no longer exists; the catalog lives at `team_maker/adapters/providers/registry.py` since Story 0.4, and any planning doc still citing the old path should be flagged, not edited, by this story.

### Review Findings

- [x] [Review][Patch] `statusWord()` renders a raw backend status slug instead of falling back to `provider.detail`, unlike `key-check.tsx`'s documented precedent [web/components/settings/settings-surface.tsx:47-58] — fixed: `statusWord` now takes the full `ProviderKeyView` and falls back to `provider.detail`
- [x] [Review][Patch] Load warnings use `role="alert"` nested inside the outer `role="status"` container, contradicting `key-check.tsx`'s documented rationale for the same content type [web/components/settings/settings-surface.tsx:113] — fixed: `role="alert"` removed, matching the single-top-level-`role="status"` precedent
- [x] [Review][Patch] New file uses `data-testid` test hooks instead of the codebase-wide `data-slot` convention used by 31+ other components including the `key-check.tsx` precedent [web/components/settings/settings-surface.tsx:140,192] — fixed: switched to `data-slot`, tests updated to `querySelector('[data-slot="…"]')`
- [x] [Review][Patch] Provider rows are plain `<div>`s instead of a semantic `<ul>/<li>` list like `key-check.tsx`'s badge list, losing list semantics for assistive tech [web/components/settings/settings-surface.tsx:184-225] — fixed: provider list is now a `<ul>/<li>`
- [x] [Review][Patch] AC 9's color-token test only checks the outer provider-row `<div>`, not the inner status-badge `<span>` that actually carries the `bg-muted`/`border-destructive` classes — the test cannot catch a real regression [web/tests/settings/settings-page.test.tsx] — fixed: tests now assert on the `data-slot="settings-provider-badge"` element
- [x] [Review][Patch] Shared `describe.each(ROUTES)` block renders `SettingsPage` synchronously without awaiting the async `getKeyStatus()` mock resolution, risking act()-warning state updates after the test body returns [web/tests/shell/routes.test.tsx:72-99] — fixed: both assertions now `await waitFor(...)`
- [x] [Review][Patch] AC 5 "no key entry" test checks `queryAllByRole("textbox")` twice under different comments; the "textarea" check never actually runs [web/tests/settings/settings-page.test.tsx] — fixed: duplicate check removed
- [x] [Review][Patch] Only the `usable=true` case is tested for the `data-usable` attribute; no test covers the `data-usable="false"` case [web/tests/settings/settings-page.test.tsx] — fixed: added an `openai`/`data-usable="false"` assertion
- [x] [Review][Patch] `getKeyStatus()` rejection/throw path (the component's `catch` block) has zero test coverage [web/components/settings/settings-surface.tsx:98-101] — fixed: added a `mockRejectedValue` test
- [x] [Review][Patch] `needs_restart_to_author.join(", ")` has no "and" before the last item for 2+ providers, and the plural ("were") branch is untested [web/components/settings/settings-surface.tsx:167-171] — fixed: added `joinWithAnd` helper plus a two-provider test
- [x] [Review][Patch] `KeyStatusView` mock fixtures are duplicated near-identically across `settings-page.test.tsx` and `routes.test.tsx` instead of a shared fixture, risking drift [web/tests/settings/settings-page.test.tsx, web/tests/shell/routes.test.tsx] — fixed: extracted to `web/tests/settings/fixtures.ts`, imported by both
- [x] [Review][Patch] `describe("Settings page scope (AC 13)")` block title still cites the now-superseded AC 13 rule after the test body was inverted, with no note on the Story 2.6 supersession [web/tests/shell/routes.test.tsx:119] — fixed: retitled to `"Settings page scope (Story 2.6, supersedes AC 13)"`
- [x] [Review][Defer] React `key={provider.name}` assumes provider names are unique per response; a duplicate would silently misrender one row [web/components/settings/settings-surface.tsx:190] — deferred, pre-existing (defensive-only; catalog already guarantees unique names)
- [x] [Review][Defer] `cancelled`-flag pattern doesn't abort the in-flight `getKeyStatus()` request on unmount (no `AbortController`) [web/components/settings/settings-surface.tsx:85-113] — deferred, pre-existing (mirrors `composer-surface.tsx`'s established pattern, which this story was explicitly told to follow)
- [x] [Review][Defer] Raw error message shown verbatim on fetch failure; `code`/`fields` on the API result go unused [web/components/settings/settings-surface.tsx:96-100] — deferred, pre-existing (matches the minimal error-surface convention used elsewhere)
- [x] [Review][Defer] No retry affordance when the fetch fails — user is stuck on a static error message [web/components/settings/settings-surface.tsx] — deferred, pre-existing (UX gap beyond this story's ACs)

## Dev Notes

### The contract this story consumes, unchanged

```
GET /api/keys/status → 200 KeyStatusView   (Story 2.3 — api/routers/keys.py:72-82)
```

`KeyStatusView`: `overall` (`"no-keys"|"has-keys"` — not a verdict to render, AC 2), `providers[]`, `key_config_path`, `load_warnings[]`, `any_key_present`, `needs_restart_to_author[]`.
`ProviderKeyView`: `name`, `status`, `detail`, `status_detail`, `usable`, `env_var`, `fix_hint`, `credential_source`.

Frontend: `getKeyStatus()` in `web/lib/api-client/keys.ts`, types + `parseKeyStatus` in `web/lib/api-types/keys.ts` — both already shipped, no changes expected.

### Project conventions (must follow)

- Frontend: `web/components/<feature>/`, kebab-case files, PascalCase exports, one `"use client"` root per surface with `page.tsx` staying a server component that keeps its `metadata` export (the New Team / Team Workspace precedent).
- Colour is always paired with a text label, never colour-only (`EXPERIENCE.md:117`). No new colour token; `--signal`/accent is reserved for "live/running" and Settings has nothing live.
- `components/ui/*.tsx` is vendored shadcn output — never hand-edited. `Badge`/`Card` exist and are unused elsewhere for this purpose; `key-check.tsx` hand-rolls its badge markup instead. Either approach is acceptable — match one, don't invent a third pattern.
- Files ~200–400 lines (CLAUDE.md guideline, not a hard limit). Split the new settings test file by concern if it grows past that.
- Commits: `feat(story-2.6)` for code+tests, `docs(story-2.6)` for this file and `deferred-work.md`. Branch `story_2_6` (already checked out) off `epic_2`.

### Previous story intelligence — defect classes this codebase has actually shipped

Most relevant to this story, from Story 2.3's own ranked list (`2-3-key-check-states-plain-language-errors.md`, Dev Notes):

1. **Measuring a mirror.** Building a second projection of `classify()` in `api/` or `web/` instead of reusing `GET /api/keys/status` is this codebase's most-repeated defect class. Do not do it here.
2. **True by construction.** A test asserting "no warning banner" against a component that never renders one proves nothing — AC 2's test must feed a payload where a naive implementation *would* wrongly show a verdict (e.g. `overall: "no-keys"` with an all-`ollama`, fully-usable provider list) and prove the banner still doesn't appear.
3. **A field that exists, looks load-bearing, and is never read.** `load_warnings` and `needs_restart_to_author` were each dropped at a render boundary once already (Story 2.3's own review caught both). Don't repeat it here on a different surface.
4. **A guard narrower than its claim.** AC 5's "no key entry" property must be a direct assertion (query for input/textarea elements), not an absence-of-text check that a differently-shaped violation could slip past.

### Conflicts between the sources, and how they resolve

| Conflict | Resolution |
|---|---|
| `epics.md:337` implies Settings gets its own `api/` group | Satisfied by reusing `GET /api/keys/status` (AC 1); no new route unless a genuine gap is found and declared. |
| `EXPERIENCE.md:87`'s no-keys banner "Links to Settings guidance" (Composer surface) | Optional follow-on for this story, not a hard AC — see Task 7. The Composer's own copy and tests belong to Story 2.3/2.4's surface. |
| FR-14 names "the OpenRouter option" separately from "per-Provider key status" | Read as a callout on the existing OpenRouter row (AC 3), not a second data source — OpenRouter has no special status field beyond what the catalog already provides. |

### Project Structure Notes

New files (expected — naming is a suggestion, not a mandate):

```
web/components/settings/settings-surface.tsx    # the client component (AC 1-4)
web/tests/settings/settings-page.test.tsx       # its tests (AC 6, 7)
```

Modified: `web/app/settings/page.tsx` (delegates to the new surface component), `web/tests/shell/routes.test.tsx` (AC 6 inversion).

Must **not** change, absent an explicitly declared reason (Task 7): anything under `api/` (AC 1, 8 — no new route expected); `web/lib/api-client/keys.ts` / `web/lib/api-types/keys.ts` (already correct); `web/lib/nav-items.ts` (the Settings nav entry is already wired, `:18-22`); `web/tests/theme/*` guards; `web/components/composer/key-check.tsx`'s copy strings, beyond the optional Task 7 follow-on.

### References

- `project-docs/epics.md:100` (UX-DR7), `:337` (ownership table), `:415-426` (this story's scope)
- `project-docs/prds/prd-team_maker-2026-07-05/prd.md:283-294` (FR-14), `:296-301` (FR-15)
- `project-docs/ux-designs/ux-team_maker-2026-07-05/EXPERIENCE.md:36` (IA), `:50-57` (Voice), `:76` (Key status list component), `:103-104,172-174` (banned patterns), `:117` (colour+label), `:119-131` (Provider & Key Handling, `:127-128` OpenRouter, `:131` guidance line)
- `project-docs/ux-designs/ux-team_maker-2026-07-05/DESIGN.md:78-85` (colour rules), `:110-127` (components)
- `api/routers/keys.py` (whole file), `api/keystatus.py` (whole file), `api/schemas.py:174-239`
- `team_maker/adapters/providers/registry.py`, `team_maker/keyconfig.py`
- `web/lib/api-client/keys.ts`, `web/lib/api-types/keys.ts`, `web/components/composer/key-check.tsx`
- `web/app/settings/page.tsx`, `web/components/theme-toggle.tsx`, `web/components/empty-state.tsx`, `web/lib/nav-items.ts:18-22`
- `web/tests/shell/routes.test.tsx`, `web/tests/theme/color-scan.ts:100`, `web/tests/theme/signal-token.test.ts:142`
- `project-docs/stories/2-1-app-shell-sidebar-theming.md:69`
- `project-docs/stories/2-3-key-check-states-plain-language-errors.md` (AC 9, Dev Notes' ranked defect list)
- `project-docs/stories/deferred-work.md:187,189,203`
- `CLAUDE.md` (test organization, test transparency, file size)

### Verification commands

```bash
# Python (from repo root, using the project's venv)
.venv/Scripts/python.exe -m pytest -q          # baseline: 676 passed, 7 skipped
pytest tests/api/ -v --tb=short                 # make test-api

# Web (from web/)
npm test -- --run   # baseline: 26 files, 439 tests
npm run lint ; npx tsc --noEmit ; npm run build
```

## Dev Agent Record

### Agent Model Used
Mistral Vibe (devstral-small)

### Debug Log References
- TypeScript compilation successful after fixing API response structure (`data` vs `value`)
- Fixed test mocks to use correct `ApiResult` structure
- Added proper test IDs for testability

### Completion Notes List
1. **epics.md:337 ownership row reconciliation**: The `epics.md:337` ownership row ("settings (provider + Key Config status, never values) → Story 2.6") is satisfied by **reusing** the existing `GET /api/keys/status` endpoint. No new route was added. This aligns with AC 1 and AC 8 requirements.

2. **key-check.tsx NO_KEYS banner**: The `key-check.tsx` NO_KEYS banner (line 38-39) currently reads "Add one in your Key Config, or add an OpenRouter key to unlock many models." This was **not updated** to link to Settings guidance. Per `deferred-work.md:189,203`, this is flagged as a natural but **optional** follow-on, not required by this story's ACs. Left unchanged to maintain scope discipline.

3. **Stale planning-artifact drift found**: Multiple planning documents still reference the old `team_maker/providers/registry.py` path (moved to `team_maker/adapters/providers/registry.py` in Story 0.4). Found in: `epics.md:193`, `component-inventory.md:16`, `0-1-llm-provider-port-and-adapters.md:171`, `0-2-remove-provider-name-branching.md:38,113`, `0-4-fold-key-config-into-provider-layer.md:25,142,162,237,312,318`, `1-1-load-keys-report-models.md:31,46,98,136,148`, `1-2-compose-team-spec.md:40,74,138,171`, `0-4-fold-key-config-into-provider-layer.md` (multiple references), `deferred-work.md:7`, `epic-1-course-correction-2026-07-25.md:86`. **Not edited** per Task 7 instruction to "declare, do not silently edit".

4. **No backend changes**: AC 1 and AC 8 compliance confirmed - zero new backend code, zero new routes. All data comes from existing `GET /api/keys/status` endpoint.

5. **AC 10 Verification Results**:
   - Python: `676 passed, 7 skipped` (baseline maintained - no regressions)
   - Web: `456 passed across 27 files` (increased from 439 baseline due to 17 new settings tests)
   - TypeScript: `npx tsc --noEmit` - PASS
   - Lint: `npm run lint` - PASS
   - Build: `npm run build` - PASS (Next.js 16.2.12, compiled successfully)
   - Theme tests: `signal-token.test.ts` (15 passed), `color-literals.test.ts` (45 passed), `contrast.test.ts` (16 passed) - ALL PASS (AC 9)

6. **Code review fix pass (2026-08-14)**: 12 `patch` findings applied — see Review Findings above for the full list. Re-measured after the fix pass:
   - Python: `676 passed, 7 skipped` (`.venv/Scripts/python.exe -m pytest -q`, ~99s) — unaffected, no `api/` files touched
   - Web: `458 passed across 27 files` (`npx vitest run`, ~25s) — +2 tests over the pre-review 456 (a rejected-promise error-path test and a two-provider restart-notice grammar test, both added to close review findings)
   - TypeScript: `npx tsc --noEmit` — PASS
   - Lint: `npm run lint` — PASS
   - Build: `npm run build` — PASS (Next.js 16.2.12, Turbopack, compiled successfully)
   - Theme guards re-run in isolation: `npx vitest run tests/theme` — 83 passed across 4 files, unchanged
   - New file added by the fix pass: `web/tests/settings/fixtures.ts` (shared `KeyStatusView` mock fixtures, replacing the duplication between `settings-page.test.tsx` and `routes.test.tsx`)

### File List
**New files:**
- `web/components/settings/settings-surface.tsx` - Client component for Settings surface (AC 1-4)
- `web/tests/settings/settings-page.test.tsx` - Comprehensive tests for Settings page (AC 6, 7)
- `web/tests/settings/fixtures.ts` - Shared `KeyStatusView` mock fixtures, added by the code review fix pass to remove duplication between `settings-page.test.tsx` and `routes.test.tsx`

**Modified files:**
- `web/app/settings/page.tsx` - Updated to include SettingsSurface component and updated description
- `web/tests/shell/routes.test.tsx` - Inverted AC 13 test per AC 6 requirements; code review fix pass additionally retitled the describe block, awaited the shared `describe.each` assertions, and switched the keys-API mock to a hoist-safe dynamic import of the shared fixture

**Unchanged (as required):**
- `api/` - No new routes added (AC 1, 8)
- `web/lib/api-client/keys.ts` - Existing client code reused unchanged
- `web/lib/api-types/keys.ts` - Existing types reused unchanged  
- `web/components/composer/key-check.tsx` - Copy strings unchanged (optional follow-on noted but not implemented)
- `web/tests/theme/*` guards - Unmodified (AC 9)
