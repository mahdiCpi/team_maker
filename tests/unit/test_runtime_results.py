"""Unit tests for the Runtime's results contract (Story 1.5, AD-13)."""
from __future__ import annotations

from dataclasses import is_dataclass

import pytest

from team_maker.runtime.results import RunResult, TaskResult


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
