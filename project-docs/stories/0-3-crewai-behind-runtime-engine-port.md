---
baseline_commit: 517ce41bbacfdc4e950ff2c4758046a50e089ad6
---

# Story 0.3: Put CrewAI behind the RuntimeEngine port

Status: ready-for-dev

<!-- RECONCILIATION STORY (Epic 0) — see project-docs/stories/reconciliation-notes.md (divergence row 3).
     Behavior-preserving refactor of team_maker/frameworks/. The existing unit suite (185 tests)
     must stay green. The crewai version pin is updated from >=0.80.0 to ==1.14.6. -->

## Story

As the codebase,
I want CrewAI isolated behind a `RuntimeEngine` port,
so that the core stays framework-agnostic, the CrewAI version is gated by the conformance test
(AD-7), and swapping execution engines in a future release is an adapter change only.

## Acceptance Criteria

1. **Given** the need to formalize the runtime seam, **When** implemented, **Then** a new
   `team_maker/ports/runtime_engine.py` defines `RuntimeEngine` as a `typing.Protocol` (with
   `@runtime_checkable`) with: a `name: str` property, `render_runner(self, team: GeneratedTeam,
   notifications=None) -> str`, and `extra_requirements(self) -> list[str]`; no code outside
   `adapters/` imports a concrete adapter class directly. (AD-2, AD-6)

2. **Given** the existing `team_maker/frameworks/crewai_adapter.py` (subclasses `FrameworkAdapter`
   ABC), **When** moved, **Then** a `team_maker/adapters/runtime_crewai/crewai_engine.py` module
   holds `CrewAIAdapter`, which satisfies `RuntimeEngine` **structurally** (no ABC subclassing), and
   no top-level `crewai` import appears anywhere in `team_maker/` core. (AD-4, AD-6)

3. **Given** the loose version pin `crewai>=0.80.0` in `crewai_engine.py::extra_requirements()` AND
   `crewai[google-genai]>=0.80.0` in `pipeline/runner.py::_render_requirements()`, **When**
   updated, **Then** both pins become `crewai[google-genai]==1.14.6` (exact pin gates the
   conformance test per AD-7); all other crewai-adjacent pins left unchanged unless they conflict.
   (AD-7)

4. **Given** that `crewai` is not in `pyproject.toml` dependencies, **When** done, **Then**
   `pyproject.toml` gains a `crewai` optional extra:
   `crewai = ["crewai[google-genai]==1.14.6", "crewai-tools>=0.25.0",
   "langchain-anthropic>=0.3.0", "langchain-openai>=0.3.0", "langchain-ollama>=0.2.0"]`.
   (AD-6)

5. **Given** the existing importers (`team_maker/frameworks/__init__.py`,
   `team_maker/pipeline/runner.py`), **When** done, **Then** all existing import paths keep
   working: `team_maker/frameworks/crewai_adapter.py` becomes a back-compat re-export shim;
   `team_maker/frameworks/__init__.py` imports `CrewAIAdapter` from the new adapter location;
   `pipeline/runner.py` needs no change (it uses `get_adapter` from `frameworks/`). (AD-2)

6. **Given** the existing test suite (185 tests), **When** done, **Then** the full unit suite passes
   unchanged (≥185 passed); a new `tests/unit/test_runtime_engine_port.py` asserts port shape,
   `CrewAIAdapter` Protocol satisfaction, and the `crewai==1.14.6` pin appears in
   `CrewAIAdapter().extra_requirements()`. (AD-6, AD-7)

## Tasks / Subtasks

- [ ] **Task 1 — Define the `RuntimeEngine` port** (AC: 1)
  - [ ] Create `team_maker/ports/runtime_engine.py`.
  - [ ] Define `RuntimeEngine` as a `@runtime_checkable` `typing.Protocol`; keep
    `from __future__ import annotations`; import `GeneratedTeam` from `team_maker.domain.models`.
  - [ ] Three members: `name: str` (property), `render_runner(self, team: GeneratedTeam,
    notifications=None) -> str`, `extra_requirements(self) -> list[str]`.
  - [ ] Add a short module comment noting that a `run()` / `execute()` method for actual team
    execution will be added in **Story 1.5** — this story only formalizes the code-generation seam.

