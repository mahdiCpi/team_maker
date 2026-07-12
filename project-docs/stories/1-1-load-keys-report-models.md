---
baseline_commit: e5021f3459fa963b731881afda13b49d2e527df5
---

# Story 1.1: Load keys and report available models

Status: done

## Story

As a user,
I want the system to read my Key Config and tell me which providers/models are usable,
so that I know what I can run before composing a team.

## Acceptance Criteria

1. **Given** a Key Config file containing some provider keys, **When** the system loads it, **Then** it reports each known provider as `available` or `missing`. (FR-12)
2. **Given** an OpenRouter key is present in the Key Config, **When** availability is computed, **Then** models reachable through OpenRouter are marked `via OpenRouter`. (FR-22)
3. **Given** a keyless local provider (ollama), **When** availability is computed, **Then** it is reported `available` even with an empty/absent Key Config. (FR-13)
4. **Given** any load or report operation, **When** it runs, **Then** key values are never written to logs, stdout, error messages, or any report output (only presence/absence). (AD-9)
5. **Given** a missing or empty Key Config file, **When** the system loads it, **Then** it does not crash: cloud providers report `missing` and keyless local providers report `available`.
6. **Given** the CLI, **When** the user runs the availability command, **Then** a readable table lists each provider with its status (available / missing / via OpenRouter / keyless-local).

## Tasks / Subtasks

- [x] **Task 1 — Define the Key Config loader** (AC: 1, 4, 5)
  - [x] Added `team_maker/keyconfig.py` with a Pydantic v2 model storing `Dict[str, SecretStr]` (repr/logging auto-redacts). Recognizes all catalog providers.
  - [x] Loads from a resolved path (`$TEAM_MAKER_KEYS` or `./team_maker.keys`), overridable by CLI `--file`. `.env`-style `KEY=VALUE` parsing (comments/blanks ignored); documented in module docstring.
  - [x] Missing/empty file → empty config, never raises.
- [x] **Task 2 — Provider registry + availability reporter** (AC: 1, 2, 3)
  - [x] Added `team_maker/providers/registry.py` with a data-driven catalog (`PROVIDERS`); `ollama` flagged `keyless_local`.
  - [x] `report_availability()` computes `available` / `keyless-local` / `via-openrouter` / `missing`; direct key beats OpenRouter.
  - [x] Returns `list[ProviderStatus]` (frozen dataclass) — presence only, no secrets.
- [x] **Task 3 — CLI command** (AC: 6)
  - [x] Added `team-maker keys status [--file]` in `team_maker/cli.py`; renders a `rich` table (status colour-coded); prints status only, never key values.
- [x] **Task 4 — Tests** (AC: 1–5)
  - [x] `tests/unit/test_keyconfig.py`: presence detection; **redaction test** (secret absent from repr/str/model_dump/json/logs; retrievable only via `.get_secret_value()`); env override; empty file.
  - [x] `tests/unit/test_provider_availability.py`: empty → cloud missing + ollama available; OpenRouter → via-openrouter; direct key precedence; report carries no secrets.

### Review Findings

_From code review 2026-07-11 (Blind Hunter + Edge Case Hunter + Acceptance Auditor). 2 decision-needed, 11 patch, 3 deferred._

**Decision-needed** — resolved 2026-07-12
- [x] [Review][Decision] Env vars vs file-only → **1a**: file is the priority source; process env vars are a fallback for providers the file doesn't set. Implemented in `from_file(include_env=True)`.
- [x] [Review][Decision] `keyless-local`/`via-openrouter` usability → **2a**: kept descriptive statuses + added `is_usable()` (only `missing` blocks). [team_maker/providers/registry.py]

