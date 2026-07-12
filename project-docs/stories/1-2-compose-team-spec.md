---
baseline_commit: e5021f3459fa963b731881afda13b49d2e527df5
---

# Story 1.2: Compose a valid Team Spec from a prompt

Status: ready-for-dev

<!-- Note: baseline_commit is HEAD (e5021f3). Story 1.1's work (keyconfig.py, providers/,
     cli.py `keys status`, tests) is present in the working tree but UNCOMMITTED — treat those
     files as existing prior art to consume, not as things to create. -->

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

- [ ] **Task 1 — Define the `LLMProvider` port** (AC: 6)
  - [ ] Create `team_maker/ports/__init__.py` and `team_maker/ports/llm_provider.py`. Define `LLMProvider` as a `typing.Protocol` (structural, mock-friendly) with a single minimal text-completion method, e.g. `def complete(self, *, system: str, prompt: str, model: str | None = None) -> str`. Keep it sync and dependency-free (core code, no SDK import).
  - [ ] Port name = capability name `LLMProvider` (spine convention: ports are `<Capability>`, adapters are `<impl>_<capability>`). Start module with `from __future__ import annotations`; full type hints.
  - [ ] This is the ONE path all LLM access flows through (Composer now; Runtime agents later — AD-8). Do not add provider-specific parameters to the port.

- [ ] **Task 2 — LLM adapter + credential resolution behind the port** (AC: 6)
  - [ ] Create `team_maker/adapters/__init__.py`, `team_maker/adapters/providers/__init__.py`, and one concrete adapter implementing `LLMProvider` for the Composer's authoring model. **Recommended default: OpenRouter** (AD-8 names it the default multi-provider path — one key, many models; OpenAI-API-compatible). See Latest-tech notes.
  - [ ] Resolve the authoring key from `KeyConfig.from_file(...)` (Story 1.1). Call `.get_secret_value()` **only** at the point of the network call. Never read a raw global env var for routing, never log or echo the key (AD-7, AD-9). Reuse `providers/registry.py` (`PROVIDERS`, `report_availability`, `is_usable`) — do not re-implement key logic.
  - [ ] Keep it data-driven: never branch on provider name in logic (AD-1/AD-8). Map user model words → provider IDs via a small alias table or registry extension (claude→anthropic, gemini→google, chatgpt→openai).
  - [ ] Add the LLM SDK dependency to `pyproject.toml`/`requirements.txt` (this is the FIRST LLM SDK in the repo). If OpenRouter: add `openai>=1.x` and point `base_url` at OpenRouter. Note the choice in the module docstring. **Decision flag** — see Project Structure Notes.

- [ ] **Task 3 — Composer core: `compose(intent, preferences) -> TeamCreationRequest`** (AC: 1, 2, 3, 4, 5)
  - [ ] Create `team_maker/composer/__init__.py` and `team_maker/composer/composer.py` with a `Composer` class that takes an `LLMProvider` by constructor injection (so tests inject a fake). Expose a single stateless `compose(intent: str, *, preferences: ... = None) -> TeamCreationRequest`.
  - [ ] Build a system prompt that instructs the model to emit structured output (JSON) matching the schema. Embed the binding field rules inline: required `team_name`/`purpose`/`output_path`, ≥1 role, `RoleDefinition.name` = `^[a-z][a-z0-9_]*$` and unique, `description` min length 5, `ProviderConfig{provider,model,api_key_env?}`, valid enum values. Parse the model output, then `TeamCreationRequest.model_validate(...)`.
  - [ ] **Validate-and-repair loop:** on `pydantic.ValidationError`, format the errors (loc → msg, like `cli.py` does) and re-prompt the same LLM to fix ONLY those errors; re-validate. Bound with `max_repair_attempts` (recommend default 3, configurable). On exhaustion raise a dedicated `ComposerError` carrying a plain-language message + the last validation errors — never return/emit an invalid spec (AC 4).
  - [ ] **Routing (FR-4):** honor named providers/models and preferences ("local/cheap" → prefer ollama / a cheaper model; "use Claude" → anthropic). With no preference, leave `role.llm`/`default_llm` unset so the template's `_DEFAULT_PROVIDER` chain applies — do NOT re-implement that resolution (it lives in `templates/software_delivery/template.py`). Optionally bias an unspecified choice toward a provider with a usable key (`report_availability`/`is_usable`), but the spec must stay schema-valid even when a named model's key is missing (key gating is Story 1.6/2.3, not here).
  - [ ] Keep `compose()` stateless and idempotently re-invokable (Story 1.3 wraps it per conversational turn; Epic 2/FR-16 wraps it as an endpoint). No conversation loop, no "run now" here — that is Story 1.3 (FR-20).

