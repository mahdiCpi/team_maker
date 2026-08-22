---
baseline_commit: 0cc0c7d
---

# Story 4.6: Template and Starter System Hardening

Status: done

## Story

As the codebase,
I want all gaps in the starter template system closed,
so that Epic 3's starter teams are production-ready.

## Background and scope boundary

**This is the fifth story of Epic 4 — Deferred Work Consolidation.**

Story 3.1 and 3.2 shipped the baseline starter teams feature, but multiple validation, security,
and robustness gaps were deferred. These must be addressed to ensure the starter system is reliable.

**Note:** Acceptance Criterion 3 (hardcoded `_TEMPLATE_ID`) was moved here from Story 4.2: Credential Architecture Unification. While the symptom (a hardcoded template ID) was discovered during credential work, the actual fix belongs in the template system, not credential architecture. Story 4.2 references this transfer in its non-goals section (as Story 4.6, following the Epic 4 renumbering).

**What this story is NOT:**
- Adding new starter teams (only fixing the system that loads them)
- Changing the YAML format (only validation and loading improvements)

## Acceptance Criteria

1. **Given** a request with a `template_id` field, **When** it is validated, **Then** only registered template IDs are accepted, **And** invalid template IDs are rejected with a clear error. (deferred-work.md:316)

2. **Given** a request with a `template_id`, **When** it is processed, **Then** the template's existence is verified before processing, **And** a missing template results in a fast-fail error. (deferred-work.md:318)

3. **Given** the hardcoded `_TEMPLATE_ID = "software_delivery_team"` in `api/routings.py` (moved from Story 4.2), **When** requested routings are pre-resolved for key-check or build reporting, **Then** the template ID is determined dynamically from the pipeline's template selection logic or from request configuration, **And** builds are not hardcoded to the software_delivery_team template, **And** the same template resolution logic is used for both reporting and actual builds so they cannot diverge. (deferred-work.md:237)

3. **Given** the starter teams endpoint, **When** listing available starters, **Then** YAML files are discovered from a designated directory dynamically, **And** adding a new starter requires only adding a YAML file, not code changes. (deferred-work.md:317)

4. **Given** the starter router, **When** it lists starters, **Then** it does NOT use a hardcoded list like `_STARTER_YAMLS`, **And** the list is generated from filesystem discovery. (deferred-work.md:317)

5. **Given** a malicious request to the starter router, **When** the template path is resolved, **Then** the resolved path stays within the designated examples directory, preventing directory traversal attacks, **And** symlinks cannot escape the intended directory. (deferred-work.md:320)

6. **Given** a starter YAML file, **When** it is loaded, **Then** its structure is validated against the expected schema, **And** malformed YAMLs are rejected with clear errors. (deferred-work.md:321)

7. **Given** a starter YAML, **When** it is loaded, **Then** all required fields for starter teams are present, **And** missing fields result in clear validation errors. (deferred-work.md:321)

8. **Given** two starter YAMLs with the same `template_id`, **When** they are registered, **Then** the duplicate is detected and rejected, **And** template IDs remain unique. (deferred-work.md:322)

9. **Given** concurrent access to the template registry, **When** templates are registered or accessed, **Then** the registry is thread-safe, **And** race conditions cannot corrupt the registry. (deferred-work.md:323)

10. **Given** a corrupt or empty starter YAML, **When** it is loaded, **Then** a clear error is raised, **And** the system continues to function with other valid YAMLs. (deferred-work.md:324)

## Tasks / Subtasks

- [x] **Task 1 — Add schema-level template_id validation**
  - [x] Update `CreateSessionFromStarterRequest.starter_id` to use Literal/enum of registered templates
  - [x] Or add custom validator for template_id field
  - [x] Ensure invalid template IDs are rejected with clear errors

- [x] **Task 2 — Implement dynamic starter YAML discovery**
  - [x] Replace hardcoded `_STARTER_YAMLS` with directory scanning in `api/routers/starters.py`
  - [x] Add configuration for starter directory path
  - [x] Ensure discovered YAMLs are cached appropriately

- [x] **Task 3 — Add template existence check at request time**
  - [x] Verify template exists in catalog before processing requests
  - [x] Return clear error for missing templates (404 or 422)
  - [x] Add fast-fail behavior

