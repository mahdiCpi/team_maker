---
baseline_commit: 93d8638648c20d7201e060e18e43d2892863094d
---

# Story 3.1: Ship baseline starter teams

Status: ready-for-dev

## Story

As the product,
I want curated starter teams included,
so that users can run something immediately.

## Background and scope boundary

**This is the first story of Epic 3 — nothing in this epic exists yet, but several
things it depends on already do.** Check what's already in place before building:

- `team_maker/templates/software_delivery/template.py` is the only registered template today
  (`software_delivery_team`). It establishes the pattern this story extends: a
  `BaseTeamTemplate` subclass with a `_ROLE_DEFAULTS` dict, a `_DEFAULT_TASKS` list, and
  `generate()`/`default_role_names()`/`default_task_names()`.
- `web/app/starter-teams/page.tsx` already exists as a sidebar destination (Story 2.1) but is
  still the original stub: an `EmptyState` reading "No starter teams yet. team_maker will offer
  ready-made templates here."
- `api/routers/teams.py`'s `_RESERVED_STARTER_NAMES` (`starter`, `example`, `demo`, `template`,
  `sample`) is an explicit placeholder. Its own comment says: *"Guessed ahead of Epic 3 shipping
  its real starter-team names; reconcile once it does (see deferred-work.md)."* — and
  `deferred-work.md`'s Story 2.5 entry repeats the same instruction. This story is "once it does."
- **`PipelineRunner._generate_from_template` (`team_maker/pipeline/runner.py:103-113`) is
  hardcoded to `get_template("software_delivery_team")`.** Nothing today lets a request select a
  different registered template — the `template:` key already present (but unused/ignored by
  Pydantic) in `examples/software_delivery_request.yaml` was never wired up. Adding two more
  templates without fixing this would leave them registered but unreachable.

The architecture spine's capability map is explicit about the shape of the fix:
`ARCHITECTURE-SPINE.md`'s Capability Map row for FR-19 reads **"Starter teams (FR-19) | Team
Specs shipped in repo | AD-5, AD-10"** — i.e., the two starter teams are concrete curated
`TeamCreationRequest` YAMLs checked into the repo (the same shape as
`examples/software_delivery_request.yaml`), validated against the same factory Pydantic schema
as any other request (AD-10), not something invented at runtime by the LLM planner (AD-5:
Composer → Factory → Runtime; a starter team skips the Composer entirely).

## Explicit non-goals (owned by Story 3.2 or later — do not build here)

- **No "run" or "Adapt with Composer" action.** Story 3.2 ("Run and adapt a starter team") owns
  selecting a starter, running it via the core (Story 1.5), and opening it pre-loaded in the
  Composer. This story ships the specs, proves they build into valid packages, and lists them —
  it does not wire the Team Workspace or the run button.
- **No broader template library.** The PRD is explicit: `[NON-GOAL for MVP]` — the ~20-domain
  template library is v2 (`prd.md:345`, `addendum.md:44-49`). Ship exactly two: baseline education
  and research/content.
- **No changes to the Composer or the LLM planner path.** Starter teams are template-driven, not
  planner-driven — `desired_roles` is always non-empty for them, so `PipelineRunner.run()` already
  takes the template branch, not `_generate_from_planner`.

## Recommended approach

1. **Make template selection data-driven** (currently the only registered template is ever used,
   full stop): add an optional `template_id` field to `TeamCreationRequest` and have
   `PipelineRunner._generate_from_template` resolve `request.template_id or
   "software_delivery_team"` through the existing registry, instead of the hardcoded string. This
   is additive and backward compatible — a request that omits `template_id` (every existing
   example and test) resolves exactly as it does today.
2. **Extract the shared role/task-building logic before writing two more templates that would
   otherwise copy-paste it a second and third time.** `SoftwareDeliveryTemplate`'s
   `_resolve_routing`, `_build_agent_from_role`, `_build_agents`, `_build_tasks`, and
   `_task_dep_available` (`template.py:241-323`) are generic to any role/task-catalog template,
   not specific to software delivery. Lift them into a shared mixin the three templates all use.
