---
baseline_commit: 517ce41bbacfdc4e950ff2c4758046a50e089ad6
---

# Story 0.5: Reconcile the request schema with the documented data model

Status: review

<!-- RECONCILIATION STORY (Epic 0) — see project-docs/stories/reconciliation-notes.md (divergence row 5).
     Primarily a DOCUMENTATION story: project-docs/data-models.md describes the pre-merge schema and
     is explicitly marked STALE. This story brings it in line with the real
     team_maker/schema/request.py. No behavior change to request.py is required or wanted — the
     `planning_llm`/`default_llm` "glossary mismatch" turns out (see Dev Notes) to be two
     intentionally-distinct fields, not a naming collision, so this story resolves it by clarifying
     documentation, not a rename. The full unit suite (185+ tests) must stay green (docs-only changes
     should not affect it, but the definition of done still requires a green run). -->

## Story

As the codebase,
I want `data-models.md` to accurately document the real `TeamCreationRequest` schema (and its
`_pre_process` normalization behavior), and the `planning_llm`/`default_llm` naming to be clearly
explained rather than ambiguous,
so that downstream stories (Epic 1+) have a trustworthy schema contract instead of a stale one (AD-10).

## Acceptance Criteria

1. **Given** `project-docs/data-models.md` (dated 2026-07-04, pre-merge, marked `STALE` since
   2026-07-12) and the real `team_maker/schema/request.py`, **When** reconciled, **Then**
   `data-models.md`'s §1 Input Schema table documents every current `TeamCreationRequest` field —
   including `planning_llm`, `framework`, `state_backend`, `git_account`, `sandbox`, `desired_tasks`,
   `suggested_tools`, `default_llm`, `notifications`, `context_dir`, `model_registry` — with type,
   required/default, and validation notes, and documents the four other models
   (`GitAccountConfig`, `NotificationConfig`, `ToolSuggestion`, `SandboxConfig`, `TaskHint`) that
   `data-models.md` doesn't mention today. The stale banner is removed. (AD-10)
2. **Given** `TeamCreationRequest._pre_process` (a `@model_validator(mode="before")` performing five
   distinct normalizations: stack dict-flattening, `auxiliary_resources_dir → context_dir` aliasing,
   `notification_channels.telegram → notifications.telegram_*` mapping, `suggested_tools →
   RoleDefinition.tools` promotion via a fixed `_REGISTRY_TOOLS` allow-list, and `model_registry`
   string-reference resolution for `default_llm`/`planning_llm`/per-role `llm`), **When**
   documented, **Then** `data-models.md` gains a new section describing each normalization's input
   shape → output shape, so a reader doesn't have to reverse-engineer `_pre_process` from source.
   (AD-10)
3. **Given** the claimed "glossary mismatch" between `planning_llm` and `default_llm` (per
   `reconciliation-notes.md` divergence row 5 and the current stale banner), **When** investigated,
   **Then** the finding is recorded accurately: they are **two intentionally distinct fields**
   (`planning_llm` — the LLM `team_maker`'s own planner uses to infer agents/tools/topology from
   `purpose`, spine-equivalent to the future Composer's model; `default_llm` — the per-agent fallback
   when a role has no `llm` override), evidenced by `_pre_process` line 346 resolving **both**
   independently via `model_registry`, and by the LLM routing resolution order (`role.llm →
   request.default_llm → _DEFAULT_PROVIDER`) never involving `planning_llm` at all. **Then**
   `data-models.md` documents both fields with a one-line note explaining why they are separate (not
   a rename — renaming either would be a breaking schema change for zero benefit, since no actual
   collision exists). No code change to `request.py`'s field names. (AD-10)
4. **Given** the full unit suite (≥185 passed) and non-live integration suite (20 passed) pass today,
   **When** this story's (documentation-only) changes land, **Then** they still pass unchanged — no
   `.py` file's runtime behavior is touched. (AD-10)

## Tasks / Subtasks

