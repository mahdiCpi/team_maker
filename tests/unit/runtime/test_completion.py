"""The completion rule (spec FR-027, FR-061 to FR-064; audit RC-11, P0-4;
contracts/receipts-and-completion.md; tasks T121-T125)."""
from __future__ import annotations

from team_maker.runtime.completion import (
    action_is_supported,
    compute_unevidenced_capabilities,
    run_is_successfully_complete,
    task_is_complete,
)
from team_maker.runtime.results import ToolReceipt
from tests.support.team_factories import task_spec


def _receipt(*, task_name: str, tool_name: str, succeeded: bool = True, sequence: int = 1) -> ToolReceipt:
    return ToolReceipt(
        sequence=sequence,
        tool_name=tool_name,
        agent_role="architect",
        task_name=task_name,
        arguments={},
        succeeded=succeeded,
        timestamp="2026-08-29T00:00:00+00:00",
        output_ref="ref-1",
    )


def test_required_but_never_invoked_capability_is_unevidenced():
    task = task_spec("build", "engineer", required_capabilities=["test_runner"])
    assert compute_unevidenced_capabilities([task], []) == ["test_runner"]
    assert not task_is_complete(task, [])
    assert not run_is_successfully_complete(None, compute_unevidenced_capabilities([task], []))


def test_required_capability_with_a_receipt_is_evidenced():
    task = task_spec("build", "engineer", required_capabilities=["test_runner"])
    receipts = [_receipt(task_name="build", tool_name="test_runner")]
    assert compute_unevidenced_capabilities([task], receipts) == []
    assert task_is_complete(task, receipts)


def test_optional_available_but_unused_tool_never_blocks_completion():
    """FR-063: `required_capabilities` is examined, never the agent's
    broader `tools` list — an available-but-unused optional tool produces
    no finding."""
    task = task_spec("build", "engineer", required_capabilities=[])
    assert compute_unevidenced_capabilities([task], []) == []
    assert task_is_complete(task, [])


def test_a_failed_receipt_satisfies_required_but_not_the_success_claim():
    """FR-064: a recorded failure is evidence of execution, not of success."""
    task = task_spec("build", "engineer", required_capabilities=["test_runner"])
    receipts = [_receipt(task_name="build", tool_name="test_runner", succeeded=False)]

    assert compute_unevidenced_capabilities([task], receipts) == []  # a receipt exists
    assert task_is_complete(task, receipts)  # "required" only needs a receipt
    assert not action_is_supported(receipts, task_name="build", tool_name="test_runner")


def test_a_successful_receipt_supports_the_claimed_action():
    receipts = [_receipt(task_name="build", tool_name="test_runner", succeeded=True)]
    assert action_is_supported(receipts, task_name="build", tool_name="test_runner")


def test_legacy_task_with_no_requiredness_marking_is_fully_optional():
    """A task loaded from a pre-remediation package (spec Assumptions,
    T124) — `required_capabilities` defaults to `[]` via `loader.py`'s
    `cfg.get(..., [])`, so it is indistinguishable from a task that
    declares no required capability at all."""
    legacy_task = task_spec("build", "engineer")  # no required_capabilities kwarg
    assert legacy_task.required_capabilities == []
    assert compute_unevidenced_capabilities([legacy_task], []) == []
    assert task_is_complete(legacy_task, [])


def test_receipt_for_a_task_that_did_not_declare_the_tool_is_ignored():
    """The rule joins on the *declaring* task; a receipt recorded under a
    different task name never satisfies this task's requirement."""
    task = task_spec("build", "engineer", required_capabilities=["test_runner"])
    receipts = [_receipt(task_name="some_other_task", tool_name="test_runner")]
    assert compute_unevidenced_capabilities([task], receipts) == ["test_runner"]


def test_run_successfully_complete_requires_no_error_and_no_unevidenced_capability():
    assert run_is_successfully_complete(None, [])
    assert not run_is_successfully_complete("boom", [])
    assert not run_is_successfully_complete(None, ["test_runner"])


def test_multiple_tasks_each_contribute_their_own_unevidenced_capabilities():
    tasks = [
        task_spec("design", "architect", required_capabilities=["state_writer"]),
        task_spec("build", "engineer", required_capabilities=["test_runner"]),
    ]
    receipts = [_receipt(task_name="design", tool_name="state_writer")]
    assert compute_unevidenced_capabilities(tasks, receipts) == ["test_runner"]