3. **Add two new templates**, each in its own subpackage mirroring `templates/software_delivery/`:
   `baseline_education_team` and `research_content_team`, each with its own curated `examples/*.yaml`
   request.
4. **Add a read-only `GET /api/starters` endpoint** that lists the two shipped specs (name,
   purpose, agent count) — a new, small `api/` surface, deliberately separate from
   `api/routers/teams.py`'s SQLite-backed *saved* teams, because starters are static shipped
   content, not user data.
5. **Replace the Starter Teams page stub** with a real listing fetched from that endpoint,
   following `MyTeamsSurface`'s established loading/error/empty/loaded state pattern.
6. **Reconcile `_RESERVED_STARTER_NAMES`** with the two real starter-team names, closing the
   loop `deferred-work.md` opened.

## Acceptance Criteria

1. **Given** the template registry, **when** `team_maker/templates/__init__.py` is imported,
   **then** two new templates are registered — `baseline_education_team` and
   `research_content_team` — alongside the existing `software_delivery_team`, each implementing
   `BaseTeamTemplate`'s three abstract methods with a non-empty role and task catalog. (FR-19)
2. **Given** a `TeamCreationRequest` naming a new optional `template_id` field, **when**
   `PipelineRunner._generate_from_template` runs, **then** it builds through the named registered
   template instead of the previously-hardcoded `software_delivery_team`
   **and**, given a request that omits `template_id` (including every existing example and test),
   **then** it still resolves to `software_delivery_team` unchanged — no existing behavior
   regresses.
3. **Given** the two curated starter request YAMLs shipped under `examples/`
   (`baseline_education_team_request.yaml`, `research_content_team_request.yaml`), **when** each
   is loaded, validated against `TeamCreationRequest`, and run through
   `PipelineRunner().run(...)`, **then** both produce a `PipelineResult` whose
   `validation.passed` is `True` — each is a valid Team Spec *and* a valid, buildable Team
   Package, mirroring Story 1.4's "a clean package reports pass". (FR-19)
4. **Given** a fresh install with no saved teams, **when** a user opens `/starter-teams`, **then**
   the page lists both starter teams (name + one-line purpose, sourced from a new
   `GET /api/starters`) instead of today's "No starter teams yet" empty state — with loading and
   failed-to-load states following the same pattern `MyTeamsSurface` already established (a
   skeleton while loading, a plain-language message on failure, never a silent blank).
5. **Given** `api/routers/teams.py`'s `_RESERVED_STARTER_NAMES` — a hardcoded placeholder its own
   comment and `deferred-work.md` flag for reconciliation once Epic 3 ships real starter-team
   names — **when** this story lands, **then** the set includes the two real, slugified
   starter-team names, so a user cannot save or rename a team into a name collision with a
   starter.
