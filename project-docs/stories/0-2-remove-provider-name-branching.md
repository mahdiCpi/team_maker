---
baseline_commit: 7c158cf
---

# Story 0.2: Remove provider-name branching from model mapping

Status: review

<!-- RECONCILIATION STORY (Epic 0) — see project-docs/stories/reconciliation-notes.md (divergence row 2).
     Behavior-preserving refactor of team_maker/llm/mapper.py. The existing unit tests in
     tests/unit/test_planner_mapper.py assert _infer_provider / _resolve_routing behavior directly and
     MUST stay green. Full suite (182) must stay green. -->

## Story

As the codebase,
I want provider/model resolution in `mapper.py` to be driven by data instead of `if`-chains,
so that no module branches on provider name or model-name prefix (AD-1/AD-8) and the behavior stays
identical.

## Acceptance Criteria

1. **Given** `team_maker/llm/mapper.py::_infer_provider`, which today branches with
   `if m.startswith("gpt-"...) / "grok-" / "claude-"` else `"ollama"`, **When** refactored, **Then** the
   mapping lives in a module-level **data table** (prefix → provider) and the function is a table lookup
   with the same fallback (`ollama`); no `if`/`elif` chain on prefixes remains. (AD-1, AD-8)
2. **Given** `team_maker/llm/mapper.py::_resolve_routing`, which today picks `api_key_env` via
   `"OPENAI_API_KEY" if provider == "openai" else "XAI_API_KEY" if ... else None`, **When** refactored,
   **Then** the provider→env-var mapping lives in a module-level **data table** and the lookup returns the
   same values (openai→`OPENAI_API_KEY`, xai→`XAI_API_KEY`, anthropic→`ANTHROPIC_API_KEY`, else `None`);
   no `if provider == ...` chain remains. (AD-1, AD-8)
3. **Given** the existing tests in `tests/unit/test_planner_mapper.py` (they call `_infer_provider` and
   `_resolve_routing` directly and assert exact provider/env-var results), **When** the refactor lands,
   **Then** they pass **unchanged**, and the full unit suite stays green (≥182 passed).
4. **Given** behavior, **When** refactored, **Then** it is a **pure structural change**: identical
   provider inference for every model string, identical routing/`api_key_env`, identical
   `_DEFAULT_ROUTING` fallback and `default_llm` handling. No functional change.
