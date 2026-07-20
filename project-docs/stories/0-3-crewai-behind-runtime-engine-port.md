---
baseline_commit: 517ce41bbacfdc4e950ff2c4758046a50e089ad6
---

# Story 0.3: Put CrewAI behind the RuntimeEngine port

Status: done

<!-- RECONCILIATION STORY (Epic 0) — see project-docs/stories/reconciliation-notes.md (divergence row 3).
     Behavior-preserving refactor + dead-code/duplication cleanup of team_maker/frameworks/ and the
     requirements-pin logic in team_maker/pipeline/runner.py. The full unit suite (185 tests) and the
     non-live integration suite (20 tests) MUST stay green throughout. -->

## Story

As the codebase,
I want the framework-selection seam (crewai/langgraph/autogen) formalized behind a `RuntimeEngine`
port with adapters, and the CrewAI dependency pin single-sourced,
so that the core stays framework-agnostic (AD-6), `crewai` never becomes a hard dependency of
`team_maker`, and the version pin lives in one place ready to be gated by the future multi-provider
conformance test (AD-7, Story 1.6).

## Acceptance Criteria

1. **Given** the `FrameworkAdapter` ABC in `team_maker/frameworks/base.py` (`name` property,
   `render_runner(team, notifications=None) -> str`, `extra_requirements() -> list[str]`), **When**
   migrated, **Then** `team_maker/ports/runtime_engine.py` defines `RuntimeEngine` with the identical
   method contract, and core code (`pipeline/runner.py`) imports the port from `team_maker/ports/` —
   never a concrete adapter class directly. (AD-2, AD-6)
2. **Given** the three concrete adapters (`CrewAIAdapter`, `LangGraphAdapter`, `AutoGenAdapter`),
   **When** migrated, **Then** they live under `team_maker/adapters/runtime_engines/` (one module per
   engine), satisfy `RuntimeEngine`, and `render_runner`'s output — the rendered
   `crewai_runner.py.j2` / `langgraph_runner.py.j2` / `autogen_runner.py.j2` content — is
   byte-identical to today for the same inputs. (AD-2, AD-4, AD-6)
3. **Given** `get_adapter(framework: str) -> FrameworkAdapter` in `team_maker/frameworks/__init__.py`
   (already a dict lookup, no `if`-chain, defaults to `"crewai"` for an unknown key), **When**
   relocated, **Then** it becomes `get_runtime_engine(name: str) -> RuntimeEngine` in
   `team_maker/adapters/runtime_engines/__init__.py`, keeps the identical dict-lookup shape and
   unknown-key-falls-back-to-crewai behavior, and `pipeline/runner.py` is the only caller updated.
   `team_maker/frameworks/` is deleted (no other module or test imports it — verified by
   `git grep`). (AD-1, AD-6)
4. **Given** the CrewAI dependency pin is currently duplicated and **inconsistent** in two places —
   `frameworks/crewai_adapter.py::extra_requirements()` (dead code, never called; returns
   `crewai>=0.80.0` with no `google-genai` extra) vs. `pipeline/runner.py::_render_requirements`'s
   hardcoded `framework_deps["crewai"]` (the list actually shipped: `crewai[google-genai]>=0.80.0`
   plus `langchain-google-genai>=2.0`) — **When** single-sourced, **Then** each engine's
   `extra_requirements()` is updated to return exactly the list `runner.py` ships today (runner.py's
   values win — they are the live behavior), `_render_requirements` calls
   `adapter.extra_requirements()` for the static per-framework list instead of a second hardcoded
   dict, the dynamic per-team additions (`litellm>=1.0` for non-native providers, `chromadb>=0.5` for
   vector/both state backends) stay in `pipeline/runner.py`, and the generated `requirements.txt`
   content is unchanged for every existing scenario. (AD-6, AD-7)
