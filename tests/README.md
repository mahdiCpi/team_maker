# Test Organization

This directory contains all Python tests for the `team_maker` and `api` packages.

## Structure

The test structure mirrors the code structure as much as possible:

```
tests/
├── api/                   # API endpoint tests (mirrors api/)
│   ├── test_*.py         # Tests for API routes
│   └── conftest.py       # Shared fixtures for API tests
├── conformance/           # Conformance tests (AD-7, FR-27, etc.)
│   └── test_*.py         # Tests verifying architectural invariants
├── unit/                 # Unit tests for internal modules
│   ├── team_maker/       # Tests for team_maker package (mirrors team_maker/)
│   │   └── test_*.py    # Unit tests for modules
│   └── api/              # Unit tests for api package
│       └── test_*.py
└── support/               # Test support utilities and fixtures
    └── *.py              # Shared test helpers, fake implementations
```

## Test Types

### 1. Unit Tests (`tests/unit/`)
- Test individual functions and classes in isolation
- Use mocks/stubs to avoid external dependencies
- Fast execution (milliseconds per test)
- Follow the same module structure as the code under test

### 2. API Tests (`tests/api/`)
- Test HTTP endpoints and request/response cycles
- Use `make_client()` harness with TestClient for FastAPI
- Test both success and error paths
- Grouped by route/endpoint being tested

### 3. Conformance Tests (`tests/conformance/`)
- Test architectural invariants (AD-*)
- Test feature requirements (FR-*)
- Often use real dependencies (with explicit failure if missing)
- Run on every push/PR via dedicated CI lane

## Naming Conventions

- **Files**: `test_<module_or_feature>.py` (lowercase, underscores)
- **Functions**: `test_<description>()` (lowercase, underscores)
- **Classes**: `Test<Feature>` (PascalCase)
- **Fixtures**: Use pytest fixtures with descriptive names

## Test Quality Rules

1. **Every test must have a meaningful assertion that can fail** (no `assert True`)
2. **Tests must be fast** (seconds, not minutes)
3. **Tests must be isolated** (no shared state between tests)
4. **Tests must be repeatable** (same result on repeated runs)
5. **Tests must be self-validating** (clear pass/fail criteria)

## Network Dependencies

All tests that make network calls or depend on external services must:
- Document the dependency in the test file header
- Use mocks/stubs where possible (preferred)
- Separate integration tests from unit tests
- Have explicit failure messages if dependencies are missing

Example header:
```python
"""
**Network Dependencies:** NONE - All tests use FastAPI TestClient (in-memory)
**External Services:** NONE - No live network calls are made
"""
```

## Running Tests

- **All tests**: `make test` (runs Python + frontend tests)
- **Python only**: `pytest tests/ -v`
- **Unit tests only**: `make test-unit`
- **API tests only**: `make test-api`
- **Frontend tests**: `make web-test`
- **E2E tests**: `make test-e2e`
- **With coverage**: `make test-cov`

## CI/CD

All tests run automatically on push and PR via GitHub Actions:
- Python tests: `.github/workflows/python-tests.yml`
- Frontend tests: `.github/workflows/frontend-tests.yml`
- Combined: `.github/workflows/test.yml`
- Conformance tests: `.github/workflows/conformance-tests.yml`
- E2E tests: `.github/workflows/e2e-tests.yml`

## Test File Size Guideline

Per CLAUDE.md, test files should be under ~400 lines. Larger files should be split by:
- Logical concerns
- Domain boundaries
- Test type (unit vs integration)

See Story 4.7 Task 4 for ongoing work on splitting oversized test files.

## Additional Resources

- [CLAUDE.md](../CLAUDE.md) - Project-wide test rules and conventions
- [ARCHITECTURE-SPINE.md](../project-docs/architecture/architecture-team_maker-2026-07-05/ARCHITECTURE-SPINE.md) - Architectural invariants that tests must verify
- [project-context.md](../project-docs/project-context.md) - Project-specific coding conventions