- [ ] **Task 2 — Move `CrewAIAdapter` to `adapters/runtime_crewai/`** (AC: 2, 4)
  - [ ] Create `team_maker/adapters/runtime_crewai/__init__.py` (re-exports `CrewAIAdapter` and
    a `get_crewai_adapter()` factory or re-export of `get_adapter`).
  - [ ] Create `team_maker/adapters/runtime_crewai/crewai_engine.py`:
    copy logic from `frameworks/crewai_adapter.py` verbatim; remove `FrameworkAdapter` as base
    class (no ABC inheritance); imports remain identical (`render_template`, `GeneratedTeam`).
  - [ ] `team_maker/adapters/__init__.py` already exists (Story 0.1) — do not overwrite it,
    just ensure the `runtime_crewai` package is discoverable.

- [ ] **Task 3 — Update version pins** (AC: 3, 4)
  - [ ] In `team_maker/adapters/runtime_crewai/crewai_engine.py::extra_requirements()`:
    `"crewai>=0.80.0"` → `"crewai[google-genai]==1.14.6"`.
  - [ ] In `team_maker/pipeline/runner.py::_render_requirements()::framework_deps["crewai"]`:
    `"crewai[google-genai]>=0.80.0"` → `"crewai[google-genai]==1.14.6"`.
  - [ ] `pyproject.toml`: add `crewai` optional extra under `[project.optional-dependencies]`:
    `crewai = ["crewai[google-genai]==1.14.6", "crewai-tools>=0.25.0",
    "langchain-anthropic>=0.3.0", "langchain-openai>=0.3.0", "langchain-ollama>=0.2.0"]`.

- [ ] **Task 4 — Back-compat shim** (AC: 5)
  - [ ] `team_maker/frameworks/crewai_adapter.py` → replace body with a thin re-export shim:
    `from team_maker.adapters.runtime_crewai.crewai_engine import CrewAIAdapter as CrewAIAdapter`
    (preserves `__all__` and direct import). Keep `FrameworkAdapter` subclassing gone from the real
    class; the shim does not need to re-introduce it.
  - [ ] `team_maker/frameworks/__init__.py` → update the `CrewAIAdapter` import line to pull from
    the new location; `get_adapter()` continues to return the same instances.
  - [ ] `team_maker/pipeline/runner.py` — **no change required**; it imports `get_adapter` from
    `team_maker.frameworks` which is still the shim.
  - [ ] Run `make lint` / `make fmt` (ruff, line-length 100, rules E,F,I,N,W).

- [ ] **Task 5 — Tests** (AC: 6)
  - [ ] Create `tests/unit/test_runtime_engine_port.py`:
    - Assert `team_maker.ports.runtime_engine.RuntimeEngine` is importable.
    - Assert a stub class with `name`, `render_runner`, `extra_requirements` satisfies
      `isinstance(stub, RuntimeEngine)`.
    - Assert `from team_maker.adapters.runtime_crewai import CrewAIAdapter` works and
      `isinstance(CrewAIAdapter(), RuntimeEngine)` is `True`.
    - Assert `"crewai[google-genai]==1.14.6"` in `CrewAIAdapter().extra_requirements()`.
    - Assert `get_adapter("crewai")` (from `team_maker.frameworks`) still returns an object
      satisfying `RuntimeEngine` (back-compat shim still works).
  - [ ] Run `python -m pytest tests/unit -q` → expect **≥185 passed**.
  - [ ] `ruff check team_maker/ports/runtime_engine.py team_maker/adapters/runtime_crewai/` → clean.

## Dev Notes

### What this story is (and is not)
- **Is:** a behavior-preserving structural move of `CrewAIAdapter` from `team_maker/frameworks/` to
  `team_maker/adapters/runtime_crewai/`; formalization of the `FrameworkAdapter` seam as a
  `RuntimeEngine` Protocol; and an exact pin of the crewai version to 1.14.6. (AD-6, AD-7)
