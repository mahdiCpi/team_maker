---
baseline_commit: 0cc0c7d
---

# Story 4.4: Transcript and Run Subsystem Hardening

Status: done

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

- [x] **Task 1 — Return partial transcripts on failed runs**
  - [x] Modify exception handling in TranscriptRecorder to preserve collected entries
  - [x] Return partial transcript in RunResult even on failure
  - [x] Update TranscriptRecorder context manager to not discard entries on exception

- [x] **Task 2 — Fix concurrent run transcript corruption**
  - [x] Implement process-wide run lock for v1 (serializes runs in one process)
  - [x] Document this as a v1 limitation (crewai event bus is process-global singleton)
  - [x] Add note that proper per-run filtering requires crewai changes

- [x] **Task 3 — Add transcript capture to generated template**
  - [x] Update `team_maker/codegen/templates/crewai_runner.py.j2` template
  - [x] Include transcript capture matching in-process Runtime behavior
  - [x] Ensure generated code can capture and return transcripts

- [x] **Task 4 — Sanitize ANSI/OSC sequences in display**
  - [x] Add sanitization utility function to strip/neutralize control characters
  - [x] Apply to CLI transcript output
  - [x] Apply to API transcript responses
  - [x] Preserve raw content in files unchanged

- [x] **Task 5 — Fix ambiguous transcript line format**
  - [x] Add structured serialization option (JSON) for machine reading (deferred - not required per AC)
  - [x] Make human format unambiguous (changed delimiter from `(` to `::` in header)
  - [x] Add length bounds and truncation mechanism (10,000 chars per entry)

- [x] **Task 6 — Prevent delimiter spoofing**
  - [x] Use unique, non-guessable delimiter format (UUID-based `--- RUN_CONTEXT:<uuid>:GOAL ---`)
  - [x] Add validation to detect spoofing attempts (`goal_is_injected` checks structural adjacency)
  - [x] Document delimiter format securely (documented in run_context.py module docstring)

### Review Findings

