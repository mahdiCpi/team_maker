---
baseline_commit: e5021f3459fa963b731881afda13b49d2e527df5
---

# Story 1.2: Compose a valid Team Spec from a prompt

Status: done

<!-- RECONCILIATION UPDATE 2026-07-12 — see project-docs/stories/reconciliation-notes.md.
     The stale baseline (e5021f3) is superseded: the real code from guru-explore is now merged
     into main/develop. This story is NO LONGER greenfield. Overlapping functionality already
     exists as team_maker/llm/planner.py (LLM-driven design) + team_maker/schema/request.py
     (a substantial `_pre_process` before-validator: stack flattening, aliasing, notification
     mapping, tool promotion, model_registry reference resolution).
     Re-scope this story as a REFACTOR: fold llm/planner.py into a composer/ module behind the
     new ports/LLMProvider Protocol (Epic 0, Story 0.1) and REUSE schema/request.py's validation
     rather than re-implementing it. Story 1.1's code (keyconfig.py, providers/, `keys status`)
     is now COMMITTED to main (no longer uncommitted) — consume it as existing prior art. -->

<!-- RECONCILIATION UPDATE 2026-07-25 (bmad-correct-course, Epic 1 course correction) —
     Epic 0 has since merged into develop (commit 87642dc) and epic_1/story_1_2 have been
     fast-forwarded to that tip. Two of this story's Tasks are now STALE because Epic 0 already
     built the things they described:
       - Task 1 ("define the LLMProvider port") is DONE — `team_maker/ports/llm_provider.py`
         exists (Story 0.1). Its real signature is `complete_structured(self, system: str,
         user: str, response_model: type[T]) -> T`, NOT the `complete(*, system, prompt,
         model=None) -> str` sketch originally written here — the port module's own docstring
         says as much ("supersedes the complete() -> str sketch in Story 1.2 Task 1").
       - Task 2 ("LLM adapter + credential resolution") is PARTIALLY done — five concrete
         adapters (`AnthropicProvider`, `OpenAIProvider`, `XAIProvider`, `GoogleProvider`,
         `OllamaProvider`) already exist under `team_maker/adapters/providers/`, all satisfying
         the port, wired through a data-driven `create_provider(config: ProviderConfig)` factory
         (Story 0.1). **No OpenRouter adapter exists yet** — the original "recommended default:
         OpenRouter" plan is still valid as an option but is no longer required to get a first
         working Composer, since five ready-made providers already exist. Recommend defaulting
         the Composer's authoring model to one of the five existing adapters (e.g. anthropic,
         matching `templates/software_delivery/template.py`'s `_DEFAULT_PROVIDER`) and treating
         an OpenRouter adapter as a follow-on enhancement, not a blocking dependency.
       - Story 0.4 also relocated the key-availability catalog to
         `team_maker/adapters/providers/registry.py` (was `team_maker/providers/registry.py`) —
         every reference to the old path below is updated accordingly. The "naming decision"
         flagged in the original Project Structure Notes is resolved: `adapters/providers/` now
         hosts both the LLM-call adapters (Story 0.1) and the availability catalog (Story 0.4) —
         two concerns, one package, exactly as Story 0.4 designed it.
     Tasks 1 and 2 below are struck through and replaced with corrected guidance. Tasks 3-5 and
     all Acceptance Criteria are unchanged — no gap was found in the story's intent, only in two
     tasks' now-outdated "how". Status moves from `needs-rescoping` to `ready-for-dev`. -->

## Story

As a user,
I want to describe a team in plain language and get a valid Team Spec,
so that I don't hand-write configuration.

## Acceptance Criteria

1. **Given** a plain-language request, **When** the Composer runs via the `LLMProvider` port, **Then** it returns a `TeamCreationRequest` that passes `team_maker/schema/request.py` validation with no manual editing. (FR-1, AD-10)
2. **Given** the request names specific agents/roles/tasks/models (e.g. "an architect on Claude and a writer on Gemini, writer depends on architect"), **When** it is composed, **Then** those names and model choices are reflected in the emitted spec: role `name`s are snake_case and unique, named models map to `ProviderConfig` routing on the right role, and task intent is captured. (FR-1)
3. **Given** the LLM's first draft fails schema validation, **When** the Composer runs, **Then** it feeds the concrete validation errors back to the model and re-derives the spec within a bounded retry budget, re-validating each attempt. (FR-2, AD-10)
4. **Given** it cannot produce a schema-valid spec within the retry budget, **When** the Composer finishes, **Then** it raises/returns a single clear, plain-language error (no raw stack trace) and never surfaces or returns an invalid spec. (FR-2, FR-15)
5. **Given** a stated preference (a named provider/model, "use local/cheap models", "use Claude") **When** per-agent routing is assigned, **Then** the emitted routing honors it; **And** absent any preference, routing is left unset so the factory default applies (`role.llm → default_llm → _DEFAULT_PROVIDER`), optionally biased toward a provider the user actually has a key for. (FR-4)
6. **Given** any LLM call the Composer makes, **When** it authors or repairs a spec, **Then** the call goes through the single `LLMProvider` port (the Composer core imports the port, never a concrete SDK; no branching on provider name), **And** the Composer's own model credentials are read from the Key Config only — never from global env, never logged, never in output. (AD-8, AD-9, AD-2, AD-4, AD-7-alignment)
7. **Given** the CLI, **When** the user runs `team-maker compose`, **Then** it emits/writes the validated spec (YAML), mirrors the `create` command's style, and uses exit codes `0` ok / `1` error / `2` spec-invalid; **And** the `LLMProvider` is injectable so unit tests run fully offline against a fake provider (no network, no real key). (FR-1, testing)