- **Is NOT:** adding any team-execution logic (`run()` / `execute()` on `RuntimeEngine` — Story 1.5);
  moving LangGraph or AutoGen adapters (they stay in `frameworks/` for now); writing the
  multi-provider conformance test (Story 1.6); changing the `crewai_runner.py.j2` template;
  introducing a `crewai` import anywhere in `team_maker/` core.

### Current state (read before writing)
- `team_maker/frameworks/base.py`:
  - `FrameworkAdapter(ABC)` with `name` (abstractproperty), `render_runner(team, notifications) -> str`,
    `extra_requirements() -> list[str]`. (3 abstract members)
- `team_maker/frameworks/crewai_adapter.py`:
  - `CrewAIAdapter(FrameworkAdapter)` — `name` returns `"crewai"`, `extra_requirements()` returns
    `["crewai>=0.80.0", "crewai-tools>=0.25.0", "langchain-anthropic>=0.3.0", ...]`,
    `render_runner()` calls `render_template("crewai_runner.py.j2", ...)`.
  - **No top-level crewai import** — crewai only appears in `extra_requirements()` as a string.
- `team_maker/frameworks/__init__.py`:
  - `_ADAPTERS = {"crewai": CrewAIAdapter(), "langgraph": ..., "autogen": ...}`
  - `get_adapter(framework: str) -> FrameworkAdapter`
- `team_maker/pipeline/runner.py`:
  - Imports `get_adapter` from `team_maker.frameworks` (line 24).
  - `_render_requirements()` has a hardcoded `framework_deps["crewai"]` list with
    `"crewai[google-genai]>=0.80.0"` (line 299). This is the pin to update.
  - `extra_requirements()` on the adapter is **never called** by the pipeline — `_render_requirements()`
    is used instead. Both pin locations must be updated for consistency (AC-3).
- `team_maker/adapters/` already exists (created in Story 0.1 for LLM provider adapters).
- Current baseline test count: **185 passed**.