5. **Given** `crewai` is declared nowhere in `pyproject.toml` and never imported at module scope
   anywhere under `team_maker/` today (it appears only inside the Jinja *string* template
   `codegen/templates/crewai_runner.py.j2` — generated code for the user's package, not
   `team_maker`'s own runtime), **When** this story completes, **Then** that remains true (add a
   regression test), and the CrewAI version bump to the spine's target (1.14.6) is explicitly **NOT**
   done here — leave a code comment noting the bump is gated by the Story 1.6 multi-provider
   conformance test (AD-7). (AD-6, AD-7)
6. **Given** the existing tests (`tests/unit/test_codegen.py`'s template-content assertions,
   `tests/integration/test_pipeline.py`'s manifest-file-presence assertions), **When** the refactor
   lands, **Then** they pass **unchanged** and the full unit suite stays green (≥185 passed). (AD-2)

## Tasks / Subtasks

- [x] **Task 1 — Define the `RuntimeEngine` port** (AC: 1)
  - [x] Create `team_maker/ports/runtime_engine.py`. Define `RuntimeEngine` with the same three
    members as today's `FrameworkAdapter`: `name` (property, `str`), `render_runner(self, team:
    GeneratedTeam, notifications=None) -> str`, `extra_requirements(self) -> list[str]`.
  - [x] Keep it an `ABC` (matches current usage — the three adapters already subclass it and nothing
    requires structural/mock typing here, unlike Story 0.1's `LLMProvider`). Start the module with
    `from __future__ import annotations`; import `GeneratedTeam` only for the type hint.
  - [x] `team_maker/ports/__init__.py` already exists (from Story 0.1) — no change needed there.

- [x] **Task 2 — Move the three engines under `adapters/runtime_engines/`** (AC: 2)
  - [x] Create `team_maker/adapters/runtime_engines/__init__.py`, `crewai_engine.py`,
    `langgraph_engine.py`, `autogen_engine.py`.
  - [x] Move `CrewAIAdapter`, `LangGraphAdapter`, `AutoGenAdapter` verbatim (class names may stay as-is
    to minimize diff) into the new modules. Change their base-class import to
    `from team_maker.ports.runtime_engine import RuntimeEngine` and subclass that instead of
    `FrameworkAdapter`. Do not touch `render_runner`'s body — same `render_template(...)` calls, same
    arguments, same template filenames.

- [x] **Task 3 — Relocate the data-driven lookup, delete `frameworks/`** (AC: 3)
  - [x] In `team_maker/adapters/runtime_engines/__init__.py`: `_ENGINES: dict[str, RuntimeEngine] =
    {"crewai": CrewAIAdapter(), "langgraph": LangGraphAdapter(), "autogen": AutoGenAdapter()}` and
    `def get_runtime_engine(name: str) -> RuntimeEngine: return _ENGINES.get(name,
    _ENGINES["crewai"])` — preserves the exact current fallback behavior of `get_adapter`.
  - [x] Update `team_maker/pipeline/runner.py`: replace `from team_maker.frameworks import
    get_adapter` with `from team_maker.adapters.runtime_engines import get_runtime_engine`, and the
    one call site `adapter = get_adapter(effective_framework)` → `adapter =
    get_runtime_engine(effective_framework)`.
  - [x] Run `git grep -rn "team_maker.frameworks\|frameworks import\|FrameworkAdapter"` — confirm the
    only remaining hits are inside `team_maker/frameworks/` itself, then delete the whole
    `team_maker/frameworks/` directory (`base.py`, `crewai_adapter.py`, `langgraph_adapter.py`,
    `autogen_adapter.py`, `__init__.py`). No back-compat shim is needed — unlike Story 0.1's
    provider move, nothing outside `pipeline/runner.py` imports this package.

- [x] **Task 4 — Single-source the requirements pin** (AC: 4, 5)
  - [x] Update each engine's `extra_requirements()` to return exactly what `runner.py`'s
    `framework_deps` table hardcodes today:
    - `crewai_engine.py`: `["crewai[google-genai]>=0.80.0", "crewai-tools>=0.25.0",
      "langchain-anthropic>=0.3.0", "langchain-google-genai>=2.0", "langchain-openai>=0.3.0",
      "langchain-ollama>=0.2.0"]`
    - `langgraph_engine.py`: `["langgraph>=0.2.0", "langchain-core>=0.3.0",
      "langchain-anthropic>=0.3.0", "langchain-google-genai>=2.0", "langchain-openai>=0.3.0",
      "langchain-ollama>=0.2.0"]`
    - `autogen_engine.py`: `["pyautogen>=0.2.0"]` (unchanged — already matched).
  - [x] In `team_maker/pipeline/runner.py::_render_requirements`, add a `framework_requirements:
    list[str]` parameter carrying the static list; remove the local `framework_deps` dict and its
    `.get(framework, framework_deps["crewai"])` lookup; use `deps = base + framework_requirements`.
    Keep the `framework: str` parameter — it is still needed for the `if framework == "crewai" and
    team is not None:` litellm-native-provider check — and keep `_CREWAI_NATIVE_PROVIDERS` and the
    `chromadb` (state-backend) branch exactly as-is.
  - [x] Update the single call site in `_build_manifest` (which already has `adapter` in scope as a
    parameter): `self._render_requirements(team.primary_framework, request.state_backend,
    adapter.extra_requirements(), team)`.
  - [x] Add a comment next to `crewai_engine.py`'s pin: version bump to CrewAI **1.14.6** (spine
    target — see ARCHITECTURE-SPINE.md Stack table) is gated by the Story 1.6 multi-provider
    conformance test (AD-7); do not bump here.

- [x] **Task 5 — Regression tests for the port + no hard `crewai` dependency** (AC: 5, 6)
  - [x] New `tests/unit/test_runtime_engine_port.py`:
    - `RuntimeEngine` exists in `team_maker.ports.runtime_engine` with `name`, `render_runner`,
      `extra_requirements`.
    - `get_runtime_engine("crewai"/"langgraph"/"autogen")` returns an instance whose `.name` matches;
      `get_runtime_engine("bogus")` falls back to the crewai engine (same as old `get_adapter`
      default).
    - Each engine's `extra_requirements()` returns exactly the list now single-sourced in Task 4
      (locks the dedup so it can't silently drift from what `requirements.txt` ships).
    - Scan `team_maker/**/*.py` (exclude `team_maker/codegen/templates/`, which are `.j2` files
      anyway and not Python) for a module-level `import crewai` / `from crewai import` — assert none
      found. This is the AD-6 regression guard.
  - [x] Run `python -m pytest tests/unit -q` → expect ≥185 passed (185 + new tests).
  - [x] Run `python -m pytest tests/integration -k "not live" -q` → expect the existing 20 to keep
    passing unchanged (manifest file lists, Dockerfile content, etc. are unaffected by this
    refactor).
  - [x] `ruff check` clean on every new/changed file (line-length 100; E,F,I,N,W; E501 ignored).

## Review Findings

_Code review run 2026-07-18 (branch `story_0_3` vs `epic_0`, commit `d47b499`) — Blind Hunter,
Edge Case Hunter, Acceptance Auditor layers, all completed. 22 raw findings → 3 patch, 1 defer,
14 dismissed (spec-directed, pre-existing-and-unchanged, or false positive from lack of spec
access), 0 decision-needed._

- [x] [Review][Patch] `pipeline/runner.py` never imports or type-annotates the `RuntimeEngine` port — `adapter` stays untyped end-to-end, so AC1's "core code imports the port from `team_maker/ports/`" isn't literally satisfied even though no concrete adapter class is imported directly [team_maker/pipeline/runner.py:79,131] — **Fixed:** imported `RuntimeEngine` from `team_maker.ports.runtime_engine` and annotated both the `adapter` local (`run()`) and the `_build_manifest` parameter.
- [x] [Review][Patch] New `team_maker/adapters/runtime_engines/__init__.py` is missing the project-standard `from __future__ import annotations` (every other new/touched file in this diff has it) [team_maker/adapters/runtime_engines/__init__.py:1] — **Fixed:** added the import.
- [x] [Review][Patch] No test exercises `_render_requirements` with `adapter.extra_requirements()` end-to-end — only each engine's `extra_requirements()` is tested in isolation, not that the value actually lands in the rendered output, which is the exact drift this story exists to prevent [tests/unit/test_runtime_engine_port.py] — **Fixed:** added `test_render_requirements_plumbs_adapter_extra_requirements_through` (parametrized over all three engines).
- [x] [Review][Defer] `get_runtime_engine`'s silent fallback-to-crewai combined with `_render_requirements`'s raw `framework == "crewai"` string check can diverge for an unrecognized framework value (requirements.txt would omit `litellm` even though the CrewAI engine is what actually renders) — deferred, pre-existing: byte-identical to the old `get_adapter`/`framework_deps.get(...)` behavior, and this story's own Dev Notes explicitly direct keeping this branch "exactly as-is" [team_maker/adapters/runtime_engines/__init__.py:13-14, team_maker/pipeline/runner.py:304-307]

## Dev Notes

### What this story is (and is not)
- **Is:** relocating the existing `frameworks/` codegen-adapter seam onto the spine's ports-and-adapters
  naming (`ports/RuntimeEngine` + `adapters/runtime_engines/`), and deduplicating the CrewAI/langgraph
  dependency-pin lists that had silently diverged between dead code (`extra_requirements()`) and the
  actually-shipped list (`pipeline/runner.py`'s `framework_deps`).
- **Is NOT:** building real runtime *execution* of a team (that is Epic 1 Story 1.5 — "Run a team and
  return results" — which does not exist in this repo yet; today `render_runner` only produces the
  *string* content of the generated package's `run_example.py`, a Factory/codegen concern). Do not add
  agent-execution logic, do not add a hard `crewai` dependency, do not bump the CrewAI version, do not
  touch `langgraph_adapter.py`/`autogen_adapter.py`'s template-selection logic beyond the mechanical
  move + import-path change, and do not touch the Ollama/docker-compose sidecar logic in
  `pipeline/runner.py` (unrelated to this seam).

### Current state (read before writing)
- `team_maker/frameworks/base.py` — `FrameworkAdapter(ABC)`: `name` (abstract property),
  `render_runner(team, notifications=None) -> str` (abstract), `extra_requirements() -> list[str]`
  (abstract).
- `team_maker/frameworks/{crewai,langgraph,autogen}_adapter.py` — each renders a Jinja template via
  `team_maker.codegen.render_template(...)` (a generic, framework-agnostic engine — no `crewai` import
  anywhere in `codegen/`). `extra_requirements()` on each is defined but **never called** anywhere in
  the codebase (verified: only definition sites match, no call sites) — pure dead code today.
- `team_maker/frameworks/__init__.py` — `_ADAPTERS: dict[str, FrameworkAdapter]` keyed by `"crewai"`,
  `"langgraph"`, `"autogen"`; `get_adapter(framework) -> FrameworkAdapter` returns
  `_ADAPTERS.get(framework, _ADAPTERS["crewai"])`.
- **Only call site:** `team_maker/pipeline/runner.py:24` (`from team_maker.frameworks import
  get_adapter`) and `:79` (`adapter = get_adapter(effective_framework)`, inside `run()`, before
  `_build_manifest(team, request, adapter)` is called at `:81`). `_build_manifest` already receives
  `adapter` and uses it once, at `:173`, for `manifest["run_example.py"] =
  adapter.render_runner(team, request.notifications)`.
- `_render_requirements` (static method, `runner.py:282-329`) is called from `_build_manifest:176-178`
  as `self._render_requirements(team.primary_framework, request.state_backend, team)` — **does not
  currently receive `adapter`**, which is why it grew its own separate, now-stale `framework_deps`
  dict instead of asking the adapter. `_CREWAI_NATIVE_PROVIDERS` (a `frozenset`, `:276-280`) and the
  `litellm`/`chromadb` conditionals are dynamic (need `team`/`state_backend`) and must stay in
  `runner.py` — only the static per-framework list moves to the engine.
- `crewai` is **not** a `pyproject.toml` dependency (confirmed) and is **not** imported anywhere at
  Python module scope in `team_maker/` — it appears only as a literal string inside the `.j2` Jinja
  template `codegen/templates/crewai_runner.py.j2`, which `tests/unit/test_codegen.py` already asserts
  contains `"from crewai import Agent, Task, Crew, Process"` in its *rendered output* (that assertion
  is untouched by this story — the template itself does not move).
- No test file references `team_maker.frameworks`, `get_adapter`, `FrameworkAdapter`, or
  `CrewAIAdapter` directly (confirmed via search) — only the Jinja templates' *rendered string content*
  is tested (`test_codegen.py`), and manifest file presence (`test_pipeline.py`,
  `test_planner_live.py`). This is why no back-compat shim is required, unlike Story 0.1.

### Architecture constraints (binding)
- **AD-6 — CrewAI (and the other engines) behind a port.** `core`/pipeline depends only on
  `ports/RuntimeEngine`; concrete engines are adapters; swapping/adding an engine is an adapter change.
  [Source: ARCHITECTURE-SPINE.md#AD-6]
- **AD-7 — conformance test gates the CrewAI pin.** The version bump to 1.14.6 is explicit future work
  tied to Story 1.6's multi-provider conformance test — do not bump the pin in this story; single-source
  it so that future gate has one place to change. [Source: ARCHITECTURE-SPINE.md#AD-7]
- **AD-1 — no branching on identity; differences are data.** `get_runtime_engine` stays a dict lookup
  (already true today — just relocate it, don't rewrite it as an `if`-chain). [Source:
  ARCHITECTURE-SPINE.md#AD-1]
- **AD-2 / AD-4 — ports-and-adapters, inward deps.** Port in `ports/`, concretes in
  `adapters/runtime_engines/`, `pipeline/runner.py` (core) imports only the port + the
  `get_runtime_engine` composition helper, never a concrete engine class. [Source:
  ARCHITECTURE-SPINE.md#AD-2, #AD-4]
- **Structural Seed** lists `adapters/runtime_crewai/` for the *future* execution adapter (Epic 1); this
  story's `adapters/runtime_engines/` is the present-day codegen-adapter seam being formalized now so
  Epic 1 has a conformant base to extend — it is not that future execution adapter itself. [Source:
  ARCHITECTURE-SPINE.md#Structural-Seed; project-docs/epics.md#Epic-0]

### Project conventions (must follow — from project-context.md)
- `from __future__ import annotations`; full type hints; built-in generics; snake_case; ruff
  line-length 100 (E,F,I,N,W; `E501` ignored); `make lint`/`make fmt`.
- **Never branch on identity/name** — `get_runtime_engine`'s dict lookup already satisfies this; do not
  regress it into an `if`/`elif` chain.
- `crewai` is NOT a dependency of this repo — never `import crewai` in `team_maker/`. This story adds a
  regression test enforcing exactly that.

### Testing standards
- pytest, `tests/unit/test_*.py`, in-memory, no filesystem/network for unit tests.
- Definition of done: `python -m pytest tests/unit -q` green (≥185) + `python -m pytest tests/integration
  -k "not live" -q` green (20 passed, unchanged) + `ruff check` clean on all new/changed files.
- `tests/integration/test_planner_live.py` auto-skips without `OPENAI_API_KEY` — do not worry about it.

### Project Structure Notes
- **New packages:** `team_maker/ports/runtime_engine.py` (port), `team_maker/adapters/runtime_engines/`
  (`__init__.py` + 3 engine modules).
- **Removed:** `team_maker/frameworks/` (entire package — `base.py`, 3 adapter modules, `__init__.py`).
  No shim needed (single internal caller, no external/test imports).
- **Modified:** `team_maker/pipeline/runner.py` (import path, `get_runtime_engine` rename,
  `_render_requirements` signature + body).
- No new top-level packages beyond what Story 0.1 already introduced (`ports/`, `adapters/`) — this
  story adds siblings under those same two roots.

### References
- [Source: project-docs/epics.md#Epic-0, #Story-0.3] — story + ACs (AD-6, AD-7)
- [Source: project-docs/stories/reconciliation-notes.md] — divergence row 3
- [Source: project-docs/architecture/architecture-team_maker-2026-07-05/ARCHITECTURE-SPINE.md#AD-1,
  #AD-2, #AD-4, #AD-6, #AD-7, #Structural-Seed]
- [Source: project-docs/architecture.md#8-Known-gaps] — confirms runtime execution is out of scope in
  this repo today; `run_example.py` is a starter, not a supported runtime
- [Source: project-docs/project-context.md#Technology-Stack, #Validation-Rules]
- [Source: team_maker/frameworks/base.py, __init__.py, crewai_adapter.py, langgraph_adapter.py,
  autogen_adapter.py; team_maker/pipeline/runner.py (lines 24, 61-96, 126-186, 275-329);
  team_maker/codegen/engine.py]
- [Source: project-docs/stories/0-1-llm-provider-port-and-adapters.md] — sibling ports/adapters move,
  ABC-vs-Protocol decision precedent, shim-vs-no-shim precedent
- [Source: project-docs/stories/0-2-remove-provider-name-branching.md] — data-table-lookup precedent,
  story format/quality bar
- [Source: tests/unit/test_codegen.py (lines 62, 123-160), tests/integration/test_pipeline.py (lines
  22-38), tests/integration/test_planner_live.py (lines 1-21)]

## Dev Agent Record

### Agent Model Used

claude-sonnet-5 (bmad-dev-story)

### Debug Log References

- Baseline: `python -m pytest tests/unit -q` → 185 passed; `python -m pytest tests/integration -k "not live" -q` → 20 passed, 7 deselected.
- Final (pre-review): `python -m pytest tests/unit -q` → 195 passed (185 baseline + 10 new in `test_runtime_engine_port.py`); `python -m pytest tests/integration -k "not live" -q` → 20 passed, 7 deselected (unchanged).
- `ruff check` on all new/changed files → clean (2 pre-existing `I001` import-sort findings in `pipeline/runner.py`, one of them in the block touched by this story, were fixed via `ruff check --fix` rather than left — both are pure import-ordering, no behavior change).
- Post-review (after applying the 3 patch findings): `python -m pytest tests/unit -q` → 198 passed (195 + 3 new parametrized cases in `test_render_requirements_plumbs_adapter_extra_requirements_through`); `python -m pytest tests/integration -k "not live" -q` → 20 passed, 7 deselected (unchanged); `ruff check` → clean.

### Completion Notes List

- `RuntimeEngine` port created as an `ABC` in `team_maker/ports/runtime_engine.py` with the identical
  three-member contract as the old `FrameworkAdapter` (`name`, `render_runner`, `extra_requirements`).
- All three engines (`CrewAIAdapter`, `LangGraphAdapter`, `AutoGenAdapter`) moved verbatim into
  `team_maker/adapters/runtime_engines/{crewai,langgraph,autogen}_engine.py`, now subclassing
  `RuntimeEngine` instead of `FrameworkAdapter`. `render_runner` bodies untouched — same
  `render_template(...)` calls/args/filenames, so rendered output is unchanged (confirmed by the
  existing `test_codegen.py` assertions still passing).
- `get_adapter`/`_ADAPTERS` relocated to `get_runtime_engine`/`_ENGINES` in
  `team_maker/adapters/runtime_engines/__init__.py` — identical dict-lookup shape, identical
  unknown-key-falls-back-to-`crewai` behavior. `pipeline/runner.py` updated to import and call it (the
  only caller).
- `team_maker/frameworks/` deleted in full (`base.py`, 3 adapter modules, `__init__.py` +
  `__pycache__`) — `git grep` confirmed zero remaining code references (only doc mentions in
  `project-docs/*.md`, expected) before deletion.
- Dependency pin single-sourced: each engine's `extra_requirements()` now returns exactly what
  `runner.py`'s old `framework_deps` table hardcoded (crewai gains the previously-missing
  `langchain-google-genai>=2.0`; langgraph/autogen unchanged). `_render_requirements` gained a
  `framework_requirements: list[str]` parameter and dropped the local `framework_deps` dict; the one
  call site in `_build_manifest` now passes `adapter.extra_requirements()`. `_CREWAI_NATIVE_PROVIDERS`
  and the dynamic `litellm`/`chromadb` additions stayed in `runner.py` as specified. Generated
  `requirements.txt` content is unchanged for every scenario (confirmed by `test_pipeline.py` still
  passing unchanged).
- Added a code comment on `crewai_engine.py`'s pin noting the 1.14.6 bump is gated by Story 1.6's
  conformance test — **no version bump was made in this story**, per AC5.
- New `tests/unit/test_runtime_engine_port.py` (10 tests): port location/abstractness, `get_runtime_engine`
  resolution for all three known names + unknown-name fallback, each engine's `extra_requirements()`
  locked to the single-sourced list, and an AST-based scan of every `team_maker/**/*.py` module confirming
  no module-level `import crewai` / `from crewai import` exists anywhere.
- No back-compat shim added for `team_maker.frameworks` — confirmed via `git grep` that nothing outside
  `pipeline/runner.py` (already updated) imported it, matching the story's explicit "no shim needed" call.

### File List

- `team_maker/ports/runtime_engine.py` (CREATE)
- `team_maker/adapters/runtime_engines/__init__.py` (CREATE)
- `team_maker/adapters/runtime_engines/crewai_engine.py` (CREATE)
- `team_maker/adapters/runtime_engines/langgraph_engine.py` (CREATE)
- `team_maker/adapters/runtime_engines/autogen_engine.py` (CREATE)
- `tests/unit/test_runtime_engine_port.py` (CREATE)
- `team_maker/pipeline/runner.py` (UPDATE — import path, `get_runtime_engine` rename,
  `_render_requirements` signature/body, isort cleanup)
- `team_maker/frameworks/base.py` (DELETE)
- `team_maker/frameworks/crewai_adapter.py` (DELETE)
- `team_maker/frameworks/langgraph_adapter.py` (DELETE)
- `team_maker/frameworks/autogen_adapter.py` (DELETE)
- `team_maker/frameworks/__init__.py` (DELETE)

## Change Log

- 2026-07-12 — Story drafted via create-story context engine (exhaustive analysis of
  `team_maker/frameworks/`, `pipeline/runner.py`'s requirements-pin logic and its duplication vs.
  `extra_requirements()`, the architecture spine AD-1/AD-2/AD-4/AD-6/AD-7, prior stories 0.1/0.2's
  patterns, and the existing test suite's actual behavioral contract). Behavior-preserving relocation +
  dependency-pin de-duplication scope, no execution logic added, CrewAI pin bump explicitly deferred to
  Story 1.6. Status → ready-for-dev.
- 2026-07-18 — Implemented via bmad-dev-story on branch `story_0_3` (off `epic_0`). All 5 tasks
  complete: `RuntimeEngine` ABC port created; all three engines relocated to
  `adapters/runtime_engines/`; `get_runtime_engine` lookup relocated and `team_maker/frameworks/`
  deleted; dependency pins single-sourced onto the engines (no version bump); regression tests added.
  Full suite green (195 unit, 20 non-live integration), `ruff check` clean. Status → review.
  (Note: an earlier `archon-plan-to-pr` run against this story produced PR #1 with a materially
  different, self-invented scope — unauthorized crewai==1.14.6 bump, wrong `adapters/runtime_crewai/`
  directory name, incomplete adapter migration, `frameworks/` not deleted. That PR was closed without
  merging; this implementation replaces it and follows the acceptance criteria above exactly.)
- 2026-07-18 — Code review (bmad-code-review, Blind Hunter + Edge Case Hunter + Acceptance Auditor):
  22 raw findings → 3 patch (all applied: typed the `RuntimeEngine` port through `runner.py`, added
  the missing `from __future__ import annotations`, added an end-to-end
  `adapter.extra_requirements()` → rendered-`requirements.txt` plumbing test), 1 defer (pre-existing
  `get_runtime_engine`/`_render_requirements` fallback-vs-raw-string-check divergence, logged in
  `project-docs/stories/deferred-work.md`), 14 dismissed (spec-directed, pre-existing-and-unchanged, or
  false positives from the Blind Hunter's lack of spec access). Full suite re-verified green (198
  unit, 20 non-live integration), `ruff check` clean. Status → done.
