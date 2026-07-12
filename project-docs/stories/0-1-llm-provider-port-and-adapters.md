---
baseline_commit: 7fe64734f86c082b2d02894e564a0eb3bf8dc2bf
---

# Story 0.1: Introduce the LLMProvider port and move providers behind adapters

Status: review

<!-- RECONCILIATION STORY (Epic 0) — see project-docs/stories/reconciliation-notes.md.
     This is a REFACTOR of existing, test-covered code merged from guru-explore, NOT greenfield.
     Goal: migrate team_maker/llm/providers.py onto the ports-and-adapters spine with ZERO behavior
     change. The full unit suite (172 tests) must stay green throughout. -->

## Story

As the codebase,
I want a single `LLMProvider` port with concrete providers living behind adapters,
so that the core never depends on a provider SDK and adding a provider is a config/registry change
rather than a new code branch (AD-2, AD-8).

## Acceptance Criteria

1. **Given** the existing abstract base `LLMProvider` in `team_maker/llm/providers.py`, **When** it is
   migrated, **Then** a new `team_maker/ports/llm_provider.py` defines `LLMProvider` as a
   `typing.Protocol` with the **existing** method signature `complete_structured(self, system: str,
   user: str, response_model: type[T]) -> T` (structural, mock-friendly, SDK-free), and core modules
   import the port from `team_maker/ports/` — never from a concrete provider module. (AD-2, AD-8)
2. **Given** the five concrete providers (`AnthropicProvider`, `OpenAIProvider`, `XAIProvider`,
   `OllamaProvider`, `GoogleProvider`), **When** migrated, **Then** they live under
   `team_maker/adapters/providers/` and satisfy the port; no core module imports a concrete adapter
   class directly (core touches only the port + the factory entry point). (AD-2, AD-4)
3. **Given** `create_provider(config: ProviderConfig) -> LLMProvider`, **When** refactored, **Then**
   provider selection is **data-driven** (a registry mapping provider-id → adapter, no `if provider ==
   "..."` chain), the function signature and its `ValueError` on unknown providers are preserved, and
   adding a provider is a registry entry, not a new branch. (AD-1, AD-8)
4. **Given** the existing callers (`team_maker/llm/__init__.py`, `team_maker/llm/planner.py`) and tests
   (`tests/unit/test_model_registry.py`, which import `create_provider`/`GoogleProvider`/`XAIProvider`
   from `team_maker.llm.providers` and call `complete_structured`), **When** the move lands, **Then**
   every import site is updated to the new locations (back-compat re-exports from
   `team_maker/llm/providers.py` are acceptable to avoid churn), and the **full unit suite passes
   unchanged (172 tests green)**.
5. **Given** provider runtime behavior, **When** the refactor completes, **Then** it is a **pure
   structural move**: identical models/defaults, identical `complete_structured` semantics, identical
   closest-model resolution (`_closest_model` / `_maybe_resolve_model`), identical import-error and
   missing-key error messages. No functional change.
6. **Given** key handling, **When** migrated, **Then** this story introduces **no** new key-sourcing
   behavior — the current `os.environ.get(api_key_env)` reads inside each adapter are preserved as-is.
   Consolidating key loading through `KeyConfig` (Story 1.1) and de-duplicating with
   `llm/model_resolver.py` remains **Story 0.4** and must not be done incidentally here.

## Tasks / Subtasks

- [x] **Task 1 — Define the `LLMProvider` port** (AC: 1, 5)
  - [x] Create `team_maker/ports/__init__.py` and `team_maker/ports/llm_provider.py`. Define
    `LLMProvider` as a `typing.Protocol` (with `@runtime_checkable` only if a runtime isinstance check
    is actually needed). Keep the **existing** method `complete_structured(self, system: str, user:
    str, response_model: type[T]) -> T` and the module `TypeVar("T", bound=BaseModel)`.
  - [x] Start the module with `from __future__ import annotations`; full type hints; built-in generics.
    Port name = capability name `LLMProvider` (spine convention: ports are `<Capability>`, adapters are
    `<impl>_<capability>`).
  - [x] **Signature decision (record in the module docstring + Change Log):** the real code uses
    `complete_structured(...) -> T`, which **supersedes** the `complete(...) -> str` sketch in Story
    1.2 Task 1. The port standardizes on `complete_structured`. Flag that epics.md Story 1.2 and its
    story file should be updated to match (follow-up, not done here).

