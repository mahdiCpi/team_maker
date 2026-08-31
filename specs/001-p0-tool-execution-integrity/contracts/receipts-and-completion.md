# Contract: Execution receipts and the completion rule

**Modules**: `team_maker/adapters/runtime_crewai/transcript_capture.py` (modified),
`team_maker/runtime/results.py` (modified), `team_maker/runtime/completion.py` (new)
**Requirements**: FR-026 to FR-029, FR-061 to FR-064 | **Root cause**: RC-11 | **Audit**: §2.4 (P0-4)
**Step**: 5

## The invariant

> A task cannot be reported successfully complete unless every capability it marks **required** has a
> receipt recording that the tool executed — and any claimed external action is supported by a
> **successful** receipt.

Attaching real tools does not make the product truthful. A model handed a working `test_runner` may
decline to call it and assert the tests passed. Every symptom in the audit's transcripts would recur
with real tools attached, and no layer would notice.

## What already exists

`transcript_capture.py` subscribes to `ToolUsageStartedEvent` and `ToolUsageFinishedEvent` (`:239-240`)
with handlers at `:402` and `:419`, argument normalization via `_as_args_dict` (`:121`), and a
documented api-key redaction guard (`:62`).

**Both handlers discard non-delegation events.** Each computes `target = self._delegate_of(event)` and
returns early when `target is None`. So every ordinary tool use is observed and thrown away.

This is a consumption change on built infrastructure, not a new capture path — which is why the audit
calls it the cheapest available guarantee of truthfulness.

## Required changes

### 1. Record, then branch (FR-026)

Both handlers record a `ToolReceipt` for every tool usage **before** the delegation branch. The
existing delegation behaviour is preserved exactly — the early return moves below the recording, it
does not disappear.

Receipt fields are in
[data-model.md](../data-model.md#5-toolreceipt--team_makerruntimeresultspy): sequence, tool name,
agent role, task name, sanitized arguments, success/failure, timestamp, output reference.

- Arguments pass the **existing** redaction guard (FR-029). Reusing it is why secret-safety comes free
  rather than being re-implemented.
- Receipts hold primitives only — no credential, no engine object (AD-9/NFR3, the constraint
  `TranscriptEntry` already documents).
- **No second bus subscription.** `_subscribe` already documents the partial-registration hazard it
  guards; adding a subscriber would mean a second lifecycle to unwind.

### 2. Widen `RunResult` additively (FR-028)

```text
tool_receipts:            list[ToolReceipt]  = field(default_factory=list)
unevidenced_capabilities: list[str]          = field(default_factory=list)
```

Both defaulted, following the convention `RunResult`'s docstring already establishes twice — for
`transcript` (Story 1.7) and `error` (Story 4.4), each widening the object rather than introducing a
second run path. Existing callers are unaffected (FR-048).

`error` keeps its meaning: a run that failed partway. An unevidenced completion is a **distinct**
outcome and callers must be able to tell them apart (D-6).

### 3. The completion rule (FR-027)

Pure function in `team_maker/runtime/completion.py`. No I/O; unit-testable without constructing a run.

```text
for each capability the task marks REQUIRED:          # not the available set — FR-061
    if no receipt exists for (task_name, required_capability):
        unevidenced_capabilities += required_capability

task successfully complete ⟺ requires no external capability
                              OR every REQUIRED capability has a receipt      # FR-062

run successfully complete  ⟺ error is None
                              AND unevidenced_capabilities is empty

claimed external action supported ⟺ a SUCCESSFUL receipt corresponds to it    # FR-064
```

Rules:

- **Required is not the same as available** (FR-061). Requiredness is a property of the task, not of
  the agent's toolset (D-12). An agent may carry a tool it does not need for a given task.
- **Optional unused tools never block completion** and never raise an unevidenced-capability finding
  (FR-063).
- **A recorded failure is evidence of execution, not evidence of success.** It satisfies "a receipt
  exists"; it does not satisfy the success claim, and it does not support a claim that the action was
  performed (FR-064).
- Receipts for a task that did not declare the tool are recorded but ignored by the rule, which keys
  on the declaring task.
- Tasks declaring no external capability are unaffected (FR-049).
- The rule lives outside the engine so it is not CrewAI-specific and stays verifiable without the run
  path (D-6).

### 4. Surfacing (FR-028)

`RunResult.unevidenced_capabilities` names which declared capability produced no evidence, so a caller
can say *which* claim is unsupported rather than only that the run is untrustworthy. The tool-execution
record is available to the user as part of the run result.

## Test obligations

| Test | Asserts | Location |
|---|---|---|
| Receipt recorded | Every tool execution produces a receipt with all required fields | `tests/unit/adapters/` |
| Delegation preserved | Existing delegation transcript entries are unchanged by the recording change | `tests/unit/adapters/` |
| Declined required tool fails the claim | Task requires a capability, tool never invoked → not reported successfully complete | `tests/unit/runtime/` |
| Optional unused tool does not block | Required capability evidenced, two optional tools unused → task completes clean | `tests/unit/runtime/` |
| Claim needs a successful receipt | A failed receipt does not support a claimed external action | `tests/unit/runtime/` |
| Legacy task defaults to optional | A task with no requiredness marking does not block on declared tools | `tests/unit/runtime/` |
| Failure ≠ success | A receipt recording failure does not satisfy the success rule | `tests/unit/runtime/` |
| No-tool tasks unaffected | A task declaring no capability completes exactly as today | `tests/unit/runtime/` |
| Redaction | No credential value appears in any receipt | `tests/security/` — permanent |
| End to end | A run with a real declared tool produces a receipt the user can inspect | `tests/integration/` |
