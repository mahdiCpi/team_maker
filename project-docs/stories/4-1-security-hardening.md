---
baseline_commit: 0cc0c7d
---

# Story 4.1: Security Hardening

Status: backlog

## Story

As the codebase,
I want all security vulnerabilities addressed before API exposure,
so that external developers can safely consume the package.

## Background and scope boundary

**This is the first story of Epic 4 — Deferred Work Consolidation.** Epic 4 exists to consolidate
all deferred technical debt from Stories 0.3–3.2 before proceeding to Epic 5 (Developer API).

This story specifically addresses **security vulnerabilities** that were deferred across multiple
previous stories. These must be fixed before exposing the API to external developers.

**What this story is NOT:**
- A full security audit (only addresses known deferred vulnerabilities)
- Encryption at rest implementation (future consideration)
- Network-level security (infrastructure concern)

## Acceptance Criteria

1. **Given** transcript content containing ANSI escape sequences or OSC sequences, **When** it is rendered to the terminal, **Then** all control characters and escape sequences are sanitized or removed, preventing terminal manipulation, cursor movement, screen clearing, or hyperlink injection, **And** the written file content remains unchanged. (deferred-work.md:108)

2. **Given** a malicious request to the starter router with a crafted path, **When** the router resolves the template path, **Then** the path stays within the designated examples directory, preventing directory traversal attacks, **And** symlinks are resolved safely without escaping the intended directory. (deferred-work.md:320)

3. **Given** a run with attached documents that fails, **When** `logger.exception` is called, **Then** the exception message and traceback do NOT contain the full document text, **And** no attached document content appears in server logs. (deferred-work.md:239)

4. **Given** a compose exception from an underlying SDK, **When** the exception is printed or logged, **Then** SDK-embedded secrets, API keys, or credentials are NOT echoed in the exception string, **And** the compose command sanitizes exception output before display. (deferred-work.md:44)

5. **Given** document text or a goal containing the run-context delimiter strings, **When** the run context is constructed, **Then** the delimiters cannot be spoofed to inject additional sections. (deferred-work.md:243)

6. **Given** the teams API surface (save/browse/rename/delete/recent), **When** a request is made without authentication, **Then** the request is rejected with an appropriate 401/403 status, **And** a basic authentication mechanism is in place. (deferred-work.md:277)

## Tasks / Subtasks

- [ ] **Task 1 — Sanitize ANSI/OSC sequences in transcript display**
  - [ ] Add sanitization utility function to strip/neutralize control characters
  - [ ] Apply to CLI transcript output (`team_maker/cli.py`)
  - [ ] Apply to API transcript responses (`api/routers/...`)
  - [ ] Ensure raw content in files is preserved unchanged

- [ ] **Task 2 — Fix path traversal in starter router**
  - [ ] Add path validation to ensure resolution stays within examples directory
  - [ ] Use secure path resolution (no symlink following outside root)
  - [ ] Add tests for path traversal attempts

- [ ] **Task 3 — Secure exception logging**
  - [ ] Review all `logger.exception` calls in run path
  - [ ] Ensure document text cannot leak to logs
  - [ ] Sanitize exception messages before logging

- [ ] **Task 4 — Sanitize compose exception output**
  - [ ] Wrap SDK exceptions before display in compose command
  - [ ] Strip potential secrets from exception strings
  - [ ] Maintain debuggability without exposing credentials

- [ ] **Task 5 — Harden run-context delimiters**
  - [ ] Use unique, non-guessable delimiter format
  - [ ] Add validation to detect and prevent spoofing attempts
  - [ ] Document delimiter format securely

- [ ] **Task 6 — Add basic auth to teams API**
  - [ ] Implement minimal authentication mechanism for teams endpoints
  - [ ] Protect all teams endpoints (save/browse/rename/delete/recent)
  - [ ] Document authentication requirements

## Dev Notes

### What this story is (and is not)
- **Is:** Addressing known security vulnerabilities deferred from previous stories
- **Is NOT:** A comprehensive security audit or implementation of encryption

### Architecture constraints (binding)
- **AD-9 — keys live only in the Key Config file, read-only.** Never entered in the UI, never logged, never in run output. This extends to all sensitive data: document text must not leak to logs.
- **AD-4 — ports-and-adapters, inward dependencies.** Security sanitization should be a shared utility, not duplicated across layers.

### Project conventions (must follow — from project-context.md)
- Start every module with `from __future__ import annotations`; full type hints; snake_case; ruff line-length 100.
- Input/config models = Pydantic v2 `BaseModel`; internal pass-around data = plain dataclasses.

## References
- [deferred-work.md](../deferred-work.md) — Security-related entries from Stories 1.2, 1.7, 2.4, 2.5
- [epics.md](../epics.md) — Epic 4: Deferred Work Consolidation
- [ARCHITECTURE-SPINE.md](../architecture/architecture-team_maker-2026-07-05/ARCHITECTURE-SPINE.md) — AD-4, AD-9
