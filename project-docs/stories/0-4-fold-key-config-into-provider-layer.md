---
baseline_commit: 517ce41bbacfdc4e950ff2c4758046a50e089ad6
---

# Story 0.4: Fold the Key Config feature into the provider layer

Status: ready-for-dev

<!-- RECONCILIATION STORY (Epic 0) — see project-docs/stories/reconciliation-notes.md (divergence row 4)
     and project-docs/stories/deferred-work.md ("Deferred from: reconciliation"). Unifies the
     Story-1.1 key/availability system (keyconfig.py + providers/registry.py) with the merged
     guru-explore model_resolver.py, which today reads keys independently via raw os.environ. The
     full unit suite (185+ tests, growing with 0.1-0.3's additions) MUST stay green throughout. -->

## Story

As the codebase,
I want one key-loading and provider-availability system behind the provider layer,
so that `keyconfig.py`/`providers/registry.py`'s Key Config file and `llm/model_resolver.py`'s
live-model validation stop sourcing keys independently (AD-9 split-brain), while the `keys status`
CLI keeps working.

## Acceptance Criteria

1. **Given** `team_maker/providers/registry.py` (the `Provider`/`ProviderStatus` dataclasses, the
   `PROVIDERS` catalog, `report_availability`/`is_usable`/`env_to_provider`) and
   `team_maker/keyconfig.py` (which imports from it), **When** relocated, **Then** the catalog moves
   to `team_maker/adapters/providers/registry.py` — physically "behind the provider layer"
   established by Story 0.1 — `keyconfig.py` and `cli.py`'s `keys status` command update their
   imports accordingly, and `team_maker/providers/` is deleted (no shim: `git grep` confirms only
   `keyconfig.py` and its own tests import it, both updated in this story). (AD-2, AD-9)
2. **Given** the catalog's env-var facts disagree with the adapters that actually authenticate LLM
   calls — `PROVIDERS` says google's key is `GOOGLE_API_KEY`, but
   `adapters/providers/google_provider.py`'s real default (preserved byte-for-byte since Story 0.1)
   is `GOOGLE_AI_API_KEY`; and `xai` (supported end-to-end by `adapters/providers/xai_provider.py`,
   `llm/mapper.py`'s `_PROVIDER_ENV_VARS`, and `llm/model_resolver.py`'s `_FETCHER_MAP`) is **absent**
   from `PROVIDERS` entirely, so `keys status` can never report on it — **When** the catalog is
   corrected, **Then** `google`'s entry uses `GOOGLE_AI_API_KEY`, an `xai` entry is added with
   `XAI_API_KEY`, and neither change touches the adapters/mapper/model_resolver (which already agree
   with each other — only the catalog was wrong). `groq` and `openrouter` remain in the catalog
   unchanged (PRD FR-6/FR-22 forward-looking intent, Story 1.1 design) with a code comment noting
   `groq` has no concrete provider adapter yet (not in `adapters/providers/`, `mapper.py`, or
   `model_resolver.py`) — building one is new-feature work, out of scope here. (AD-1, AD-9)
3. **Given** `llm/model_resolver.py`'s per-provider fetchers (`_anthropic_models`,
   `_openai_models`, `_xai_models`, `_google_models`) read a key **exclusively** via
   `os.environ.get(api_key_env, "")`, completely bypassing the Key Config file — so a key present
   only in `team_maker.keys` (not the shell env) is correctly reported "available" by `keys status`
   but silently never used for live model-list validation (the fetch fails, is caught, and
   `resolve_routing` falls back to trusting the YAML unchanged) — **When** unified, **Then**
   `resolve_routing`/`normalize_team_routings` resolve each agent's key by checking a loaded
   `KeyConfig` **first** (`config.has(provider)` → `config.keys[provider].get_secret_value()`) and
   falling back to `os.environ.get(api_key_env, "")` only when the provider has no Key Config entry
   (covers a per-agent custom `api_key_env` override that names a non-default env var). This is
   **strictly additive**: every case that resolved a key via `os.environ` before still does (the
   fallback path is unchanged); the only new behavior is that a key living solely in the Key Config
   file now also gets used. (AD-9)
