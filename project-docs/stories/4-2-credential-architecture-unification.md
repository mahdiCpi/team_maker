---
baseline_commit: 0cc0c7d
---

# Story 4.2: Credential Architecture Unification

Status: backlog

## Story

As the codebase,
I want a single, consistent credential resolution system,
so that provider/key management is not fragmented across multiple modules.

## Background and scope boundary

**This is the second story of Epic 4 — Deferred Work Consolidation.**

The current architecture has a **provider/key split-brain** that was identified in Story 0.4 and
never resolved. Two separate credential systems coexist:

- **Story 1.1 system:** `team_maker/keyconfig.py` + `team_maker/providers/registry.py` + `keys status` CLI
- **Story 0.4 system:** `team_maker/llm/model_resolver.py` (availability/substitution)

Both handle credential loading and provider availability, but independently. This creates:
- Duplicate key definitions silently resolve (last-wins) with no warning
- Keyless-local provider keys are ignored
- OpenRouter gateway uses hardcoded name instead of data-driven flags
- `ProviderRouting.api_key_env` is dead data that contradicts the package format
- `api/deps.py` duplicates ~10 lines of `cli.py`'s credential logic
- `_TEMPLATE_ID` is hardcoded in `api/routings.py` and gates builds
- xai's `openrouter_slug` and `openrouter_reachable` are inconsistent

**Epic 0's Story 0.4** explicitly called for folding the Key Config feature into the provider layer,
but this was never completed. This story finishes that work.

**What this story is NOT:**
- Changing the Key Config file format (only internal resolution changes)
- Adding new providers (only fixing existing provider handling)
- Modifying the external API contracts (only internal unification)

## Explicit non-goals (do not build here)

- **No changes to the Key Config user experience.** The file format, loading behavior, and CLI commands remain unchanged.
- **No changes to provider catalog structure.** Only the credential resolution logic is unified.
- **No changes to runtime engine credential passing.** Only the resolution before runtime is unified.

## Acceptance Criteria

1. **Given** the current split between `keyconfig.py`/`providers/registry.py` and `llm/model_resolver.py`, **When** credential resolution occurs, **Then** key loading and availability reporting live in ONE place behind the provider layer, **And** the split-brain between Story 0.4 and Story 1.1 implementations is removed. (Story 0.4, FR-12, FR-13, FR-21, FR-22)

2. **Given** a Key Config with duplicate provider entries (e.g., both `ANTHROPIC_API_KEY=` and `anthropic=`), **When** the config is loaded, **Then** a warning is issued instead of silently resolving to the last value, **And** the resolution order is documented and deterministic. (deferred-work.md:14)

3. **Given** a keyless-local provider like `ollama`, **When** a key is supplied for it in the Key Config, **Then** the key is NOT silently ignored, **And** the key is either used (if the provider supports it) or a warning is issued. (deferred-work.md:15)

4. **Given** the OpenRouter provider configuration, **When** gateway detection occurs, **Then** it uses a data flag (e.g., `is_gateway`) on the Provider model instead of hardcoded string comparison, **And** adding a second gateway provider requires only a catalog change, not code changes. (deferred-work.md:16)

5. **Given** the `ProviderRouting.api_key_env` field, **When** the credential resolution is unified, **Then** this dead data field is removed from the package format, **And** all code that wrote to this field is updated. (deferred-work.md:92)

6. **Given** the duplicated credential bridging in `api/deps.py` and `cli.py`, **When** this story completes, **Then** the duplication is eliminated by extracting a shared credential module under `team_maker/`, **And** both API and CLI use the same credential resolution path. (deferred-work.md:136)

7. **Given** the hardcoded `_TEMPLATE_ID = "software_delivery_team"` in `api/routings.py`, **When** builds are gated, **Then** the template ID is determined dynamically or from configuration, **And** builds are not hardcoded to a single template. (deferred-work.md:237)

8. **Given** the `xai` provider catalog entry, **When** OpenRouter reachability is checked, **Then** if `openrouter_slug="x-ai"` exists, `openrouter_reachable` should also be `True`, **And** the inconsistency between these fields is resolved. (deferred-work.md:186)

