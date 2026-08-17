---
baseline_commit: 0cc0c7d
---

# Story 4.4: API Contract and Error Handling

Status: backlog

## Story

As the codebase,
I want robust error handling and contract compliance for the API layer,
so that external developers have a reliable and predictable experience.

## Background and scope boundary

**This is the fourth story of Epic 4 — Deferred Work Consolidation.**

Multiple stories have deferred issues related to API contract reliability and error handling:
- Story 1.2 deferred generic exception printing that could echo SDK secrets
- Story 2.0 introduced the API seam but left several contract gaps
- Story 2.2 added the Workspace but didn't guard all edge cases
- Story 2.4 exposed transcripts but didn't handle partial/failure cases properly

These must be addressed before Epic 5 exposes the API to external developers.

**What this story is NOT:**
- Changing the API response format (only content quality improvements)
- Adding new endpoints (only fixing existing ones)
- Implementing full streaming (that's v2)

## Acceptance Criteria

1. **Given** a compose exception from an underlying SDK, **When** the exception is raised or printed, **Then** SDK-embedded secrets, API keys, or credentials are NOT present in the exception string, **And** the compose command sanitizes exception output before display. (deferred-work.md:44)

2. **Given** a compose session with a spec routing roles to multiple providers, **When** `compose --build` runs, **Then** not just the authoring provider's key, but ALL provider keys needed for the team are bridged into `os.environ`, **And** the build can access all required provider credentials. (deferred-work.md:44)

3. **Given** an API request with any field, **When** the request is validated, **Then** all fields have proper schema-level validation, **And** invalid values are rejected with clear, actionable error messages. (deferred-work.md:62)

4. **Given** a spec stored via PUT .../spec {}, **When** it is read back, **Then** the spec is unchanged (no mutation during round-trip), **And** validation does not have side effects on the spec. (deferred-work.md:62)

5. **Given** a spec with empty `desired_roles`, **When** the build path is invoked, **Then** a clear error is returned before any LLM calls, **And** the guard is consistent with the edit route's behavior. (deferred-work.md:62)

6. **Given** a session where a build has already succeeded, **When** a second build is attempted, **Then** it no longer always fails with `output_exists`, **And** legitimate changes to the team allow a new build. (deferred-work.md:154)

7. **Given** an API error response with `fields[].message`, **When** the error is returned, **Then** `fields[].message` contains authored copy (plain-language, user-facing), NOT pydantic-derived text or SDK error messages, **And** error messages are consistent and helpful. (deferred-work.md:140)

8. **Given** a run request for a team with multiple providers, **When** the run is initiated, **Then** all provider keys needed for the team's roles are bridged, **And** the run has access to all required credentials. (Story 1.6 precedent)

## Tasks / Subtasks

- [ ] **Task 1 — Sanitize compose exception output**
  - [ ] Review all exception printing in compose command (`team_maker/cli.py`)
  - [ ] Add sanitization layer for SDK exceptions
  - [ ] Strip potential secrets from exception strings
  - [ ] Maintain debuggability without exposing credentials

- [ ] **Task 2 — Bridge per-role provider keys in compose --build**
  - [ ] Identify all providers needed for a spec by analyzing role assignments
  - [ ] Bridge all required keys into `os.environ`, not just authoring provider
  - [ ] Ensure keys are available before build starts

- [ ] **Task 3 — Add schema validation for all request fields**
  - [ ] Audit all API request schemas in `api/schemas.py`
  - [ ] Add missing validations (template_id, starter_id, etc.)
  - [ ] Ensure all fields have proper types, constraints, and patterns

- [ ] **Task 4 — Fix spec round-trip mutation**
  - [ ] Review PUT .../spec implementation in `api/routers/compose.py`
  - [ ] Ensure spec is reconstructed without mutation
  - [ ] Fix `context_dir` validation that breaks round-trip

- [ ] **Task 5 — Guard empty desired_roles in build path**
  - [ ] Add validation before build in `api/build.py`
  - [ ] Return clear error message (422 spec_invalid)
  - [ ] Align with edit route behavior (PUT .../spec)

- [ ] **Task 6 — Fix second build in same session**
  - [ ] Review `output_exists` logic in `api/build.py` and `api/output.py`
  - [ ] Allow rebuilds when spec changes (different team_name or content)
  - [ ] Or implement versioned output paths

- [ ] **Task 7 — Author error messages in fields[].message**
  - [ ] Create error message catalog mapping pydantic errors to user-friendly messages
  - [ ] Update `api/errors.py` fields_from_composer_errors to use authored copy
  - [ ] Ensure all error paths return user-facing, not technical, messages

- [ ] **Task 8 — Bridge per-role keys for run endpoint**
  - [ ] Identify all providers in team spec
  - [ ] Bridge all required keys before run
  - [ ] Ensure credentials are available throughout run

## Dev Notes

### What this story is (and is not)
- **Is:** Ensuring API contract reliability and consistent error handling
- **Is NOT:** Changing response formats or adding new endpoints

### Architecture constraints (binding)
- **AD-4 — Inward dependency direction: UI → API → core → adapters.** API layer should not import from UI or contain UI-specific logic.
- **AD-9 — Keys live only in the Key Config file, read-only.** Never in API responses, logs, or error messages.
- **AD-10 — Composer output validated against factory Pydantic schema.** All validation must use existing schema patterns.

### Project conventions (must follow — from project-context.md)
- Start every module with `from __future__ import annotations`; full type hints; snake_case; ruff line-length 100.
- Input/config models = Pydantic v2 `BaseModel`; internal pass-around data = plain dataclasses.

## References
- [deferred-work.md](../deferred-work.md) — Entries from Stories 1.2, 2.0, 2.2, 2.4
- [epics.md](../epics.md) — Epic 4: Deferred Work Consolidation
- [ARCHITECTURE-SPINE.md](../architecture/architecture-team_maker-2026-07-05/ARCHITECTURE-SPINE.md) — AD-4, AD-9, AD-10
- [Story 1.2](../1-2-compose-team-spec.md) — Composer implementation
- [Story 2.0](../2-0-api-seam-compose-endpoints.md) — API seam creation
- [Story 2.2](../2-2-new-team-conversational-composer.md) — Composer with review
