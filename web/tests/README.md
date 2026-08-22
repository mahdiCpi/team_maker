# Web Tests Organization

This directory contains all frontend tests for the Next.js web application.

## Structure

```
web/tests/
├── composer/              # Tests for the Composer surface (Story 2.0+)
│   ├── *.test.ts          # Component and integration tests
│   ├── fixtures/          # Test fixtures and captured responses
│   └── harness.tsx        # Test harness for Composer API mocking
├── e2e/                  # End-to-end tests (Story 4.7 Task 3)
│   ├── *.test.ts          # Playwright-based E2E tests
│   └── base.test.ts       # Base fixtures and utilities
├── workspace/             # Tests for the Workspace surface (Story 2.4+)
│   ├── *.test.tsx         # Component and integration tests
│   ├── fixtures/          # Test fixtures
│   └── harness.tsx        # Test harness for Workspace API mocking
├── shell/                 # Tests for app shell components (Story 2.1)
│   └── *.test.ts
├── theme/                 # Tests for theming (Story 2.1)
│   └── *.test.ts
└── nav/                   # Tests for navigation (Story 2.1)
    └── *.test.ts
```

## Test Types

### 1. Unit Tests
- Test individual React components in isolation
- Use `@testing-library/react` for rendering
- Use `vi` (vitest) for mocking
- Located alongside the components they test

### 2. Integration Tests
- Test component interactions
- Use mocked API responses via test harnesses
- Verify component behavior with user events

### 3. E2E Tests (`e2e/`)
- Test complete user journeys across multiple pages
- Use Playwright for browser automation
- Run against a real build of the application
- Critical journeys: compose → build → run

## Test Harnesses

Each major surface has its own test harness that:
- Replaces global `fetch` with a queue-based mock
- Tracks all requests made by components
- Throws on unexpected requests ("loud on unexpected request" property)
- Provides fixtures for common response patterns

- **Composer**: `tests/composer/harness.tsx`
- **Workspace**: `tests/workspace/harness.tsx`

## Running Tests

- **All frontend tests**: `npm --prefix web test`
- **E2E tests**: `make test-e2e` or `npm --prefix web run test:e2e`
- **With UI mode**: `npm --prefix web run test:e2e:ui`
- **Headed mode**: `npm --prefix web run test:e2e:headed`

## CI/CD

Frontend tests run automatically on push and PR via:
- `.github/workflows/frontend-tests.yml` - Vitest tests
- `.github/workflows/e2e-tests.yml` - Playwright E2E tests

## Test Quality Rules

1. **All network traffic must be mocked** - No real API calls
2. **Use captured responses** - Responses should be verbatim captures from live servers
3. **Document dependencies** - If a test requires external services, document it
4. **Follow naming conventions** - Files: `*.test.ts` or `*.test.tsx`, functions: `test(...)` or `it(...)`
5. **Keep tests fast** - E2E tests may be slower but should still complete in seconds

## Network Dependency Documentation

All test files that make API calls must document their network dependencies in the module docstring:

```typescript
/**
 * The Workspace surface (Story 2.4 AC 11–14).
 *
 * Fully offline, exactly like `tests/composer/`'s suites: `createFetchQueue`
 * replaces `fetch`, so these prove the real client/components handle the
 * real (synthesised — see `fixtures/index.ts`) wire shape, not that the
 * backend works.
 */
```

## Test Transparency

Per CLAUDE.md, all tests must be transparent about:
- What they're testing
- What dependencies they have
- What assumptions they make
- Whether they're unit, integration, or E2E tests

Tests that use mocked `fetch` should explicitly state this in their documentation.

## Additional Resources

- [CLAUDE.md](../../CLAUDE.md) - Project-wide test rules
- [project-context.md](../../project-docs/project-context.md) - Project conventions