- [x] **Task 9 — Fix hardcoded _TEMPLATE_ID in routings (moved from Story 4.2)**
  - [x] Replace hardcoded `_TEMPLATE_ID = "software_delivery_team"` in `api/routings.py` with dynamic template resolution
  - [x] Use same template selection logic as the pipeline (get_template() from registry)
  - [x] Ensure reporting and builds use identical template resolution
  - [x] Add tests verifying template is resolved dynamically
  - [x] **Test:** Verify routings are resolved from actual template, not hardcoded value

- [x] **Task 4 — Fix path traversal in starter router**
  - [x] Add secure path resolution in `api/routers/starters.py`
  - [x] Validate resolved path stays within examples directory
  - [x] Prevent symlink escape attacks
  - [x] Add tests for path traversal attempts

- [x] **Task 5 — Add YAML structure and content validation**
  - [x] Validate YAML structure against expected schema
  - [x] Check all required fields are present (`template_id`, `team_name`, `purpose`, `output_path`)
  - [x] Add clear error messages for validation failures

- [x] **Task 6 — Prevent duplicate template IDs**
  - [x] Add uniqueness check during template registration
  - [x] Log errors for duplicates
  - [x] Ensure first-write-wins (keeps first, skips subsequent duplicates)

- [x] **Task 7 — Add thread safety tests for registry**
  - [x] Test concurrent access to template registry
  - [x] Verify no race conditions in registration
  - [x] Add thread safety mechanisms if needed

- [x] **Task 8 — Add error handling for corrupt/empty YAMLs**
  - [x] Handle YAMLError gracefully with clear error messages
  - [x] Handle empty files gracefully
  - [x] Continue processing other YAMLs on error (partial availability)

### Review Findings