## Tasks / Subtasks

- [x] ~~**Task 1 — Define the `LLMProvider` port** (AC: 6)~~ **DONE by Story 0.1 — consume, do not recreate.**
  - [x] `team_maker/ports/llm_provider.py` already defines `LLMProvider` as a `typing.Protocol` with `complete_structured(self, system: str, user: str, response_model: type[T]) -> T` (structured-output, not the free-text `complete()` sketch originally planned here). Import it from `team_maker.ports.llm_provider`; do not redefine it.
  - [x] Update this story's downstream tasks/tests to call `complete_structured(system=..., user=..., response_model=TeamCreationRequest)` (or an intermediate draft model) instead of a free-text `complete()` call.

- [x] **Task 2 — Pick/extend an LLM adapter for the Composer's authoring model** (AC: 6)
  - [x] Five concrete adapters already exist and satisfy the port: `team_maker/adapters/providers/{anthropic,openai,xai,google,ollama}_provider.py`, wired through the data-driven `create_provider(config: ProviderConfig) -> LLMProvider` factory in `team_maker/adapters/providers/__init__.py` (Story 0.1). **Default the Composer's authoring model to one of these** (recommend `anthropic`, matching `templates/software_delivery/template.py`'s `_DEFAULT_PROVIDER`) rather than building a new adapter first.
  - [x] **No OpenRouter adapter exists yet.** Adding one (via the `openai` SDK pointed at OpenRouter's `base_url`, per the original Latest-tech notes below) remains a valid option for "one key → many models," but is now an *enhancement*, not a blocking dependency — a working Composer no longer requires a new SDK dependency to ship. (Not added — out of scope per the reconciliation note; tracked as future work, not deferred-work.md since it was never started.)
  - [x] Resolve the authoring key from `KeyConfig.from_file(...)` (Story 1.1). Call `.get_secret_value()` **only** at the point of the network call. Never read a raw global env var for routing, never log or echo the key (AD-7, AD-9). Reuse `team_maker/adapters/providers/registry.py` (`PROVIDERS`, `report_availability`, `is_usable`) — moved here from `team_maker/providers/registry.py` by Story 0.4; do not re-implement key logic.
  - [x] Keep it data-driven: never branch on provider name in logic (AD-1/AD-8). Map user model words → provider IDs via a small alias table or registry extension (claude→anthropic, gemini→google, chatgpt→openai).
  - [x] If (and only if) an OpenRouter adapter is added: add the LLM SDK dependency to `pyproject.toml`/`requirements.txt`, add `openai>=1.x`, point `base_url` at OpenRouter, and note the choice in the module docstring. (N/A — no OpenRouter adapter added this story.)

- [x] **Task 3 — Composer core: `compose(intent, preferences) -> TeamCreationRequest`** (AC: 1, 2, 3, 4, 5)
  - [x] Create `team_maker/composer/__init__.py` and `team_maker/composer/composer.py` with a `Composer` class that takes an `LLMProvider` by constructor injection (so tests inject a fake). Expose a single stateless `compose(intent: str, *, preferences: ... = None) -> TeamCreationRequest`.
  - [x] Build a system prompt that instructs the model to emit structured output (JSON) matching the schema. Embed the binding field rules inline: required `team_name`/`purpose`/`output_path`, ≥1 role, `RoleDefinition.name` = `^[a-z][a-z0-9_]*$` and unique, `description` min length 5, `ProviderConfig{provider,model,api_key_env?}`, valid enum values. Parse the model output, then `TeamCreationRequest.model_validate(...)`.
  - [x] **Validate-and-repair loop:** on `pydantic.ValidationError`, format the errors (loc → msg, like `cli.py` does) and re-prompt the same LLM to fix ONLY those errors; re-validate. Bound with `max_repair_attempts` (recommend default 3, configurable). On exhaustion raise a dedicated `ComposerError` carrying a plain-language message + the last validation errors — never return/emit an invalid spec (AC 4).
  - [x] **Routing (FR-4):** honor named providers/models and preferences ("local/cheap" → prefer ollama / a cheaper model; "use Claude" → anthropic). With no preference, leave `role.llm`/`default_llm` unset so the template's `_DEFAULT_PROVIDER` chain applies — do NOT re-implement that resolution (it lives in `templates/software_delivery/template.py`). Optionally bias an unspecified choice toward a provider with a usable key (`report_availability`/`is_usable`), but the spec must stay schema-valid even when a named model's key is missing (key gating is Story 1.6/2.3, not here).
  - [x] Keep `compose()` stateless and idempotently re-invokable (Story 1.3 wraps it per conversational turn; Epic 2/FR-16 wraps it as an endpoint). No conversation loop, no "run now" here — that is Story 1.3 (FR-20).

- [x] **Task 4 — `team-maker compose` CLI command** (AC: 7)
  - [x] Add a `compose` command in `team_maker/cli.py` via `@main.command()`, mirroring `create`: positional `intent` (or `--intent`), `--out/-o` (write the spec YAML using `utils/yaml_utils.dump_yaml`), `--key-file/-f` (`click.Path(exists=True, dir_okay=False)`), `--model` (override authoring model), optional `--build` (chain into `PipelineRunner().run(request)`), `--quiet/-q`.
  - [x] Wire the real adapter (Task 2) but keep the port injectable. Use module-level `console`/`err_console`; render a `rich` summary of the composed spec. Exit `1` on load/LLM/parse/compose errors, `2` if the produced spec fails validation, `0` on success. Never print key values (`rich.markup.escape` any user text; follow `keys status` precedent).

- [x] **Task 5 — Tests (offline, fake provider)** (AC: 1–7)
  - [x] Add `tests/unit/test_composer.py` with a `FakeLLMProvider` implementing the port (returns scripted strings; NO network). Cover: happy path → valid `TeamCreationRequest`; named models/roles/tasks reflected (AC 2); repair loop (fake returns an invalid draft, then a valid one → asserts success within the bound and that re-validation occurred) (AC 3); exhausted retries → `ComposerError` with a clear message and **no invalid spec returned** (AC 4); preference honored vs. default-left-unset routing (AC 5); constructor injection proves no concrete SDK is needed in tests (AC 6).
  - [x] Add `tests/unit/test_cli_compose.py` mirroring `tests/unit/test_cli_keys_status.py`: monkeypatch/inject the fake provider, assert exit codes `0/1/2`, the spec YAML is written, and **no key value appears in output**.
  - [x] Reuse `tests/conftest.py` fixtures (`minimal_request`, `full_request`) to assert the Composer can produce equivalent validated requests. Keep everything in-memory (`tmp_path` for any file). pytest discovery: `tests/unit/test_*.py`.

### Review Findings

- [x] [Review][Decision] Composer's own authoring key is bridged into global `os.environ` for the existing adapters to read, contradicting AD-7/AD-9/AC6's "never from global env" — Confirmed to leak the real secret into the process environment persistently: reproduced directly (`ANTHROPIC_API_KEY` remained set to `test_compose_writes_spec_and_never_prints_secret`'s literal test secret after the test ran, since `os.environ.setdefault(...)` bypasses `monkeypatch`'s rollback). The 5 existing adapters (Story 0.1) only read credentials via `os.environ.get(self.api_key_env)` internally, so full AD-7 compliance ("explicit per-call credentials, never global env") requires either (a) accepting a scoped/restored env-bridge as an interim compromise, or (b) extending an adapter to accept an explicit key parameter (Story 1.6 scope per this story's own Dev Notes). **RESOLVED 2026-07-26: user chose option (a)** — scope the bridge with save/restore; tracked as the `[Review][Patch]` item immediately below. [`team_maker/cli.py:_resolve_authoring_provider`]
- [x] [Review][Patch] Scope the `os.environ` credential bridge with save/restore so it does not persist past the single CLI invocation — fixes the confirmed leak above and the "stale key across repeated calls" risk on key rotation. [team_maker/cli.py:_resolve_authoring_provider] — Fixed: replaced the `setdefault`-based mutation in `_resolve_authoring_provider` with a new `_bridged_credential` context manager that saves/restores the prior env value; `compose()` now wraps provider construction + `composer.compose()` in `with _bridged_credential(...)`. Verified with `test_bridged_credential_restores_prior_value_after_block` and `test_resolve_authoring_provider_and_bridged_credential_roundtrip`.
- [x] [Review][Patch] `--quiet` combined with no `--out` and no `--build` silently discards the composed spec — `spec_yaml` is computed but neither printed (guarded by `not quiet`) nor written, so the command exits `0` with no artifact at all. `--quiet` should only suppress the decorative summary Panel, consistent with its own help text ("Suppress progress output") — the spec itself is the deliverable and should always be emitted somewhere. [team_maker/cli.py:compose] — Fixed: the spec now always prints to stdout when `--out` is not given, regardless of `--quiet`. Verified with `test_compose_still_emits_spec_under_quiet_with_no_out_and_no_build`.
- [x] [Review][Patch] `out.write_text(spec_yaml, encoding="utf-8")` is unguarded — a missing parent directory or a permission error raises an unhandled traceback instead of a clean CLI error like the rest of the command. [team_maker/cli.py:compose] — Fixed: parent directories are created (`mkdir(parents=True, exist_ok=True)`) and the write is wrapped in `try/except OSError` → `sys.exit(1)` with a clean message.
- [x] [Review][Patch] `compose --build`'s `runner.run(request)` only catches `FileExistsError`; unlike the `create` command it's meant to mirror, it has no fallback `except Exception` clause to print a friendly `[bold]Pipeline error:[/bold]` message before re-raising. [team_maker/cli.py:compose] — Fixed: added the matching `except Exception as exc: ... raise` clause, now identical to `create`'s pipeline-error handling.
- [x] [Review][Patch] `_format_errors` produces a malformed `": <msg>"` string (leading colon, no location) for any pydantic error with an empty `loc` tuple — confirmed to occur for `TeamCreationRequest`'s own `check_unique_role_names` model-level validator, the exact scenario `test_compose_raises_after_exhausting_repair_budget` exercises. Fix: `loc = " → ".join(...) or "(root)"`. [team_maker/composer/composer.py:_format_errors] — Fixed exactly as specified.
- [x] [Review][Patch] `Composer.__init__` accepts a negative `max_repair_attempts` with no validation — `range(1, total_attempts + 1)` becomes empty, the provider is never called even once, and `ComposerError` is raised with an empty `errors` list and a nonsensical negative attempt count in the message. [team_maker/composer/composer.py:Composer.__init__] — Fixed: `__init__` now raises `ValueError` for `max_repair_attempts < 0`.
- [x] [Review][Patch] `_resolve_authoring_provider` — the only new code that calls `.get_secret_value()` — has no direct unit test; the existing CLI tests bypass it entirely by monkeypatching `create_provider`, so a broken key-resolution/env-bridge implementation would still pass every current test. Add a focused test (using `monkeypatch.setenv`/`delenv` for isolation, folding in the save/restore patch above). [tests/unit/test_cli_compose.py] — Fixed: added `test_resolve_authoring_provider_and_bridged_credential_roundtrip` and `test_bridged_credential_restores_prior_value_after_block`, exercising the real (non-mocked) resolution + bridging path.
- [x] [Review][Patch] AC5's "stated preference... routing honors it" is proven only via a direct `Composer.compose(..., preferences=...)` library call in `test_composer.py`; no test exercises a stated preference through the actual `team-maker compose` CLI command, even though AC7 requires CLI-level offline coverage. Add one CLI test where the intent text itself states a preference and assert it reaches the provider end-to-end. [tests/unit/test_cli_compose.py] — Fixed: added `test_compose_honors_stated_preference_through_the_cli`.
- [x] [Review][Defer] `compose --build` bridges only the authoring provider's key; per-role provider keys (openai/google/xai, as chosen by the LLM per the Composer's own alias table) are never bridged into env before `PipelineRunner().run()`. [team_maker/cli.py:compose] — deferred, pre-existing pattern; degrades gracefully via `model_resolver`'s existing "API unreachable — trust the YAML" fallback, and run-time key gating for non-authoring providers is explicitly Story 1.6/FR-10 scope per this story's own Dev Notes.
- [x] [Review][Defer] The generic `except Exception as exc: ... escape(str(exc))` around `composer.compose(intent)` could in theory echo secret-bearing text if an underlying SDK exception embeds credentials in its message. [team_maker/cli.py:compose] — deferred, matches the existing `create` command's identical raw-exception-printing pattern elsewhere in `cli.py`; not a new regression, and there's no existing scrubbing convention in the codebase to extend.
- [x] [Review][Defer] `_PROVIDER_ALIASES` is prompt-only guidance, never enforced in code — a malformed provider word from the LLM costs one extra repair round-trip instead of being silently corrected. [team_maker/composer/composer.py] — deferred; already caught by the existing AC3 validate-and-repair loop, an efficiency nit rather than a correctness gap.
- [x] [Review][Defer] `Composer.compose`'s repair loop only retries on `pydantic.ValidationError`; transient/network/parsing failures propagate immediately with no retry. [team_maker/composer/composer.py:Composer.compose] — deferred; AC3 explicitly scopes the retry budget to schema-validation failures, not general resilience.
- [x] [Review][Defer] No progress feedback (e.g. "repair attempt 2/3") is shown in non-quiet mode when the repair loop runs more than once. [team_maker/cli.py:compose] — deferred; a UX nicety not required by any AC.
- [x] [Review][Defer] `compose --model` overrides only the model string; the authoring provider is hardcoded to `anthropic` with no CLI flag to change it. [team_maker/cli.py:compose] — deferred; matches Task 4's literal spec, which only asked for a `--model` override, not a `--provider` override.

## Dev Notes

### What this story is (and is not)
- **Is:** the Composer — turn plain-language intent into a `TeamCreationRequest` that passes the existing factory schema, via a new single `LLMProvider` port, with a bounded validate-and-repair loop. Introduces the port + first LLM adapter + `composer/` module + a `compose` CLI surface.
- **Is NOT:** multi-turn conversational tuning or a "run now" escape (that is **Story 1.3 / FR-20** — but `compose()` must be re-invokable per turn so 1.3 can wrap it). NOT the Factory (it already builds packages — `PipelineRunner`, untouched). NOT run-time key gating / fast-fail (Story 1.6 / FR-10). NOT the UI (Epic 2). Do not add agent-execution or CrewAI here (factory-not-runtime invariant).

### Architecture constraints (binding)
- **AD-10 — Composer output must pass the factory schema.** Emit structured output validated against the factory Pydantic schema with a **bounded validate-and-repair loop; only a passing spec is surfaced or built.** The validation target is the existing `TeamCreationRequest` in `team_maker/schema/request.py` — reuse `.model_validate(...)`; do not fork or redefine the schema. [Source: project-docs/architecture/architecture-team_maker-2026-07-05/ARCHITECTURE-SPINE.md#AD-10]
- **AD-8 — one `LLMProvider` port; OpenRouter is an adapter and the default multi-provider path.** All LLM access (Composer and, later, agents) goes through one `LLMProvider` port; providers/gateways are adapters; adding a provider is an adapter/config change, never core branching. [Source: ...#AD-8]
- **AD-5 — Composer → Factory → Runtime.** The Composer authors the spec; the Factory deterministically builds; the Runtime only executes. Do not let the Composer build packages itself (delegate to `PipelineRunner`) and do not push composition into the runtime. [Source: ...#AD-5]
- **AD-2 / AD-4 — ports-and-adapters, inward dependencies.** Core (`composer/`) depends only on the port interface; the concrete adapter is never imported by core. Dependency direction `UI → API → core → adapters`; keep `composer/` free of UI/CLI/SDK imports so Epic 2 (UI) and Epic 4 (API/FR-16) can consume it. [Source: ...#AD-2, #AD-4]
- **AD-9 — keys live only in the Key Config file, read-only.** The Composer's own authoring key comes from the Key Config (Story 1.1's `KeyConfig`), never entered in UI, never logged, never in output. Use `SecretStr`; call `.get_secret_value()` only at the network boundary. [Source: ...#AD-9]
- **AD-7 alignment — explicit per-call credentials, never global env.** The adapter must pass credentials explicitly to the client; do not rely on ambient `OPENAI_API_KEY`/`ANTHROPIC_API_KEY` env fallbacks for routing. (The hard per-agent conformance test is Story 1.6, but establish the discipline now.) [Source: ...#AD-7]
- **AD-1 — factory stays pure.** Generators remain pure string producers; only the writer touches disk; no provider-name branching. The Composer adds behavior *outside* the factory. [Source: ...#AD-1]

### Project conventions (must follow — from project-context.md)
- Start every module with `from __future__ import annotations`; full type hints; built-in generics (`list`/`dict`, `X | None`); snake_case; ruff line-length 100 (rules E,F,I,N,W, `E501` ignored). Run `make lint` / `make fmt`. [Source: project-docs/project-context.md]
- **Never branch on provider name** — provider differences live in the `PROVIDERS` catalog (data), not code paths. The word→provider alias map must also be data. [Source: project-docs/project-context.md#Validation-Rules]
- Input/config models = Pydantic v2 `BaseModel`; internal pass-around data = plain dataclasses. The Composer's *output* is the existing `TeamCreationRequest` (Pydantic) — don't invent a parallel model. [Source: project-docs/project-context.md#Language-Specific-Rules]
- Rich console output is cosmetic — the CLI must read from the returned object, never carry logic in the view. [Source: project-docs/project-context.md#Critical-Dont-Miss-Rules]
- `crewai` is NOT a dependency and must not be imported in `team_maker/`. [Source: project-docs/project-context.md#Technology-Stack]

### Existing code to align with (read before writing)
- `team_maker/schema/request.py` — the validation target. `TeamCreationRequest{team_name(min2, `^[A-Za-z][A-Za-z0-9_ \-]*$`), purpose(min10), output_path, desired_roles(min1, unique names via model_validator), default_llm?, documentation_level=STANDARD, template=SOFTWARE_DELIVERY, overwrite, tags, metadata}`; `RoleDefinition{name(`^[a-z][a-z0-9_]*$`), display_name?, description(min5), goal?, backstory?, capabilities[], tools[], llm?, is_optional}`; `ProviderConfig{provider(lowercased), model(stripped), api_key_env?}`. [Source: team_maker/schema/request.py]
- `templates/software_delivery/template.py` — holds `_DEFAULT_PROVIDER = ProviderConfig(provider="anthropic", model="claude-sonnet-4-6")` and the resolution chain `role.llm or default_llm or _DEFAULT_PROVIDER`. **Leave `llm` null when no preference** so this fills in — do not duplicate it in the Composer. [Source: team_maker/templates/software_delivery/template.py:198,245]
- `team_maker/keyconfig.py` — `KeyConfig.from_file(path=None, *, include_env=True)` (never raises; `.env`-style; file is source of truth, env is fallback), `has(provider)`, `default_path()`. Consume this for the authoring key. [Source: team_maker/keyconfig.py]
- `team_maker/adapters/providers/registry.py` (moved here from `team_maker/providers/registry.py` by Story 0.4) — `PROVIDERS` catalog (anthropic/openai/google/xai/ollama/openrouter/groq with `env_var`, `keyless_local`, `openrouter_reachable`), `report_availability(config) -> list[ProviderStatus]`, `is_usable(status)`, `USABLE_STATUSES`, `OPENROUTER`. Use for provider/model preference biasing. [Source: team_maker/adapters/providers/registry.py]
- `team_maker/cli.py` — `create` command is the template for `compose`: `load_yaml` guarded by try/except → `sys.exit(1)`; `TeamCreationRequest.model_validate(raw)` in try/except `ValidationError` printing `"  • {loc joined by →}: {msg}"` → `sys.exit(1)`; `PipelineRunner().run(request)`; `if not result.validation.passed: sys.exit(2)`. `keys status` shows the `--file` + `KeyConfig` + `rich.Table` + `escape()` pattern. Module `console`/`err_console`. [Source: team_maker/cli.py]
- `team_maker/pipeline/runner.py` — `PipelineRunner().run(request)` is the ONLY build path; `--build` should call it, not re-implement generation. [Source: team_maker/pipeline/runner.py]

### Previous story intelligence (Story 1.1 — done)
- Story 1.1 built the key/provider foundation this story consumes: `SecretStr` redaction is proven (repr/str/model_dump/json all redact; read only via `.get_secret_value()`) — reuse it for the authoring key. Statuses are descriptive; only `missing` blocks (`is_usable()`); direct key beats OpenRouter. [Source: project-docs/stories/1-1-load-keys-report-models.md#Completion-Notes]
- Key Config format decided in 1.1: `.env`-style `KEY=VALUE`, default `./team_maker.keys` or `$TEAM_MAKER_KEYS`, git-ignored (`.gitignore` already updated). [Source: 1-1#Completion-Notes]
- 1.1 review lessons to carry forward: guard all file reads (become warnings, don't crash); escape rich markup in any echoed user/path text; use built-in generics; add a CLI test AND a no-secret-in-output assertion. [Source: 1-1#Review-Findings]
- Deferred from 1.1 (do not "fix" incidentally): OpenRouter is identified by hardcoded name `OPENROUTER` (fine while it's the only gateway); keyless-local key ignored; duplicate-key last-wins. [Source: project-docs/stories/deferred-work.md]

### Testing standards
- pytest; `tests/unit/test_*.py`; in-memory, `tmp_path` for any file, NO network and NO real key in any test. The `LLMProvider` port exists partly to make this trivial — inject a `FakeLLMProvider`. [Source: project-docs/project-context.md#Testing-Rules; team_maker/tests/unit/]
- Mirror `tests/unit/test_cli_keys_status.py` for the CLI test (Click `CliRunner`, assert exit codes, assert no secret in output). Reuse `conftest.py` fixtures. [Source: tests/conftest.py, tests/unit/test_cli_keys_status.py]
- Highest-value tests here: the repair-loop-succeeds-within-bound and the exhausted-retries-never-emits-invalid-spec tests (they enforce AD-10/FR-2).

### Latest-tech notes
- **Structured output:** prefer JSON (not free-form YAML) from the model — easier to parse and validate. If using the OpenAI-compatible SDK, use JSON-mode / `response_format={"type":"json_object"}` where supported; otherwise instruct + parse defensively and let the repair loop catch drift. Pydantic v2 `model_validate` on the parsed dict is the gate.
- **OpenRouter adapter (recommended authoring path, AD-8):** OpenRouter is OpenAI-API-compatible — use the `openai` SDK with `base_url="https://openrouter.ai/api/v1"` and `api_key=<OPENROUTER key from KeyConfig>`. One key → many models (`anthropic/claude-*`, `openai/gpt-*`, `google/gemini-*`, …). **Verify the exact base URL, model-id format, and any required headers at implementation time** (endpoints drift). This keeps the repo to a single new SDK dependency.
- **Composer's own model / key source is a PRD Open Question (Q2/Q7)** — "which model authors the spec, and where its key comes from." Recommended resolution: default to OpenRouter with a configurable model, key from Key Config, overridable via `--model`; make the whole thing swappable behind the port. Confirm the default model choice with the user if unsure. [Source: prd.md#8 Open Questions]

### Project Structure Notes
- **Already exist (Story 0.1/0.4 — do not recreate):** `team_maker/ports/llm_provider.py`, `team_maker/adapters/providers/` (five concrete LLM adapters + `create_provider` factory + the relocated availability catalog `registry.py`). Only `team_maker/composer/` (`composer.py`, `ComposerError`) and the new CLI command in `cli.py` are net-new for this story. Tests under `tests/unit/`.
- **~~Naming decision~~ — RESOLVED by Story 0.4:** the key-availability catalog (Story 1.1) was relocated from `team_maker/providers/` into `team_maker/adapters/providers/registry.py`, alongside the LLM-call adapters (Story 0.1). One package, two concerns, exactly as the spine's structural seed intended — no further action needed here.
- **Dependency decision (only if adding OpenRouter):** which LLM SDK to add (recommend `openai` targeting OpenRouter) and the default authoring model — no longer a hard blocker since five adapters already exist; default to `anthropic` via the existing `create_provider` factory unless OpenRouter is explicitly chosen.
- Keep `composer/` import-clean: it may import `schema/`, `ports/`, `adapters/providers/` (factory + catalog), `keyconfig.py` — but NOT concrete adapter classes directly, NOT `cli.py`, NOT any LLM SDK.

### References
- [Source: project-docs/epics.md#Story-1.2] — story + ACs (FR-1, FR-2, FR-4, AD-8, AD-10)
- [Source: project-docs/prds/prd-team_maker-2026-07-05/prd.md#FR-1, #FR-2, #FR-4, #FR-15, #FR-16, #FR-20, #FR-21, #8-Open-Questions]
- [Source: project-docs/prds/prd-team_maker-2026-07-05/addendum.md#Conversational-Composer, #Key-aware-resolution-&-OpenRouter, #Foundation-reuse]
- [Source: project-docs/architecture/architecture-team_maker-2026-07-05/ARCHITECTURE-SPINE.md#AD-1, #AD-2, #AD-4, #AD-5, #AD-7, #AD-8, #AD-9, #AD-10, #Structural-Seed, #Consistency-Conventions]
- [Source: project-docs/ux-designs/ux-team_maker-2026-07-05/EXPERIENCE.md#Voice-and-Tone, #Provider-&-Key-Handling, #Component-Patterns] — word→provider mapping, spec-valid-even-if-key-missing
- [Source: project-docs/data-models.md#Input-schema, #LLM-routing-resolution-order]
- [Source: team_maker/schema/request.py, team_maker/cli.py, team_maker/keyconfig.py, team_maker/providers/registry.py, team_maker/templates/software_delivery/template.py]
- [Source: project-docs/stories/1-1-load-keys-report-models.md, project-docs/stories/deferred-work.md]
- [Source: project-docs/project-context.md]

## Dev Agent Record

### Agent Model Used

Claude Sonnet 5 (claude-sonnet-5), via the `bmad-dev-story` workflow.

### Debug Log References

None — implementation went green on first full-suite run; no debugging sessions required.

### Completion Notes List

- Implemented `team_maker/composer/` (`Composer`, `ComposerError`) per the corrected Tasks 1-2 guidance: consumes `LLMProvider.complete_structured` directly with `response_model=TeamCreationRequest`, so schema validation happens inside the same call the repair loop catches (`pydantic.ValidationError`) — no separate parse step was needed, since the existing adapters already validate-and-return via the response model.
- Validate-and-repair loop (AC 3/4): bounded by `max_repair_attempts` (default 3, i.e. up to 4 total LLM calls). On each `ValidationError`, the concrete `loc → msg` errors are formatted (same style as `cli.py`'s `create` command) and fed back into the next prompt. Exhausting the budget raises `ComposerError` carrying those errors — `compose()` has no code path that returns an invalid spec (verified in `test_compose_raises_after_exhausting_repair_budget`).
- Routing (AC 2/5): the Composer does not itself decide provider/model choices — that's the authoring LLM's job, per its system prompt (embedded schema rules + a data-driven word→provider alias table: claude→anthropic, chatgpt/gpt→openai, gemini→google, grok→xai, llama→ollama). The Composer's own code only passes preferences through into the user message and never overrides `role.llm`/`default_llm`, so "leave unset when no preference" falls out naturally rather than needing special-cased logic.
- Optional key-aware bias (Task 3, "optionally bias..."): `Composer` accepts an optional `key_config: KeyConfig`; when given, it computes usable providers via the existing `report_availability`/`is_usable` (Story 0.4/1.1, no reimplementation) and appends them as a hint in the system prompt. Spec validity never depends on this — it's a pure prompt hint.
- CLI `compose` command (Task 4, AC 7): mirrors `create`'s structure. Credential resolution bridges the Key Config into the resolved authoring provider's env var, scoped to the single CLI call via the `_bridged_credential` context manager (save previous env value, set for the duration, restore on exit) — `.get_secret_value()` is called only at that point, never logged, and never persists past the invocation. This was necessary because the existing five adapters (Story 0.1) read credentials via `os.environ.get(self.api_key_env)` internally and are out of scope to modify in this story; full AD-7 (explicit per-call credentials, no env reliance at all) is the deferred Story 1.6 conformance test per the story's own Dev Notes — see code review note below.
- Exit codes: `0` success, `1` config/LLM/system errors (missing key, import error, etc. — caught by a generic `except Exception`), `2` when the Composer exhausts its repair budget (`ComposerError`) or `--build` produces a spec that fails post-build validation. This mirrors `create`'s `1`=error / `2`=invalid-output split, with `ComposerError` treated as the "invalid" case since it means no valid spec could be produced.
- No OpenRouter adapter was added — per the story's own reconciliation note this is an optional enhancement, not a blocker; the Composer defaults its authoring model to `anthropic`/`claude-sonnet-4-6`, matching the template's `_DEFAULT_PROVIDER`.
- Tests: `tests/unit/test_composer.py` (10 tests) — happy path, named roles/models/tasks reflected, repair-succeeds-within-bound, repair-budget-exhausted raises `ComposerError`, preference honored, no-preference-leaves-unset, non-SDK constructor injection, two tests reusing `conftest.py`'s `minimal_request`/`full_request` fixtures round-tripped through a scripted `FakeLLMProvider`, and one confirming the available-providers hint is included when a `KeyConfig` is passed. `tests/unit/test_cli_compose.py` (8 tests after code review) — spec written to `--out` with no secret in output or file, spec printed to stdout without `--out`, exit code `2` on exhausted repair budget, exit code `1` on a provider error, spec still emitted under `--quiet` with no `--out`/`--build`, direct (non-mocked) test of `_resolve_authoring_provider`/`_bridged_credential`, env-restore verification, and AC5 stated-preference routing proven through the actual CLI. All offline; `FakeLLMProvider`/`_FakeProvider` implement the port structurally with no network and no real key.
- **Code review (bmad-code-review, 2026-07-26):** 3-layer adversarial review (Blind Hunter, Edge Case Hunter, Acceptance Auditor) against this story's spec. Directly reproduced and confirmed two of the findings before acting on them: (1) the original `os.environ.setdefault` credential bridge leaked the real secret into the process environment persistently (proven by running the CLI test and inspecting `os.environ` afterward), and (2) `_format_errors` produced a malformed `": msg"` string for pydantic errors with an empty `loc` tuple (proven against `TeamCreationRequest`'s own `check_unique_role_names` validator). User resolved the one `decision-needed` item (scope the env-bridge with save/restore rather than touching the out-of-scope Story 0.1 adapters) and chose to apply all 8 `patch` findings now; see the "Review Findings" subsection under Tasks/Subtasks for the full list, fixes, and the 6 `defer`red items (with rationale) also logged to `deferred-work.md`.
- Full regression suite after review fixes: 241 passed, 7 pre-existing skips (live-API integration tests requiring real keys), 0 failures. `ruff check` clean on all new/changed files.

### File List

- `team_maker/composer/__init__.py` (new)
- `team_maker/composer/composer.py` (new)
- `team_maker/cli.py` (modified — added the `compose` command, `_resolve_authoring_provider` helper, and supporting imports)
- `tests/unit/test_composer.py` (new)
- `tests/unit/test_cli_compose.py` (new)

## Change Log

- 2026-07-12 — Story drafted via create-story context engine (exhaustive artifact analysis: PRD/addendum, architecture spine, UX, epics, existing code). Status → ready-for-dev.
- 2026-07-25 — `bmad-correct-course` (Epic 1 course correction): `epic_0` merged into `develop` (87642dc); `epic_1`/`story_1_2` fast-forwarded from the stale pre-Epic-0 baseline to the new `develop` tip. Found Tasks 1-2 stale (Story 0.1 already built `ports/llm_provider.py` with `complete_structured`, not the planned `complete()`; Story 0.1 already built 5 concrete adapters + `create_provider`; Story 0.4 already relocated the catalog to `adapters/providers/registry.py`). Rewrote Tasks 1-2 and the affected Dev Notes to consume the existing port/adapters/catalog rather than rebuild them; no OpenRouter adapter exists yet, now scoped as optional. Acceptance Criteria and Tasks 3-5 unchanged — no gap in intent, only in two tasks' implementation guidance. Status: `needs-rescoping` → `ready-for-dev`.
- 2026-07-25 — Implemented Story 1.2: `team_maker/composer/` (`Composer`, `ComposerError`) built on the existing `LLMProvider` port + `create_provider` factory; bounded validate-and-repair loop against `TeamCreationRequest`; `team-maker compose` CLI command with Key Config credential resolution and exit codes `0/1/2`. 14 new tests (10 composer unit tests + 4 CLI tests), all offline against fake providers. Full suite 237 passed (7 pre-existing live-API skips), ruff clean. Status → review.
- 2026-07-26 — `bmad-code-review`: 3-layer adversarial review (Blind Hunter, Edge Case Hunter, Acceptance Auditor). 1 `decision-needed` (env-bridge design — resolved: scope with save/restore), 8 `patch` (all applied — confirmed secret leak in the original `os.environ.setdefault` bridge, malformed error formatting for empty `loc`, silent spec-discard under `--quiet`, unguarded file write, missing `--build` exception fallback, no negative-`max_repair_attempts` guard, missing direct test of the credential-bridging path, missing CLI-level test of AC5), 6 `defer` (logged to `deferred-work.md`), 3 dismissed (citation mismatches / already mitigated). Full suite 241 passed (7 pre-existing live-API skips), ruff clean. Status → done.
- 2026-07-26 — Accepted: code review complete (8/8 patch findings applied, 1 decision resolved, 0 outstanding), full suite (241 passed, 7 pre-existing live-API skips) green. Merged `story_1_2` → `epic_1`.