- [x] **Task 2 — Move concrete providers under `adapters/providers/`** (AC: 2, 5)
  - [x] Create `team_maker/adapters/__init__.py` and `team_maker/adapters/providers/__init__.py`.
    Move the five provider classes out of `llm/providers.py` into `adapters/providers/` (either one
    module per provider — `anthropic.py`, `openai.py`, `xai.py`, `ollama.py`, `google.py` — or a single
    `providers.py`; prefer per-provider modules for clarity, but keep it a mechanical move).
  - [x] Move the shared helper `_closest_model(...)` alongside them (e.g.
    `adapters/providers/_model_match.py` or keep private in the shared module). Each adapter keeps its
    lazy `import <sdk>` inside `complete_structured` and its `os.environ.get(api_key_env)` read
    **exactly as-is** (AC 6).
  - [x] Adapters satisfy the Protocol structurally; explicit subclassing is optional. Do NOT add an SDK
    import at module top-level (keep the lazy-import-inside-method pattern that makes optional extras
    work).

- [x] **Task 3 — Data-driven `create_provider` factory** (AC: 3)
  - [x] Replace the `if provider == "anthropic" / "openai" / ...` chain with a registry, e.g.
    `_ADAPTERS: dict[str, Callable[[ProviderConfig], LLMProvider]]` (or `dict[str, type]` + a small
    builder) keyed by lowercased provider id, preserving each provider's default `model`/`api_key_env`/
    `base_url` fallbacks. Keep `create_provider(config: ProviderConfig) -> LLMProvider` and its
    `ValueError("Unknown provider '{provider}'. Supported: ...")` behavior identical.
  - [x] Place the factory + registry in `team_maker/adapters/providers/__init__.py` (composition edge).
    Core (`planner.py`) may import the port from `ports/` and `create_provider` from `adapters/` as a
    composition-root convenience; it must NOT import individual concrete adapter classes.

- [x] **Task 4 — Update call sites + back-compat** (AC: 4)
  - [x] `team_maker/llm/planner.py`: import `LLMProvider` from `team_maker.ports.llm_provider` and
    `create_provider` from `team_maker.adapters.providers`. `TeamPlanner.__init__(provider: LLMProvider)`
    already injects the port — keep that; only `TeamPlanner.from_request` uses the factory.
  - [x] `team_maker/llm/__init__.py`: update its re-exports. To avoid test churn, **re-export**
    `LLMProvider`, `create_provider`, and the concrete providers from `team_maker.llm.providers` as
    thin back-compat aliases (import from the new locations). Keep `team_maker/llm/providers.py` as a
    shim module that re-exports from `adapters/providers/` + `ports/` (or update the tests — see Task 5;
    prefer shims to minimize diff).
  - [x] Run `make lint` / `make fmt` (ruff, line-length 100, rules E,F,I,N,W).

- [x] **Task 5 — Tests stay green** (AC: 4, 5)
  - [x] `tests/unit/test_model_registry.py` imports `create_provider`, `GoogleProvider`, `XAIProvider`
    from `team_maker.llm.providers` and calls `complete_structured`. Either (a) keep those symbols
    importable from `team_maker.llm.providers` via the shim (preferred — zero test edits), or (b) update
    the imports to the new adapter paths. Do not weaken any assertion.
  - [x] Add a focused test asserting the port location + shape: `team_maker.ports.llm_provider.LLMProvider`
    exists and a fake object with a `complete_structured` method satisfies it (structural check), and
    that `create_provider` has no `if provider ==` branching by asserting all six/five known ids resolve
    via the registry and an unknown id raises `ValueError`.
  - [x] Run the **full** unit suite: `python -m pytest tests/unit -q` → expect **172 passed** (or 172 +
    the new test). No behavior regressions.