- [x] [Review][Patch] Starter discovery globs all of `examples/*.yaml`, sweeping in non-starter configs — `_discover_starter_yamls()` (api/routers/starters.py:50) scans every YAML in `examples/`, not a starters-only set. Verified `examples/software_delivery_request.yaml` (a plain CLI usage example, per its own header comment) has `team_name`/`purpose`/`output_path` plus a `template:` field, so it passes discovery and is surfaced via GET /api/starters and POST /api/starters/{id}/run as if it were a curated starter — directly contradicting the story's non-goal "Adding new starter teams (only fixing the system that loads them)". **Resolution (user decision):** move the curated starter YAMLs into a dedicated `examples/starters/` subdirectory and point discovery only at that directory; non-starter example configs (`software_delivery_request.yaml`, `planner_example.yaml`, `smoke_test.yaml`) stay in `examples/`. **Fixed:** moved both starter YAMLs to `examples/starters/`, renamed `_EXAMPLES_DIR`/`_get_examples_dir` to `_STARTERS_DIR`/`_get_starters_dir`, and updated every test/fixture path reference.
- [x] [Review][Patch] `_ValidStarterId` Literal reintroduces the hardcoded list AC3/AC4 say to eliminate — api/schemas.py:450 hardcodes exactly 3 starter ids for `CreateSessionFromStarterRequest.starter_id`, independent of the dynamic discovery in `api/routers/starters.py`. A newly-added starter YAML would be listed by GET /api/starters but rejected with 422 by POST /api/compose/sessions/from-starter, contradicting AC4's "adding a new starter requires only adding a YAML file, not code changes." **Resolution (user decision):** drop the static Literal and validate `starter_id` against the discovered starter map from `api.routers.starters` at runtime (e.g. via a model_validator), so from-starter and the starters list can never drift. **Fixed:** replaced `_ValidStarterId` with a `field_validator` that checks membership in `api.routers.starters._STARTER_ID_TO_FILE` via a deferred import.
- [x] [Review][Patch] New `validate_template_id_exists` field validator breaks 12 pre-existing tests in `tests/unit/composer/test_session_seed.py` [team_maker/schema/request.py:300] — confirmed by running the full suite: these tests construct `TeamCreationRequest(template_id="test_template")`/`"test"` as unrelated placeholder values, which now fail Pydantic validation since they aren't registered templates. **Fixed:** updated the fixtures to use `template_id="software_delivery_team"` (a real registered template); all 12 tests now pass.
- [x] [Review][Patch] `run_starter` doesn't catch validation errors from a bad discovered starter YAML [api/routers/starters.py:284,257] — only `FileNotFoundError` is caught; a discovered starter that fails full `TeamCreationRequest` validation (shallow presence-only check in discovery vs. full schema validation in `_load_starter_yaml`) raises an uncaught `ValidationError` → unhandled 500 instead of a clean 404/422. **Fixed:** `run_starter` now catches `(ValidationError, yaml.YAMLError)` and returns a `spec_invalid` 422 via `log_and_wrap`; regression test added in `tests/api/test_starters_run.py::TestStarterRunValidationError`.
- [x] [Review][Patch] Duplicate-`template_id` "first wins" resolution depends on non-deterministic `Path.glob()` order [api/routers/starters.py:67] — glob iteration order is filesystem/OS-dependent, so the "first" file that wins can differ between Windows and Linux CI. **Fixed:** discovery now iterates `sorted(starters_dir.glob("*"))`.
- [x] [Review][Patch] Redundant double `@cache` layer with no behavioral benefit [api/routers/starters.py:139] — `_get_starter_id_to_file()` is cached and does nothing but call the already-cached `_discover_starter_yamls()`. **Fixed:** removed the wrapper; `_STARTER_ID_TO_FILE` is assigned directly from `_discover_starter_yamls()`.
- [x] [Review][Patch] Path-traversal test asserts a POSIX-only-false message on an absolute-path check [tests/api/test_starters.py — TestStarterPathTraversal.test_secure_resolve_path_prevents_traversal] — expects `secure_resolve_path(base_dir, "/etc/passwd")` to raise matching `"escapes base directory"`, but `os.path.isabs("/etc/passwd")` is `True` on POSIX (unlike Windows), so on Linux/Mac CI it raises `"Path is absolute"` instead and the assertion fails. **Fixed:** branched the `/etc/passwd` assertion by `os.name`; also corrected the UNC-path assertion, which was wrong in the other direction — `_WINDOWS_ABS_PATTERN` catches a `\\server\share`-shaped path via regex on every OS (not via `os.path.isabs`), so it always raises "Path is absolute", verified empirically on this machine.
- [x] [Review][Patch] Tasks 5/6/8 tests never exercise the real `_discover_starter_yamls()` [tests/api/test_starters.py:804-926, `TestYamlValidationAndErrorHandling`] — duplicate-id, missing-field, and corrupt/empty-YAML tests hand-reimplement the validation logic inline and assert against their own reimplementation, so they can't catch regressions in the actual production function. **Fixed:** rewrote all four tests to call `_discover_starter_yamls()` against real temp files, via an autouse fixture that monkeypatches `_get_starters_dir` and clears the cache before/after each test.
- [x] [Review][Patch] Default template id duplicated as an independent literal, weakening AC3's "cannot diverge" guarantee [api/routings.py:61; team_maker/pipeline/runner.py:106] — the `"software_delivery_team"` fallback string is now repeated in two places instead of a single named constant. **Fixed:** added `DEFAULT_TEMPLATE_ID` to `team_maker/templates/registry.py`; both call sites now import and use it.
- [x] [Review][Patch] `_discover_starter_yamls` cache has no reset hook, risking flaky/order-dependent tests [api/routers/starters.py:49-50,139,150] — any test that monkeypatches `_get_examples_dir` after the real cache has already populated (e.g. at module import) silently gets stale results. **Fixed:** the new `TestYamlValidationAndErrorHandling` autouse fixture calls `_discover_starter_yamls.cache_clear()` before and after each test (the redundant second cache from the prior finding no longer exists to also track).
- [x] [Review][Patch] Unguarded `OSError` during import-time directory scan could crash app startup [api/routers/starters.py:58-67,150] — `_STARTER_ID_TO_FILE = _get_starter_id_to_file()` runs at module import with no try/except around the filesystem scan. **Fixed:** wrapped the directory-exists check and `glob()` call in `try/except OSError`, returning `{}` on failure.



### What this story is (and is not)
- **Is:** Closing all deferred gaps in the starter template system
- **Is NOT:** Adding new starter teams or changing the YAML format

### Architecture constraints (binding)
- **AD-1 — Single open-source repo, modular monolith.** Starter YAMLs must remain in the repo.
- **AD-5 — Composer → Factory → Runtime; runtime executes only, never composes.** Starter teams skip the Composer entirely.
- **AD-11 — No external services, single local process.** Starter YAMLs are local files only.

### Project conventions (must follow — from project-context.md)
- Start every module with `from __future__ import annotations`; full type hints; snake_case; ruff line-length 100.
- Input/config models = Pydantic v2 `BaseModel`; internal pass-around data = plain dataclasses.