- [ ] **Task 4 — `team-maker compose` CLI command** (AC: 7)
  - [ ] Add a `compose` command in `team_maker/cli.py` via `@main.command()`, mirroring `create`: positional `intent` (or `--intent`), `--out/-o` (write the spec YAML using `utils/yaml_utils.dump_yaml`), `--key-file/-f` (`click.Path(exists=True, dir_okay=False)`), `--model` (override authoring model), optional `--build` (chain into `PipelineRunner().run(request)`), `--quiet/-q`.
  - [ ] Wire the real adapter (Task 2) but keep the port injectable. Use module-level `console`/`err_console`; render a `rich` summary of the composed spec. Exit `1` on load/LLM/parse/compose errors, `2` if the produced spec fails validation, `0` on success. Never print key values (`rich.markup.escape` any user text; follow `keys status` precedent).

- [ ] **Task 5 — Tests (offline, fake provider)** (AC: 1–7)
  - [ ] Add `tests/unit/test_composer.py` with a `FakeLLMProvider` implementing the port (returns scripted strings; NO network). Cover: happy path → valid `TeamCreationRequest`; named models/roles/tasks reflected (AC 2); repair loop (fake returns an invalid draft, then a valid one → asserts success within the bound and that re-validation occurred) (AC 3); exhausted retries → `ComposerError` with a clear message and **no invalid spec returned** (AC 4); preference honored vs. default-left-unset routing (AC 5); constructor injection proves no concrete SDK is needed in tests (AC 6).
  - [ ] Add `tests/unit/test_cli_compose.py` mirroring `tests/unit/test_cli_keys_status.py`: monkeypatch/inject the fake provider, assert exit codes `0/1/2`, the spec YAML is written, and **no key value appears in output**.
  - [ ] Reuse `tests/conftest.py` fixtures (`minimal_request`, `full_request`) to assert the Composer can produce equivalent validated requests. Keep everything in-memory (`tmp_path` for any file). pytest discovery: `tests/unit/test_*.py`.

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
- `team_maker/providers/registry.py` — `PROVIDERS` catalog (anthropic/openai/google/groq/ollama/openrouter with `env_var`, `keyless_local`, `openrouter_reachable`), `report_availability(config) -> list[ProviderStatus]`, `is_usable(status)`, `USABLE_STATUSES`, `OPENROUTER`. Use for provider/model preference biasing. [Source: team_maker/providers/registry.py]
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
- **New packages:** `team_maker/ports/` (`llm_provider.py`), `team_maker/adapters/providers/` (concrete LLM adapter), `team_maker/composer/` (`composer.py`, `ComposerError`). New CLI command in existing `cli.py`. Tests under `tests/unit/`. This matches the architecture spine's structural seed (`composer/`, `ports/`, `adapters/providers/` inside the `team_maker/` package). [Source: ARCHITECTURE-SPINE.md#Structural Seed]
- **⚠ Naming decision (call out, then proceed):** an existing `team_maker/providers/` package already holds the **key-availability catalog/registry** (Story 1.1), while the spine puts **LLM adapters** under `team_maker/adapters/providers/`. These are different concerns. Recommendation: **leave `providers/` as the catalog** (it is data, not an adapter) and put the new LLM adapter under `adapters/providers/`. Do not move or rename 1.1's `providers/` (would churn imports/tests). Note the slight name overlap in the adapter module docstring.
- **Dependency decision (flag for confirmation):** which LLM SDK to add (recommend `openai` targeting OpenRouter) and the default authoring model. This is the first LLM SDK dependency in the repo — add it to both `pyproject.toml` and `requirements.txt`.
- Keep `composer/` import-clean: it may import `schema/`, `ports/`, `providers/` (catalog), `keyconfig.py` — but NOT `adapters/` concretely, NOT `cli.py`, NOT any LLM SDK.

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

_(to be filled by dev-story)_

### Debug Log References

### Completion Notes List

### File List

## Change Log

- 2026-07-12 — Story drafted via create-story context engine (exhaustive artifact analysis: PRD/addendum, architecture spine, UX, epics, existing code). Status → ready-for-dev.
