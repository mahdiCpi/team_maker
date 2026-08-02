"""Unit tests for the Runtime's results contract (Story 1.5, AD-13; Story 1.7)."""
from __future__ import annotations

from dataclasses import is_dataclass

import pytest

from team_maker.runtime.results import (
    ENTRY_AGENT_ACTION,
    ENTRY_AGENT_MESSAGE,
    ENTRY_DELEGATION,
    ENTRY_DELEGATION_RESULT,
    ENTRY_TASK_COMPLETED,
    ENTRY_TASK_STARTED,
    RunResult,
    TaskResult,
    TranscriptEntry,
)


def test_task_result_holds_name_agent_role_and_output():
    result = TaskResult(name="architecture_design", agent_role="architect", output="the plan")

    assert result.name == "architecture_design"
    assert result.agent_role == "architect"
    assert result.output == "the plan"


def test_run_result_holds_final_output_and_task_results_in_batch():
    task_results = [
        TaskResult(name="architecture_design", agent_role="architect", output="the plan"),
        TaskResult(name="backend_implementation", agent_role="backend_engineer", output="the code"),
    ]

    result = RunResult(final_output="done", task_results=task_results)

    assert result.final_output == "done"
    assert result.task_results == task_results
    assert len(result.task_results) == 2


def test_results_are_plain_dependency_free_dataclasses():
    assert is_dataclass(TaskResult)
    assert is_dataclass(RunResult)

    # Pure data — no filesystem/network/crewai import anywhere in this module.
    import ast
    import inspect

    import team_maker.runtime.results as results_module

    tree = ast.parse(inspect.getsource(results_module))
    imported_names = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert "crewai" not in imported_names


def test_task_result_and_run_result_reject_unknown_fields():
    with pytest.raises(TypeError):
        TaskResult(name="a", agent_role="b", output="c", extra="not a field")
    with pytest.raises(TypeError):
        RunResult(final_output="x", task_results=[], extra="not a field")


# ---------------------------------------------------------------------------
# Transcript contract (Story 1.7, FR-27, AD-13)
# ---------------------------------------------------------------------------


def test_transcript_entry_carries_order_attribution_kind_and_content():
    entry = TranscriptEntry(
        sequence=7,
        kind=ENTRY_AGENT_MESSAGE,
        agent_role="architect",
        task_name="design",
        content="here is the plan",
    )

    assert entry.sequence == 7
    assert entry.kind == ENTRY_AGENT_MESSAGE
    assert entry.agent_role == "architect"
    assert entry.task_name == "design"
    assert entry.content == "here is the plan"
    assert entry.target_role is None  # only handoffs name a counterpart


def test_a_delegation_entry_names_the_agent_it_handed_off_to():
    entry = TranscriptEntry(
        sequence=3,
        kind=ENTRY_DELEGATION,
        agent_role="coordinator",
        task_name="design",
        content="design it",
        target_role="architect",
    )

    assert entry.target_role == "architect"


def test_an_entry_is_independently_meaningful():
    """AD-13: a streaming consumer receives entry N with no access to 1..N-1.

    Every field needed to render an entry must therefore be on the entry — no
    lookups into sibling entries, and no reliance on list position for order.
    """
    entry = TranscriptEntry(
        sequence=42,
        kind=ENTRY_TASK_STARTED,
        agent_role="architect",
        task_name="design",
        content="Design it.",
    )

    rendered = f"[{entry.sequence}] {entry.task_name}/{entry.agent_role} {entry.kind}"
    assert rendered == "[42] design/architect task_started"


def test_run_result_still_constructs_without_a_transcript():
    """Story 1.5's contract is unchanged: the new field is purely additive."""
    result = RunResult(final_output="done", task_results=[])

    assert result.transcript == []


def test_each_run_result_gets_its_own_transcript_list():
    """A shared mutable default would leak one run's transcript into the next."""
    first = RunResult(final_output="a", task_results=[])
    second = RunResult(final_output="b", task_results=[])

    first.transcript.append(
        TranscriptEntry(
            sequence=1,
            kind=ENTRY_AGENT_MESSAGE,
            agent_role="architect",
            task_name="design",
            content="x",
        )
    )

    assert second.transcript == []


def test_transcript_entry_is_a_plain_dataclass_rejecting_unknown_fields():
    assert is_dataclass(TranscriptEntry)
    with pytest.raises(TypeError):
        TranscriptEntry(
            sequence=1,
            kind=ENTRY_AGENT_MESSAGE,
            agent_role="a",
            task_name="t",
            content="c",
            extra="not a field",
        )


def test_entry_kinds_are_distinct_constants():
    """Consumers branch on `kind`; two kinds colliding would silently merge
    unrelated entry types in the UI."""
    kinds = {
        ENTRY_TASK_STARTED,
        ENTRY_TASK_COMPLETED,
        ENTRY_AGENT_MESSAGE,
        ENTRY_AGENT_ACTION,
        ENTRY_DELEGATION,
        ENTRY_DELEGATION_RESULT,
    }
    assert len(kinds) == 6