6. **Given** `CLAUDE.md`'s test-transparency and test-organization rules, **when** this story
   lands, **then**: the two new templates and the `template_id` selection fix have unit tests
   (reorganized into `tests/unit/templates/` — a third template makes the current flat
   `test_templates.py` crowded, per CLAUDE.md's own worked example of when to reorganize), the
   new `/api/starters` endpoint has a test under `tests/api/`, and the frontend listing has a test
   mirroring `web/tests/my-teams/`'s pattern; `pytest`/`npm test` before/after counts are recorded
   in Completion Notes.

## Tasks / Subtasks

- [x] **Task 1 — Make template selection data-driven** (AC: 2)
  - [x] Add `template_id: Optional[str] = Field(None, description=...)` to `TeamCreationRequest`
    (`team_maker/schema/request.py`).
  - [x] Update `PipelineRunner._generate_from_template` (`team_maker/pipeline/runner.py:103-113`)
    to call `get_template(request.template_id or "software_delivery_team")` instead of the
    hardcoded string literal.
  - [x] Leave `examples/software_delivery_request.yaml`'s existing (inert, differently-named)
    `template:` key alone — out of scope; it is a different field that Pydantic already silently
    ignores, and renaming it is not needed for this fix to work.
  - [x] Confirm every existing test/example that omits `template_id` still resolves to
    `software_delivery_team` (regression guard for AC 2).

- [x] **Task 2 — Extract shared role/task-building helpers** (AC: 1, prerequisite for Tasks 3–4)
  - [x] Create `team_maker/templates/role_based.py` with a mixin (e.g.
    `RoleBasedTemplateMixin`) holding the generic parts of
    `SoftwareDeliveryTemplate`: `_DEFAULT_PROVIDER`, `_resolve_routing`,
    `_build_agent_from_role`, `_build_agents`, `_build_tasks`, `_task_dep_available` — lifted
    verbatim from `team_maker/templates/software_delivery/template.py:199,241-323`. These methods
    are already generic over any `_ROLE_DEFAULTS`/`_DEFAULT_TASKS` shape; nothing about them is
    software-delivery-specific.
  - [x] Refactor `SoftwareDeliveryTemplate` to subclass `(RoleBasedTemplateMixin,
    BaseTeamTemplate)`, keeping only its own `_ROLE_DEFAULTS`, `_DEFAULT_TASKS`, and
    `generate()`/`default_role_names()`/`default_task_names()`.
  - [x] Run the existing template tests unchanged first, to confirm the refactor is
    behavior-preserving before building the two new templates on top of it.

- [ ] **Task 3 — Baseline education team template** (AC: 1, 3)
  - [ ] `team_maker/templates/education/__init__.py` (empty/marker) and
    `team_maker/templates/education/template.py`:
    `@register("baseline_education_team") class EducationTeamTemplate(RoleBasedTemplateMixin,
    BaseTeamTemplate)`. See Dev Notes for the concrete role/task catalog to implement.
  - [ ] `examples/baseline_education_team_request.yaml` — a curated request exercising this
    template (`template_id: baseline_education_team`), in the same shape as
    `examples/software_delivery_request.yaml`.
  - [ ] Import the new module in `team_maker/templates/__init__.py` so its `@register` decorator
    fires.

- [ ] **Task 4 — Research/content team template** (AC: 1, 3)
  - [ ] `team_maker/templates/research_content/__init__.py` and `template.py`:
    `@register("research_content_team") class ResearchContentTeamTemplate(RoleBasedTemplateMixin,
    BaseTeamTemplate)`. See Dev Notes for the concrete role/task catalog.
  - [ ] `examples/research_content_team_request.yaml`.
  - [ ] Import in `team_maker/templates/__init__.py`.

- [ ] **Task 5 — `GET /api/starters` read-only listing** (AC: 4)
  - [ ] `api/routers/starters.py`: reads the two shipped YAMLs directly (path resolved relative to
    the repo root, the same style `api/output.py` uses for `output_root()`), validates each via
    `TeamCreationRequest.model_validate(load_yaml(path))`, and returns a small view per starter
    (id, team name, purpose, template_id, agent count). This endpoint never builds a package and
    never touches `output_root()`/the filesystem beyond reading the two source YAMLs — building
    is Story 3.2's job when a user actually selects one to run.
  - [ ] Add `StarterTeamView`/`StarterTeamListView` to `api/schemas.py`, following the existing
    `TeamView`/`TeamListView` shape (`api/schemas.py:404-417`).
  - [ ] Register the router in `api/main.py`: `app.include_router(starters_router, prefix="/api")`,
    matching the existing four-router registration pattern.
  - [ ] Test in `tests/api/test_starters.py`.

- [ ] **Task 6 — Reconcile reserved starter names** (AC: 5)
  - [ ] Update `_RESERVED_STARTER_NAMES` in `api/routers/teams.py:124` to include the two real
    slugified starter-team names (`baseline_education_team`, `research_content_team`), keeping the
    existing generic guesses (`starter`, `example`, `demo`, `template`, `sample`) unless this
    story's implementation proves one of them wrong.

- [ ] **Task 7 — Frontend Starter Teams listing** (AC: 4)
  - [ ] `web/lib/api-types/starters.ts` + `web/lib/api-client/starters.ts`, mirroring
    `teams.ts`'s one-view/one-parser shape (`parseStarterTeam`/`parseStarterTeamList`).
  - [ ] `web/components/starter-teams/starter-teams-surface.tsx`, mirroring
    `web/components/my-teams/my-teams-surface.tsx`'s loading (`Skeleton`) / failed-to-load (plain
    alert text) / loaded states.
  - [ ] Wire it into `web/app/starter-teams/page.tsx`, replacing the current stub `EmptyState`
    (keep an empty-state fallback only for the theoretical case the endpoint returns zero
    starters, e.g. a misconfigured install).
  - [ ] No run/select/"Adapt with Composer" affordance — each listed team is display-only here;
    Story 3.2 adds the actions.

