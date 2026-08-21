---
baseline_commit: 0cc0c7d
---

# Story 4.7: Testing Infrastructure

Status: backlog

## Story

As the codebase,
I want proper CI automation and comprehensive test coverage,
so that regressions are caught automatically and the codebase remains reliable.

## Background and scope boundary

**This is the sixth and final story of Epic 4 — Deferred Work Consolidation.** Epic 4 exists to consolidate
all deferred technical debt from Stories 0.3–3.2 before proceeding to Epic 5 (Developer API).

This story specifically addresses **testing infrastructure gaps** that were deferred across multiple
previous stories. These are foundational quality issues that, if left unaddressed, will cause
regressions to go undetected as the project scales.

**What this story covers:**
- CI/CD pipeline gaps (missing automation for pytest, npm test)
- Test transparency violations (undisclosed live-network dependencies, importorskip holes)
- Test coverage gaps (missing tests for edge cases, error paths, and conformance)
- Test quality improvements (line length compliance, test splitting, anti-pattern fixes)
- Test organization and maintainability

**What this story is NOT:**
- Adding new functional tests for features (those belong in their respective feature stories)
- Fixing production code bugs (those belong in their respective category stories: 4.1–4.5)
- A full test suite rewrite (only addresses known deferred gaps)

## Explicit non-goals (do not build here)

- **No changes to production code.** This story focuses solely on test infrastructure, not on fixing
  the code being tested.
- **No new testing frameworks.** Use existing pytest, vitest, and related tooling.
- **No changes to existing test behavior.** Only add missing tests, do not modify existing ones.

## Acceptance Criteria

1. **Given** the absence of CI lanes running pytest and npm test (deferred-work.md:121, 134, 135),
   **When** this story completes,
   **Then** CI automation runs `pytest` for Python tests and `npm test` for frontend tests on every
   push and pull request,
   **And** a `make test` command exists that runs both test suites locally.

2. **Given** `pytest.importorskip("crewai")` makes the AD-7 conformance gate silently skippable
   (deferred-work.md:93),
   **When** conformance tests are run in an environment without crewai installed,
   **Then** the tests fail explicitly rather than skip,
   **And** a dedicated CI lane exists that installs the runtime extra and fails if conformance
   tests do not actually execute.

3. **Given** the absence of a browser test lane (deferred-work.md:164),
   **When** frontend E2E tests are needed,
   **Then** a Playwright-based E2E test infrastructure exists under `web/tests/e2e/`,
   **And** a `make test-e2e` command runs these tests,
   **And** the E2E suite covers critical user journeys (compose → build → run).

4. **Given** test files exceeding CLAUDE.md's ~400-line guideline (deferred-work.md:173, 204, 230, 307),
   **When** this story completes,
   **Then** all test files over 400 lines have been split into smaller, focused modules,
   **And** the split follows logical seams (by concern, domain, or test type).

5. **Given** missing tests for starter teams (deferred-work.md:329, 331, 336, 337),
   **When** this story completes,
   **Then** `tests/api/test_starters.py` covers: empty starter list, YAML loading failures, missing
   template_id, corrupt YAMLs, invalid schema, and concurrent access patterns,
   **And** frontend tests cover the starter teams listing surface.

6. **Given** test transparency violations with undisclosed live-network dependencies
   (deferred-work.md:245),
   **When** tests make network calls or depend on external services,
   **Then** these dependencies are clearly documented in test file headers,
   **And** tests that require live network access are separated from unit tests,
   **And** a mock-based alternative exists for offline testing.

7. **Given** `test_documents_are_never_written_to_disk` cannot catch the regression it names
   (deferred-work.md:237),
   **When** this story completes,
   **Then** the test is updated to exercise the real execution engine path,
   **And** the test proves that document text cannot reach disk through any component in the run path.

8. **Given** the Workspace test harness's "loud on unexpected request" property does not hold
   (deferred-work.md:238),
   **When** an unexpected API request is made in tests,
   **Then** the harness throws an error that is not swallowed by the client under test,
   **And** the harness is updated to maintain this property for the Workspace surface.

9. **Given** test anti-patterns like `test_the_policy_constants_are_named_not_magic` asserting
   nothing that can fail (deferred-work.md:244, 272),
   **When** this story completes,
   **Then** all such tests have been rewritten to assert meaningful, falsifiable conditions,
   **And** `test_the_policy_constants_are_named_not_magic` specifically asserts `MAX_STORED_RUNS`
   and other policy constants that can actually fail.

10. **Given** missing error handling tests for corrupt/empty starter YAML in the from-starter
    compose path (deferred-work.md:341),
    **When** this story completes,
    **Then** `tests/api/test_starters_run.py` covers YAML parse errors and validation errors
    in the compose-from-starter flow,
    **And** these tests do not rely on `importorskip` for the starter path.

11. **Given** no CI lane runs `pytest` or `npm test` (deferred-work.md:134),
    **When** this story completes,
    **Then** GitHub Actions workflows run both test suites on push and PR,
    **And** a badge in the README shows test status.

## Tasks / Subtasks

- [ ] **Task 1 — Set up CI/CD automation**
  - [ ] Create GitHub Actions workflow for Python tests (`pytest`)
  - [ ] Create GitHub Actions workflow for frontend tests (`npm test`)
  - [ ] Add `make test` command that runs both suites
  - [ ] Add test status badges to README
  - [ ] Configure workflow to run on push and PR events