4. **Given** `report_availability`/`is_usable`/`STATUS_*` constants and the `keys status` CLI table
   are the load-bearing, already-tested contract (`tests/unit/test_provider_availability.py`,
   `tests/unit/test_cli_keys_status.py`, `tests/unit/test_keyconfig.py`), **When** this story lands,
   **Then** all three pass **unchanged** except `test_cli_keys_status.py`'s `PROVIDER_ENVS`
   env-clearing hygiene list, which gains `GOOGLE_AI_API_KEY` and `XAI_API_KEY` (additive — prevents a
   real shell env var from leaking into the test now that the catalog checks those names), and the
   full unit suite stays green (≥185 passed, growing with this story's new tests). (AD-9)

## Tasks / Subtasks

- [ ] **Task 1 — Relocate the catalog behind the provider layer** (AC: 1)
  - [ ] Create `team_maker/adapters/providers/registry.py`; move `Provider`, `ProviderStatus`,
    `PROVIDERS`, `STATUS_*` constants, `USABLE_STATUSES`, `OPENROUTER`, `is_usable`,
    `env_to_provider`, `report_availability` into it verbatim (the `TYPE_CHECKING`-guarded
    `from team_maker.keyconfig import KeyConfig` import stays — it's only for the type hint on
    `report_availability`, and the import-cycle concern is identical to today).
  - [ ] Update `team_maker/keyconfig.py`'s `from team_maker.providers.registry import PROVIDERS,
    env_to_provider` → `from team_maker.adapters.providers.registry import PROVIDERS,
    env_to_provider`.
  - [ ] Update `team_maker/cli.py`'s `keys status` command import site to the new path.
  - [ ] Run `git grep -rn "team_maker.providers\b\|from team_maker\.providers"` — confirm the only
    remaining hits are the two files just updated plus this story's own tests (Task 4), then delete
    `team_maker/providers/` (`__init__.py`, `registry.py`). No shim needed.

- [ ] **Task 2 — Fix the catalog's data disagreements** (AC: 2)
  - [ ] In the relocated `PROVIDERS` list: change `Provider("google", "GOOGLE_API_KEY", ...)` →
    `Provider("google", "GOOGLE_AI_API_KEY", ...)` (matches
    `adapters/providers/google_provider.py`'s real default — do not touch that adapter).
  - [ ] Add `Provider("xai", "XAI_API_KEY")` (no `openrouter_reachable=True` — no existing source
    claims xai is OpenRouter-reachable; leave the default `False` rather than guessing).
  - [ ] Add a comment above `PROVIDERS` (or on the `groq` row) noting: `groq` is catalogued per PRD
    FR-6 but has no concrete adapter in `adapters/providers/`, `llm/mapper.py`, or
    `llm/model_resolver.py` yet — it will always report `missing` unless reached `via-openrouter`;
    wiring a real Groq adapter is tracked as separate future work, not this story.

- [ ] **Task 3 — Thread `KeyConfig` into `model_resolver.py`, additively** (AC: 3)
  - [ ] Change each fetcher's parameter from the env-var **name** to the resolved key **value**:
    `_anthropic_models(api_key: str)`, `_openai_models(api_key: str)`, `_xai_models(api_key: str)`,
    `_google_models(api_key: str)` — replace each fetcher's internal `key =
    os.environ.get(api_key_env, "")` line with using the `api_key` parameter directly (the
    `@lru_cache` still works: it now caches per key-value instead of per-env-var-name, which is
    equivalent or better since the same value should resolve identically regardless of which name it
    came from).
  - [ ] Add a module-level `_resolve_key(provider: str, api_key_env: str, config: KeyConfig) -> str`:
    `return config.keys[provider].get_secret_value() if config.has(provider) else
    os.environ.get(api_key_env, "")`.
  - [ ] In `resolve_routing(routing, config)` — add a `config: KeyConfig` parameter — replace
    `api_key_env = routing.api_key_env or ""` + the direct `fetcher(api_key_env)` call with:
    resolve `api_key = _resolve_key(provider, routing.api_key_env or "", config)`, then call
    `fetcher(api_key)`.
  - [ ] `normalize_team_routings(team: GeneratedTeam, config: KeyConfig | None = None)` — load
    `config = config or KeyConfig.from_file()` once at the top (do NOT reload per-agent), pass it to
    every `resolve_routing(agent.routing, config)` call. Keep the default-`None`-loads-from-disk
    behavior so `pipeline/runner.py`'s existing call site (`normalize_team_routings(team)`) needs
    **zero changes**.
  - [ ] Import `KeyConfig` from `team_maker.keyconfig` at module level in `model_resolver.py` (no
    cycle: `keyconfig.py` only imports from `adapters/providers/registry.py`, not from
    `llm/model_resolver.py`).

- [ ] **Task 4 — Tests** (AC: 4)
  - [ ] Move `tests/unit/test_provider_availability.py`'s import
    `from team_maker.providers.registry import (...)` → `from team_maker.adapters.providers.registry
    import (...)` (mechanical, no assertion changes).
  - [ ] `tests/unit/test_cli_keys_status.py`: add `"GOOGLE_AI_API_KEY"` and `"XAI_API_KEY"` to
    `PROVIDER_ENVS`.
  - [ ] New `tests/unit/test_model_resolver_keyconfig.py`: monkeypatch one fetcher (e.g.
    `team_maker.llm.model_resolver._anthropic_models`) to assert it is called with the key **value**
    from a `KeyConfig` built in-memory (`KeyConfig(keys={"anthropic": SecretStr("sk-from-file")})`)
    when no matching env var is set, proving the Key-Config-first resolution works; and a second case
    confirming the `os.environ` fallback still fires when `config.has(provider)` is `False` (empty
    `KeyConfig()`), matching today's exact behavior.
  - [ ] Run `python -m pytest tests/unit -q` → expect ≥185 passed (185 + new tests, unchanged
    assertions in the three files touched for import-path/hygiene only).
  - [ ] Run `python -m pytest tests/integration -k "not live" -q` → expect the existing 20 to keep
    passing (no network/keys in CI means `normalize_team_routings` stays a no-op there, unchanged).
  - [ ] `ruff check` clean on every new/changed file (line-length 100; E,F,I,N,W; E501 ignored).

## Dev Notes

### What this story is (and is not)
- **Is:** relocating the Story-1.1 key-availability catalog into the provider layer (`adapters/
  providers/`), fixing its two concrete data bugs (google's env var, missing xai) so it agrees with
  the adapters/mapper/model_resolver that already agree with each other, and making
  `model_resolver.py`'s live-model validation **additionally** consult the Key Config file (file
  first, `os.environ` fallback — never a regression, only a new source).
- **Is NOT:** wiring `KeyConfig` into `llm/planner.py` or the `adapters/providers/*` provider classes'
  own key-reading (`os.environ.get(self.api_key_env)` inside each adapter, preserved exactly since
  Story 0.1) — that is pre-run credential resolution proper (FR-10/FR-21, Epic 1 Story 1.6's job, and
  arguably needs its own fail-fast design). **Is NOT** adding a real Groq provider/adapter (new
  feature, not reconciliation). **Is NOT** touching `mapper.py`'s `_PROVIDER_ENV_VARS` (Story 0.2,
  done — deliberately local by design) or the CrewAI/runtime seam (Story 0.3, done).

### Current state (read before writing)
- `team_maker/providers/registry.py` — `Provider`/`ProviderStatus` dataclasses, `PROVIDERS: list[Provider]`
  = anthropic (`ANTHROPIC_API_KEY`), openai (`OPENAI_API_KEY`), google (`GOOGLE_API_KEY` — **wrong**,
  should be `GOOGLE_AI_API_KEY`), groq (`GROQ_API_KEY` — **no adapter anywhere**), ollama (keyless),
  openrouter (`OPENROUTER_API_KEY`). **Missing: xai.** `report_availability(config)` computes
  MISSING/AVAILABLE/KEYLESS_LOCAL/VIA_OPENROUTER per provider; `is_usable` treats only MISSING as
  blocking.
- `team_maker/keyconfig.py` — `KeyConfig.from_file(path=None, include_env=True)`: reads the
  `.env`-style file (file wins), then fills any provider `env_to_provider()` recognizes that the file
  didn't set from `os.environ` (fallback). Result: `KeyConfig.keys: dict[str, SecretStr]` keyed by
  **provider name**. `KeyConfig.has(provider)` / `.keys[provider].get_secret_value()`.
- `team_maker/llm/model_resolver.py` — `_FETCHER_MAP` = anthropic/openai/xai/google (no groq, no
  ollama — ollama is skipped by `resolve_routing` via `fetcher_info is None`). Each `_xxx_models`
  fetcher is `@lru_cache`d, takes `api_key_env: str`, does `os.environ.get(api_key_env, "")` —
  **never consults `KeyConfig`**, so a key that's only in `team_maker.keys` is invisible here (fetch
  returns `()`, treated as "API unreachable — trust the YAML", not a crash — just silently skipped).
  `resolve_routing(routing) -> (updated_routing, message|None)`; `normalize_team_routings(team)` is
  the only function called externally, from `pipeline/runner.py:143-144`
  (`normalize_team_routings(team)`, no config arg today).
- **No existing test exercises `model_resolver.py`'s internals directly** (confirmed via search) —
  only `pipeline/runner.py`'s call to `normalize_team_routings(team)` in `_build_manifest` touches it,
  and integration tests run with no network/keys, so today it's always a no-op in CI. This gives Task
  3 freedom to change fetcher signatures.
- `adapters/providers/google_provider.py` default `api_key_env="GOOGLE_AI_API_KEY"`;
  `adapters/providers/xai_provider.py` default `api_key_env="XAI_API_KEY"` — both from Story 0.1,
  behavior-preserved from the original merged code; these are the ground truth the catalog must
  match.
- `schema/request.py::ProviderConfig.provider` is a free-form string documented as
  `"anthropic | openai | xai | google | ollama"` — confirms xai (not groq) is the real 5th provider
  in the actual execution path today; groq is catalog-only/aspirational (PRD FR-6 lists it for a
  *future* state).

### Architecture constraints (binding)
- **AD-9 — one key/provider-availability system, keys read-only from Key Config, never logged.** This
  story is the direct implementation of that invariant for the *availability-reporting + live-model-
  validation* seam (planner/adapter key-reading is explicitly out of scope — see "Is NOT"). [Source:
  ARCHITECTURE-SPINE.md#AD-9]
- **AD-1 — no branching on identity; differences are data.** The catalog stays a data table
  (`PROVIDERS` list); do not introduce `if provider == "xai"` anywhere. [Source:
  ARCHITECTURE-SPINE.md#AD-1]
- **AD-2 — ports-and-adapters.** The availability catalog belongs under `adapters/providers/`
  (the provider layer), alongside Story 0.1's LLM-call adapters — not a separate top-level
  `providers/` package. [Source: ARCHITECTURE-SPINE.md#AD-2]

### Project conventions (must follow — from project-context.md)
- `from __future__ import annotations`; full type hints; built-in generics; snake_case; ruff
  line-length 100 (E,F,I,N,W; `E501` ignored); `make lint`/`make fmt`.
- Keys are `pydantic.SecretStr`; never log or print a secret value — `_resolve_key` returns a plain
  `str` only at the point of use (matches the existing `KeyConfig` docstring's own rule).
- Never branch on provider name — `PROVIDERS`/`_FETCHER_MAP`/`_resolve_key` all stay data-driven.

### Testing standards
- pytest, `tests/unit/test_*.py`, in-memory, no real network/keys.
- Definition of done: `python -m pytest tests/unit -q` green (≥185, growing) +
  `python -m pytest tests/integration -k "not live" -q` green (20, unchanged) + `ruff check` clean.

### Project Structure Notes
- **New file:** `team_maker/adapters/providers/registry.py` (moved catalog).
- **Removed:** `team_maker/providers/` (entire package).
- **Modified:** `team_maker/keyconfig.py` (import path only), `team_maker/cli.py` (import path only),
  `team_maker/llm/model_resolver.py` (fetcher signatures + `KeyConfig`-aware resolution).
- No change to `team_maker/adapters/providers/__init__.py`'s `create_provider`/`_ADAPTERS` (Story
  0.1) — that factory is a different concern (constructing an `LLMProvider` for the planner) from
  this story's availability catalog + model-substitution key-sourcing.

### References
- [Source: project-docs/epics.md#Epic-0, #Story-0.4] — story + ACs (AD-9)
- [Source: project-docs/stories/reconciliation-notes.md] — divergence row 4
- [Source: project-docs/stories/deferred-work.md] — "Deferred from: reconciliation" (confirms
  unification of keyconfig.py/providers/registry.py with model_resolver.py is this story's job,
  not indefinitely deferred)
- [Source: project-docs/stories/0-2-remove-provider-name-branching.md#Scope-guard] — flagged the
  google env-var mismatch / missing xai as deferred to this story
- [Source: project-docs/architecture/architecture-team_maker-2026-07-05/ARCHITECTURE-SPINE.md#AD-1,
  #AD-2, #AD-9]
- [Source: project-docs/project-context.md#Validation-Rules, #Technology-Stack]
- [Source: team_maker/keyconfig.py, team_maker/providers/registry.py, team_maker/llm/model_resolver.py,
  team_maker/adapters/providers/google_provider.py, xai_provider.py, __init__.py,
  team_maker/schema/request.py (ProviderConfig docstring), team_maker/cli.py (keys status)]
- [Source: tests/unit/test_provider_availability.py, test_cli_keys_status.py, test_keyconfig.py] —
  the load-bearing behavioral contract this story must not regress

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List

## Change Log

- 2026-07-12 — Story drafted via create-story context engine (exhaustive analysis of the
  keyconfig.py/providers/registry.py/model_resolver.py split-brain, the google env-var and missing-xai
  data bugs flagged by Story 0.2, the adapters' real defaults from Story 0.1, deferred-work.md's
  explicit non-deferral of this unification, and the existing test suite's exact behavioral contract —
  no test exercises model_resolver.py's internals directly, giving room to change fetcher signatures
  safely). Additive-only scope for the KeyConfig↔model_resolver unification; planner/adapter key-
  reading and a real Groq adapter explicitly deferred. Status → ready-for-dev.