- [ ] **Task 8 — Tests and reorganization** (AC: 6)
  - [ ] Reorganize `tests/unit/test_templates.py` into `tests/unit/templates/` with
    `test_registry.py` (registry-level assertions: registration, unknown-id error), plus one file
    per template — `test_software_delivery.py` (existing content, moved), `test_education.py`,
    `test_research_content.py` — per CLAUDE.md's test-organization rule.
  - [ ] Add a pipeline-level test proving both new example YAMLs build to a passing
    `PipelineResult.validation` (AC 3) — a natural home is `tests/integration/`.
  - [ ] Add `tests/api/test_starters.py`.
  - [ ] Add `web/tests/starter-teams/starter-teams-surface.test.tsx`.
  - [ ] Run `pytest` and `npm test` before and after; record both counts in Completion Notes.

## Dev Notes

### Role/task catalogs (concrete content — implement as specified, not a placeholder)

Nothing in the epics/PRD specifies these personas beyond "education team" and "research/content
team" — these catalogs are this story's own content decision, written concretely so
implementation isn't vague. Follow `_ROLE_DEFAULTS`/`_DEFAULT_TASKS`'s existing dict/list shape
(`software_delivery/template.py:21-197`) for both.

**`baseline_education_team`** — three roles:
- `tutor` (`is_orchestrator=True`) — explains the requested topic at the learner's level; goal:
  give a clear, correctly-leveled explanation, checking understanding as it goes.
- `researcher` — gathers accurate supporting facts and examples on the topic before the tutor
  explains.
- `clarity_reviewer` — checks the tutor's draft for jargon, correctness, and level; simplifies
  where needed.

Tasks (DAG): `research_topic` (researcher, no deps) → `draft_explanation` (tutor, depends on
`research_topic`) → `review_for_clarity` (clarity_reviewer, depends on `draft_explanation`).

**`research_content_team`** — the PRD's "flagship" showcase (`addendum.md:48`), four roles:
- `researcher` — gathers and verifies facts/sources on the topic.
- `writer` — drafts content (article/report) from the research.
- `fact_checker` — verifies claims and citations in the draft.
- `editor` (`is_orchestrator=True`) — edits for clarity, tone, and structure; owns final output.

Tasks (DAG): `research_topic` (researcher) → `draft_content` (writer, depends on
`research_topic`) → `fact_check` (fact_checker, depends on `draft_content`) → `edit_content`
(editor, depends on `fact_check`).

Both examples' `desired_roles`/`default_llm` should follow
`examples/software_delivery_request.yaml`'s shape (anthropic/claude-sonnet-4-6 default, per-role
overrides optional).

### Architecture compliance