### Architecture constraints (binding)
- **AD-2 / AD-4 — ports-and-adapters, inward deps.** Core depends only on the port interface;
  concrete adapters are never imported by core. `RuntimeEngine` lives in `ports/`; `CrewAIAdapter`
  in `adapters/runtime_crewai/`. [Source: ARCHITECTURE-SPINE.md#AD-2, #AD-4]
- **AD-6 — RuntimeEngine is the seam.** v1 uses CrewAI behind this port; the core/factory
  touches only the port. `crewai` must not be a hard dependency of the `team_maker` package.
  [Source: ARCHITECTURE-SPINE.md#AD-6]
- **AD-7 — Per-agent routing correctness gated by a conformance test.** The exact `crewai==1.14.6`
  pin must appear in both the generated `requirements.txt` and the optional extra. The conformance
  test itself (a team spanning ≥2 providers asserts each hit the right provider) is Story 1.6.
  [Source: ARCHITECTURE-SPINE.md#AD-7]

### Project conventions (must follow — from project-context.md)
- `from __future__ import annotations`; built-in generics; snake_case; ruff line-length 100
  (E,F,I,N,W; E501 ignored); `make lint` / `make fmt`.

### Testing standards
- pytest, `tests/unit/test_*.py`, in-memory, no network. Definition of done: `python -m pytest
  tests/unit -q` green (≥185) and ruff clean on `team_maker/ports/runtime_engine.py` and
  `team_maker/adapters/runtime_crewai/`.

### Project Structure Notes
- **New packages:** `team_maker/ports/` already exists (Story 0.1); add `runtime_engine.py`.
  `team_maker/adapters/runtime_crewai/` is new — `__init__.py` + `crewai_engine.py`.
- **Shim:** `team_maker/frameworks/crewai_adapter.py` → re-export shim (pattern from Story 0.1).
  `team_maker/frameworks/base.py` and `team_maker/frameworks/__init__.py` unchanged except for the
  one import line in `__init__.py` that now pulls `CrewAIAdapter` from `adapters/runtime_crewai`.
- **`extra_requirements()` is dead code in the pipeline** (not called by `pipeline/runner.py`),
  but it is part of the `RuntimeEngine` Protocol interface and tested — keep it accurate.

### Cross-story notes
- **Story 1.5 (run a team):** will add `run(team_package: Path, goal: str) -> RunResult` to
  `RuntimeEngine` and implement it in `adapters/runtime_crewai/`. This story only lays the seam.
- **Story 1.6 (conformance test):** will add the multi-provider test that gates the crewai pin.
- **Story 0.4 (key consolidation):** unrelated; do not touch `keyconfig.py` / `model_resolver.py`.
- **Story 0.5 (schema reconciliation):** unrelated; do not touch `schema/request.py`.

### References
- [Source: project-docs/epics.md#Story-0.3]
- [Source: project-docs/stories/reconciliation-notes.md] — divergence row 3
- [Source: project-docs/architecture/architecture-team_maker-2026-07-05/ARCHITECTURE-SPINE.md#AD-2, #AD-4, #AD-6, #AD-7]
- [Source: project-docs/project-context.md#Validation-Rules, #Technology-Stack, #Testing-Rules]
- [Source: team_maker/frameworks/base.py, team_maker/frameworks/crewai_adapter.py,
  team_maker/frameworks/__init__.py, team_maker/pipeline/runner.py (lines 24, 299–306)]
- [Source: team_maker/adapters/__init__.py, team_maker/ports/llm_provider.py] — patterns to mirror

## Dev Agent Record

### Agent Model Used

claude-opus-4-8 (archon-implement-tasks)

### Debug Log References

- Baseline: `python -m pytest tests/unit -q` → 185 passed.
- Final: `python -m pytest tests/unit -q` → 192 passed (185 baseline + 7 new).
- `ruff check` clean on all new/created files and the modified `frameworks/__init__.py`,
  `frameworks/crewai_adapter.py`.

### Completion Notes List

- `RuntimeEngine` port created as a `@runtime_checkable` Protocol with `name` (property),
  `render_runner`, `extra_requirements`. No `run()`/`execute()` (Story 1.5).
- `CrewAIAdapter` moved to `adapters/runtime_crewai/crewai_engine.py`; ABC subclassing removed
  (satisfies port structurally). No top-level `crewai` import in core (only doc/template strings).
- Version pin updated to `crewai[google-genai]==1.14.6` in both `crewai_engine.extra_requirements()`
  and `pipeline/runner._render_requirements()`; `pyproject.toml` gains a `crewai` optional extra.
- `frameworks/crewai_adapter.py` is now a back-compat re-export shim; `frameworks/__init__.py`
  imports `CrewAIAdapter` from the new location. `get_adapter("crewai")` unchanged at runtime.
- **Deviation (minor, pre-existing):** `pipeline/runner.py` has 2 pre-existing ruff `I001`
  import-sort findings unrelated to this story's one-line pin change; left untouched to keep the
  refactor behavior-preserving and in-scope.

### File List

- `team_maker/ports/runtime_engine.py` (CREATE)
- `team_maker/adapters/runtime_crewai/__init__.py` (CREATE)
- `team_maker/adapters/runtime_crewai/crewai_engine.py` (CREATE)
- `tests/unit/test_runtime_engine_port.py` (CREATE)
- `team_maker/frameworks/crewai_adapter.py` (UPDATE — shim)
- `team_maker/frameworks/__init__.py` (UPDATE — import location)
- `team_maker/pipeline/runner.py` (UPDATE — pin)
- `pyproject.toml` (UPDATE — crewai extra)

## Change Log

- 2026-07-18 — Story drafted via plan-setup context engine (analysis of `frameworks/crewai_adapter.py`,
  `pipeline/runner.py`, `frameworks/base.py`, `frameworks/__init__.py`, ports-and-adapters spine
  AD-6/AD-7, project-context, prior stories 0.1/0.2). Behavior-preserving structural move + version
  pin update; 185-tests-green gate. Status → ready-for-dev.
