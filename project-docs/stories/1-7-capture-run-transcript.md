---
baseline_commit: 52779f4b9497bb31a1c282fb7e8daea38e81c585
---

# Story 1.7: Capture and return the full agent run transcript

Status: review

## Story

As a user,
I want to see everything the agents said and handed off to each other,
so that I can follow and trust how the result was produced instead of only seeing the final answer.

## Acceptance Criteria

1. **Given** a completed team run, **When** `run_team_package` returns, **Then** the returned `RunResult` carries an **ordered** transcript alongside the existing `final_output` and `task_results` — the existing two fields are unchanged in name, type and content. This **widens** the Story 1.5 result object; it does not introduce a second run path, a side channel, a log file, or an engine-owned buffer the caller reads afterwards. (FR-27, AD-13, `epics.md:294-296`)

2. **Given** any transcript entry, **When** it is inspected, **Then** it is attributed to **both a task and an agent**, carries an explicit **monotonic sequence number** (ordering is data, not list position), and carries a **kind discriminator** distinguishing at minimum an agent message, a delegation/handoff, and a task boundary. Every entry is independently meaningful — a consumer handed entry *N* alone, without entries 1..N-1, can render it. (FR-27, AD-13, `epics.md:289-290`; Story 2.4 needs this at `epics.md:342-344`)

3. **Given** a team whose agents pass work along the Task DAG, **When** it runs, **Then** the transcript records each agent's messages in execution order. **Given** a team with an `is_orchestrator` agent (hierarchical process), **When** the manager delegates, **Then** the delegation is recorded as a distinct entry naming the delegating agent, the delegate, and the returned answer. (FR-27, FR-9)

4. **Given** a run using a real API key, **When** the transcript is produced, printed, and written to a file, **Then** **no key or secret value appears anywhere** in it — not in an entry, not in a `repr()`, not in the written file. The transcript object never holds a `ResolvedCredential`, an `Agent`, a `Task`, or any live crewai object. (NFR3, AD-9, `epics.md:293`)

5. **Given** the `team-maker run` CLI with no new flags, **When** a run completes, **Then** the output is **unchanged from Story 1.5** — the same banner Panel, the same `Final result` Panel, the same `Per-task results` Table, and `--quiet` still suppresses all three. The transcript is strictly **opt-in**. (`epics.md:291`)

6. **Given** the CLI, **When** the user opts in, **Then** the transcript can be **shown** and **written to a file**; every dynamic field is Rich-escaped; a write failure exits `1` with a plain message and no traceback. (`epics.md:290`; CLI exit-code contract from Story 1.5 AC 6)

7. **Given** AD-13, **When** a future story adds per-turn streaming, **Then** it requires **no change to `ExecutionEngine.run`'s signature and no change to the transcript entry type** — only the delivery changes (accumulate-then-return → emit-as-you-go). The batch transcript must be exactly the accumulated sequence of the units that would later be streamed one at a time. A single blob, a pre-rendered string, or a list reconstructed post-hoc from `tasks_output` **fails this AC even if every other AC passes**. (AD-13, `epics.md:291-293`)

8. **Given** the engine-neutrality rule, **When** transcript capture is implemented, **Then** the transcript **type** lives in `team_maker/runtime/results.py` (crewai-free, guard-tested) and all crewai-specific capture lives **only** under `team_maker/adapters/runtime_crewai/`. `team_maker/ports/execution_engine.py` gains no crewai import and no `adapters/` import. (AD-6, AD-4)