**Patch** — all applied 2026-07-12
- [x] [Review][Patch] UTF-8 BOM drops the first key — now read with `utf-8-sig` [team_maker/keyconfig.py]
- [x] [Review][Patch] `from_file` could raise on non-UTF-8 / permission-denied — read guarded, becomes a `load_warnings` entry + empty config [team_maker/keyconfig.py]
- [x] [Review][Patch] Default key file not git-ignored — added `team_maker.keys` + `*.keys` to `.gitignore` [.gitignore]
- [x] [Review][Patch] Inline `# comment` after a value corrupted the key — stripped via `_unwrap_value` [team_maker/keyconfig.py]
- [x] [Review][Patch] Quote-stripping removed char-sets — now unwraps one matched pair only [team_maker/keyconfig.py]
- [x] [Review][Patch] Unknown/misspelled key names silently dropped — now collected in `load_warnings` and surfaced by the CLI [team_maker/keyconfig.py, cli.py]
- [x] [Review][Patch] `--file` missing/dir path — now validated via `click.Path(exists=True, dir_okay=False)` [team_maker/cli.py]
- [x] [Review][Patch] No CLI test (AC6) — added `tests/unit/test_cli_keys_status.py` (table + no-secret + missing-file) [tests/unit]
- [x] [Review][Patch] No empty-file test (AC5) — added `test_existing_but_empty_file_returns_empty_config` [tests/unit]
- [x] [Review][Patch] Rich markup in printed path — now `escape()`d [team_maker/cli.py]
- [x] [Review][Patch] `typing.Dict/List/Optional` — switched to built-in generics `dict`/`list`/`X | None` [team_maker/keyconfig.py, providers/registry.py]

**Deferred**
- [x] [Review][Defer] Duplicate key definitions silently resolve last-wins (no warning) — low value; acceptable
- [x] [Review][Defer] A key supplied for a keyless-local provider is ignored (`has()`/report inconsistency) — harmless today
- [x] [Review][Defer] OpenRouter gateway identified by a hardcoded name vs a data flag (AD-8 note) — revisit if a 2nd gateway is added

## Dev Notes

### What this story is (and is not)
- **Is:** the read-only foundation of key handling — load the Key Config, know what's runnable, report it. Every later story (1.2 Composer routing, 1.6 per-agent multi-provider, 2.3 UI key-check states, 2.6 Settings) consumes this.
- **Is NOT:** running teams, entering keys, or the runtime. No CrewAI here. No key *entry* UI ever (AD-9).

