---
baseline_commit: 25883a8
---

# Story 4.8: My Teams Auth Wiring

Status: review

## Story

As a user of the local team_maker web app,
I want the web app to authenticate its own requests to the FastAPI backend,
so that Story 4.1's fail-closed API-key auth doesn't lock me out of my own local app.

## Background and scope boundary

**This is a post-merge regression fix for Epic 4 — Deferred Work Consolidation**, filed after Epic 4
was merged to `develop`. Story 4.1 (Security Hardening) made every `/api/teams/*` route reject
requests that don't carry a matching `X-API-Key` or `Authorization: Bearer` header, fail-closed by
design. That change only touched the backend — nothing updated the Next.js web app to send the
header, so the running app's "My Teams" tab started failing with
`authentication_required` the moment the key was configured (and would have failed identically
even before that, since no key was ever sent).

**What this story covers:**
- Wiring the local web app to authenticate its own proxied requests to FastAPI, server-side, without
  exposing the key to browser JavaScript.

**What this story is NOT:**
- A change to Story 4.1's authentication mechanism or its fail-closed default.
- A fix for the separate `compose_failed` team-creation error reported alongside this bug — that is
  a distinct issue (an unclassified exception in the compose flow) tracked separately.

## Acceptance Criteria

1. **Given** `TEAM_MAKER_API_KEY` is configured for both the FastAPI process and the Next.js process,
   **When** the browser calls any `/api/teams/*` route (e.g. `GET /api/teams/browse` from My Teams),
   **Then** the request is authenticated via an `X-API-Key` header attached server-side before Next's
   existing rewrite proxies it to FastAPI,
   **And** the key is never sent to, or readable by, browser JavaScript.

2. **Given** `TEAM_MAKER_API_KEY` is not set in the Next.js process's environment,
   **When** the same request is proxied,
   **Then** no key is fabricated,
   **And** the backend's existing fail-closed 401 behavior (Story 4.1 AC 6) is preserved unchanged.

3. **Given** the fix is in place,
   **When** any `/api/*` request is proxied,
   **Then** no changes are required to `web/lib/api-client/transport.ts` or to the backend's
   authentication logic (`api/deps.py`) — the fix is isolated to the proxy boundary.

## Tasks / Subtasks

- [x] **Task 1 — Diagnose the regression** (AC: #1, #2)
  - [x] Confirm `api/deps.py`'s `authenticated_request` fails closed on `/api/teams/*` per Story 4.1 AC 6
  - [x] Confirm `web/lib/api-client/transport.ts` sends no auth header on any request
  - [x] Confirm `next.config.ts`'s rewrite is a pure passthrough with no header-injection capability,
        and that no `web/app/api/` route handler exists (by design, per `tests/api/test_dev_topology.py`)

- [x] **Task 2 — Add a server-side auth bridge** (AC: #1, #2, #3)
  - [x] Add `web/middleware.ts` matching `/api/:path*` that attaches `X-API-Key` from
        `process.env.TEAM_MAKER_API_KEY` before Next's rewrite proxies to FastAPI
  - [x] Preserve fail-closed behavior when `TEAM_MAKER_API_KEY` is unset (no header attached, no
        fabricated key)

- [x] **Task 3 — Test and verify** (AC: #1, #2)
  - [x] Add `web/tests/middleware.test.ts` (Vitest): header attached when the key is set; no header
        added when the key is unset
  - [x] Manually verify end-to-end against a real `next dev` instance and a stub HTTP backend that the
        header actually reaches the proxied request (not just Next's internal response
        representation)

## File List
- `web/middleware.ts` — new. Attaches `X-API-Key` server-side to proxied `/api/*` requests.
- `web/tests/middleware.test.ts` — new. Unit tests for the above.

## Change Log
- Added Next.js middleware that attaches `X-API-Key` to every proxied `/api/*` request, closing the
  gap between Story 4.1's backend auth and the web app's frontend.

## Dev Notes

### What this story is (and is not)
- **Is:** A minimal, isolated fix for a post-merge Epic 4 regression — the web app never sent the
  auth header Story 4.1 requires.
- **Is NOT:** A change to the backend's authentication logic, a new auth mechanism, or a weakening of
  the fail-closed default (Story 4.1 AC 6, code review D1).

### Architecture constraints (binding)
- **AD-9 — keys live only in config/environment, read-only; never in the UI, never logged, never
  exposed to browser JS.** Middleware runs server-side only, so `TEAM_MAKER_API_KEY` is never shipped
  to the client.
- Story 4.1's fail-closed decision (`api/deps.py:87-94`, code review D1) is unchanged: if
  `TEAM_MAKER_API_KEY` is unset on the Next.js process, no header is attached and the backend still
  rejects the request.

### Local setup required
- `TEAM_MAKER_API_KEY` must be set in `web/.env.local` (gitignored) to the same value the FastAPI
  process uses, so the Next.js server process (where middleware runs) can read it via
  `process.env`.

## References
- [4-1-security-hardening.md](4-1-security-hardening.md) — the auth mechanism this story bridges to
- [epics.md](../epics.md) — Epic 4: Deferred Work Consolidation, Story 4.8

## Dev Agent Record

### Agent Model Used
Claude Sonnet 5

### Debug Log References
- Confirmed via a throwaway stub HTTP backend (`python -m http.server`-style handler) plus a live
  `next dev` instance that `X-API-Key` reached the proxied request end-to-end. Verification
  artifacts (stub server, temp env file) were not committed.

### Completion Notes List
- Both tasks complete; 2 new Vitest tests passing.
- Full `web` test suite run: 3 pre-existing failures (`tests/shell/routes.test.tsx` Starter Teams
  heading/description/action, plus two Playwright specs picked up by Vitest) confirmed identical on
  a clean `story_4_8` checkout before this change — unrelated, not touched by this story.
- Implementation pushed to `story_4_8` (branched from `epic_4`); pending code review before merge.
