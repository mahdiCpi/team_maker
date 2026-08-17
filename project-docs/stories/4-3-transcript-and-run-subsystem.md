---
baseline_commit: 0cc0c7d
---

# Story 4.3: Transcript and Run Subsystem Hardening

Status: backlog

## Story

As the codebase,
I want a robust transcript capture system,
so that Epic 5's HTTP endpoints can reliably expose transcripts to external developers.

## Background and scope boundary

**This is the third story of Epic 4 — Deferred Work Consolidation.**

The transcript subsystem has several known issues from Stories 1.7 and 2.4 that would block
or complicate Epic 5's API work. Story 1.7 added transcript capture, but several gaps remain:

- Partial transcripts on failed runs are discarded
- Concurrent runs in one process corrupt each other's transcripts (measured in Story 1.7 review)
- The generated `crewai_runner.py.j2` template doesn't capture transcripts
- ANSI/OSC escape sequences can reach the terminal verbatim
- Transcript line format is ambiguous and unbounded
- Document text can spoof run-context delimiters
- Server logs can leak document text on failures

This story hardens the transcript subsystem before Epic 5 exposes it via HTTP.

**What this story is NOT:**
- Implementing per-turn streaming (that's v2, AD-13)
- Persisting transcripts to database (that's Story 2.5 / AD-11)

## Acceptance Criteria

1. **Given** a team run that fails partway through, **When** the run fails, **Then** the transcript entries collected before the failure are returned, **And** these partial transcripts are not discarded along with the exception. (deferred-work.md:101)

2. **Given** two simultaneous `run_team_package` calls in one process, **When** both runs complete, **Then** each run returns only its own transcript entries, **And** there is no cross-contamination between runs' transcripts. (deferred-work.md:102)

3. **Given** a team built and run via the generated `run_example.py`, **When** the team runs, **Then** the transcript is captured and available, **And** the `crewai_runner.py.j2` template includes transcript capture. (deferred-work.md:103)

4. **Given** transcript content containing ANSI escape sequences or OSC sequences, **When** displayed to the terminal, **Then** all control characters and escape sequences are removed. (deferred-work.md:108)

5. **Given** a transcript line reading `    [7] design / architect (agent_message)`, **When** the transcript is formatted, **Then** it is unambiguous and cannot be confused with a real header, **And** there is a length cap on transcript content. (deferred-work.md:111)

6. **Given** document text or a goal containing the run-context delimiter strings, **When** the run context is injected, **Then** the delimiters cannot be spoofed to inject additional sections. (deferred-work.md:243)

## Tasks / Subtasks

- [ ] **Task 1 — Return partial transcripts on failed runs**
  - [ ] Modify exception handling in TranscriptRecorder to preserve collected entries
  - [ ] Return partial transcript in RunResult even on failure
  - [ ] Update TranscriptRecorder context manager to not discard entries on exception

- [ ] **Task 2 — Fix concurrent run transcript corruption**
  - [ ] Implement process-wide run lock for v1 (serializes runs in one process)
  - [ ] Document this as a v1 limitation (crewai event bus is process-global singleton)
  - [ ] Add note that proper per-run filtering requires crewai changes

- [ ] **Task 3 — Add transcript capture to generated template**
  - [ ] Update `team_maker/codegen/templates/crewai_runner.py.j2` template
  - [ ] Include transcript capture matching in-process Runtime behavior
  - [ ] Ensure generated code can capture and return transcripts

- [ ] **Task 4 — Sanitize ANSI/OSC sequences in display**
  - [ ] Add sanitization utility function to strip/neutralize control characters
  - [ ] Apply to CLI transcript output
  - [ ] Apply to API transcript responses
  - [ ] Preserve raw content in files unchanged

- [ ] **Task 5 — Fix ambiguous transcript line format**
  - [ ] Add structured serialization option (JSON) for machine reading
  - [ ] Make human format unambiguous (add prefixes, quotes, or markers)
  - [ ] Add length bounds and truncation mechanism

- [ ] **Task 6 — Prevent delimiter spoofing**
  - [ ] Use unique, non-guessable delimiter format
  - [ ] Add validation to detect spoofing attempts
  - [ ] Document delimiter format securely

## Dev Notes

### What this story is (and is not)
- **Is:** Hardening the transcript subsystem for API exposure
- **Is NOT:** Implementing streaming or database persistence

### Architecture constraints (binding)
- **AD-6 — CrewAI 1.14.6 behind the RuntimeEngine port.** Transcript capture must work with existing CrewAI version.
- **AD-13 — Batch results behind a streamable interface.** Partial transcripts must fit this pattern.

### Project conventions (must follow — from project-context.md)
- Start every module with `from __future__ import annotations`; full type hints; snake_case; ruff line-length 100.

## References
- [deferred-work.md](../deferred-work.md) — Entries from Stories 1.7, 2.4
- [epics.md](../epics.md) — Epic 4: Deferred Work Consolidation
- [ARCHITECTURE-SPINE.md](../architecture/architecture-team_maker-2026-07-05/ARCHITECTURE-SPINE.md) — AD-6, AD-13
- [Story 1.7](../1-7-capture-run-transcript.md) — Original transcript capture implementation
- [Story 2.4](../2-4-team-workspace-chat-documents-run-results.md) — Workspace transcript display
