---
baseline_commit: 0cc0c7d
---

# Story 4.6: Template and Starter System Hardening

Status: backlog

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

- [ ] **Task 1 — Add schema-level template_id validation**
  - [ ] Update `CreateSessionFromStarterRequest.starter_id` to use Literal/enum of registered templates
  - [ ] Or add custom validator for template_id field
  - [ ] Ensure invalid template IDs are rejected with clear errors

- [ ] **Task 2 — Implement dynamic starter YAML discovery**
  - [ ] Replace hardcoded `_STARTER_YAMLS` with directory scanning in `api/routers/starters.py`
  - [ ] Add configuration for starter directory path
  - [ ] Ensure discovered YAMLs are cached appropriately

- [ ] **Task 3 — Add template existence check at request time**
  - [ ] Verify template exists in catalog before processing requests
  - [ ] Return clear error for missing templates (404 or 422)
  - [ ] Add fast-fail behavior

- [ ] **Task 9 — Fix hardcoded _TEMPLATE_ID in routings (moved from Story 4.2)**
  - [ ] Replace hardcoded `_TEMPLATE_ID = "software_delivery_team"` in `api/routings.py` with dynamic template resolution
  - [ ] Use same template selection logic as the pipeline (get_template() from registry)
  - [ ] Ensure reporting and builds use identical template resolution
  - [ ] Add tests verifying template is resolved dynamically
  - [ ] **Test:** Verify routings are resolved from actual template, not hardcoded value

- [ ] **Task 4 — Fix path traversal in starter router**
  - [ ] Add secure path resolution in `api/routers/starters.py`
  - [ ] Validate resolved path stays within examples directory
  - [ ] Prevent symlink escape attacks
  - [ ] Add tests for path traversal attempts

- [ ] **Task 5 — Add YAML structure and content validation**
  - [ ] Validate YAML structure against expected schema
  - [ ] Check all required fields are present (`template_id`, `desired_roles`, etc.)
  - [ ] Add clear error messages for validation failures

- [ ] **Task 6 — Prevent duplicate template IDs**
  - [ ] Add uniqueness check during template registration
  - [ ] Log warnings for duplicates
  - [ ] Ensure last-write-wins has collision detection

- [ ] **Task 7 — Add thread safety tests for registry**
  - [ ] Test concurrent access to template registry
  - [ ] Verify no race conditions in registration
  - [ ] Add thread safety mechanisms if needed

- [ ] **Task 8 — Add error handling for corrupt/empty YAMLs**
  - [ ] Handle YAMLError gracefully with clear error messages
  - [ ] Handle empty files gracefully
  - [ ] Continue processing other YAMLs on error (partial availability)

## Dev Notes

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
