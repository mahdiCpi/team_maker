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
class RunResult:
    """The final output plus every task's individual output, in batch.

    ``transcript`` is additive (Story 1.7): it widens this object rather than
    introducing a second run path, and it is independently omittable so an API
    caller can drop it from a response without reshaping anything else.
    """

    final_output: str
    task_results: list[TaskResult]
    transcript: list[TranscriptEntry] = field(default_factory=list)
