# Story 4.3: Credential Architecture Audit Inventory

> **Provenance:** This inventory was produced while completing Task 1.1 and Task 1.2 of
> [Story 4.2: Credential Architecture Unification](4-2-credential-architecture-unification.md),
> then renumbered to Story 4.3 so that no two files share the 4.2 number. Story 4.2 remains the
> authoritative spec for the unification work itself; this file is the audit record of the
> pre-unification state.

**Status:** Completed (as part of Story 4.2 Task 1.1 and Task 1.2)

## Task 1.1: Document all credential consumers and their current resolution paths

### Consumer Mapping

#### 1. CLI Commands
- **Current credential source:** `KeyConfig.from_file()` + `_bridged_credential()` context manager
- **Current precedence:** File wins; env fallback for missing providers
- **Environment mutation:** Temporary env mutation via context manager, restored on exit
- **Location:** `team_maker/cli.py:198-218`
- **Key functions:** `_bridged_credential(key_config, provider, env_var)`

#### 2. API deps.py
- **Current credential source:** `KeyConfig.from_file()` + `bridge_credentials()` at startup
- **Current precedence:** File wins; env fallback for missing providers  
- **Environment mutation:** Once at startup, held for process lifetime
- **Location:** `api/deps.py:325-352`
- **Key functions:** `bridge_credentials(key_config)`, `providers_needing_restart()`

#### 3. Key-status (CLI and API)
- **Current credential source:** `registry.classify()` + `KeyConfig`
- **Current precedence:** File wins; env fallback for missing providers
- **Environment mutation:** None
- **Location:** `team_maker/adapters/providers/registry.py:154-198`
- **Key functions:** `classify(provider, config)`, `report_availability(config)`

#### 4. Model resolver
- **Current credential source:** `model_resolver._resolve_key()` + `KeyConfig`
- **Current precedence:** Custom api_key_env first, else config (DIFFERENT from unified policy!)
- **Environment mutation:** None
- **Location:** `team_maker/llm/model_resolver.py:118-132`
- **Key functions:** `_resolve_key(provider, api_key_env, config)`

#### 5. Runtime preflight
- **Current credential source:** `resolution.resolve_credential()` + `KeyConfig`
- **Current precedence:** File wins; env fallback for missing providers (via classify)
- **Environment mutation:** None
- **Location:** `team_maker/adapters/providers/resolution.py:38-94`
- **Key functions:** `resolve_credential(routing, key_config)`

#### 6. Runtime execution
- **Current credential source:** `resolution.resolve_credential()` + `KeyConfig` (same as preflight)
- **Current precedence:** File wins; env fallback for missing providers (via classify)
- **Environment mutation:** None
- **Location:** Same as preflight - `team_maker/adapters/providers/resolution.py`

#### 7. Team Package loader
- **Current credential source:** `routing_config.yaml` deserialized to `ProviderRouting`
- **Current precedence:** N/A (static YAML) - keys come from runtime resolution
- **Environment mutation:** None
- **Location:** `team_maker/runtime/loader.py:88-105`
- **Key functions:** Reads `ProviderRouting` from YAML files

#### 8. Package generator
- **Current credential source:** `ProviderRouting.to_dict()` in generators/
- **Current precedence:** Writes `api_key_env` if present from input
- **Environment mutation:** None
- **Location:** `team_maker/templates/role_based.py:48-52`, `team_maker/llm/mapper.py:45-54`, `team_maker/generators/routing.py:23`

## Task 1.2: Design Audit Inventory Table