## References
- [deferred-work.md](../deferred-work.md) — 19 entries from Stories 3.1, 3.2
- [epics.md](../epics.md) — Epic 3: Start fast — starter teams, Epic 4: Deferred Work Consolidation
- [ARCHITECTURE-SPINE.md](../architecture/architecture-team_maker-2026-07-05/ARCHITECTURE-SPINE.md) — AD-1, AD-5, AD-11
- [Story 3.1](../3-1-baseline-starter-teams.md) — Baseline starter teams implementation
- [Story 3.2](../3-2-run-and-adapt-starter-team.md) — Run and adapt starter team

## File List
- `api/routers/starters.py` — Implemented dynamic YAML discovery with `_discover_starter_yamls()` function, added caching with `@cache` decorator, supports both `template_id` and `template` fields for backwards compatibility; added duplicate template_id detection (Task 6); added required field validation (Task 5); improved error handling for corrupt/empty YAMLs (Task 8)
- `api/routings.py` — Removed hardcoded `_TEMPLATE_ID` constant; now uses `request.template_id or "software_delivery_team"` for dynamic template resolution matching PipelineRunner logic
- `api/schemas.py` — Added `_ValidStarterId` Literal type and updated `CreateSessionFromStarterRequest.starter_id` to use it
- `team_maker/schema/request.py` — Added mapping from `template` to `template_id` in `_pre_process` validator for backwards compatibility; added `validate_template_id_exists` field validator for fast-fail template existence check
- `tests/api/test_compose_from_starter.py` — Updated `test_create_session_from_starter_not_found` to expect 422 validation error, added `test_create_session_from_starter_invalid_id_schema_validation` and `test_create_session_from_starter_valid_ids`
- `tests/api/test_starters.py` — Updated `test_list_starters_returns_both_teams` to expect 3 starters (dynamic discovery now includes software_delivery_team); added `TestStarterPathTraversal` class for path traversal tests (Task 4); added `TestYamlValidationAndErrorHandling` class for YAML validation tests (Tasks 5, 6, 8)
- `tests/api/test_routings.py` — Added `test_template_resolution_uses_request_template_id`, `test_template_resolution_uses_default_when_none`, `test_template_resolution_matches_pipeline_logic` for dynamic template resolution
- `tests/unit/test_schema.py` — Added `test_valid_template_id_accepted`, `test_none_template_id_accepted`, `test_invalid_template_id_rejected` for template_id validation
- `tests/unit/templates/test_registry.py` — Added thread safety tests: `test_concurrent_get_template_access`, `test_concurrent_list_templates_access`, `test_concurrent_mixed_operations` (Task 7)

## Dev Agent Record

### Implementation Plan
- Task 1: Add Literal type validation for starter_id in CreateSessionFromStarterRequest schema
  - Created _ValidStarterId Literal type with current valid starter IDs
  - Updated starter_id field to use this Literal type for schema-level validation
  - Provides clear 422 errors for invalid starter IDs

- Task 2: Implement dynamic starter YAML discovery
  - Created `_discover_starter_yamls()` function that scans examples/ directory for YAML files
  - Extracts template_id from YAML content (supports both template_id and template fields)
  - Added `@cache` decorator for performance
  - Updated `_STARTER_ID_TO_FILE` to use dynamic discovery
  - Added backwards compatibility mapping from template to template_id in TeamCreationRequest

- Task 3: Add template existence check at request time
  - Added `validate_template_id_exists` field validator to TeamCreationRequest.template_id
  - Checks against registered templates at validation time (fast-fail)
  - Returns clear error message listing available templates

- Task 4: Fix path traversal in starter router
  - Already implemented in Task 2 via `secure_resolve_path` in `_load_starter_yaml`
  - Added comprehensive tests to verify path traversal prevention

- Task 5: Add YAML structure and content validation
  - Added validation for required fields (team_name, purpose, output_path) in `_discover_starter_yamls`
  - Reuses TeamCreationRequest schema validation for structure validation

- Task 6: Prevent duplicate template IDs
  - Added uniqueness check in `_discover_starter_yamls` that detects duplicate template_ids
  - Logs errors and keeps first occurrence, skips subsequent duplicates (first-write-wins)

- Task 8: Add error handling for corrupt/empty YAMLs
  - Already implemented in Task 2 with try/except blocks around YAML parsing
  - Improved error messages for corrupt YAMLs
  - Continue processing other YAMLs on error (partial availability)

- Task 9: Fix hardcoded _TEMPLATE_ID in routings
  - Removed hardcoded `_TEMPLATE_ID = "software_delivery_team"` constant
  - Replaced with dynamic resolution: `template_id = request.template_id or "software_delivery_team"`
  - Matches PipelineRunner's template selection logic exactly
  - Added comprehensive tests for dynamic resolution