- [x] **Task 1 — Rewrite §1 Input Schema to match the real schema** (AC: 1)
  - [x] Replace `data-models.md`'s `TeamCreationRequest` table with the full current field list
    (21 fields, verified by direct count against `team_maker/schema/request.py` lines 174-269 —
    the story's "23 fields" estimate was off; the transcribed table itself was accurate).
  - [x] Add new tables for `GitAccountConfig`, `NotificationConfig`, `ToolSuggestion`,
    `SandboxConfig`, `TaskHint` (same table format as the existing `RoleDefinition`/`ProviderConfig`
    tables) — field, type, required, default, notes.
  - [x] Note in `RoleDefinition`'s section (or a footnote) that a role dict may also carry an
    **input-only** `suggested_tools` key (list of tool names) consumed by `_pre_process` step 4 and
    promoted into `tools` — it is not a declared `RoleDefinition` field and does not survive into the
    validated model or `AgentSpec`.
  - [x] Remove the `> ⚠️ STALE` banner at the top of the file once the rewrite is verified against
    the live source.

- [x] **Task 2 — Document `_pre_process`'s five normalizations** (AC: 2)
  - [x] Add a new "§1a. Input normalization (`_pre_process`)" section (or fold into §1) covering, in
    order: (1) `stack` dict → flattened string (drops values that look like a placeholder — start
    with `"deferred"` — or a bare snake_case token); (2) `auxiliary_resources_dir` → `context_dir`
    alias (only applied if `context_dir` wasn't already set); (3)
    `notification_channels.telegram.{enabled,credentials}` → `notifications.telegram_*` fields
    (only when `telegram.enabled` is true; existing `notifications` values win via `setdefault`);
    (4) `suggested_tools` on a role dict → `RoleDefinition.tools`, filtered through the fixed
    `_REGISTRY_TOOLS` allow-list (git_account, code_writer, test_runner, linter, context_reader,
    shell, filesystem, docker_runner, web_search, http_client, ci_tool, code_reader, state_reader,
    state_writer) — unrecognized names are silently dropped, and this only fires when the role has
    no `tools` already set; (5) `model_registry` string-reference resolution — a string value for
    `default_llm`, `planning_llm`, or any role's `llm` that matches a key in `model_registry` is
    replaced with that entry's `provider`/`model`/`api_key_env`/`base_url` fields inline, before
    normal field validation runs.

- [x] **Task 3 — Resolve the `planning_llm`/`default_llm` note** (AC: 3)
  - [x] Add the finding (two distinct fields, not a collision) to `data-models.md` per AC 3 — a short
    callout box or table footnote, not a rename.
  - [x] Optional, low-risk clarifying touch to `team_maker/schema/request.py`: strengthen the
    existing one-line comments above `planning_llm` (`# LLM used by team_maker to infer agents,
    tools, and topology`) and `default_llm` (`# Per-agent LLM fallback`) if they need it — they
    already correctly distinguish the two, so this is likely a no-op; do not rename either field or
    add a `model_config` alias, since no consumer actually confuses them (verified: no test or code
    path treats them interchangeably). **Confirmed no-op** — existing comments already correctly
    distinguish the two fields; left `request.py` untouched.
  - [x] Update `reconciliation-notes.md`'s divergence-table row 5 status (or add a one-line note)
    recording that the "glossary mismatch" was investigated and resolved as documentation, not code.

- [x] **Task 4 — Verify nothing broke** (AC: 4)
  - [x] Run `python -m pytest tests/unit -q` → 203 passed (baseline before and after the docs edit;
    exceeds the ≥185 expectation, confirms no accidental edit crept into `request.py`).
  - [x] Run `python -m pytest tests/integration -k "not live" -q` → 20 passed (matches baseline).
  - [x] Task 3's optional `request.py` comment tweak was not made (confirmed no-op), so the `ruff
    check` sub-step does not apply — no `.py` file was touched.

## Dev Notes

### What this story is (and is not)
- **Is:** a documentation reconciliation — `data-models.md` catches up to the real,
  already-shipped `request.py` schema (grown substantially since the merge), plus a small, accurate
  write-up of `_pre_process`'s normalization behavior and the `planning_llm`/`default_llm` question.
- **Is NOT:** a schema redesign, a field rename, or any change to validation/normalization behavior.
  This story produces **zero functional diffs** to `request.py` (the one "optional" sub-task is a
  comment tweak at most). It is also NOT the place to add `model_registry`/`_pre_process` test
  coverage gaps (out of scope — flag as a documentation TODO if desired, don't implement).

### Current state — the real `TeamCreationRequest` (read before writing docs)
Transcribed from `team_maker/schema/request.py`, lines 174-269 (23 fields):

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `team_name` | str | ✅ | — | min_length 2; regex `^[a-zA-Z][a-zA-Z0-9_ \-]*$`; stripped |
| `purpose` | str | ✅ | — | min_length 10 |
| `output_path` | str | ✅ | — | non-empty after strip |
| `stack` | str? | — | None | may arrive as a dict, flattened by `_pre_process` |
| `constraints` | list[str] | — | `[]` | passed through to docs/report |
| `planning_llm` | `ProviderConfig` | — | anthropic/claude-sonnet-4-6/`ANTHROPIC_API_KEY` | LLM the **planner** uses to infer agents/tools/topology — distinct from `default_llm` |
| `framework` | `FrameworkChoice` enum | — | `crewai` | `crewai` \| `langgraph` \| `autogen` |
| `state_backend` | `StateBackend` enum | — | `file` | `file` \| `vector` \| `both` |
| `git_account` | `GitAccountConfig`? | — | None | enables a `GitAccountTool` for agents that need it |
| `sandbox` | `SandboxConfig` | — | `SandboxConfig()` | Docker sandbox for tool execution |
| `desired_roles` | list[`RoleDefinition`] | — | `[]` | role hints; empty ⇒ planner infers all roles; names must be unique (`check_unique_role_names`) |
| `desired_tasks` | list[`TaskHint`] | — | `[]` | explicit task plan; if provided, planner uses these as-is |
| `suggested_tools` | list[`ToolSuggestion`] | — | `[]` | custom tools the planner may assign; stubs generated in `tools.py` |
| `default_llm` | `ProviderConfig`? | — | None | fallback LLM for roles without their own `llm` — distinct from `planning_llm` |
| `notifications` | `NotificationConfig`? | — | None | webhook/email/Telegram alert config |
| `context_dir` | str? | — | None | must be an existing directory (validated, resolved to absolute path); aliased from `auxiliary_resources_dir` |
| `model_registry` | dict[str, Any]? | — | None | named LLM configs; string refs in `default_llm`/`planning_llm`/role `llm` resolve to inline `ProviderConfig` fields before validation |
| `documentation_level` | `DocumentationLevel` enum | — | `standard` | `minimal` \| `standard` \| `full` \| `detailed` (data-models.md was also missing `detailed`) |
| `overwrite` | bool | — | False | allow overwriting a non-empty output dir |
| `tags` | list[str] | — | `[]` | free-form labels |
| `metadata` | dict[str, Any] | — | `{}` | free-form; carried into `GeneratedTeam.metadata` |

Note: `data-models.md` today also lists a `template: TeamTemplateId` field and a top-level `tools:
list[str]` field that do **not** exist on the current `TeamCreationRequest` (verify against source
during the rewrite — they may be further pre-merge drift to drop, not just additions to make).

### `_pre_process` — five normalizations (see Task 2 for the write-up plan)
Full source: `team_maker/schema/request.py` lines 271-354. Read it directly before writing the docs
section — do not paraphrase from memory; the exact `_REGISTRY_TOOLS` allow-list and the `setdefault`
(existing-value-wins) semantics in the Telegram mapping both matter and are easy to get subtly wrong.

### The `planning_llm` / `default_llm` finding (AC 3)
Investigated directly: PRD §3 Glossary (`project-docs/prds/prd-team_maker-2026-07-05/prd.md`) defines
no term named `planning_llm` or `default_llm` at all — the "glossary mismatch" description in the
stale banner is imprecise. What's actually true: these are **two different, independently-configured
LLM slots** by design —
- `planning_llm` powers `team_maker`'s own plan-inference step (today: `llm/planner.py`'s
  `TeamPlanner`) — conceptually the pre-plan ancestor of the spine's future Composer.
- `default_llm` is the fallback for agent roles in the generated team that don't specify their own
  `llm` (see `data-models.md`'s existing §3 "LLM routing resolution order":
  `role.llm → request.default_llm → _DEFAULT_PROVIDER`; `planning_llm` never appears in that chain).
`_pre_process` (line 346) resolves `model_registry` references for **both** independently, which
would make no sense if they were meant to be the same field. **Resolution: document, don't rename.**

### Architecture constraints (binding)
- **AD-10 — the schema is the contract; Composer output must pass the factory schema.**
  `data-models.md` being accurate is a prerequisite for Epic 1's Composer work (Story 1.2) to target
  the real schema instead of a stale description. [Source: ARCHITECTURE-SPINE.md#AD-10]

### Project conventions (must follow — from project-context.md)
- If the optional `request.py` comment tweak (Task 3) is made: `from __future__ import annotations`
  already present; ruff line-length 100 clean; no behavior change.
- Markdown docs: match the existing `data-models.md` table style (`| Field | Type | Required |
  Default | Notes |`) for consistency with the parts that are already correct (§2-§5 are current and
  should be left as-is).

### Testing standards
- This is a documentation story; the "test" is the accuracy of the transcription against
  `team_maker/schema/request.py`'s actual source, plus confirming the full suite is unaffected.
- Definition of done: `python -m pytest tests/unit -q` green (≥185, unchanged) +
  `python -m pytest tests/integration -k "not live" -q` green (20, unchanged).

### Project Structure Notes
- **Modified:** `project-docs/data-models.md` (rewrite §1, add new model tables and the
  `_pre_process` section, remove the stale banner). §2 (domain model), §3 (LLM routing order), §4
  (output contract), §5 (task dependency graph) are already accurate — verify but don't need a
  rewrite.
- **Modified (maybe):** `project-docs/stories/reconciliation-notes.md` (one-line status note on row
  5). **Modified (optional, no behavior change):** `team_maker/schema/request.py` comments only.
- No new files, no package changes — this story touches zero `team_maker/` runtime behavior.

### References
- [Source: project-docs/epics.md#Epic-0, #Story-0.5] — story + ACs (AD-10)
- [Source: project-docs/stories/reconciliation-notes.md] — divergence row 5
- [Source: project-docs/data-models.md] — the file being rewritten, incl. its own stale banner's
  field list (a starting checklist, verify each against source rather than trusting it verbatim)
- [Source: project-docs/prds/prd-team_maker-2026-07-05/prd.md#3-Glossary] — confirms no
  `planning_llm`/`default_llm` glossary term exists; the mismatch is documentation-only
  imprecision, not a real naming collision
  - [Source: project-docs/architecture/architecture-team_maker-2026-07-05/ARCHITECTURE-SPINE.md#AD-10]
- [Source: team_maker/schema/request.py (full file, esp. lines 29-52, 55-160, 167-269, 271-354)]
- [Source: tests/unit/test_schema.py, test_model_registry.py] — confirms the currently-tested subset
  of schema/validator behavior, to avoid documenting something that's actually untested/unverified as
  if it were a guaranteed contract

## Dev Agent Record

### Agent Model Used

Claude Sonnet 5 (claude-sonnet-5)

### Debug Log References

- Verified field count directly against `team_maker/schema/request.py` lines 174-269: 21 fields
  (the story's "23 fields" phrasing in Task 1 was an overcount — the transcribed field table itself
  was accurate and used as-is).
- Confirmed `TeamTemplateId`/top-level `tools: list[str]` are not fields on the current
  `TeamCreationRequest` (pre-merge drift) — dropped from the rewritten table with an explanatory note
  rather than silently disappearing.
- Confirmed `ProviderConfig` gained a `base_url` field (for Ollama) not present in the stale
  `data-models.md` — added it to the table.
- Baseline test run before any edit: `pytest tests/unit -q` → 203 passed; `pytest tests/integration -k
  "not live" -q` → 20 passed. Re-ran identically after the docs edit — same counts, confirming the
  change is purely additive to documentation.

### Completion Notes List

- Rewrote `project-docs/data-models.md` §1 (`TeamCreationRequest` input schema) against the live
  `team_maker/schema/request.py`: full 21-field table with accurate required/default/notes, five new
  model tables (`GitAccountConfig`, `NotificationConfig`, `ToolSuggestion`, `SandboxConfig`,
  `TaskHint`), a footnote on the input-only `suggested_tools` role key, an updated `ProviderConfig`
  table (added `base_url`), and updated Enums (added `DocumentationLevel.detailed`, replaced the
  removed `TeamTemplateId` with the current `FrameworkChoice`/`StateBackend` enums). Removed the
  `⚠️ STALE` banner.
- Added new §1a documenting all five `_pre_process` normalizations (stack flattening,
  `auxiliary_resources_dir` aliasing, Telegram notification mapping, `suggested_tools` promotion via
  the `_REGISTRY_TOOLS` allow-list, and `model_registry` reference resolution) plus a dedicated
  `planning_llm` vs `default_llm` note recording that they are two intentionally distinct,
  independently-resolved LLM slots — not a naming collision — per AC 3's investigation.
  §2-§5 (domain model, LLM routing order, output contract, task dependency graph) were verified
  accurate and left unchanged.
- Updated `reconciliation-notes.md` divergence-table row 5 with a resolution note (documentation,
  not code).
- Skipped the optional `request.py` comment tweak (Task 3) — confirmed a no-op, existing comments
  already correctly distinguish the two LLM fields. Zero `.py` files touched; zero behavior change.
- Full unit (203 passed) and non-live integration (20 passed) suites confirmed green before and
  after the change.

### File List

- Modified: `project-docs/data-models.md`
- Modified: `project-docs/stories/reconciliation-notes.md`

## Change Log

- 2026-07-25 — Implemented Story 0.5: rewrote `data-models.md` §1 against the live
  `team_maker/schema/request.py` (21-field `TeamCreationRequest` table, five new model tables,
  input-only `suggested_tools` footnote, updated `ProviderConfig`/Enums, removed the stale banner),
  added §1a documenting `_pre_process`'s five normalizations and the `planning_llm`/`default_llm`
  finding, and updated `reconciliation-notes.md` row 5. No `.py` files changed. Full unit (203) and
  non-live integration (20) suites verified green before and after. Status → review.

- 2026-07-12 — Story drafted via create-story context engine (line-by-line comparison of
  `data-models.md` against the live `team_maker/schema/request.py`, full transcription of all 23
  `TeamCreationRequest` fields and the five `_pre_process` normalizations, and a direct investigation
  of the PRD glossary that found the "planning_llm/default_llm mismatch" is documentation imprecision
  — they are two intentionally distinct, independently-resolved LLM slots, not a naming collision —
  so scoped this story as docs-only with no schema rename). Status → ready-for-dev.