### Architecture constraints (binding)
- **AD-9 — keys live only in the Key Config file, read-only.** Never entered in the UI, never logged, never in run output. This story establishes that discipline: use `SecretStr`; the availability report carries **presence, not values**. [Source: project-docs/architecture/architecture-team_maker-2026-07-05/ARCHITECTURE-SPINE.md#AD-9]
- **AD-8 — one LLMProvider port; OpenRouter is an adapter + default multi-provider path.** Adding a provider is config/catalog, never core branching. Model the catalog so a new provider is a data entry. OpenRouter presence unlocks many models with one key. [Source: ...#AD-8]
- **AD-2 / AD-4 — ports-and-adapters, inward dependencies.** This code is foundational core/config; keep it free of UI/runtime imports so the API (Epic 4) and UI (Epic 2) can consume it. [Source: ...#AD-2, #AD-4]
- **AD-3 — single repo, local-only.** No external service; a local file + static catalog. [Source: ...#AD-3, #AD-11]

### Project conventions (must follow — from project-context.md)
- Start every module with `from __future__ import annotations`; full type hints; snake_case; ruff line-length 100 (rules E,F,I,N,W). [Source: project-docs/project-context.md]
- **Input/config models = Pydantic v2 `BaseModel`** (put the KeyConfig model with the schema-style code, not as a plain dataclass). Internal pass-around data = plain dataclasses. [Source: project-docs/project-context.md#Language-Specific-Rules]
- **Never branch on provider name** for routing logic — keep provider differences in data (the catalog), not code paths. [Source: project-docs/project-context.md#Validation-Rules]
- Rich console output is cosmetic — the CLI table must read from the returned report object, not compute logic in the view. [Source: project-docs/project-context.md#Critical-Dont-Miss-Rules]

### Existing code to align with (read before writing)
- `team_maker/cli.py` — Click group with `create` and `list-templates`; add the new command in the same style (Click + `rich` table, `console`/`err_console`). [Source: c:/Projects/CoinPela/Projects/team_maker/team_maker/cli.py]
- `team_maker/schema/request.py` — existing `ProviderConfig` already has `provider`, `model`, `api_key_env`. Reuse provider-name normalization ideas; the new Key Config is about *keys per provider*, distinct from per-agent routing. [Source: team_maker/schema/request.py]
- `team_maker/utils/` — reuse `fs`/`yaml_utils` helpers if a YAML format is chosen. [Source: team_maker/utils/]

### Testing standards
- pytest; files `tests/unit/test_*.py`; in-memory, use `tmp_path` for the config file (no real paths). Mirror existing unit-test style in `tests/unit/`. [Source: c:/Projects/CoinPela/Projects/team_maker/tests/unit/]
- The **redaction test is the highest-value test here** — it enforces AD-9.

### Latest-tech notes
- **Pydantic v2 `SecretStr`** is the idiomatic redaction mechanism: `str(secret)` shows `**********`; you must call `.get_secret_value()` to read it (do that only at the point of use in later stories, never here). Optional: `pydantic-settings` for `.env` loading, but stdlib parsing is fine and dependency-light.
- Ollama = keyless/local (confirmed in CrewAI provider docs); treat as always-available for reporting. [Source: web verification 2026-07-06 — CrewAI LLM connections]

### Project Structure Notes
- New files: `team_maker/keyconfig.py`, `team_maker/providers/registry.py` (+ `team_maker/providers/__init__.py`), tests under `tests/unit/`. New CLI command in existing `team_maker/cli.py`.
- Aligns with the spine's structural seed (`adapters/providers/` will grow later); for this foundational story a `team_maker/providers/` module is acceptable and can host the adapter package as Epic 1 progresses. Note this as the seed location.
- **Decision to make (small):** Key Config file format (`.env`-style vs YAML) and default path — pick one, document it in the module docstring and Settings guidance (Story 2.6 will surface the path). Recommend `.env`-style for familiarity; gitignore it.

### References
- [Source: project-docs/epics.md#Story-1.1] — story + ACs
- [Source: project-docs/prds/prd-team_maker-2026-07-05/prd.md#FR-12, #FR-13, #FR-21, #FR-22]
- [Source: project-docs/architecture/architecture-team_maker-2026-07-05/ARCHITECTURE-SPINE.md#AD-8, #AD-9]
- [Source: project-docs/ux-designs/ux-team_maker-2026-07-05/EXPERIENCE.md#Provider-&-Key-Handling]
- [Source: project-docs/project-context.md]

## Dev Agent Record

### Agent Model Used

claude-opus-4-8 (Claude Code / bmad-dev-story)

### Debug Log References

- Env setup: `pip install -e ".[dev]"` (pytest 9.1.1, ruff 0.15.21, pydantic 2.x). Python 3.14.0.
- Baseline: `git rev-parse HEAD` = e5021f3; full suite green before changes (79 passed).
- New tests: 12 passed. Full suite after changes: **91 passed, 0 regressions**.
- Ruff on story files: clean (the single `E741` on `cli.py:86` is pre-existing in the `create` command, out of scope).
- CLI smoke test: `team-maker keys status --file <tmp>` produced the correct table; grep confirmed **no key value in output**.

### Completion Notes List

- All 6 ACs satisfied; all tasks/subtasks complete.
- **AD-9 (secrets) enforced**: keys stored as `pydantic.SecretStr`; redaction verified across repr/str/model_dump/json/logging; CLI prints presence only. Values retrievable solely via `.get_secret_value()` (unused in this story).
- **AD-8 (data-driven providers)**: adding a provider = one row in `PROVIDERS`; no branching on provider name anywhere.
- Key Config format decision (flagged in story): chose `.env`-style `KEY=VALUE`, default path `./team_maker.keys` (or `$TEAM_MAKER_KEYS`); should be git-ignored — surface this in Story 2.6 Settings guidance.
- Cosmetic: replaced an em-dash with ASCII hyphen in one detail string to avoid Windows-console mojibake.
- Out of scope (left as-is): pre-existing `E741` lint in `cli.py` `create` command.

### File List

- `team_maker/keyconfig.py` (new)
- `team_maker/providers/__init__.py` (new)
- `team_maker/providers/registry.py` (new)
- `team_maker/cli.py` (modified — added `keys` group + `status` command)
- `tests/unit/test_keyconfig.py` (new)
- `tests/unit/test_provider_availability.py` (new)
- `tests/unit/test_cli_keys_status.py` (new — added in review)
- `.gitignore` (modified — ignore key files, added in review)

## Change Log

- 2026-07-11 — Implemented Story 1.1: Key Config loader (`SecretStr`), data-driven provider availability report, `team-maker keys status` CLI, and unit tests (incl. AD-9 redaction test). 12 new tests; full suite 91 passed. Status → review.
- 2026-07-12 — Code review (3 adversarial layers). Resolved 2 decisions (1a file-priority + env fallback; 2a `is_usable()` helper) and applied 11 patches: utf-8-sig BOM handling, guarded read (`load_warnings`), inline-comment strip, matched-pair quote unwrap, unknown-key warnings, `--file` validation, markup escaping, `.gitignore` for key files, built-in generics, + CLI and empty-file tests. 3 items deferred (see deferred-work.md). Full suite 103 passed, ruff clean. Status → done.