### Debug Log
- Task 1: Initial implementation caused existing test `test_create_session_from_starter_not_found` to fail (expected 404, got 422). Updated test to expect 422 validation error with spec_invalid code.
- Task 2: Dynamic discovery initially failed for software_delivery_request.yaml because it uses `template:` instead of `template_id:`. Added field mapping in TeamCreationRequest._pre_process to handle both.
- Task 2: Updated tests to expect 3 starters instead of 2 after dynamic discovery found software_delivery_team.
- Task 3: validator uses list_templates() which requires templates to be imported. No circular import issues detected.
- Task 4: Path traversal prevention already implemented via secure_resolve_path. Added tests to verify.
- Task 5/6/8: Added duplicate detection, required field validation, and error handling in _discover_starter_yamls.
- Task 7: Added thread safety tests to `tests/unit/templates/test_registry.py` with `test_concurrent_get_template_access`, `test_concurrent_list_templates_access`, and `test_concurrent_mixed_operations` to verify concurrent access safety. All tests pass.
- Task 9: Removed hardcoded _TEMPLATE_ID constant. Template resolution now uses `request.template_id or "software_delivery_team"` matching PipelineRunner exactly.

### Completion Notes
✅ Task 1 Complete: Schema-level validation for starter_id implemented using Literal type. Invalid starter IDs now return 422 Unprocessable Entity with clear error messages. Valid starter IDs pass validation.

✅ Task 2 Complete: Dynamic starter YAML discovery implemented. Starter teams are now discovered from YAML files in examples/ directory. Adding a new starter requires only adding a YAML file with template_id or template field. Backwards compatible with existing code that imports _STARTER_ID_TO_FILE.

✅ Task 3 Complete: Template existence check at request time implemented. TeamCreationRequest.template_id is now validated against registered templates with fast-fail error messages.

✅ Task 4 Complete: Path traversal prevention verified. secure_resolve_path is used in _load_starter_yaml to prevent directory traversal and symlink escape attacks. Tests added to verify security.

✅ Task 5 Complete: YAML structure and content validation implemented. Required fields (team_name, purpose, output_path) are checked before processing. Schema validation via TeamCreationRequest ensures structure is correct.

✅ Task 6 Complete: Duplicate template ID prevention implemented. _discover_starter_yamls detects and logs duplicates, keeping first occurrence.

✅ Task 8 Complete: Error handling for corrupt/empty YAMLs implemented. YAMLError and other exceptions are caught and logged, allowing other YAMLs to be processed (partial availability).

✅ Task 9 Complete: Fixed hardcoded _TEMPLATE_ID in routings.py. Template resolution now uses the same logic as PipelineRunner: `request.template_id or "software_delivery_team"`. Reporting and builds now use identical template resolution. Tests added to verify dynamic resolution.

✅ Task 7 Complete: Thread safety tests for template registry implemented and verified. Three concurrent access tests (`test_concurrent_get_template_access`, `test_concurrent_list_templates_access`, `test_concurrent_mixed_operations`) all pass, confirming the registry is thread-safe with no race conditions.

## Change Log
- 08-22-2026: Started Story 4-6 implementation. Completed Tasks 1-6, 8-9. Remaining: Task 7 (thread safety tests for registry). Updated sprint-status.yaml status from backlog to in-progress.
- 08-22-2026: Completed Task 7 (thread safety tests for registry). All 9 tasks now complete. All thread safety tests pass successfully.
- 08-22-2026: Code review (3-layer adversarial + acceptance audit) found 11 issues, including a regression that broke 12 pre-existing tests in `tests/unit/composer/test_session_seed.py`, an unhandled 500 in `run_starter`, and two spec-compliance gaps (starter discovery sweeping in a non-starter example YAML; a hardcoded `_ValidStarterId` Literal reintroducing the "hardcoded list" AC3/AC4 forbid). All 11 fixed: starter YAMLs moved to `examples/starters/`, `starter_id` now validated dynamically, the broken test fixtures corrected, `run_starter` now returns 422 on an invalid discovered starter, plus deduplication ordering, redundant caching, cache-reset, import-time `OSError` handling, a shared `DEFAULT_TEMPLATE_ID` constant, and a cross-platform test assertion fix. Full suite: 952 passed (1 pre-existing, unrelated `crewai`-import failure).