9. **Given** the existing test suite, **When** this story lands, **Then** `tests/conformance/test_multi_provider_conformance.py` still passes **with its assertions unweakened**, the run path still writes nothing to `os.environ`, and the pre-run credential gate still runs before any engine work. (AD-7, AD-9; Story 1.6's gate)

10. **Given** this story's scope, **When** implementing it, **Then** the following are explicitly **out of scope**: any UI rendering (Story 2.4), the HTTP endpoint or its `include_transcript` param (Story 4.2), persisting transcripts to SQLite (Story 2.5 / AD-11), implementing actual streaming (v2), changes to the Factory (`pipeline/`, `generators/`, `validation/`, `artifacts/`, `codegen/`), and changes to the generated `crewai_runner.py.j2` template. (AD-1, AD-11; scope fence inherited from Stories 1.5/1.6)

## Tasks / Subtasks

- [x] **Task 0 — Spike the seam before writing a single assertion** (AC: 3, 7)
  - [x] This is not optional and it is not ceremony. Stories 1.5 and 1.6 **each** lost two rework rounds to an assumed CrewAI API, and 1.6's first spike made a real network call that came back `401` from Anthropic. Write a throwaway script **outside the repo tree** (system temp dir), run it, delete it.
  - [x] Reuse the proven offline interception from `tests/conformance/test_multi_provider_conformance.py` — walk the `BaseLLM` subclass tree, patch every class defining `call`, block `httpx.Client.send`/`AsyncClient.send`, opt out of telemetry. Do **not** invent a new interception approach.
  - [x] Confirm against *your* installed crewai: (a) `step_callback` never fires; (b) `emission_sequence` increases monotonically but sparsely over your subscribed subset; (c) delegation surfaces as a `ToolUsage*` pair with the delegate's `AgentExecution*` events hanging off it via `parent_event_id`.
  - [x] **⚠️ Delegation will not happen offline unless you also patch `supports_function_calling`.** Patching `BaseLLM.call` alone is not enough: the default executor takes the **native function-calling branch** (`experimental/agent_executor.py:1366-1405`), which never reaches the ReAct parser, so a stubbed response is swallowed as a final answer and **zero `ToolUsage*` events are emitted**. Measured: a hierarchical manager + two coworkers produced 1 LLM call, 8 events, **no delegation** — even when the stub returned well-formed `Action: Delegate work to coworker` text. Set `supports_function_calling() -> False` on every patched `BaseLLM` subclass *in addition to* patching `call`. The expected ladder once you do:
    ```
     5 ToolUsageStartedEvent      role='manager'   task='coordinate'  tool='Delegate work to coworker'
     6 AgentExecutionStartedEvent parent=ToolUsageStartedEvent
     8 AgentLogsExecutionEvent    role='architect' task=None
    10 ToolUsageFinishedEvent     role='manager'   task='coordinate'  output='done'
    ```
  - [x] Record what you observed in Debug Log References. If your observation contradicts Dev Notes, **your observation wins** — say so and adjust.

- [x] **Task 1 — The transcript contract** (AC: 1, 2, 7, 8)
  - [x] Extend `team_maker/runtime/results.py`. Add `TranscriptEntry` as a plain, dependency-free dataclass. Suggested shape — adjust from Task 0's findings, but every one of these fields is required by an AC:
    - `sequence: int` — monotonic, from crewai's `emission_sequence` (AC 2: ordering is data, not list position)
    - `kind: str` — discriminator. Define module-level constants and use them at every call site, never bare literals. The set AC 2 requires, at minimum: `ENTRY_TASK_STARTED`, `ENTRY_TASK_COMPLETED`, `ENTRY_AGENT_MESSAGE` (an `AgentFinish` turn), `ENTRY_AGENT_ACTION` (an `AgentAction` turn — a delegating turn emits both, in sequence), `ENTRY_DELEGATION`
    - `agent_role: str` — attribution (AC 2)
    - `task_name: str` — attribution (AC 2)
    - `content: str` — the message/output text
    - `target_role: str | None = None` — the delegate, for handoff/delegation entries (AC 3)
  - [x] Add **one** field to `RunResult`: `transcript: list[TranscriptEntry] = field(default_factory=list)`. It **must be last** and **must have a default** — `task_results` has no default, so a non-defaulted field after it is a `TypeError` at class-creation time.
  - [x] **Do not add any field to `TaskResult`.** `tests/unit/adapters/test_crewai_execution_engine.py:78` asserts dataclass *equality* against a hand-built `TaskResult`; any populated new field breaks it, and a defaulted-but-always-empty one is dead weight.
  - [x] Keep `RunResult` a plain non-frozen dataclass — `tests/unit/runtime/test_results.py:52-56` requires `TypeError` on unknown kwargs. Do not switch to Pydantic, `**kwargs`, or `extra="allow"`.
  - [x] Tests in `tests/unit/runtime/test_results.py`: field shape; `RunResult` still constructible with only the two Story-1.5 fields (backward compatibility); unknown-kwarg `TypeError` still raised; module stays import-free of crewai.

- [x] **Task 2 — Capture from the crewai event bus** (AC: 1, 2, 3, 8)
  - [x] New module `team_maker/adapters/runtime_crewai/transcript_capture.py`. This is the **only** place crewai transcript types may be touched. The whole `adapters/runtime_crewai/` directory is exempt from the crewai-import guard, so a new file here is automatically allowed.
  - [x] Subscribe to the **global event bus** — `from crewai.events import crewai_event_bus`. **Not `step_callback`** (see Dev Notes; it is dead in 1.14.6). Register handlers with `.on(EventClass)`.
  - [x] **Dispatch is exact-type.** Registering on `BaseEvent` catches nothing — you must enumerate concrete classes. At minimum: `TaskStartedEvent`, `TaskCompletedEvent`, `AgentExecutionStartedEvent`, `AgentExecutionCompletedEvent`, `AgentLogsExecutionEvent`, `ToolUsageStartedEvent`, `ToolUsageFinishedEvent`.
  - [x] **Project scalars inside the handler. Never retain the event object.** Read only `emission_sequence`, an agent role, a task name, and a content string. Never call `event.to_json()`; never touch `.agent`, `.task` or `.crew` beyond reading `.role`/`.name`. Apply this **unconditionally to every event class** — see the verified leak table in Dev Notes; the safe/unsafe split is per-event and per-emit-site, so there is no class you may treat as exempt. This is AC 4.
  - [x] **Attribution needs a parent-chain resolver — this is a real design decision, not a detail.** `AgentLogsExecutionEvent` (the per-turn event) has **no `task` and no `agent` attribute**, and its `task_name` is `None`, so neither a direct read nor the obvious fallback works. Maintain an `event_id -> (task_name, agent_role)` map populated from `Task*`, `AgentExecution*` and `ToolUsage*` events as they arrive, and resolve each per-turn entry by walking `parent_event_id`. Observed chains: a normal turn resolves `AgentLogsExecutionEvent -> AgentExecutionStartedEvent` (read `.task.name`, `.agent.role`); a delegated turn continues `AgentExecutionStartedEvent -> ToolUsageStartedEvent`, which carries a populated `task_name` **and** `agent_role`. Without this, every per-turn entry has `task_name=None` and silently fails AC 2.
  - [x] **Content extraction:** `formatted_answer` is a live `AgentAction`/`AgentFinish`. Take `.text` (present on both); fall back to `str(.output)`. Never store the object — a blind `str()` yields `"AgentFinish(thought='', output='done', text='…')"` as user-visible transcript content, and retaining it violates AC 4.
  - [x] **Do not use `crewai_event_bus.scoped_handlers()`.** It `off()`s every already-registered handler on entry (`event_bus.py:766-800`), including crewai's own console formatter and tracing listener — a side effect a library adapter must not impose on its host. Register and unregister your own handlers explicitly.
  - [x] **Sort by `emission_sequence` at the end.** Handlers run on a 10-worker thread pool, so arrival order is *not* emission order (observed `[…,7,9,8,10,…]`). Do not append-and-trust.
  - [x] **Always `off()` every handler in a `finally`.** The bus is a process-global singleton; a leaked handler accumulates entries from every later run in the process, which in a test suite means cross-test contamination.
  - [x] **Call `crewai_event_bus.flush()` after `kickoff()`** — `kickoff` flushes internally *before* emitting its final event, so the tail can still be in flight when it returns.
  - [x] **Map delegation carefully — the two `ToolUsage*` events disagree with each other.** Measured on one delegation:

    | Event | `tool_name` | `tool_args` |
    |---|---|---|
    | `ToolUsageStartedEvent` | `'Delegate work to coworker'` | JSON **`str`** |
    | `ToolUsageFinishedEvent` | `'delegate_work_to_coworker'` | **`dict`** |

    The emit sites differ: `tools/tool_usage.py:254` uses the raw tool name, `experimental/agent_executor.py:1808` sanitizes it. **Matching on the snake_case name alone gives you dead code no real-kickoff test can reach** — the exact "unfailable test" trap from Story 1.6. Normalize both sides: match on `sanitize_tool_name(event.tool_name)` (from `crewai.utilities.string_utils`, adapter-only so the import is allowed) against `{"delegate_work_to_coworker", "ask_question_to_coworker"}`, and `json.loads` `tool_args` when it is a `str` before reading `coworker`.
  - [x] Delegated turns carry a **synthetic** task name (crewai builds a throwaway `Task`). Resolve them to the real crew task through the parent chain above.
  - [x] Tests in a **new** `tests/unit/adapters/test_crewai_transcript_capture.py` — do not append to `test_crewai_execution_engine.py`, which is already 260 lines / 11 tests spanning credentials + topology + result mapping.
  - [x] **Know what the adapter unit tests can and cannot assert.** `_install_fake_kickoff` (`test_crewai_execution_engine.py:52-57`) monkeypatches `Crew.kickoff` wholesale, so no events are ever emitted and `result.transcript == []` in all 10 of those tests — by construction, not by bug. Adapter-level tests should assert only that the field exists and that handlers were unregistered. **Any assertion about transcript *content* requires a real `kickoff` and therefore belongs in `tests/conformance/`.** Putting the redaction test here would give a vacuous pass.

- [x] **Task 3 — Wire capture into the engine** (AC: 1, 9)
  - [x] `team_maker/adapters/runtime_crewai/crewai_execution_engine.py::run` — register handlers, `kickoff`, flush, unregister in `finally`, sort, pass `transcript=` into the existing `RunResult(...)` construction.
  - [x] **Accumulate into a list local to `run()`, captured by closure. Never on `self`.** The engine is currently stateless (`_build_crew`/`_build_llm` are `@staticmethod`); a reused instance holding transcript state would leak entries across runs.
  - [x] **Do not change `ExecutionEngine.run`'s signature.** `tests/unit/runtime/test_executor.py:34`'s `_FakeEngine.run(self, team, credentials, goal)` breaks on a new parameter, taking all four executor tests with it. Capture unconditionally in the engine; opt-in lives entirely in the CLI. Widen the return, never the parameters.
  - [x] Preserve every existing behavior: `Process` selection and manager exclusion, `topological_sort` order, the `context=` wiring, the task-output count-mismatch `RuntimeError`, `_build_llm` always passing `api_key` even when `None`, and the `zip`-derived `task_results`.
  - [x] `team_maker/ports/execution_engine.py` — **docstring only**, stating that the returned `RunResult` carries an ordered transcript. No signature change, no new import.

- [x] **Task 4 — Redaction, proven** (AC: 4)
  - [x] The leak is real and located: `AgentExecutionStartedEvent.agent.llm.api_key` and `TaskStartedEvent.task.agent.llm.api_key` are **plain strings**, and `BaseEvent.to_json()` serializes them. Projection (Task 2) is the defence; this task proves it.
  - [x] Test: run a team whose Key Config holds a sentinel value (e.g. `sk-ant-SENTINEL-DO-NOT-LEAK`) and assert the sentinel appears in **none** of: any `entry.content`, `repr(result.transcript)`, the CLI's rendered output, or the written transcript file.
  - [x] **Put the sentinel on an agent that actually produces transcript entries.** Story 1.6 shipped a leak test that could not fail because the secret sat on a provider that resolved cleanly and never reached the renderer.
  - [x] Guard the loop: `assert result.transcript` before iterating, or a zero-entry transcript passes the redaction test vacuously.

- [x] **Task 5 — CLI opt-in surface** (AC: 5, 6)
  - [x] `team_maker/cli.py` — add options after `--quiet` (line ~392). `-t` is free. Suggested: `--transcript/-t` (print) and `--transcript-out PATH` (write).
  - [x] **Do not add a parameter to `run_team_package`.** All 13 tests in `tests/unit/cli/test_cli_run.py` monkeypatch it with the exact signature `(package, goal, key_config, engine=None)`; a new kwarg `TypeError`s inside every one of them.
  - [x] New `_print_transcript(result)` helper beside `_print_run_result`. **Escape every dynamic field** — transcript content is raw LLM text and will contain brackets. Keep `from rich.markup import escape` a function-local import, matching every other command.
  - [x] Write failure → `sys.exit(1)` with a plain message, following `compose`'s `out.write_text` OSError handler. `run` never uses exit 2.
  - [x] Decide `--quiet` interaction deliberately and state it: precedent from `compose` is that a file deliverable is still written under `--quiet` while stdout is suppressed.
  - [x] Tests in a **new** `tests/unit/cli/test_cli_run_transcript.py` — `test_cli_run.py` is already 316 lines / 13 tests. Cover: default output byte-identical without the flag; flag prints; markup in transcript content survives escaping (feed real `[...]`, or the test guards nothing); write-to-file; OSError → exit 1; `--quiet` interaction.

- [x] **Task 6 — Conformance: prove it end to end, offline** (AC: 3, 7, 9)
  - [x] New `tests/conformance/test_transcript_conformance.py`. Do **not** append to `test_multi_provider_conformance.py` (460 lines, AD-7 gate, assertions declared unweakenable).
  - [x] The shared helpers (`_install_call_recorder`, `_block_all_network`, `_mixed_provider_package`, `_warm_up_models`) are module-private in the AD-7 file. Extract to `tests/support/crewai_interception.py` — behavior-preserving — and **re-run the AD-7 test to prove its assertions are unchanged**. Three things must move or be replicated with them, or the extraction breaks: the `pytest.importorskip("crewai")` guard at `test_multi_provider_conformance.py:56` (it gates every crewai import below it); the `LLMCall` dataclass (`:83-91`), which is the helpers' return element type; and `_NetworkEscaped` (`:146-153`), which is deliberately a `BaseException` so no `except Exception` retry layer can swallow it. Note also that `_install_call_recorder` constructs real `LLM(...)` objects as a warm-up side effect, permanently growing `BaseLLM.__subclasses__()` process-wide — global state that survives `monkeypatch` undo, so keep tests order-independent.
  - [x] Run a real `Crew.kickoff` offline for (a) a sequential 2-agent team and (b) a hierarchical team with an orchestrator, asserting: transcript non-empty; `sequence` **unique and strictly increasing after sort** (never contiguous); every entry has both `agent_role` and `task_name`; both agents appear; the hierarchical case contains a delegation entry with `target_role` set; the sentinel key appears nowhere.
  - [x] Remember the hierarchical case needs `supports_function_calling -> False` patched as well as `call` (Task 0), or it produces no delegation and the AC 3 assertion is untestable.
  - [x] **Interception caveat:** patching `BaseLLM.call` *suppresses* `LLMCallStartedEvent`/`LLMCallCompletedEvent`, since those are emitted from inside the real `call`. Use `AgentLogsExecutionEvent` (which does fire under interception) as the per-turn signal, or your assertions will be about events that never happen.
  - [x] This new file inherits the same `importorskip` hole already logged for the AD-7 gate (`deferred-work.md:93`) — a conformance test that silently skips is not a gate. Not this story's to fix; note it so it is a known second instance rather than a new surprise.

- [x] **Task 7 — Documentation and flags, not silent edits** (AC: 10)
  - [x] Record in Completion Notes, do **not** edit the planning artifacts (Story 1.4/1.5/1.6 precedent):
    - `FR-27` and `NFR3` **do not exist in the PRD** — they live only in `epics.md`. The spine's `binds:` list stops at FR-26.
    - `ARCHITECTURE-SPINE.md:225-226`'s "CrewAI version pin" Deferred entry is stale — resolved by Story 1.6.
    - `project-docs/project-context.md:24` ("`crewai` is NOT a dependency of this repo … Never `import crewai` in `team_maker/`") is now false; the narrowed rule is adapter-only. `:29` ("factory, not a runtime") remains stale — flagged for the third time.
  - [x] Add to `deferred-work.md`: partial transcripts on failed runs (PRD Open Q5 is still open; this story's AC says "When it completes"); transcript capture in the generated `crewai_runner.py.j2` (out of scope here, as in 1.5/1.6); and **concurrent-run isolation** — the event bus is a process-global singleton with a shared worker pool, so two simultaneous `run()` calls in one process would interleave into each other's transcript. v1 assumes one run at a time; Story 4.2's HTTP endpoint is exactly where that assumption breaks.
  - [x] **Do not add anything to `must_stay_clean` in `tests/unit/adapters/test_runtime_engine_port.py:148-157`.** `runtime/results.py` is already listed at `:152`, and the only new production module — `adapters/runtime_crewai/transcript_capture.py` — is crewai-**bearing**; adding it to that list fails the test. It is already covered by the directory exemption at `:134`. (This bullet exists because the obvious instinct is wrong.)
  - [x] Verify `pytest --collect-only -q | tail -1` before and after any test move; 1.6's move broke a cross-module import and only this check caught it.

## Dev Notes

### What this story is (and is not)

- **Is:** widening the Story 1.5 result object with an ordered, per-turn, attributed transcript, captured from CrewAI's event bus and translated into an engine-neutral type.
- **Is:** the last story in Epic 1. FR-27 is the **only** FR in Epic 1's coverage list not yet delivered; everything else is discharged by 1.1–1.6.
- **Is NOT** streaming. Three independent statements defer it to v2 (`prd.md:236`, `prd.md:395`, `ARCHITECTURE-SPINE.md:220`). This story makes streaming *possible later*; building a callback or generator API now is scope creep.
- **Is NOT** UI (Story 2.4) or API (Story 4.2). Deliver a data contract plus a CLI affordance.
- **Is NOT** a Factory or template change. `crewai_runner.py.j2` stays untouched for the third story running.

### ⚠️ The seam: use the event bus. `step_callback` is dead.

**This is the single most important fact in this story, and it contradicts what the CrewAI docs and most tutorials say.**

`Crew(step_callback=...)` and `Agent(step_callback=...)` **never fire** in crewai 1.14.6. Verified by two independent spikes: **0 invocations** across sequential and hierarchical runs. Stick to the measurable observations — after `kickoff`, `agent.agent_executor.step_callback` is `None` (the propagation did not happen), and pydantic emits `UserWarning: function callbacks cannot be serialized and will prevent checkpointing`. Do not go hunting through the executor state machine: the `_invoke_step_callback` call sites at `experimental/agent_executor.py:1403,1514` *are* on executed paths — the callback is simply never set. The default executor is `crewai.experimental.agent_executor.AgentExecutor`, not the `crewai.agents.crew_agent_executor.CrewAgentExecutor` the documentation describes.

Even if it fired it would be unusable here: `AgentAction`/`AgentFinish` (`crewai/agents/parser.py:25-43`) carry **no agent and no task reference**, so AC 2's dual attribution would be impossible under delegation.

`Crew(task_callback=...)` does work but is per-task only — a strict subset of `TaskCompletedEvent`. No reason to use both.

**Use `crewai.events.crewai_event_bus`.** It is what crewai's own console formatter and tracing listener are built on, it is the documented extension point, and it survives a minor bump far better than a callback that already silently rotted between two executor implementations *inside this very version*.

### Verified facts about the installed crewai 1.14.6 — do not re-derive

Independently corroborated in this repo's `.venv`: the bus exists (`CrewAIEventsBus`), `emission_sequence` is a field on `BaseEvent`, and `AgentExecutionStartedEvent`/`ToolUsageStartedEvent` carry `.agent`/`.task`.

- **Registration:** `from crewai.events import crewai_event_bus`; `.on(EventClass)` decorator, `.off(EventClass, handler)`, `.flush(timeout=30.0)`. Singleton at `crewai/events/event_bus.py:887`.
- **Exact-type dispatch** (`event_bus.py:541-551`): `type(event)` is the dict key. Subscribing to a base class catches nothing.
- **Handlers run off-thread** on a `ThreadPoolExecutor(max_workers=10)` (`event_bus.py:170-171, 571-574`). Arrival order ≠ emission order. `LLMStreamChunkEvent` is the sole exception, dispatched inline to preserve ordering — which is precisely why the bus is the right seam for a future streaming retrofit.
- **`emission_sequence`** is a per-kickoff counter assigned synchronously in the emitting thread before dispatch (`event_bus.py:479-511`), backed by an `itertools.count` in a `ContextVar`, reset per top-level `kickoff` (`crews/utils.py:278-290`). **Sort by it. Do not sort by `timestamp`** — sub-millisecond ties. **It is not contiguous over your subscribed subset** (observed `2,3,5,7,8,9,11,13`, because you subscribe to some classes and not others), and pre-kickoff events can duplicate `1` (the reset fires inside `kickoff`, after crew-construction events have already drawn numbers). Assert **strictly increasing after sort** — never contiguity, never a `range()` comparison.
- **Handler exceptions are swallowed and printed** (`event_bus.py:360-372`). A broken handler cannot fail loudly, so tests must assert on captured content with a non-emptiness guard.
- **`kickoff` flushes at `crew.py:1841`, before the final `CrewKickoffCompletedEvent`.** Flush again yourself after `kickoff()` returns.
- **Delegation is a tool call, not an event.** `AgentTools` (`tools/agent_tools/agent_tools.py:16-36`) injects `delegate_work_to_coworker` and `ask_question_to_coworker` onto `allow_delegation=True` agents and unconditionally onto the hierarchical manager. There is no `DelegationStartedEvent`.
- **`AgentExecutionStartedEvent.agent_role` and `task_name` are both `None`.** Read `event.agent.role` and `event.task.name` instead. A test asserting `agent_role` on those events fails.
- **`AgentLogsExecutionEvent` has neither an `agent` nor a `task` attribute** (`events/types/logging_events.py:19-27` — its fields are `agent_role`, `formatted_answer`, `verbose`, plus the `BaseEvent` envelope), and its `task_name` is always `None`. This is the designated per-turn event, so **attribution must come from the parent chain** — see Task 2.
- **`formatted_answer` is a live object**, typed `Any` with `arbitrary_types_allowed`: an `AgentAction(thought, tool, tool_input, text)` or an `AgentFinish(thought, output, text)`, where `AgentFinish.output` may itself be a `BaseModel` (`agents/parser.py:36-44`). Never store it; extract `.text`.
- **`TaskOutput.messages` already exists** (`tasks/task_output.py:46`) and the current adapter discards it — a complete per-task message list including the delegation round-trip, with no hook at all. This is the **fallback** seam if the bus is judged too internal, but it is per-task, cannot interleave, and cannot become per-turn streaming without a contract change, which is exactly why it is not the primary.

Carried forward from Stories 1.5/1.6 — still true, do not contradict:
- `crewai.LLM` is a **factory**, not a class; patching `crewai.LLM.call` intercepts nothing. Walk the `BaseLLM` subclass tree.
- `"Final Answer: done"` terminates the ReAct loop in one step.
- Omitting `api_key=` is not neutral — crewai reads the provider's env var.
- Ollama receives a placeholder `api_key="ollama"`; `base_url` is normalized with `/v1`.
- Telemetry must be opted out in offline tests or the network block trips spuriously.
- `litellm` is not installed; there is no fallback for unrecognized model strings.

### ⚠️ Secret-leak surface — verified, not theorized

Measured with a sentinel key, searching every event's `to_json()` recursively on a real hierarchical run:

```
TaskStartedEvent              leaks at  .task.agent.llm.api_key
TaskCompletedEvent            leaks at  .task.agent.llm.api_key
AgentExecutionStartedEvent    leaks at  .agent.llm.api_key  and  .task.agent.llm.api_key
AgentExecutionCompletedEvent  leaks at  .agent.llm.api_key  and  .task.agent.llm.api_key
AgentExecutionErrorEvent      same (by declaration)
ToolUsageStartedEvent         leaks at  .agent.llm.api_key
ToolUsageFinishedEvent        clean on the observed path (.agent is None)
```

**The leak/clean split is per-event AND per-emit-site — do not generalize it.** `ToolUsageStartedEvent` leaks while `ToolUsageFinishedEvent` does not, because `tools/tool_usage.py:254` puts `"agent": self.agent` in the Started payload while the Finished path leaves it `None`. The `from_agent`/`from_task` nulling in `LLMEventBase.__init__` is real but does **not** cover the separate `agent` field. Since `ToolUsageStartedEvent` is the event you must inspect most closely (for `tool_args`), this is exactly where relaxed projection discipline would bite.

`api_key` on the completion object is a **plain `str`**, not a `SecretStr` — pydantic gives you no automatic redaction anywhere. **Therefore: project unconditionally, on every event class, with no "this one is safe" exceptions.**

Two further surfaces: `LLMCallStartedEvent.messages`, `TaskOutput.messages` and `AgentExecutionStartedEvent.task_prompt` carry **full prompt text** — no provider credential, but a secret in a user's goal or backstory lands verbatim. And provider SDK exception text can embed credential fragments; `deferred-work.md:45` already notes there is no scrubbing convention in this codebase, and **this story is where a transcript becomes a persisted artifact rather than a console print**.

**Defence:** project scalars out of each event inside the handler and retain nothing else.

### ⚠️ The AC says "RuntimeEngine port". That is the wrong port name.

There are two ports and they must never merge:

- `team_maker/ports/execution_engine.py` — `ExecutionEngine.run(team, credentials, goal) -> RunResult`. **This is the run path. Widen this one.**
- `team_maker/ports/runtime_engine.py` — `RuntimeEngine.render_runner(...) -> str`. Codegen-only, renders `run_example.py` text at build time. Never executes anything. **Touching it is a Factory change (AD-1) and implements nothing.**

`epics.md:288`'s "RuntimeEngine port" is the spine's generic seam name from AD-6, not the Python symbol. The `execution_engine.py` docstring itself warns: *"The two must never collide or merge."*

### AD-13 — what "batch behind a streamable interface" actually requires

Verbatim, `ARCHITECTURE-SPINE.md:150-154`:

> **AD-13 — Results are batch behind a streamable interface**
> **Rule:** v1 returns final + per-task outputs in batch through a results interface shaped to later stream; the UI reads run progress via that interface (v1: on-completion; v2: incremental).

Decomposed into what you must and must not do:

1. **One interface, two delivery modes.** The v2 change is *delivery*, never *type*.
2. **Each entry independently meaningful** — hence per-entry sequence, task, agent, kind.
3. **Ordering is data, not list position** — streaming can arrive out of order.
4. **The same object serves completed transcript and live progress**, so an entry must be valid before `final_output` exists. Corollary: the transcript must **not** be derived from `task_results` after the run.
5. **No contract change on retrofit** — additive only.

**The specific way this gets built wrong:** capturing crewai's output into a formatted string or `list[str]` and calling it the transcript. It satisfies every *visible* AC — ordered, opt-in, no secrets, CLI prints it — and silently forecloses AD-13, because there is no per-turn unit to stream and no per-entry attribution for Story 2.4. **The second way:** synthesizing it from `output.tasks_output` after `kickoff()` returns — structurally unstreamable, and it cannot capture intra-task turns or delegations at all.

### Downstream consumers — the shape they force

- **Story 2.4** (`epics.md:342-344`): *"the full agent transcript for that run (Story 1.7) — every agent message and handoff in order, attributed to agent and task."* The UI groups by task row and renders "message" vs "handoff" differently, so it must not be asked to regex `content` to tell them apart. It crosses the API boundary first, so entries must be plain primitives, JSON-serializable without loss.
- **Story 4.2** (`epics.md:412-420`): the transcript is *"available on request rather than always inlined."* So it must be **independently omittable** — a distinct field, not interleaved into `task_results` or concatenated into `final_output`. Omitting it is a projection, not a different run.
- **UX docs say nothing about a transcript.** A grep for `transcript|handoff|activity|agent message` across `ux-designs/` returns zero hits — those docs predate FR-27 by a month. **Do not invent UX requirements from them.** What they *do* constrain: task rows show agent + model + status (`EXPERIENCE.md:75`), each row expandable to its output (`:90`), batch on completion in v1 (`:89`), and never hide a failure silently (`:103`).

### Previous story intelligence — the mistakes this codebase actually makes

Story 1.6's review found five tests that could not fail. The three that bite *this* story directly:

1. **A test guarding an escape/sanitize call must feed input containing the hostile token.** 1.6's Rich-markup test had no brackets in it and passed with `escape()` deleted. Your transcript-escaping test must feed real `[...]`.
2. **A secret-absence test must put the secret on the path that actually renders.** 1.6's put it on a provider that resolved cleanly, so the renderer never saw it. Your sentinel must sit on an agent that actually produces entries.
3. **Every assertion-in-a-loop needs a non-emptiness guard first.** `for entry in result.transcript:` over an empty transcript is a vacuous pass — and given the adapter tests fake `kickoff`, an empty transcript is the *default* state in most of the suite.

Also from that review, and directly applicable: **a docstring claim is a testable assertion** — 1.6 shipped a dead helper while its docstring advertised the behavior it would have provided.

Other recurring lessons:
- **Verify the real API before writing assertions** — two stories, two rework rounds, one real 401. Hence Task 0.
- **Collect all failures; never short-circuit on the first.** Four separate instances across 1.5–1.6 (`zip` truncation, first-orchestrator-wins, first-missing-provider, duplicate roles collapsing).
- **Rich markup has bitten three times.** Escape every dynamic field.
- **Self-reported evidence must be measured.** 1.6's Change Log claimed 35 tests/332 passed; actual was 36/333/340 collected. Paste the real `pytest` tail line.
- **Declare every deviation from the story text** — and check the rationale. 1.6 declared two, the review found two more undeclared plus one whose stated reason was factually false.
- **Structural defects the review keeps finding:** ports importing adapters; secrets in repr-able dataclasses; `assert` as production control flow (stripped under `-O`); `frozen=True` with a `list` field (advertised hashable, raises on `hash()` — use `tuple`); exceptions that can't round-trip their own `args`; `Optional[str]` interpolated unguarded into user text.

### Existing code to reuse — read before writing

- `team_maker/runtime/results.py` — 27 lines, the whole contract. Docstring already cites AD-13.
- `team_maker/adapters/runtime_crewai/crewai_execution_engine.py` — 138 lines; `run()` builds agents, topo-sorts, wires `context`, kickoffs, length-checks, maps results. Wire capture around `kickoff`.
- `tests/conformance/test_multi_provider_conformance.py` — the proven offline interception. Reuse; do not reinvent.
- `tests/support/team_factories.py` — shared `AgentSpec`/`TaskSpec`/`GeneratedTeam` builders. Extracting these was 1.6's own fix for copy-paste; use them.
- `team_maker/cli.py:587-608` — `_print_run_result`, the escaping pattern to mirror.

### Architecture constraints (binding)

- **AD-13** — batch behind a streamable interface. [`ARCHITECTURE-SPINE.md:150-154`]
- **AD-6** — CrewAI behind a port; core/runtime depends only on the port. [`:98-102`]
- **AD-9 / NFR3** — keys never logged, never in run output. [`:121-126`; `epics.md:73`]
- **AD-4** — dependency direction; the transcript type lives with the results contract, not in the adapter. [`:67-71`]
- **AD-5** — the Runtime executes only. Do **not** set `Crew(planning=True)`, switch a sequential team to hierarchical, or add agents just to make delegations appear. [`:90-96`]
- **AD-1** — the Factory stays untouched. [`:47-52`]
- **AD-11 / AD-12** — persistence is Epic 2; the transcript is per-run, not memory. [`:135-148`]

### Project conventions (must follow)

- `from __future__ import annotations` first line; full type hints; built-in generics; ruff line-length 100, rules `E,F,I,N,W`.
- **Environment:** activate `./.venv` (Python 3.13.13) before `pytest`/`ruff`/`make`. System Python cannot host modern crewai.
- **Lint only what you touch** — a repo-wide `ruff check team_maker` reports ~9 pre-existing findings in untouched files. Leave the drift.
- Domain layer stays dependency-free plain dataclasses; Pydantic only in `schema/`.
- **Never branch on provider name.** 1.6 retired the last one; the run path now has zero. Do not add one back.
- `team_maker/` must never `import crewai` at module scope outside `adapters/runtime_crewai/`.
- Preserve the deliberate lazy, function-body import of `CrewAIExecutionEngine` in `runtime/executor.py` — it keeps crewai genuinely optional for `create`/`compose`/`keys status`.
- Write tests task-by-task alongside the code, red before green — not batched at the end.
- Per CLAUDE.md: label mocks/monkeypatches explicitly; never report a live-variant test as evidence unless it actually ran.

### Git intelligence

`52779f4` docs(story-1.6) · `d6e1fae` feat(story-1.6) · `0f1addf` docs(epics) · `e4508c5` docs(story-1.5): accept + merge to epic_1 · `fea9f62` feat(story-1.5).

Rhythm: one `feat(story-N)` for code+tests, one `docs(story-N)` for the story file and deferred-work, then `docs(story-N): accept story, merge to epic_N` and a fast-forward into `epic_1` (history is linear — no merge commits). Commit bodies are long-form prose explaining *why*, ending with `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`.

Branch `story_1_7` from `epic_1` at `52779f4`. There is **no `sprint-status.yaml`** in this repo — status is tracked inline in this file's `Status:` field.

### Project Structure Notes

- **New:** `team_maker/adapters/runtime_crewai/transcript_capture.py`, `tests/unit/adapters/test_crewai_transcript_capture.py`, `tests/unit/cli/test_cli_run_transcript.py`, `tests/conformance/test_transcript_conformance.py`, `tests/support/crewai_interception.py` (extracted).
- **Modified:** `team_maker/runtime/results.py` (`TranscriptEntry` + one defaulted `RunResult` field), `crewai_execution_engine.py` (wire capture), `ports/execution_engine.py` (docstring only), `cli.py` (two opt-in options + `_print_transcript`), `tests/unit/runtime/test_results.py`, `tests/unit/adapters/test_runtime_engine_port.py` (name any new crewai-free module), `deferred-work.md`.
- **Untouched:** `pipeline/`, `generators/`, `validation/`, `artifacts/`, `templates/`, `codegen/`, `schema/`, `composer/`, `ports/runtime_engine.py`, `adapters/runtime_engines/`, `runtime/{loader,ordering,preflight}.py`.
- `tests/unit/` root still holds ~16 flat factory/schema/composer files. Pre-existing, not this story's scope.

### References

- [Source: project-docs/epics.md:282-296] — Story 1.7 statement + AC; [:40-41] FR-27; [:73] NFR3; [:108,133] Epic 1 FR coverage; [:342-344] Story 2.4; [:412-420] Story 4.2
- [Source: project-docs/architecture/architecture-team_maker-2026-07-05/ARCHITECTURE-SPINE.md:150-154] AD-13; [:98-102] AD-6; [:121-126] AD-9; [:67-71] AD-4; [:90-96] AD-5; [:47-52] AD-1; [:220] streaming deferred; [:225-226] stale pin entry
- [Source: project-docs/prds/prd-team_maker-2026-07-05/prd.md:218-222] FR-9; [:236,395] batch-only v1; [:245-250] FR-12; [:457-460] Open Q4/Q5
- [Source: project-docs/stories/1-5-run-team-return-results.md] — the result contract this widens
- [Source: project-docs/stories/1-6-multi-provider-routing-conformance.md] — review findings; the five unfailable tests; verified crewai facts
- [Source: project-docs/stories/deferred-work.md:45,70,82-97] — scrubbing convention gap; template defects; open 1.6 defers
- [Source: project-docs/ux-designs/ux-team_maker-2026-07-05/EXPERIENCE.md:74-75,89-91,103-104,113-114]
- [Source: .venv crewai 1.14.6 — events/event_bus.py:170-171,236-271,314-345,360-372,479-511,541-551,568-574,669-704,887; events/base_events.py:13-87; events/types/{agent,task,llm,tool_usage,logging,crew}_events.py; tasks/task_output.py:46; agents/parser.py:25-43; tools/agent_tools/agent_tools.py:16-36; crew.py:269-276,1841,2037-2041; crews/utils.py:100-108,278-290] — verified by spike, not assumed
- [Source: project-docs/project-context.md] — conventions; lines 24 and 29 flagged stale
- [Source: CLAUDE.md] — test organization and test-transparency rules

### Open questions for the PM (not blocking implementation)

1. **FR-27 and NFR3 are not in the PRD.** Both exist only in `epics.md` (added by `0f1addf`); `prd.md` ends at FR-26 and has no NFR section at all, and the spine's `binds:` list stops at FR-26. Sharper still: **AD-13's own `Binds:` names FR-11 only** (`ARCHITECTURE-SPINE.md:151`) — nothing in the spine binds FR-27, yet this entire story hangs off AD-13. `epics.md` is the sole binding source. Should the PRD and spine be backfilled?
2. **PRD Open Q5 — partial results on a failed run — is still open** (`prd.md:457-460`), and `EXPERIENCE.md:91` explicitly marks partial-results behavior as deferred to it. This story's AC says "**When** it completes", so partial transcripts on failure are out of scope by omission. Confirm that is intended rather than an oversight; it is a natural follow-up.
3. **Entry granularity.** The event bus can yield per-LLM-call, per-agent-turn, or per-task entries. This story specifies per-turn (`AgentLogsExecutionEvent`) plus task and delegation boundaries. If Story 2.4's UI wants something coarser or finer, saying so now is cheaper than reshaping the contract later.

### Review Findings

_Adversarial code review, 2026-08-02. Three parallel layers (Blind Hunter — diff only; Edge Case Hunter — diff + project + live runs; Acceptance Auditor — diff + spec). 47 raw findings → 33 after dedup; 2 dismissed. **Caveat on independence: the same model implemented and reviewed this story.** The Blind Hunter was given the diff and nothing else to compensate, and both other layers verified claims by running code rather than reading the Dev Agent Record._

_The Auditor independently measured and **confirmed every self-reported number** (34 new tests, 376 passed / 383 collected, ruff clean on all touched files, the real-CLI sequences `[2,5,7,8,11,13]`, zero sentinel occurrences), and mechanically verified the AD-7 claim: the only removed assertion is the one that moved verbatim with its helper, and the `^def test`-to-EOF region is byte-identical to HEAD. All 10 ACs are MET or PARTIAL — but the review found **four tests that cannot fail**, which is the same defect class this story's own Dev Notes warned about and that the Story 1.6 review found five of._

**Patches — source**

- [x] [Review][Patch] **The `"unknown"` sentinel is written into the attribution map and poisons every descendant** [team_maker/adapters/runtime_crewai/transcript_capture.py:753-758,815-821] — `_resolve` substitutes `_UNKNOWN_TASK`/`_UNKNOWN_AGENT`, and the handlers then `_remember` those placeholders. `"unknown"` is truthy, so a descendant's `parent_task or <own fallback>` short-circuits on the placeholder and never consults its own perfectly good `.task.name`, nor the grandparent that knew the answer. **Reproduced deterministically, no threads:** handling `exec1` before `task1` yields `map={'exec1': ('unknown','architect'), 'task1': ('design','architect')}` and an entry with `task_name='unknown'` — while the grandparent held `'design'`. One missed link silently corrupts an entire branch. Fix: never store a sentinel; store `None` and resolve through a real multi-level walk.
- [x] [Review][Patch] **Attribution depends on handler ordering that the bus does not guarantee** [transcript_capture.py:746-751] — handlers run on a 10-worker pool and `emit` returns without awaiting, so a child's handler can run before its parent's `_remember`. The lock makes map access atomic but does nothing about ordering. **Edge Hunter reproduced it** by delaying parent handlers 600 ms (three entries came back `task_name='unknown'`), and measured the natural margin on the delegation link at **2.7 ms** — fine on an idle box, not fine under CI or `pytest-xdist`. Fix: resolve attribution lazily in `entries()` (after all handlers have run and flushed) rather than eagerly inside each handler, so a late parent still resolves.
- [x] [Review][Patch] **Transcript and `task_results` disagree on `agent_role` for the same task in hierarchical crews** [transcript_capture.py:790,806] — `_role_of(task.agent)` reads the manager CrewAI rebinds onto the task, while `TaskResult.agent_role` is the declared owner. Measured: `transcript` says `('design','task_started','coordinator')` where `task_results` says `('design','architect')`. **This affects every Factory-built team**: `templates/software_delivery/template.py:129,269` forces `is_orchestrator=True` on `coordinator` and discards the request's flag, so the hierarchical branch is the normal path, not an edge case. This is the same correlation defect the `name=` fix addressed, one field over — and Story 2.4 is specified to render exactly this attribution. Fix: attribute task-boundary entries to the declared owner, or carry both and say which is which.
- [x] [Review][Patch] **An exception partway through `_subscribe` leaks handlers onto the global bus permanently** [transcript_capture.py:700-702,719-731] — Python does not call `__exit__` when `__enter__` raises. If `crewai_event_bus.on()` fails on the 4th of 7 registrations, three handlers stay on the process-global singleton for the life of the process and `_registered` is never drained. This is precisely the failure the context-manager shape is documented as preventing. Fix: `try/except` around the registration loop that unwinds what was registered.
- [x] [Review][Patch] **`flush()` raising in `__exit__` masks the real kickoff exception** [transcript_capture.py:704-710] — if the body raised (an auth error the user needs) and `flush()` then raises while draining a handler, the flush error is what propagates and the original is demoted to `__context__`, invisible to a CLI that prints `str(exc)`. `_unsubscribe` is likewise unguarded: an `off()` that raises on the first pop strands the remaining six.
- [x] [Review][Patch] **`_answer_text`'s fallback stringifies an arbitrary pydantic model** [transcript_capture.py:664-677] — the docstring itself notes `AgentFinish.output` may be a `BaseModel`, then calls `str()` on it, and `BaseModel.__str__` renders every field. Edge Hunter confirmed `str(model)` → `"secret='sk-LEAK'"`. Latent in v1 (the engine never sets `output_pydantic`) but it contradicts the module's "projects scalars unconditionally" guarantee, and the unit test only ever passes a plain string. Fix: only accept `str`; otherwise a bounded, type-name-only representation.
- [x] [Review][Patch] **`_format_transcript` raises an uncaught `TypeError` when `transcript` is `None`** [team_maker/cli.py:646-658 via :484] — `RunResult` has no validation and any `ExecutionEngine` may return `transcript=None`. The `except OSError` does not catch it and it sits outside the run's `try`, so the user gets a raw traceback. `_print_transcript` guards the identical state — the asymmetry is the tell. Confirmed.
- [x] [Review][Patch] **`--transcript-out` writes a silent zero-byte file and reports success** [cli.py:481-491] — an empty transcript produces a 0-byte file plus `Transcript written to …` and exit 0, while the console path explicitly says "No transcript was captured". Confirmed: `exit 0 | size 0`.
- [x] [Review][Patch] **The transcript write catches only `OSError`** [cli.py:485] — `write_text(..., encoding="utf-8")` raises `UnicodeEncodeError` (a `ValueError`) on lone surrogates, which model output can contain. That path produces the traceback the AC forbids, and the guard test only injects `OSError` so it cannot expose it.
- [x] [Review][Patch] **A delegation whose args don't parse still emits an entry naming nobody** [transcript_capture.py:651-661,849-864] — if CrewAI renames `coworker` or emits truncated JSON, `_as_args_dict` returns `{}` and an `ENTRY_DELEGATION` is emitted with `content=""` and `target_role=None`. FR-27's whole point is that a delegation names both agents; a plausible-but-wrong "handoff to nobody" is worse than omission. Fix: skip the entry (or mark it degraded) when the delegate cannot be identified.
- [x] [Review][Patch] **Non-string delegation args are stringified verbatim** [transcript_capture.py:309-318,326-335] — `{"coworker": ["architect"]}` yields `target_role="['architect']"`, which no consumer can match against an agent role. Confirmed by direct call.
- [x] [Review][Patch] **`_on_agent_completed` is dead code** [transcript_capture.py:823-827] — it emits no entry and writes a map entry nothing reads (`AgentExecutionCompletedEvent` is terminal, nothing is parented to it). Deleting it and its subscription changes no test and no transcript, while costing one of seven global-bus registrations and widening the partial-registration surface.
- [x] [Review][Patch] **The module docstring references a `_HANDLED` collection that does not exist** [transcript_capture.py:556 vs :720] — the handled-event set is an unnamed local list inside `_subscribe`. A maintainer following the docstring finds nothing. Either name the constant or fix the prose.
- [x] [Review][Patch] **An empty or duplicated `TaskSpec.name` re-triggers the exact description-fallback the `name=` fix was added to prevent** [crewai_execution_engine.py:53-67] — `name: ""` makes CrewAI fall back to the description again (`task_name='do '` vs `TaskResult.name=''`), and duplicate names collapse `crewai_tasks_by_name`, silently breaking `context=` wiring for dependents. `preflight.py:109` already guards the duplicate *agent role* case for exactly this reason; the task-name analogue is now load-bearing because `name` is the transcript's join key. Confirmed with a hand-built `GeneratedTeam`.

**Patches — tests (the four that cannot fail are first)**

- [x] [Review][Patch] **`test_handlers_are_removed_so_a_second_run_is_not_contaminated` cannot detect the leak it is named for** [tests/conformance/test_transcript_conformance.py:1272-1292] — the engine constructs a **fresh** `TranscriptRecorder` per run, so leaked handlers from run 1 append to run 1's dead object; run 2 reads its own recorder and is unaffected. **Delete the entire `_unsubscribe` body and this test still passes.** The symptom it cites only occurs with a reused recorder, which production never does. Fix: assert against the bus itself (handler count before/after), not against run-to-run entry counts.
- [x] [Review][Patch] **`test_the_recorder_unsubscribes_when_its_context_exits` asserts on the recorder's own bookkeeping, never on the bus** [tests/unit/adapters/test_crewai_transcript_capture.py:1577-1595] — `_unsubscribe` is `while self._registered: pop()`, so the list empties itself regardless of whether `off()` did anything. Stub `crewai_event_bus.off` to a no-op and both tests still pass. Combined with the finding above, **nothing in this story verifies handlers actually leave the global bus** — the single most-documented risk in the module is untested.
- [x] [Review][Patch] **`assert sequences == sorted(sequences)` is true by construction** [test_transcript_conformance.py:1170] — `entries()` returns `sorted(...)`. The assertion can never fail. Only the adjacent uniqueness check carries information.
- [x] [Review][Patch] **`assert entry.agent_role` / `assert entry.task_name` pass on the `"unknown"` sentinel** [test_transcript_conformance.py:1173-1176] — a run in which *every* entry was mis-attributed passes, with the message "has no agent attribution" never firing. This is the assertion defending AC 2. Fix: `assert entry.agent_role != "unknown"`.
- [x] [Review][Patch] **The conformance `orchestrator` parameter is dead — the "sequential" case is hierarchical** [test_transcript_conformance.py:1121-1136] — `templates/software_delivery/template.py:269` discards `role.is_orchestrator` and `:129` hardcodes `coordinator → True`. **Verified: `_package(orchestrator=False)` and `_package(orchestrator=True)` both produce `[('coordinator', True), ('architect', False)]`.** Five of six transcript conformance tests believe they exercise `Process.sequential`; none do, so that branch of `_build_crew` has zero real-kickoff transcript coverage. The docstring claiming otherwise is false. Fix: build the sequential fixture from roles the template does not force, and assert the process actually selected.
- [x] [Review][Patch] **The secret test never reaches the `ToolUsage` emit site, nor the CLI console/file** [test_transcript_conformance.py:1252-1269] — it runs `orchestrator=False`, so `_on_tool_started`/`_on_tool_finished` never execute, and `ToolUsageStartedEvent` is the one emit site the module docstring lists as a *measured* leak path. Task 4 explicitly names "the CLI's rendered output, or the written transcript file"; neither is asserted anywhere (the CLI tests use a hand-built `RunResult` containing no secret at all). Behaviour verified correct by hand, but the guarantee is unlatched.
- [x] [Review][Patch] **AC 3's DAG-ordering clause is untested** [test_transcript_conformance.py:1143-1145] — every transcript test uses a single-task package, so "records each agent's messages in execution order" across a multi-task DAG rests on no assertion. Verified manually (2-task run interleaved correctly); needs a test.
- [x] [Review][Patch] **The CLI write-failure test's "no traceback" assertion cannot fail** [tests/unit/cli/test_cli_run_transcript.py:1747-1768] — `CliRunner` captures an unhandled exception into `result.exception`, sets `exit_code=1`, and writes no traceback to `result.output`. Both `exit_code == 1` and `"Traceback" not in output` hold whether or not the handler exists. Only the message assertion has teeth.
- [x] [Review][Patch] **No conformance assertion covers `ENTRY_AGENT_ACTION`** [test_transcript_conformance.py] — that mapping is exercised only by hand-built stubs, so a wrong `formatted_answer.tool` attribute name would go unnoticed in a real run.
- [x] [Review][Patch] **AC 5's "byte-identical" is checked by substring, not comparison** [test_cli_run_transcript.py:1657-1669] — verified structurally instead (the diff leaves `_print_run_result` untouched and appends only flag-gated blocks), so AC 5 holds; the test is simply weaker than the task text. Capture the no-flag output and compare it directly.

**Deferred**

- [x] [Review][Defer] Concurrent runs in one process corrupt each other's transcripts — already logged, but the deferred entry **understates it**: Edge Hunter reproduced duplicated entries, a *lost* entry, and `emission_sequence` collision (the counter is ContextVar-scoped and restarts at 1 per run), plus `flush()` blocking across runs. Entry updated.
- [x] [Review][Defer] The transcript is discarded when `kickoff` raises [crewai_execution_engine.py:75-77] — `recorder.entries()` sits outside the `with`, so a mid-run failure loses the forensics and the CLI writes no file. Already logged as "partial transcripts on failed runs"; AC scope is "when it completes".
- [x] [Review][Defer] ANSI/OSC escape sequences in entry content reach the terminal verbatim — `rich.markup.escape` neutralizes `[` only, not `ESC`. Confirmed.
- [x] [Review][Defer] Six deep crewai internal import paths (`crewai.events.types.*`, `crewai.utilities.string_utils`) are now load-bearing for running a team at all — the engine imports the capture module at module scope, so a moved symbol turns an observability regression into total loss of `run`.
- [x] [Review][Defer] A renamed/removed `emission_sequence` would silently discard the whole transcript [transcript_capture.py:770-772] — `getattr(..., None)` cannot distinguish "no sequence" from "attribute gone", and the CLI then reassuringly reports "No transcript was captured".
- [x] [Review][Defer] `_format_transcript`'s line format is ambiguous — an LLM quoting a prior transcript produces a content line indistinguishable from a header, and there is no length cap on unbounded capture.
- [x] [Review][Defer] `TranscriptEntry` carries no run identity, which a streaming/HTTP consumer needs — and adding it later is "a change to the entry type", which AC 7 forbids. Worth resolving before Story 4.2 rather than after.
- [x] [Review][Defer] Widening `RunResult` changes generated `__eq__`/`__repr__`/`asdict` for existing consumers — two results equal before may now differ, and `repr()` dumps the whole conversation into any log or assertion message.

**Review patches applied — 2026-08-02**

All applied. Verified: **393 passed, 7 pre-existing live-API skips, 0 failures, 400 collected** (up from 376/383 — the fixes added 17 tests). `ruff` clean on every touched file. The AD-7 gate re-run green, and its assertions diffed against HEAD again: the *only* difference remains the one assertion that moved verbatim into `tests/support/crewai_interception.py:146`. Re-verified in the real CLI: a two-task sequential run printed and wrote a correctly ordered, correctly attributed transcript, with zero occurrences of the API key in console or file.

The two structural changes worth calling out:

- **Attribution is now resolved lazily in `entries()`, not eagerly in each handler.** Handlers record what they know and a `_Pending` row; the parent chain is walked once, after every handler has run and the bus has flushed. That removes the ordering race outright rather than narrowing it — a parent whose handler ran late still resolves. Two supporting changes make the walk trustworthy: sentinels are never stored in the map (only `None`), so a placeholder can no longer short-circuit a descendant's lookup; and the walk is genuinely multi-level with a visited-set and a depth cap, so it survives an unsubscribed or unknown link instead of stopping there.
- **Task-boundary entries are attributed to the declared owner.** The engine passes `{task_name: agent_role}` into the recorder, so a hierarchical crew no longer reports `coordinator` on a task that `task_results` says belongs to `architect`. There is now a conformance test asserting the two halves agree, on a fixture verified to actually *be* hierarchical.

Also: `_on_agent_completed` deleted (it wrote a map entry nothing read); `_subscribe` unwinds a partial registration; `__exit__` no longer lets a `flush()` failure mask the caller's exception; `_answer_text` refuses to stringify a non-string, so a structured output cannot dump its fields into `content`; a delegation whose args do not name a coworker is skipped rather than emitted as a handoff to nobody; and `InvalidPackageError` now covers blank/duplicate task names alongside duplicate agent roles, since task name became a join key.

On the tests, the four that could not fail were replaced with ones that can: handler removal is asserted **against the bus's own handler count** rather than the recorder's self-emptying list; `sorted(...)` tautology replaced with uniqueness plus strict increase; `assert entry.agent_role` replaced with `!= "unknown"`; and the write-failure test now asserts the exception is a `SystemExit` rather than the original error, which is what actually distinguishes handled from unhandled under `CliRunner`. The conformance fixture's dead `orchestrator` parameter is fixed and guarded by `_assert_topology`, so the sequential path is finally covered.

**Dismissed (2, not carried forward)**

- "Two undeclared deviations" (a recorder object rather than a closure; two CLI helpers rather than one) — both are strictly better than the task text and materially so; informational only.
- A delegation entry preceding the `agent_action` that caused it — faithful to `emission_sequence`, which is the contract. Worth a note for Story 2.4's renderer, not a defect.

## Dev Agent Record

### Agent Model Used

Claude Opus 5 (claude-opus-5[1m]), via the `bmad-dev-story` workflow.

### Debug Log References

- **Task 0's spike earned its place twice over — it corrected the story, and my first attempt at it was itself wrong.**
  1. Spike v1 concluded nothing about delegation because my stub always returned `"Final Answer: done"` — no agent ever *asked* to delegate. Zero `ToolUsage*` events, but for my reason, not CrewAI's. Caught before it became a false "the bus doesn't surface delegation" conclusion. Spike v2 added a stateful responder (manager delegates on call 1, answers on call 2).
  2. Spike v1 also produced `emission_sequence = [1,1,2,2,3,3,...]` across two runs in one process. Not a CrewAI quirk: I had not unregistered handlers between runs, so every event was recorded twice. **This is the process-global-singleton hazard the story warns about, reproduced live** — and it is why the recorder is a context manager with `off()` in a `finally`, and why there is a test for it.
- **Two of the story's own Dev Notes were wrong, and the spike overturned them:**
  - "`step_callback` … 0 invocations" is too strong. It fired **once** on the native-tools run, and `agent.agent_executor.step_callback` was **set**, not `None`. The story's *conclusion* still holds — `AgentAction`/`AgentFinish` carry no agent or task, so attribution is impossible — but the stated evidence was overconfident. Recorded here rather than quietly relied on.
  - Delegation requires patching `supports_function_calling → False` *in addition to* `call`. Confirmed exactly: native-tools run = 8 events, no delegation even with delegation-shaped text; forced-ReAct run = 15 events with the full ladder.
- **Measured leak paths, matching the story:** `TaskStartedEvent`/`TaskCompletedEvent` at `.task.agent.llm.api_key`; `AgentExecutionStartedEvent`/`AgentExecutionCompletedEvent` at both `.agent.llm.api_key` and `.task.agent.llm.api_key`; **`ToolUsageStartedEvent` at `.agent.llm.api_key`** while `ToolUsageFinishedEvent` is clean. The safe/unsafe split really is per-emit-site, so the recorder projects unconditionally.
- **Arrival order ≠ emission order, observed:** `[…, 9, 11, 10, 12, …]`. Entries are sorted by `emission_sequence` on read.
- **A real integration defect the conformance test caught, which no unit test would have.** Two tests failed with `assert 'Design it.' == 'design'`. The engine was building crewai `Task` objects **without `name=`**, so CrewAI stamped the *description* onto its events. The transcript would have said `"Design it."` where `task_results` says `"design"` — leaving Story 2.4 unable to line a transcript entry up with its task row. Fixed at the source by passing `name=task_spec.name`.

### Completion Notes List

- **The seam is the crewai event bus, not `step_callback`.** `TranscriptRecorder` subscribes to seven concrete event classes (dispatch is exact-type, so a base class catches nothing), projects scalars inside each handler, sorts by `emission_sequence`, and unregisters in a `finally`. It never retains an event object, never calls `to_json()`, and never reads `.agent`/`.task` beyond `.role`/`.name`.
- **Attribution needed a parent-chain resolver, exactly as the story predicted.** `AgentLogsExecutionEvent` — the per-turn event — has neither a `task` nor an `agent` attribute and its `task_name` is always `None`. The recorder maintains an `event_id → (task_name, agent_role)` map and resolves each entry through `parent_event_id`. The same mechanism solves delegated turns, whose own `.task` is a synthetic throwaway CrewAI invents: preferring the parent's task yields the real crew task in both the normal and delegated cases, so one rule covers both.
- **Both delegation tool-name spellings are handled.** `ToolUsageStartedEvent` carries the raw `'Delegate work to coworker'` with `tool_args` as a JSON **string**; `ToolUsageFinishedEvent` carries the sanitized `'delegate_work_to_coworker'` with `tool_args` as a **dict**. Matching one spelling would have produced a branch no real run reaches. Both sides go through `sanitize_tool_name`, and args are normalized before reading `coworker`.
- **One deliberate change beyond the task text, for correctness:** the engine now passes `name=task_spec.name` when building each crewai `Task`. Without it the transcript's `task_name` is the task *description*, which silently breaks correlation with `task_results` — see Debug Log. Small, but it is a change to `_build_crew`'s sibling code that the task list did not call for, so it is declared here.
- **One deliberate addition to the entry kinds:** the story specified five; I added `ENTRY_DELEGATION_RESULT` so the delegate's answer coming back is its own entry rather than being folded into the handoff. The story said "at minimum", and a UI rendering a handoff needs both ends of it.
- **`--transcript` prints, `--transcript-out` writes.** The written file is byte-identical to what is printed (both from `_format_transcript`), so what the user saw is what they saved. The file is written even under `--quiet` — an explicitly requested deliverable, matching `compose`'s precedent — while the printed form is suppressed. An empty transcript says so rather than printing nothing, per `EXPERIENCE.md:103`'s "always say why".
- **AD-13 held to literally.** The batch transcript is the accumulated sequence of exactly the units a streaming engine would emit one at a time: each entry carries its own sequence, task, agent, kind and content, so it is renderable in isolation. Nothing is reconstructed post-hoc from `tasks_output`, and `ExecutionEngine.run`'s signature is unchanged — adding streaming later is a delivery change only.
- **The AD-7 gate was touched with care.** Its four interception helpers moved to `tests/support/crewai_interception.py` so the transcript conformance test reuses the *proven* implementation; the `importorskip` guard, the `LLMCall` return type and the `BaseException`-derived `_NetworkEscaped` moved with them. **No assertion in `test_multi_provider_conformance.py` was changed**, and it was re-run green immediately after the move (6 passed) and again in the full suite.
- **Verified in the real CLI, not only in tests.** Built a two-agent package, ran `team-maker run --transcript --transcript-out` against it fully offline. Ordered, dual-attributed output with sparse sequences `[2,5,7,8,11,13]` exactly as designed; the file matched the console; the default no-flag run was byte-identical to Story 1.5's; and `grep` found **zero** occurrences of the API key in either the console output or the written file.
- **Tests:** 34 new tests across 4 files (13 transcript capture, 8 CLI transcript, 7 results contract, 6 transcript conformance). Full suite: **376 passed, 7 pre-existing live-API skips, 0 failures, 0 regressions**, 383 collected (baseline 342 passed / 349 collected). `ruff check` clean on every file this story touched or added; the 9 repo-wide findings that remain are all in `pipeline/`, `schema/` and `utils/` — files neither this story nor the Story 1.6 review touched.
- **Scope held.** No UI, no HTTP endpoint, no persistence, no actual streaming, no Factory change, and no edit to `crewai_runner.py.j2`. Four items logged to `deferred-work.md`.
- **Stale planning artifacts flagged, not edited** (Story 1.4/1.5/1.6 precedent): FR-27 and NFR3 exist only in `epics.md` — `prd.md` ends at FR-26 with no NFR section, and AD-13's own `Binds:` names FR-11 only, so nothing in the spine binds the requirement this story implements. `ARCHITECTURE-SPINE.md:225-226`'s "CrewAI version pin" Deferred entry remains stale from Story 1.6. `project-context.md:24` ("Never `import crewai` in `team_maker/`") is false — the narrowed rule is adapter-only; `:29` ("factory, not a runtime") is stale for the fourth story running.

### File List

- `team_maker/runtime/results.py` (modified — `TranscriptEntry`, six `ENTRY_*` kind constants, one defaulted `RunResult.transcript` field)
- `team_maker/adapters/runtime_crewai/transcript_capture.py` (new — `TranscriptRecorder`, the crewai→neutral translation)
- `team_maker/adapters/runtime_crewai/crewai_execution_engine.py` (modified — recorder wired around `kickoff`; crewai `Task` now built with `name=`)
- `team_maker/ports/execution_engine.py` (modified — docstring only; signature unchanged)
- `team_maker/cli.py` (modified — `--transcript` / `--transcript-out`, `_format_transcript`, `_print_transcript`)
- `tests/support/crewai_interception.py` (new — interception harness extracted from the AD-7 test, plus `responder`/`force_react` hooks)
- `tests/conformance/test_multi_provider_conformance.py` (modified — imports the shared harness; **assertions unchanged**)
- `tests/conformance/test_transcript_conformance.py` (new — 6 tests, real `Crew.kickoff`, offline)
- `tests/unit/adapters/test_crewai_transcript_capture.py` (new — 13 tests, synthetic events)
- `tests/unit/cli/test_cli_run_transcript.py` (new — 8 tests)
- `tests/unit/runtime/test_results.py` (modified — 7 tests added for the transcript contract)
- `project-docs/stories/deferred-work.md` (modified — 4 new entries)

## Change Log

- 2026-08-02 — Story drafted via the create-story context engine on branch `epic_1` @ `52779f4`. Four parallel research agents analyzed (a) the installed crewai 1.14.6 transcript seam, (b) epics/PRD/spine requirements, (c) the exact runtime code to modify, and (d) prior-story lessons plus UX. Three findings reshaped the story beyond the epic's four lines: (1) **`Crew`/`Agent` `step_callback` never fires in 1.14.6** — proven by spike, 0 invocations across three execution paths, because the default executor is `crewai.experimental.agent_executor.AgentExecutor` rather than the documented `CrewAgentExecutor`; the story is therefore built on the event bus, and an initial code-analysis recommendation to use per-agent `step_callback` closures was discarded on that evidence. (2) **The secret-leak surface is real and located** — `AgentExecutionStartedEvent.agent.llm.api_key` and `TaskStartedEvent.task.agent.llm.api_key` are plain strings that `to_json()` serializes, so the capture layer must project scalars and retain no event object. (3) **The AC's "RuntimeEngine port" names the wrong port** — `ports/runtime_engine.py` is codegen-only; the run path is `ports/execution_engine.py`, and the two are documented as never to merge. Also flagged: FR-27 and NFR3 exist only in `epics.md`, not the PRD, and AD-13's own `Binds:` names FR-11 only. The draft was then validated in a fresh context by an independent agent that ran four further offline spikes; it refuted five tactical claims, all corrected here — `ToolUsageStartedEvent` **does** leak `.agent.llm.api_key` (the leak/clean split is per-emit-site, so projection must be unconditional); `tool_name` is the raw `'Delegate work to coworker'` on the Started event and sanitized on Finished, with `tool_args` a `str` then a `dict`; `AgentLogsExecutionEvent` has neither `.task` nor `.agent`, so per-turn attribution needs a parent-chain resolver; `emission_sequence` is sparse over a subscribed subset rather than contiguous; and — the one that would have blocked Task 6 — **delegation is never emitted offline unless `supports_function_calling` is patched to `False` alongside `call`**, because the native function-calling branch swallows the stubbed response. The same pass confirmed the regression analysis is complete: all 14 `RunResult`/`TaskResult` construction sites use keyword args, so the defaulted trailing field breaks nothing. Status → ready-for-dev.
- 2026-08-02 — Implemented Story 1.7 on branch `story_1_7` (from `epic_1` @ `52779f4`). Added `TranscriptEntry` to the results contract and one defaulted `RunResult.transcript` field, so the Story 1.5 object is widened rather than replaced. Capture is a `TranscriptRecorder` in the CrewAI adapter that subscribes to the crewai event bus — **not** `step_callback`, which carries no agent or task reference and so cannot satisfy AC 2's dual attribution. Per-turn attribution required a parent-chain resolver, because `AgentLogsExecutionEvent` has neither a `task` nor an `agent` attribute; the same mechanism maps a delegated turn back to the real crew task instead of the synthetic one CrewAI invents. Delegation is recorded from the `ToolUsage*` pair, whose two emit sites disagree on both the tool name and the type of `tool_args` — both spellings are normalized. The CLI gained `--transcript` and `--transcript-out`; default output is byte-identical to Story 1.5. Task 0's spike overturned two claims in the story's own Dev Notes (`step_callback` fires *sometimes*, not never) and reproduced the handler-leak hazard first-hand, which is why the recorder is a context manager. The conformance test then caught a defect no unit test would have: the engine was building crewai `Task` objects without `name=`, so the transcript would have attributed entries to the task *description* while `task_results` used the name — fixed at the source. The AD-7 interception harness was extracted for reuse with **no assertion changed**, and re-run green. Verified in the real CLI offline: ordered, attributed, written to file, zero key occurrences. 34 new tests; full suite 376 passed, 7 pre-existing skips, 0 regressions, 383 collected; ruff clean on all touched files. 4 items logged to `deferred-work.md`, including partial transcripts on failed runs (PRD Open Q5) and concurrent-run isolation for Story 4.2. Status → review.
- 2026-08-02 — Adversarial code review (three parallel layers) and fixes. **Caveat: the same model implemented and reviewed this story**, so the Blind Hunter was given the diff and nothing else, and the other two layers verified by running code rather than by reading the Dev Agent Record. 47 raw findings, 33 after dedup, 24 patched, 8 deferred, 2 dismissed. All 10 ACs MET (AC 3 was PARTIAL, now closed), and the Auditor independently confirmed every self-reported number and mechanically verified the AD-7 extraction claim. The review's substance was **four tests that could not fail** — the same class this story's Dev Notes warned about and that the Story 1.6 review found five of. Two were the ones guarding handler removal from the process-global bus: the engine builds a fresh recorder per run, so leaked handlers appended to a dead object, and the other asserted on `_registered`, which `_unsubscribe` empties itself — deleting `off()` entirely would have kept both green. Two real defects were reproduced rather than argued: the `"unknown"` sentinel was being written into the attribution map, where its truthiness short-circuited descendants past a grandparent that knew the answer (deterministic, no threads needed), and the conformance fixture's `orchestrator` parameter was dead because the template forces `is_orchestrator=True` on `coordinator` and discards the request's flag — so the "sequential" case was hierarchical and `Process.sequential` had zero real-kickoff coverage. The same template forcing meant the transcript/`task_results` `agent_role` disagreement affected every Factory-built team, not an edge case. Fixes: attribution moved to lazy resolution in `entries()` with a real multi-level walk and no sentinels in the map; task boundaries attributed to the declared owner via a map passed from the engine; partial-registration unwind; `flush()` no longer masks the caller's exception; non-string outputs never stringified into content; unnameable delegations skipped; blank/duplicate task names refused as `InvalidPackageError`. 393 passed, 7 skips, 400 collected; ruff clean; AD-7 gate green with assertions still byte-identical to HEAD; re-verified in the real CLI. Status stays `review` pending acceptance.