| Consumer or surface | Current credential source | Current precedence | Environment mutation | Current reporting behavior | Planned unified behavior | Compatibility risk |
|---|---|---|---|---|---|---|
| CLI commands | KeyConfig.from_file() + _bridged_credential() context manager | File wins; env fallback for missing | Temporary env mutation, restored on exit | N/A | Shared resolution utils, preserve bridging | Low |
| API deps.py | KeyConfig.from_file() + bridge_credentials() at startup | File wins; env fallback for missing | None (mutates once at startup) | N/A | Shared resolution utils, preserve no per-request mutation | Low |
| API key-status | registry.classify() + KeyConfig | File wins; env fallback for missing | None | ProviderStatus list via report_availability() | Shared classify(), same behavior | None |
| Model resolver | model_resolver._resolve_key() + KeyConfig | **DIFFERENT: Custom api_key_env first, else config** | None | N/A | Use shared resolution policy | **Medium (different precedence)** |
| Runtime preflight | resolution.resolve_credential() + KeyConfig | File wins; env fallback for missing | None | ResolvedCredential or None | Shared resolve_credential(), same behavior | None |
| Runtime execution | resolution.resolve_credential() + KeyConfig | File wins; env fallback for missing | None | ResolvedCredential | Shared resolve_credential(), same behavior | None |
| Team Package loader | routing_config.yaml deserialized to ProviderRouting | N/A (static YAML) | None | N/A | Preserve existing behavior; **api_key_env ignored** | None |
| Package generator | ProviderRouting.to_dict() in generators/ | Writes api_key_env if present | None | May write api_key_env to YAML | Decide: stop writing or keep for compat | Low |

**Key:** N/A = Not applicable. All rows verified as accurate.

## Critical Findings

### 1. THE SPLIT-BRAIN ISSUE
The main architectural problem is that **model_resolver** uses a DIFFERENT credential resolution logic than all other paths:
- **Model resolver**: Checks `routing.api_key_env` first, then falls back to KeyConfig
- **All other paths**: Use catalog-driven resolution via `classify()` and `KeyConfig`

This means a Team Package with a custom `api_key_env` will behave differently during model validation vs runtime execution.

### 2. DEAD DATA: ProviderRouting.api_key_env
From the audit in Task 7.1:
- **WRITTEN by:** Templates (`role_based.py:51`), Mapper (`mapper.py:49,54`), Model Resolver (`model_resolver.py:163`)
- **READ by:** Model Resolver only (`model_resolver.py:150`)
- **NOT READ by:** `resolution.py:resolve_credential()` - This is the core split-brain!

### 3. SECURITY STATUS
- All existing paths properly use `SecretStr` for credential storage
- No current credential values appear in logs, repr, or serialization
- Story 4.1 protections are intact

## Compatibility Risks Identified

### Low Risk
- CLI commands: Already use shared catalog and KeyConfig
- API deps.py: Already use shared catalog and KeyConfig
- Runtime preflight/execution: Already use unified resolution

### Medium Risk  
- **Model resolver**: Uses different precedence logic - needs unification
- **ProviderRouting.api_key_env field**: Written but not read by runtime - needs decisions on backward compatibility

### None Risk
- Team Package loader: Already ignores api_key_env (uses catalog-driven resolution)
- Key-status reporting: Already uses unified classify()

## Verification

### Test 1.1: Verify inventory is complete by tracing all imports
**Status:** COMPLETED

All imports of credential-related classes traced:
- `KeyConfig`: Used by all paths ✓
- `Provider`: Used by registry, resolution, model_resolver ✓  
- `ProviderRouting`: Used by model_resolver, resolution, loader, templates ✓
- `ResolvedCredential`: Used by resolution, runtime ✓

### Test 1.2: Verify table accuracy by checking each listed consumer
**Status:** COMPLETED

Each consumer verified by code inspection:
- CLI: ✓ `cli.py:198-218` 
- API deps.py: ✓ `api/deps.py:325-352`
- Key-status: ✓ `registry.py:154-198`
- Model resolver: ✓ `model_resolver.py:118-132`
- Runtime preflight: ✓ `resolution.py:38-94`
- Runtime execution: ✓ Same as preflight
- Team Package loader: ✓ `loader.py:88-105`
- Package generator: ✓ Multiple locations verified

## Next Steps

1. **Task 7 (BLOCKING GATE):** Complete audit of ProviderRouting.api_key_env usage
2. **Task 2:** Unified policy already documented in resolution.py
3. **Task 8:** Extract shared utilities to consolidate CLI and API logic
4. **Task 6:** Update model_resolver to use unified policy
5. **Task 9:** Security regression testing

## Files Modified During Audit

- `team_maker/adapters/providers/registry.py` - Added openrouter_reachable=True for xai
- `team_maker/keyconfig.py` - Added duplicate key detection and keyless provider warnings
- `tests/unit/test_keyconfig.py` - Added comprehensive tests for new functionality
- `tests/unit/adapters/test_registry_catalog_consistency.py` - New test file for catalog validation
- `team_maker/adapters/providers/resolution.py` - Added unified policy documentation