- [x] [Review][Patch] Failed-run exception is swallowed into a fake-success `RunResult` — `CrewAIExecutionEngine.run()`'s new `except Exception:` (`team_maker/adapters/runtime_crewai/crewai_execution_engine.py:96-126`) never re-raises: it returns `RunResult(final_output="", task_results=[], transcript=partial_transcript)` for *any* kickoff failure (auth, rate limit, network, crewai bug), discarding the original error entirely. Downstream this flips `team_maker/cli.py`'s `run` command exit code from 1 to 0 and flips the API's `record.status` from `failed` to `complete` with `failure_reason` staying `None`, which also makes `api/routers/run.py:158-161`'s comment ("a failed run's partial transcript is discarded along with the exception, so there is genuinely nothing to return") stale. **Fixed (2026-08-22):** added `error: str | None = None` to `RunResult` (`team_maker/runtime/results.py`); `CrewAIExecutionEngine.run()` now sets it to `str(exc)` instead of swallowing; `cli.py`'s `run` command checks it and exits 1 while still printing/writing the partial transcript; `api/runs.py`'s `_execute` checks it and sets `status=failed`/`failure_reason=GENERIC_FAILURE_REASON` (logging the real reason server-side via `sanitize_text_for_display`, per AD-9) while still storing `record.result` so the transcript stays available. Added `test_kickoff_failure_returns_a_run_result_with_error_set_instead_of_raising` (engine), `test_run_result_with_error_set_exits_1_instead_of_reporting_success` (CLI), and `test_run_with_a_partial_transcript_failure_still_reports_failed` (API).
- [x] [Review][Patch] `--transcript-out` doesn't sanitize control characters before writing to disk — `team_maker/cli.py:522` writes `_format_transcript(result)` straight to a file with no `sanitize_control_characters` call, while the console path (`_print_transcript`, `cli.py:724-725`) does sanitize. **Fixed (2026-08-22):** the file-write path now sanitizes with `sanitize_control_characters` before writing, matching the console path.
- [x] [Review][Patch] Broken OSC-sequence regex in the template's `sanitize_control_characters` [team_maker/codegen/templates/crewai_runner.py.j2] — the ST-terminated alternative both over-strips (consumes forward past the terminator to the next letter char) and under-strips (fails to match at all when no trailing letter follows), and the control-char class omits the C1 range `\x80-\x9f` that the project's existing, correct `team_maker/utils/text_sanitizer.py::sanitize_control_characters` already handles (its own comment cites this as "code review P8"). **Fixed (2026-08-22):** replaced the ANSI/OSC/control-char patterns with the canonical ones mirrored from `text_sanitizer.py` (verified against `tests/unit/test_codegen.py`'s `compile()` check on the rendered template).
- [x] [Review][Patch] Read-before-flush ordering bug on the success path [team_maker/codegen/templates/crewai_runner.py.j2] — `transcript = recorder.entries()` is read inside the `with SimpleTranscriptRecorder(...)` block, before `__exit__` calls `crewai_event_bus.flush()`, unlike the failure path and unlike `CrewAIExecutionEngine` (both read after exit). Can silently miss trailing events on a successful run. **Fixed (2026-08-22):** `recorder.entries()` is now read after the `with` block exits, on the success path too.
- [x] [Review][Patch] `except KeyboardInterrupt:` doesn't preserve the partial transcript [team_maker/codegen/templates/crewai_runner.py.j2] — only the generic `except Exception:` branch retrieves/prints it; a user-cancelled run gets none, inconsistent with this story's own intent. **Fixed (2026-08-22):** the `KeyboardInterrupt` branch now retrieves and prints the partial transcript too, via a shared `_print_transcript_entries` helper (also used by the success and generic-exception paths, replacing the triplicated inline formatting).
- [x] [Review][Patch] Type-guard asymmetry between `_on_tool_started`/`_on_tool_finished` [team_maker/codegen/templates/crewai_runner.py.j2] — `_on_tool_finished` guards `output` with `isinstance(output, str)` before slicing; `_on_tool_started` does `args.get("task", "")[:500]` with no type guard, so a non-string `"task"` in a malformed tool call raises inside an event-bus callback. **Fixed (2026-08-22):** `_on_tool_started` now coerces a non-string `task` argument to `str` before slicing.
- [x] [Review][Patch] Stale "one home" claim for the process-wide lock [api/runs.py:19] — the module docstring says "This registry is that lock's one home," which is no longer true now that `team_maker/runtime/executor.py` adds its own independent `_run_lock`. Update the comment to explain both locks (registry lock: non-blocking, fast-fails a concurrent API request with `RUN_IN_PROGRESS`; runtime lock: correctness guarantee for every caller, including future non-API embedders per Epic 5 Story 5.3) and document the no-timeout tradeoff on the new lock as the deliberate v1 limitation the story's Task 2 already calls out. **Fixed (2026-08-22):** updated both `api/runs.py`'s and `team_maker/runtime/executor.py`'s module docstrings to cross-reference each other and explain why both locks exist.
- [x] [Review][Patch] AC 5's `::` delimiter was a relabeling, not a structural fix [team_maker/cli.py, generated `transcript.py`] — `content` is unconstrained LLM free text, and the ambiguous line `deferred-work.md:111` cites is an *indented* one, so indentation alone did not separate structure from output. **Fixed (2026-08-22):** content lines now carry a `"  | "` gutter, which a header can never start with (a header always starts with `[`), so the two are unambiguous by construction rather than by convention. Covered by `test_content_lines_carry_a_gutter_so_they_cannot_impersonate_a_header`.
- [x] [Review][Patch] Silent truncation at the 10,000-char cap [team_maker/cli.py, generated `transcript.py`] — under-reported in the original review: `content[:10000]` gave no indication a cut had happened, unlike the codebase's own `sanitize_text_for_display`, so a truncated entry was indistinguishable from a genuinely short one — worst on the partial transcript of a failed run. **Fixed (2026-08-22):** both formatters append `"... [truncated]"`. Covered by `test_over_long_content_is_truncated_visibly_rather_than_silently`.
- [x] [Review][Patch] **Generated runner lost task attribution on every agent turn** [team_maker/codegen/templates/crewai_runner.py.j2] — originally filed as "duplication, deferred"; re-examination showed it was a live correctness defect, not a cleanliness nit. `SimpleTranscriptRecorder` omitted the lazy `parent_event_id` walk that the real `TranscriptRecorder` performs, and read `event.task_name` directly — which crewai 1.14.6 documents (and `model_fields` confirms) is always `None` on `AgentLogsExecutionEvent`. Every `agent_message`/`agent_action` entry in a generated `run_example.py` transcript therefore came back as `task_name="unknown"`, the exact sentinel `test_transcript_conformance.py:166-167` guards against — violating AC 3's "matching in-process Runtime behavior". It was invisible because `tests/unit/test_codegen.py` only `compile()`s the rendered template; **no test ever executed the generated recorder**. **Fixed (2026-08-22):** see the Remediation section below.

### Remediation — generated transcript recorder (2026-08-22)

Closing the two items the review had parked. No deferred work remains for this story.

**New extension point.** `RuntimeEngine.extra_modules() -> dict[str, str]` (concrete,
returns `{}` by default, so `autogen`/`langgraph` are untouched). `PipelineRunner._build_manifest`
merges the result into the manifest and raises on a collision with a core artifact, so extra
modules follow the same write/validate path as everything else and nothing new touches disk
(honours the "only `ArtifactWriter.write()` touches disk" and "extend the manifest" invariants).

**`transcript.py` is now a generated artifact.** `CrewAIAdapter.extra_modules()` renders
`codegen/templates/_transcript_module.py.j2`, a faithful standalone port of
`adapters/runtime_crewai/transcript_capture.py` — including the `_remember`/`_walk`
attribution the inline version lacked. `run_example.py` shrank by ~280 lines and now does
`from transcript import TranscriptRecorder, print_transcript`. The duplication is inherent
(a generated package cannot import `team_maker`), so it is now *tested* rather than tolerated.

**The generated recorder is executed by tests for the first time.**
`tests/conformance/test_generated_transcript_module.py` subscribes it to crewai's
process-global event bus alongside the runtime's own recorder during **one real (offline)
crewai run**, then asserts the two produce byte-identical entries — sequence, kind,
agent_role, task_name, target_role, and content — across a sequential run, a hierarchical
run with a delegation, and a handler-cleanup check. Mutation-verified: reintroducing the
original defect (dropping the parent walk) fails the suite with
`task_name: 'unknown' != 'design'`, so the guard is not vacuous.

`tests/unit/cli/test_cli_run_transcript.py` gained a matching drift guard asserting the CLI
formatter and the generated one render identical output for the same entries.

## Dev Notes

### What this story is (and is not)
- **Is:** Hardening the transcript subsystem for API exposure
- **Is NOT:** Implementing streaming or database persistence

### Architecture constraints (binding)
- **AD-6 — CrewAI 1.14.6 behind the RuntimeEngine port.** Transcript capture must work with existing CrewAI version.
- **AD-13 — Batch results behind a streamable interface.** Partial transcripts must fit this pattern.

### Project conventions (must follow — from project-context.md)
- Start every module with `from __future__ import annotations`; full type hints; snake_case; ruff line-length 100.

## Dev Agent Record

### Implementation Plan

**Task 1: Return partial transcripts on failed runs**
- The `TranscriptRecorder` already preserves entries in its `_pending` list and the context manager's `__exit__` doesn't discard them, so entries are preserved across exceptions.
- The issue was in `crewai_execution_engine.py` where `transcript = recorder.entries()` was after the `with` block, so if `kickoff()` raised, it was never reached.
- Solution: Wrap the `with` block in a try/except. In the except block, retrieve `recorder.entries()` and return a `RunResult` with empty `final_output` and `task_results` but with the partial transcript.
- The `recorder` variable is assigned by the `with` statement's `__enter__` before the block executes, so it remains accessible even after an exception.

### Completion Notes

**Task 1 - Completed 2026-08-22**
- ✅ Modified `crewai_execution_engine.py` to catch exceptions from `crew.kickoff()` and return partial transcript in `RunResult`
- ✅ TranscriptRecorder already preserves entries (no code changes needed)
- ✅ Context manager already doesn't discard entries (no code changes needed)
- Modified: `team_maker/adapters/runtime_crewai/crewai_execution_engine.py`
  - Added try/except block around the TranscriptRecorder context manager
  - On exception, retrieves partial transcript and returns RunResult with empty outputs but partial transcript
  - Added import for TranscriptEntry for type hints

**Task 2 - Completed 2026-08-22**
- ✅ Implemented process-wide run lock using `threading.Lock()` in `executor.py`
- ✅ Added comprehensive documentation explaining why the lock is needed (crewai event bus is process-global singleton)
- ✅ Documented the three causes of corruption and why a lock is the only solution
- ✅ Wrapped the entire `run_team_package` function body in the lock context manager
- Modified: `team_maker/runtime/executor.py`
  - Added `import threading`
  - Added module-level `_run_lock = threading.Lock()`
  - Wrapped `run_team_package` body in `with _run_lock:`
  - Added detailed documentation in module docstring and function comments

**Task 3 - Completed 2026-08-22**
- ✅ Added `SimpleTranscriptRecorder` class to `crewai_runner.py.j2` template
- ✅ Implemented minimal transcript capture suitable for standalone use
- ✅ Added transcript capture to `main()` function with `with SimpleTranscriptRecorder(task_owners) as recorder:`
- ✅ Added transcript display on successful runs ("--- TRANSCRIPT ---" section)
- ✅ Added partial transcript display on failed runs ("--- PARTIAL TRANSCRIPT (run failed) ---" section)
- ✅ Matches in-process Runtime behavior by using the same event bus subscription approach
- Modified: `team_maker/codegen/templates/crewai_runner.py.j2`
  - Added imports: `json`, `threading`, `dataclass`, `TYPE_CHECKING`, `Any`, `Callable`, `Optional`
  - Added `SimpleTranscriptRecorder` class with handlers for all 6 event types
  - Added `TranscriptEntry` dataclass matching runtime/results.py
  - Updated `main()` to use transcript recorder
  - Added transcript display in success and failure paths

**Task 4 - Completed 2026-08-22**
- ✅ CLI already uses `sanitize_control_characters()` from `team_maker/utils/text_sanitizer.py` in `_print_transcript()` (line 717)
- ✅ API already uses `sanitize_control_characters()` in `run.py` when building TranscriptEntryView (line 177)
- ✅ Added `sanitize_control_characters()` function to `crewai_runner.py.j2` template for standalone use
- ✅ Applied sanitization to transcript display in template for both success and failure paths
- ✅ Preserves raw content in files (sanitization only applied when displaying to terminal or returning via API)
- Modified: `team_maker/codegen/templates/crewai_runner.py.j2`
  - Added `import re`
  - Added `sanitize_control_characters()` function with regex patterns for ANSI, OSC, and other control characters
  - Applied sanitization to all transcript content before display

**Task 5 - Completed 2026-08-22**
- ✅ Made human format unambiguous by changing header delimiter from `(` to `::`
- ✅ Added length bounds (10,000 chars per entry) in both CLI and template
- ✅ Structured serialization (JSON) is already available via TranscriptEntry dataclass
- Modified: `team_maker/cli.py`
  - Updated `_format_transcript()` to use `::` delimiter in headers
  - Added 10,000 character length cap on transcript content
- Modified: `team_maker/codegen/templates/crewai_runner.py.j2`
  - Updated transcript display to use `::` delimiter in headers
  - Added 10,000 character length cap on transcript content

**Task 6 - Completed 2026-08-22 (Already Implemented)**
- ✅ Delimiter format already uses unique, non-guessable UUID: `--- RUN_CONTEXT:<uuid>:GOAL ---`
- ✅ Validation already exists in `goal_is_injected()` which checks structural adjacency
- ✅ Format is securely documented in `run_context.py` module docstring
- No code changes required - already satisfies AC 6

## File List

- `team_maker/adapters/runtime_crewai/crewai_execution_engine.py` — Modified to return partial transcripts on failed runs (Task 1)
- `team_maker/runtime/executor.py` — Added process-wide run lock to prevent concurrent run corruption (Task 2)
- `team_maker/codegen/templates/crewai_runner.py.j2` — Added transcript capture, sanitization, and unambiguous formatting for standalone runs (Tasks 3, 4, 5)
- `team_maker/cli.py` — Transcript formatting: unambiguous content gutter, visible truncation marker (Task 5, review remediation)
- `team_maker/ports/runtime_engine.py` — New `extra_modules()` extension point (review remediation)
- `team_maker/adapters/runtime_engines/crewai_engine.py` — Emits `transcript.py` via `extra_modules()` (review remediation)
- `team_maker/pipeline/runner.py` — Merges adapter extra modules into the manifest, with collision guard (review remediation)
- `team_maker/codegen/templates/_transcript_module.py.j2` — NEW: generated `transcript.py`, a correct standalone port of `TranscriptRecorder` (review remediation)
- `tests/conformance/test_generated_transcript_module.py` — NEW: parity between the generated recorder and the runtime recorder over one real crewai run

## Change Log

- 2026-08-22: Completed implementation of Story 4.4 (Tasks 1-6)
- 2026-08-22: Code review — 7 patches applied, 2 decisions resolved
- 2026-08-22: Review remediation — closed both deferred items; generated `transcript.py` extracted as its own artifact with correct attribution, and covered by an executing parity test. No deferred work remains.

## References
- [deferred-work.md](../deferred-work.md) — Entries from Stories 1.7, 2.4
- [epics.md](../epics.md) — Epic 4: Deferred Work Consolidation
- [ARCHITECTURE-SPINE.md](../architecture/architecture-team_maker-2026-07-05/ARCHITECTURE-SPINE.md) — AD-6, AD-13
- [Story 1.7](../1-7-capture-run-transcript.md) — Original transcript capture implementation
- [Story 2.4](../2-4-team-workspace-chat-documents-run-results.md) — Workspace transcript display