9. **Given** a direct `openrouter` routing entry with model string `gpt-4o`, **When** the model is resolved, **Then** it is properly qualified with the vendor namespace (e.g., `openrouter/openai/gpt-4o`), **And** unqualified model strings are rejected or properly qualified. (deferred-work.md:94)

## Tasks / Subtasks

- [ ] **Task 1 — Audit current credential resolution paths**
  - [ ] Document all places where credentials are loaded/resolved
  - [ ] Identify the split-brain between existing implementations
  - [ ] Map all credential-related code and data flows

- [ ] **Task 2 — Design unified credential architecture**
  - [ ] Create single credential resolution module under `team_maker/`
  - [ ] Define clear interfaces for key loading, validation, availability checking
  - [ ] Ensure backward compatibility with existing Key Config format

- [ ] **Task 3 — Implement unified resolution**
  - [ ] Migrate `keyconfig.py` credential functionality to unified module
  - [ ] Migrate `providers/registry.py` credential parts to unified module
  - [ ] Migrate `model_resolver.py` credential resolution to unified module
  - [ ] Remove duplicate code and dead data fields

- [ ] **Task 4 — Fix duplicate key handling**
  - [ ] Add warning when duplicate keys are detected
  - [ ] Document resolution order and precedence rules
  - [ ] Add tests for duplicate key scenarios

- [ ] **Task 5 — Fix keyless provider key ignoring**
  - [ ] Update logic to check keyless-local first, but not ignore supplied keys
  - [ ] Or document that keys for keyless providers are always ignored

- [ ] **Task 6 — Make OpenRouter gateway data-driven**
  - [ ] Add `is_gateway` flag to Provider model
  - [ ] Update all gateway detection to use flag instead of hardcoded names
  - [ ] Remove hardcoded `OPENROUTER = "openrouter"` comparisons

- [ ] **Task 7 — Remove dead data fields**
  - [ ] Remove `ProviderRouting.api_key_env` from package format
  - [ ] Update Factory to not write this field
  - [ ] Update all code that reads this field (or remove it)

- [ ] **Task 8 — Create shared credential module**
  - [ ] Extract common credential logic from `api/deps.py` and `cli.py`
  - [ ] Create `team_maker/credentials/` or shared module
  - [ ] Update both API and CLI to use shared module

## Dev Notes

### What this story is (and is not)
- **Is:** Unifying the fragmented credential resolution architecture into a single coherent system
- **Is NOT:** Changing the user-facing Key Config experience or adding new providers

### Architecture constraints (binding)
- **AD-1 — Single open-source repo, modular monolith.** Credential resolution must remain in the core package.
- **AD-2 — Ports-and-adapters.** Credential resolution should be behind a clean port interface.
- **AD-8 — One LLMProvider port; OpenRouter is an adapter.** Provider selection must be data-driven, not hardcoded.
- **AD-9 — Keys live only in the Key Config file, read-only.** Never entered in the UI, never logged.
- **AD-10 — Composer output validated against factory Pydantic schema.** Credential validation must use existing schema.

### Project conventions (must follow — from project-context.md)
- Start every module with `from __future__ import annotations`; full type hints; snake_case; ruff line-length 100.
- Input/config models = Pydantic v2 `BaseModel`; internal pass-around data = plain dataclasses.
- Inward dependency direction: UI → API → core → adapters.

## References
- [deferred-work.md](../deferred-work.md) — Multiple entries from Stories 0.4, 1.1, 1.6, 2.0, 2.3
- [epics.md](../epics.md) — Epic 4: Deferred Work Consolidation, originally Epic 0 Story 0.4
- [ARCHITECTURE-SPINE.md](../architecture/architecture-team_maker-2026-07-05/ARCHITECTURE-SPINE.md) — AD-1, AD-2, AD-8, AD-9, AD-10
- [Story 0.4](../0-4-fold-key-config-into-provider-layer.md) — Original epic that called for this unification
- [Story 1.1](../1-1-load-keys-report-models.md) — First key config implementation
- [Story 1.6](../1-6-multi-provider-routing-conformance.md) — Multi-provider routing