## Dev Notes

### What this story is (and is not)
- **Is:** a pure structural refactor that lifts `LLMProvider` into `team_maker/ports/`, moves the five
  concrete providers into `team_maker/adapters/providers/`, and makes `create_provider` data-driven —
  the first slice of the ports-and-adapters spine, with zero behavior change.
- **Is NOT:** any change to *how keys are sourced* (env-var reads stay; KeyConfig consolidation is
  **Story 0.4**), NOT removing the provider-name inference in `llm/mapper.py` (**Story 0.2**), NOT the
  CrewAI/runtime seam (**Story 0.3**), NOT the schema reconciliation (**Story 0.5**), NOT the Composer
  (**Story 1.2**). Keep the diff mechanical and reviewable.

### Current state (read before writing — the code being moved)
- `team_maker/llm/providers.py`:
  - `LLMProvider(ABC)` with abstract `complete_structured(self, system, user, response_model: Type[T]) -> T`
    (line 39). Module `T = TypeVar("T", bound=BaseModel)`.
  - Five concrete providers, each: lazy `import <sdk>` inside `complete_structured`, `api_key =
    os.environ.get(self.api_key_env)` then `EnvironmentError` if missing, a `_maybe_resolve_model(client)`
    that calls `client.models.list()` once and applies `_closest_model(...)` (Anthropic line 74, OpenAI
    130, XAI 188, Ollama 262, Google 322). Defaults: anthropic/claude-sonnet-4-6, openai/gpt-4o,
    xai/grok-2 (base_url https://api.x.ai/v1), ollama/llama3.2 (base_url http://localhost:11434, no key),
    google/gemini-1.5-pro.
  - Module-level `_closest_model(requested, available, fallback)` (difflib ratio; warns to stderr).
  - `create_provider(config: ProviderConfig) -> LLMProvider` (line 409): `if provider == "..."` chain
    over anthropic/openai/xai/google/ollama, else `ValueError` (line 440). **This is the branch to make
    data-driven.**
- Importers to update (from `git grep`):
  - `team_maker/llm/__init__.py:3` re-exports `AnthropicProvider, OllamaProvider, OpenAIProvider, create_provider`.
  - `team_maker/llm/planner.py:5` `from team_maker.llm.providers import LLMProvider, create_provider`;
    `__init__(provider: LLMProvider)` (already port-injected), `from_request` calls `create_provider`
    (line 25), `plan()` calls `self._provider.complete_structured(...)` (line 43).
  - `tests/unit/test_model_registry.py` imports `create_provider`/`GoogleProvider`/`XAIProvider` from
    `team_maker.llm.providers` and calls `complete_structured` (lines 235–321).

### Architecture constraints (binding)
- **AD-2 / AD-4 — ports-and-adapters, inward deps.** Core depends only on the port interface; concrete
  adapters are never imported by core. Dependency direction `UI → API → core → adapters`. The port lives
  in `ports/`; concretes in `adapters/providers/`. [Source: ARCHITECTURE-SPINE.md#AD-2, #AD-4]
- **AD-8 — one `LLMProvider` port; adding a provider is config, not code.** All LLM access flows through
  the single port; providers are adapters selected by data. [Source: ...#AD-8]
- **AD-1 — no branching on provider name.** Provider differences live in data (the registry / `PROVIDERS`
  catalog), not `if`-chains. `create_provider` becomes a registry lookup. [Source: ...#AD-1]
- **Naming conventions.** Ports named `<Capability>` (`LLMProvider`); adapters named `<impl>_<capability>`
  (module/class naming under `adapters/providers/`). [Source: ARCHITECTURE-SPINE.md#Consistency-Conventions]
- **Structural Seed.** `team_maker/ports/` and `team_maker/adapters/providers/` are exactly the spine's
  prescribed package locations. [Source: ARCHITECTURE-SPINE.md#Structural-Seed]

### Project conventions (must follow — from project-context.md)
- Start every module with `from __future__ import annotations`; full type hints; built-in generics
  (`list`/`dict`, `X | None`); snake_case; ruff line-length 100 (E,F,I,N,W; `E501` ignored).
  `make lint` / `make fmt`. [Source: project-docs/project-context.md]
- **Never branch on provider name** — differences live in data. [Source: project-context.md#Validation-Rules]
- `crewai` is NOT a dependency and must not be imported in `team_maker/`. (Not touched here, but do not
  introduce it.) [Source: project-context.md#Technology-Stack]

### Cross-story reconciliation notes
- The port method is `complete_structured(...) -> T` (real code), which **supersedes** Story 1.2 Task 1's
  proposed `complete(...) -> str`. When Story 1.2 is picked up, its port task must be updated to the real
  signature (the Composer will call `complete_structured` with a Pydantic `response_model`). Flag this;
  do not edit 1.2's implementation here.
- `team_maker/providers/registry.py` (Story 1.1's **key-availability catalog** — a data module) is a
  DIFFERENT concern from `team_maker/adapters/providers/` (LLM adapters). Do not move or merge 1.1's
  `providers/` in this story; its integration is Story 0.4. Note the name overlap in a docstring.

### Testing standards
- pytest; `tests/unit/test_*.py`; in-memory, no network, no real key. Provider `complete_structured`
  network paths are already exercised in `test_model_registry.py` via monkeypatched clients — keep those
  passing. Prefer back-compat shims so `test_model_registry.py` needs no edits. [Source:
  project-context.md#Testing-Rules; tests/unit/test_model_registry.py]
- Definition of done for this story: `python -m pytest tests/unit -q` is green (≥172 passed) and
  `make lint` is clean.

### Project Structure Notes
- **New packages:** `team_maker/ports/` (`llm_provider.py`), `team_maker/adapters/` +
  `team_maker/adapters/providers/` (the five moved adapters + data-driven `create_provider`).
- **Shim (recommended):** keep `team_maker/llm/providers.py` as a re-export shim (`from
  team_maker.adapters.providers import *` + `from team_maker.ports.llm_provider import LLMProvider`) so
  existing imports and tests keep working with a minimal diff. Remove the shim in a later cleanup once all
  call sites are migrated (track in deferred-work if kept).
- Keep adapters' lazy SDK imports; do not add SDKs to top-level module scope.

### References
- [Source: project-docs/epics.md#Epic-0, #Story-0.1] — story + ACs (AD-1, AD-2, AD-6, AD-8)
- [Source: project-docs/stories/reconciliation-notes.md] — context, divergence table (row 1)
- [Source: project-docs/architecture/architecture-team_maker-2026-07-05/ARCHITECTURE-SPINE.md#AD-1, #AD-2, #AD-4, #AD-8, #Structural-Seed, #Consistency-Conventions]
- [Source: project-docs/project-context.md#Validation-Rules, #Language-Specific-Rules, #Technology-Stack, #Testing-Rules]
- [Source: team_maker/llm/providers.py (ABC line 39, create_provider line 409), team_maker/llm/planner.py, team_maker/llm/__init__.py, tests/unit/test_model_registry.py]
- [Source: project-docs/stories/1-2-compose-team-spec.md#Task-1] — the superseded `complete()->str` port sketch
- [Source: project-docs/stories/deferred-work.md] — Story 0.4 (key/provider unification), Story 0.2 (mapper de-branching)

## Dev Agent Record

### Agent Model Used

claude-opus-4-8 (Claude Code, dev-story workflow)

### Debug Log References

- `python -m pytest tests/unit -q` → **182 passed** (172 pre-existing + 10 new). No regressions.
- `python -m ruff check` on all new/changed files → **All checks passed** (after autofix combined the
  shim's port imports).
- Import smoke: `from team_maker.llm.providers import GoogleProvider, XAIProvider` (shim) and
  `from team_maker.ports.llm_provider import LLMProvider` both resolve; `python -m team_maker
  list-templates` and `keys status` unaffected.

### Completion Notes List

- **Port (Task 1):** `team_maker/ports/llm_provider.py` defines `LLMProvider` as a `@runtime_checkable`
  `typing.Protocol` with the **existing** `complete_structured(system, user, response_model: type[T]) -> T`
  signature (kept the `TypeVar` bound to `BaseModel`). Documented that this supersedes Story 1.2's
  `complete() -> str` sketch — flagged for 1.2, not changed here.
- **Adapters (Task 2):** the five providers moved verbatim (behavior-identical) to
  `team_maker/adapters/providers/<impl>_provider.py`; they satisfy the port structurally (no subclassing).
  Shared `_closest_model` moved to `adapters/providers/_model_match.py`. Modules named `*_provider.py`
  to avoid shadowing the top-level `anthropic`/`openai`/`google` packages. Lazy SDK imports preserved.
- **Factory (Task 3):** `create_provider` is now a registry lookup (`_ADAPTERS: dict[str, Callable]`) — no
  `if provider == ...` chain. Signature, per-provider defaults, and the exact `ValueError("Unknown
  provider '...'. Supported: ...")` message are preserved (registry insertion order reproduces the old
  "anthropic | openai | xai | google | ollama" list).
- **Call sites (Task 4):** `llm/planner.py` imports the port from `ports/` and `create_provider` from
  `adapters/providers`; `llm/__init__.py` re-exports the concretes from their new home. `llm/providers.py`
  kept as a **back-compat shim** re-exporting port + adapters, so `tests/unit/test_model_registry.py`
  needed zero edits.
- **Scope guards honored:** no change to key sourcing (env-var reads preserved — Story 0.4); mapper
  de-branching untouched (Story 0.2); no `crewai` import introduced.
- **Follow-up:** the shim can be removed once all imports migrate; track in deferred-work if kept. Story
  1.2's port task should be updated to `complete_structured`.

### File List

- `team_maker/ports/__init__.py` (new)
- `team_maker/ports/llm_provider.py` (new — `LLMProvider` Protocol + `T`)
- `team_maker/adapters/__init__.py` (new)
- `team_maker/adapters/providers/__init__.py` (new — data-driven `create_provider` + re-exports)
- `team_maker/adapters/providers/_model_match.py` (new — `_closest_model`)
- `team_maker/adapters/providers/anthropic_provider.py` (new — moved)
- `team_maker/adapters/providers/openai_provider.py` (new — moved)
- `team_maker/adapters/providers/xai_provider.py` (new — moved)
- `team_maker/adapters/providers/ollama_provider.py` (new — moved)
- `team_maker/adapters/providers/google_provider.py` (new — moved)
- `team_maker/llm/providers.py` (modified — now a back-compat re-export shim)
- `team_maker/llm/__init__.py` (modified — re-export from `adapters/providers`)
- `team_maker/llm/planner.py` (modified — import port from `ports/`, factory from `adapters/`)
- `tests/unit/test_llm_provider_port.py` (new — port shape + data-driven factory)

## Change Log

- 2026-07-12 — Story drafted via create-story context engine (exhaustive analysis of the merged
  guru-explore code: `llm/providers.py`, `llm/planner.py`, `llm/__init__.py`, `test_model_registry.py`;
  architecture spine; project-context; prior stories 1.1/1.2). Pure-refactor scope, behavior-preserving,
  172-tests-green gate. Status → ready-for-dev.
- 2026-07-12 — Implemented via dev-story. Migrated `LLMProvider` → `team_maker/ports/`, moved the five
  providers → `team_maker/adapters/providers/`, made `create_provider` data-driven, kept
  `llm/providers.py` as a back-compat shim. Added `tests/unit/test_llm_provider_port.py`. Full suite
  **182 passed**, ruff clean. Behavior unchanged. Status → review.
