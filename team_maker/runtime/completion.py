"""The completion rule (spec FR-027, FR-061 to FR-064; audit RC-11, P0-4;
contracts/receipts-and-completion.md).

Pure function, no I/O: a task cannot be reported successfully complete
unless every capability it marks REQUIRED has a receipt recording that the
tool executed, and any claimed external action is supported by a
SUCCESSFUL receipt. Attaching real tools (Phase 5) does not make the
product truthful by itself — a model handed a working tool may still
decline to call it and assert success anyway; this module is the layer that
notices.
"""
from __future__ import annotations

from typing import Sequence

from team_maker.domain.models import TaskSpec
from team_maker.runtime.results import ToolReceipt


def compute_unevidenced_capabilities(
    tasks: Sequence[TaskSpec], receipts: Sequence[ToolReceipt]
) -> list[str]:
    """Every capability a task marks REQUIRED — not merely available to its
    agent (FR-061, D-12) — with no receipt recorded against that task's own
    name (FR-027).

    A receipt for a task that did not declare the tool is recorded but
    ignored here (data-model.md §5) — the join is on the declaring task.
    An optional capability that was available but unused never appears
    (FR-063): only `required_capabilities` is examined, never `tools`.
    """
    evidenced = {(receipt.task_name, receipt.tool_name) for receipt in receipts}
    missing: list[str] = []
    for task in tasks:
        for capability in task.required_capabilities:
            if (task.name, capability) not in evidenced:
                missing.append(capability)
    return missing


def task_is_complete(task: TaskSpec, receipts: Sequence[ToolReceipt]) -> bool:
    """FR-062: a task requiring no external capability is trivially
    complete; otherwise every required capability needs a receipt against
    this task. A **failed** receipt still counts as "a receipt exists" here
    — completion is about evidence of execution, not evidence of success
    (that distinction is `action_is_supported`'s job, FR-064)."""
    evidenced_for_task = {
        receipt.tool_name for receipt in receipts if receipt.task_name == task.name
    }
    return all(capability in evidenced_for_task for capability in task.required_capabilities)


def run_is_successfully_complete(error: str | None, unevidenced: Sequence[str]) -> bool:
    """FR-027: error is None AND no unevidenced capability remains."""
    return error is None and not unevidenced


def action_is_supported(
    receipts: Sequence[ToolReceipt], *, task_name: str, tool_name: str
) -> bool:
    """FR-064: a claimed external action is supported only by a
    **successful** receipt. A recorded failure satisfies "the tool was
    invoked" but never "the action was performed"."""
    return any(
        receipt.task_name == task_name and receipt.tool_name == tool_name and receipt.succeeded
        for receipt in receipts
    )
