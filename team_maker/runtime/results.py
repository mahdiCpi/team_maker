"""Batch results contract for a Runtime run (Story 1.5, AD-13; Story 1.7).

Plain dataclasses, dependency-free, same style as ``domain/models.py`` — but a
distinct concept from the Factory's ``PipelineResult`` (a build result), kept
in ``runtime/`` rather than ``domain/`` since results are a Runtime-only idea.

AD-13 ("results are batch behind a streamable interface") is what shapes
``TranscriptEntry``: the batch transcript is exactly the accumulated sequence of
the units that would later be streamed one at a time, so adding per-turn
streaming in v2 changes *delivery* only, never this contract.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# Transcript entry kinds. Constants rather than bare literals so a consumer
# (Story 2.4's UI, Story 4.2's API) can branch on them without string-matching
# content, and so a typo is an ImportError rather than a silently dead branch.
ENTRY_TASK_STARTED = "task_started"
ENTRY_TASK_COMPLETED = "task_completed"
ENTRY_AGENT_MESSAGE = "agent_message"  # an agent's answer for a turn
ENTRY_AGENT_ACTION = "agent_action"  # an agent's intermediate step (tool use)
ENTRY_DELEGATION = "delegation"  # agent hands work to another agent
ENTRY_DELEGATION_RESULT = "delegation_result"  # the delegate's answer coming back


@dataclass
class TaskResult:
    """One task's output from a run."""

    name: str
    agent_role: str
    output: str


@dataclass
class TranscriptEntry:
    """One ordered, attributed moment in a run (Story 1.7, FR-27).

    Every entry is independently meaningful: handed entry N alone, with no
    access to 1..N-1, a consumer can still render it. That is what makes the
    batch list streamable later without a contract change (AD-13).

    ``sequence`` carries the ordering as *data* — never rely on list position,
    because a streaming consumer can receive entries out of order. Values are
    monotonically increasing but **sparse**, since only some engine events map
    to a transcript entry. Sort by it; never assume contiguity.

    Holds only primitives. No credential, no engine object — see AD-9/NFR3.
    """

    sequence: int
    kind: str
    agent_role: str
    task_name: str
    content: str
    target_role: str | None = None  # the delegate, on handoff/delegation entries


@dataclass
class ToolReceipt:
    """Records that a tool executed — the sole admissible evidence for the
    completion rule in `runtime/completion.py` (spec FR-026 to FR-029; audit
    RC-11, P0-4).

    Holds primitives only, matching `TranscriptEntry`'s own constraint
    (AD-9/NFR3): no credential, no engine object. ``output_ref`` identifies
    the corresponding transcript entry rather than carrying the output text
    itself, so a receipt can never become a second place a secret leaks.

    One receipt per execution. Repeated invocations of the same tool
    produce repeated receipts. A receipt for a task that did not declare the
    tool is still recorded — the completion rule keys on the declaring task
    and ignores it.
    """

    sequence: int
    tool_name: str
    agent_role: str
    task_name: str
    arguments: dict[str, str]
    succeeded: bool
    timestamp: str
    output_ref: str


@dataclass
class RunResult:
    """The final output plus every task's individual output, in batch.

    ``transcript`` is additive (Story 1.7): it widens this object rather than
    introducing a second run path, and it is independently omittable so an API
    caller can drop it from a response without reshaping anything else.

    ``error`` is additive too (Story 4.4 AC 1): a run that fails partway
    through returns normally, with this set, rather than raising — so its
    ``transcript`` (collected before the failure) is never discarded along
    with an exception. ``None`` means the run succeeded; every other field is
    then fully populated. A caller MUST check this field before treating a
    returned `RunResult` as a success.

    ``tool_receipts`` and ``unevidenced_capabilities`` are additive too
    (Phase 6, spec FR-028): every tool execution recorded during the run,
    and which declared-REQUIRED capabilities produced no receipt. ``error``
    keeps its existing meaning — a run that failed partway. A non-empty
    ``unevidenced_capabilities`` is a **distinct** outcome (D-6): the run
    completed without raising, but made a claim it cannot evidence, so it
    MUST NOT be reported as successfully complete either — see
    `runtime/completion.py`.
    """

    final_output: str
    task_results: list[TaskResult]
    transcript: list[TranscriptEntry] = field(default_factory=list)
    error: str | None = None
    tool_receipts: list[ToolReceipt] = field(default_factory=list)
    unevidenced_capabilities: list[str] = field(default_factory=list)