- [ ] **Task 2 — Fix importorskip holes in conformance tests**
  - [ ] Create dedicated CI lane with runtime extra installed
  - [ ] Update AD-7 conformance gate to fail explicitly without crewai
  - [ ] Document the dependency requirement in test file headers
  - [ ] Add mechanism to require conformance tests to actually execute

- [ ] **Task 3 — Add browser E2E test infrastructure**
  - [ ] Set up Playwright as dev dependency
  - [ ] Create `web/tests/e2e/` directory structure
  - [ ] Add `make test-e2e` command
  - [ ] Create base E2E test fixtures and utilities
  - [ ] Add E2E tests for critical user journeys

- [ ] **Task 4 — Split oversized test files**
  - [ ] Split `tests/api/test_review_patches.py` (636 lines) by concern
  - [ ] Split `web/tests/composer/api-client.test.ts` (583 lines) by domain
  - [ ] Split `web/components/composer/spec-editor.tsx` related tests by component
  - [ ] Split `web/lib/api-client.ts` tests (454 lines) by transport vs routes
  - [ ] Split `web/components/composer/composer-surface.tsx` tests (428 lines) by extracting hooks
  - [ ] Ensure all split files are under 400 lines

- [ ] **Task 5 — Add missing tests for starter teams**
  - [ ] Add test for empty starter list in `tests/api/test_starters.py`
  - [ ] Add tests for YAML loading failures (missing files, corrupt YAML)
  - [ ] Add test for missing or null `template_id` field
  - [ ] Add test for invalid YAML schema
  - [ ] Add concurrency tests for starter endpoint
  - [ ] Add frontend tests for starter teams listing surface

- [ ] **Task 6 — Address test transparency violations**
  - [ ] Audit all tests for undisclosed live-network dependencies
  - [ ] Separate integration tests from unit tests
  - [ ] Add mock-based alternatives for tests requiring network access
  - [ ] Document external service dependencies in test headers
  - [ ] Update `tests/api/test_starters_run.py` to use mocks instead of live network

- [ ] **Task 7 — Fix test anti-patterns**
  - [ ] Rewrite `test_the_policy_constants_are_named_not_magic` to assert `MAX_STORED_RUNS`
  - [ ] Review all tests that use `assert True` or similar no-ops
  - [ ] Ensure every test has a meaningful, falsifiable assertion
  - [ ] Add regression tests for all guards

- [ ] **Task 8 — Update Workspace test harness**
  - [ ] Fix the "loud on unexpected request" property for Workspace surface
  - [ ] Create separate harness for Workspace tests
  - [ ] Ensure harness throws on unexpected requests
  - [ ] Verify the property cannot be silently swallowed

- [ ] **Task 9 — Add document leak test**
  - [ ] Update `test_documents_are_never_written_to_disk` to use real execution engine
  - [ ] Prove document text cannot reach disk through any run path component
  - [ ] Add test that document text does not appear in logs

- [ ] **Task 10 — Add from-starter compose error tests**
  - [ ] Add test for corrupt YAML in `create_session_from_starter`
  - [ ] Add test for empty starter YAML in compose path
  - [ ] Ensure tests catch YAML parse and validation errors
  - [ ] Verify errors are properly handled and do not leak secrets

- [ ] **Task 11 — Document and verify test organization**
  - [ ] Update CLAUDE.md with test organization rules if needed
  - [ ] Verify all test files follow naming conventions
  - [ ] Ensure test structure mirrors code structure
  - [ ] Add test directory README explaining organization

## Dev Notes

### What this story is (and is not)
- **Is:** Addressing known testing infrastructure gaps and quality issues deferred from previous stories
- **Is NOT:** A comprehensive test suite rewrite or adding tests for new features

### Architecture constraints (binding)
- **AD-4 — ports-and-adapters, inward dependencies.** Test utilities should be shared, not duplicated across layers.
- **AD-11 — local-only / no infra.** CI must work in a local development environment without external services.

### Project conventions (must follow — from project-context.md)
- Start every module with `from __future__ import annotations`; full type hints; snake_case; ruff line-length 100.
- Input/config models = Pydantic v2 `BaseModel`; internal pass-around data = plain dataclasses.
- Test files follow the same naming convention as the code they test.
- Every test must have a meaningful assertion that can fail.

### Test quality guidelines
- Tests should be **fast** (run in seconds, not minutes)
- Tests should be **isolated** (not depend on shared state or order)
- Tests should be **repeatable** (produce same results on repeated runs)
- Tests should be **self-validating** (clear pass/fail criteria)
- Tests should be **timely** (written at the same time as the code they test)

### CI/CD principles
- CI must run on every push and pull request
- CI must fail fast (don't run all tests if early ones fail)
- CI must provide clear feedback on failures
- CI must be reproducible locally (`make test` should match CI behavior)

## References
- [deferred-work.md](../deferred-work.md) — Testing infrastructure entries from Stories 1.2–3.2
- [epics.md](../epics.md) — Epic 4: Deferred Work Consolidation
- [ARCHITECTURE-SPINE.md](../architecture/architecture-team_maker-2026-07-05/ARCHITECTURE-SPINE.md) — AD-4, AD-11
- [CLAUDE.md](../CLAUDE.md) — Test organization and quality rules
- [project-context.md](../project-context.md) — Project conventions and standards