5. **Scope guard:** do **not** unify these tables with `team_maker/providers/registry.py` (Story 1.1's
   key catalog) in this story — that catalog currently disagrees on env-var names (`GOOGLE_API_KEY` vs the
   adapters' `GOOGLE_AI_API_KEY`) and omits `xai`; consolidating the two catalogs is **Story 0.4**. Keep
   the tables local to `mapper.py`, with a comment pointing at Story 0.4.

## Tasks / Subtasks

- [x] **Task 1 — Data table for model-prefix → provider** (AC: 1, 4)
  - [x] Add a module-level ordered data structure, e.g.
    `_MODEL_PREFIX_PROVIDERS: tuple[tuple[tuple[str, ...], str], ...]` = `((("gpt-","o1-","o3-","o4-"),
    "openai"), (("grok-",), "xai"), (("claude-",), "anthropic"))`, plus `_FALLBACK_PROVIDER = "ollama"`.
  - [x] Rewrite `_infer_provider(model)` to lowercase then loop the table with `m.startswith(prefixes)`
    (str.startswith accepts a tuple), returning the matched provider or the fallback. Keep the signature.

- [x] **Task 2 — Data table for provider → api_key_env** (AC: 2, 4)
  - [x] Add `_PROVIDER_ENV_VARS: dict[str, str]` = `{"openai": "OPENAI_API_KEY", "xai": "XAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY"}`.
  - [x] In `_resolve_routing`, replace the ternary chain with `_PROVIDER_ENV_VARS.get(provider)` (returns
    `None` for providers not in the table, matching the old `else None`). Leave the `default_llm` and
    `_DEFAULT_ROUTING` branches untouched.
  - [x] Add a short comment: these tables are local by design; unifying with `providers/registry.py` is
    Story 0.4.

- [x] **Task 3 — Tests** (AC: 3)
  - [x] Run `tests/unit/test_planner_mapper.py` — it must pass unchanged (do not edit its assertions).
  - [x] Add a small guard test asserting the data-driven contract: `_infer_provider("grok-2") == "xai"`
    (grok path was previously untested) and `_resolve_routing("grok-2", None).api_key_env == "XAI_API_KEY"`,
    and an unknown-prefix model (e.g. `"mistral"`) → provider `ollama` with `api_key_env is None`.
  - [x] Run the full suite: `python -m pytest tests/unit -q` → expect ≥182 passed.

## Dev Notes

### What this story is (and is not)
- **Is:** a behavior-preserving conversion of two `if`-chains in `team_maker/llm/mapper.py`
  (`_infer_provider`, `_resolve_routing`) into module-level data-table lookups (AD-1/AD-8).
- **Is NOT:** unifying provider catalogs (Story 0.4), touching the port/adapters (Story 0.1, done), the
  runtime/CrewAI seam (Story 0.3), or the schema (Story 0.5). Do not change any behavior or env-var value.

### Current state (read before writing)
- `team_maker/llm/mapper.py`:
  - `_infer_provider(model)` — `m.startswith(("gpt-","o1-","o3-","o4-"))`→openai; `("grok-",)`→xai;
    `"claude-"`→anthropic; else `"ollama"`.
  - `_resolve_routing(llm_override, default_llm)` — if `llm_override`: `provider=_infer_provider(...)`,
    `api_key_env = "OPENAI_API_KEY" if provider=="openai" else "XAI_API_KEY" if provider=="xai" else
    "ANTHROPIC_API_KEY" if provider=="anthropic" else None`. Else if `default_llm`: copy its fields. Else
    `_DEFAULT_ROUTING` (anthropic/claude-sonnet-4-6/ANTHROPIC_API_KEY).
  - `map_plan_to_team(...)` builds `AgentSpec`/`TaskSpec` and derives topology — leave untouched.
- Tests: `tests/unit/test_planner_mapper.py` imports `_infer_provider`, `_resolve_routing`,
  `map_plan_to_team` and asserts exact results (gpt-4o/o1-/o3-→openai; claude-→anthropic; llama3.2/mistral
  →ollama; `_resolve_routing("gpt-4o", None)`→openai/OPENAI_API_KEY; default_llm and hardcoded-default
  paths). All must remain green **without edits**.

### Architecture constraints (binding)
- **AD-1 / AD-8 — never branch on provider name; provider differences are data.** The prefix→provider and
  provider→env-var facts become tables; adding a mapping is a data edit. [Source: ARCHITECTURE-SPINE.md#AD-1,
  #AD-8; project-context.md#Validation-Rules]

### Project conventions (must follow — from project-context.md)
- `from __future__ import annotations`; built-in generics; snake_case; ruff line-length 100 (E,F,I,N,W;
  E501 ignored); `make lint`/`make fmt`.

### Testing standards
- pytest, `tests/unit/test_*.py`, in-memory, no network. Definition of done: `python -m pytest tests/unit
  -q` green (≥182) and ruff clean on `team_maker/llm/mapper.py` + the new/edited test.

### Project Structure Notes
- Single-file change: `team_maker/llm/mapper.py` + `tests/unit/test_planner_mapper.py` (append guard test).
  No new packages. The local data tables are a stepping stone; Story 0.4 folds provider facts into one
  shared catalog.

### References
- [Source: project-docs/epics.md#Story-0.2]
- [Source: project-docs/stories/reconciliation-notes.md] — divergence row 2, Story 0.4 dependency
- [Source: project-docs/architecture/architecture-team_maker-2026-07-05/ARCHITECTURE-SPINE.md#AD-1, #AD-8]
- [Source: project-docs/project-context.md#Validation-Rules]
- [Source: team_maker/llm/mapper.py, tests/unit/test_planner_mapper.py, team_maker/providers/registry.py]

## Dev Agent Record

### Agent Model Used

claude-opus-4-8 (Claude Code, dev-story workflow)

### Debug Log References

- `grep -nE "if provider ==|startswith\(\(\"gpt"` on mapper.py → none (branching removed).
- `python -m pytest tests/unit -q` → **185 passed** (182 + 3 new). `test_planner_mapper.py` unchanged
  assertions all pass.
- `ruff check team_maker/llm/mapper.py` → clean. The 4 ruff `I001`/`F401` findings in
  `tests/unit/test_planner_mapper.py` are **pre-existing** (present on the epic_0 baseline; my change
  introduced zero new lint) and left untouched per scope discipline — sweep in a dedicated lint story.

### Completion Notes List

- **`_infer_provider` (Task 1):** now a lookup over `_MODEL_PREFIX_PROVIDERS` (ordered data table of
  prefix-tuple → provider) with `_FALLBACK_PROVIDER = "ollama"`. No prefix `if`-chain. Behavior identical
  (gpt-/o1-/o3-/o4-→openai, grok-→xai, claude-→anthropic, else ollama).
- **`_resolve_routing` (Task 2):** `api_key_env` now comes from `_PROVIDER_ENV_VARS.get(provider)` (data
  table), returning `None` for unmapped providers — identical to the old ternary chain. `default_llm` and
  `_DEFAULT_ROUTING` branches untouched.
- **Scope guard honored:** did NOT unify with `providers/registry.py` (it disagrees on env-var names /
  omits xai) — that is Story 0.4; left an in-code comment pointing there.
- **Tests:** `test_planner_mapper.py` assertions unchanged; added 3 guard tests (grok→xai inference,
  grok→XAI_API_KEY routing, unknown-prefix→ollama with `api_key_env is None`).

### File List

- `team_maker/llm/mapper.py` (modified — two `if`-chains → data-table lookups)
- `tests/unit/test_planner_mapper.py` (modified — appended 3 Story 0.2 guard tests; existing assertions untouched)

## Change Log

- 2026-07-12 — Story drafted via create-story context engine (analysis of `mapper.py`, its tests, the
  Story 1.1 registry, spine AD-1/AD-8). Behavior-preserving, local-tables scope with Story 0.4 flagged for
  catalog unification. Status → ready-for-dev.
- 2026-07-12 — Implemented via dev-story. Converted `_infer_provider` and `_resolve_routing` to
  module-level data tables (`_MODEL_PREFIX_PROVIDERS`, `_PROVIDER_ENV_VARS`); no provider-name/prefix
  branching remains. Added 3 guard tests. Full suite **185 passed**, mapper.py ruff clean, behavior
  unchanged. Status → review.