- **AD-5 / AD-10** (`ARCHITECTURE-SPINE.md`'s Capability Map): starter teams are Team Specs
  shipped in the repo, validated against the same factory Pydantic schema as any other request —
  not planner-authored. `desired_roles` must be non-empty in both curated YAMLs so
  `PipelineRunner.run()` takes the template branch, never `_generate_from_planner`.
  [[bmad-architecture]]
- **Idempotency contract** (`project-docs/project-context.md`): agent/task YAML generated from
  these templates must be byte-identical across runs (`test_pipeline_is_idempotent`-style
  guarantee). The only permitted nondeterminism is the timestamp fields already carved out
  (`generation_report.md`, `team_config.yaml`'s `generated_at`). Don't introduce anything
  time/random-based in the new templates.
- **Generators stay pure string producers; only `ArtifactWriter.write()` writes to disk.** The new
  `/api/starters` endpoint must not call `PipelineRunner`/`ArtifactWriter` at all — it only reads
  and validates the two source YAMLs. Building a starter into a package is explicitly Story 3.2's
  job, not this story's.
- **Template registration**: both new templates *must* be imported in
  `team_maker/templates/__init__.py` — the `@register` decorator only fires on import
  (`project-docs/project-context.md`, confirmed by `templates/registry.py`'s own docstring).
- **Stale doc, verified against code — do not follow it**: `project-docs/project-context.md`
  claims `AgentSpec.to_dict()` "emits routing under the key `llm`". The actual code
  (`team_maker/domain/models.py:73-85`) intentionally *omits* routing from `to_dict()` entirely —
  its own comment says routing_config.yaml is the single source of truth for LLM config. Trust the
  code, not that doc line; don't add a `routing`/`llm` key to `to_dict()` output for the new
  templates or anywhere else.

### File structure requirements

New files (mirrors existing conventions exactly — see the files cited alongside each):
- `team_maker/templates/role_based.py` (new — shared mixin; see `software_delivery/template.py`)
- `team_maker/templates/education/{__init__.py,template.py}` (new — mirrors
  `templates/software_delivery/`)
- `team_maker/templates/research_content/{__init__.py,template.py}` (new — same)
- `examples/baseline_education_team_request.yaml`,
  `examples/research_content_team_request.yaml` (new — mirrors `examples/software_delivery_request.yaml`)
- `api/routers/starters.py` (new — mirrors `api/routers/keys.py`'s read-only-router shape more
  than `teams.py`'s DB-backed one)
- `web/lib/api-types/starters.ts`, `web/lib/api-client/starters.ts` (new — mirror `teams.ts`)
- `web/components/starter-teams/starter-teams-surface.tsx` (new — mirrors
  `web/components/my-teams/my-teams-surface.tsx`)
- `tests/unit/templates/{test_registry.py,test_software_delivery.py,test_education.py,test_research_content.py}`
  (new — replaces `tests/unit/test_templates.py`)
- `tests/api/test_starters.py`, `web/tests/starter-teams/starter-teams-surface.test.tsx` (new)

Modified (read fully before touching — each already carries other stories' load-bearing comments):
- `team_maker/schema/request.py` (add `template_id` field only — do not touch `_pre_process` or
  any validator)
- `team_maker/pipeline/runner.py` (`_generate_from_template`, lines 103-113 only)
- `team_maker/templates/software_delivery/template.py` (extract to mixin; behavior must not change
  — existing tests are the regression guard)
- `team_maker/templates/__init__.py` (add two imports)
- `api/schemas.py` (add two view models near the existing Teams section, `:400-417`)
- `api/main.py` (add one `include_router` call, matching the existing pattern at `:134-146`)
- `api/routers/teams.py` (`_RESERVED_STARTER_NAMES` only, `:124`)
- `web/app/starter-teams/page.tsx` (swap the stub body for the new surface component)

### Project Structure Notes

- Alignment: every new file lands inside the existing per-template subpackage convention
  (`team_maker/templates/<name>/`), the existing `api/routers/` convention, and the existing
  `web/{lib,components,app}` split — no new top-level directories.
- Detected variance requiring a decision this story makes explicit: `api/routers/teams.py` handles
  *saved* (user, DB-backed) teams; starters are *static, shipped* content with no DB row and no
  `data/` footprint. Keeping them in a separate `starters.py` router avoids conflating the two
  models under one file, and avoids adding starter-specific special-casing into `teams.py`'s
  already-large save/rename/delete/browse surface.

### Testing standards summary

- Generators/templates: unit-tested in-memory, no filesystem (`tests/unit/templates/`).
- The "does it actually build" proof (AC 3) is filesystem-touching and belongs in
  `tests/integration/`, using `tmp_path` per the existing convention — never a real path.
- API: `tests/api/` already has a `conftest.py` fixture pattern (see `test_teams.py` for the
  closest analog); follow it for `test_starters.py`.
- Frontend: `web/tests/<domain>/` mirrors `web/components/<domain>/`, per CLAUDE.md and this
  repo's own convention (`web/tests/my-teams/`, `web/tests/help/`, etc.) — do not add a new file
  under `web/tests/shell/` or similar mismatched location.
- Record `pytest`/`npm test` before/after counts in Completion Notes, verified by actually running
  the suites (not estimated) — Story 2.11's code review caught a fabricated test-count claim; don't
  repeat it.

### Previous story intelligence (2.11, most recent shipped story)

- A prior story's Completion Notes claimed test counts that were later proven false by actually
  running the suite — the fix was to always verify by running the command, not by counting `it()`
  blocks added. Apply that here from the start.
- 2.11's code review found a component mounted unconditionally instead of scoped to the branch its
  own task said to scope it to. Task 7 here is explicit that the education/research listing
  replaces the *existing* stub in `starter-teams/page.tsx`, not something mounted alongside it.

### Git intelligence

Recent history (`epic_2`/`develop`, most recent first: `93d8638`, `3ff560a`, `b57e133`,
`6cc7ab2`, `7af1154`) is entirely Epic 2 story merges and their code-review fix-pass commits. No
prior commit touches `team_maker/templates/`, `api/routers/`, or `web/app/starter-teams/` beyond
their initial creation in Stories 2.1 and 2.5 — this story is the first to modify any of them
since. `epic_3` and this story's branch (`story_3_1`) are both cut directly from `develop` at
`93d8638`, which already includes all of Epic 2.

### References

- `project-docs/epics.md:496-505` (Epic 3, Story 3.1 and 3.2 text)
- `project-docs/prds/prd-team_maker-2026-07-05/prd.md:329-345` (§4.7 Starter Teams, FR-19)
- `project-docs/prds/prd-team_maker-2026-07-05/addendum.md:44-49` (v2 template-library deferral)
- `project-docs/architecture/architecture-team_maker-2026-07-05/ARCHITECTURE-SPINE.md:204-210`
  (Capability Map — FR-19 row)
- `project-docs/ux-designs/ux-team_maker-2026-07-05/EXPERIENCE.md:27-46,68-77,198-205` (Starter
  Teams IA, Team card component, Flow 2 — Omar starts from a starter team)
- `project-docs/stories/deferred-work.md:276` (the `_RESERVED_STARTER_NAMES` reconciliation note)
- `team_maker/templates/software_delivery/template.py`, `base.py`, `registry.py`, `__init__.py`
  (template pattern to extend)
- `team_maker/pipeline/runner.py:62-121` (`PipelineRunner.run`, `_generate_from_template`)
- `team_maker/schema/request.py` (`TeamCreationRequest`)
- `team_maker/domain/models.py` (`AgentSpec`, `TaskSpec`, `GeneratedTeam` — and the stale
  `to_dict()` doc claim noted above)
- `api/routers/teams.py`, `api/schemas.py:400-417`, `api/main.py:134-148`, `api/output.py` (API
  conventions to mirror)
- `web/app/starter-teams/page.tsx`, `web/components/my-teams/my-teams-surface.tsx`,
  `web/lib/api-client/teams.ts`, `web/lib/api-types/teams.ts` (frontend conventions to mirror)
- `CLAUDE.md` (test organization and transparency rules)

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List
- Task 1 complete: Added template_id field to TeamCreationRequest and updated PipelineRunner._generate_from_template. All existing tests pass (369 passed).
- Task 2 complete: Created RoleBasedTemplateMixin with shared helpers and refactored SoftwareDeliveryTemplate to use it. All existing tests pass (369 passed).

### File List
- team_maker/schema/request.py (MODIFIED: Added template_id field)
- team_maker/pipeline/runner.py (MODIFIED: Updated _generate_from_template to use template_id)
- team_maker/templates/role_based.py (NEW: RoleBasedTemplateMixin with shared helpers)
- team_maker/templates/software_delivery/template.py (MODIFIED: Refactored to use RoleBasedTemplateMixin)
- tests/unit/test_template_id.py (NEW: Tests for template_id functionality)
