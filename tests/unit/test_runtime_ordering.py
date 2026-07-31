"""Unit tests for framework-agnostic task dependency ordering (Story 1.5, AC 2)."""
from __future__ import annotations

import pytest

from team_maker.domain.models import TaskSpec
from team_maker.runtime.ordering import TaskDependencyCycleError, topological_sort


def _task(name: str, dependencies: list[str] | None = None) -> TaskSpec:
    return TaskSpec(
        name=name,
        description=f"do {name}",
        expected_output="output",
        agent_role="someone",
        dependencies=dependencies or [],
    )


def test_linear_chain_sorts_in_dependency_order():
    a, b, c = _task("a"), _task("b", ["a"]), _task("c", ["b"])

    sorted_tasks = topological_sort([c, b, a])  # deliberately out of order

    assert [t.name for t in sorted_tasks] == ["a", "b", "c"]


def test_diamond_dependency_resolves_valid_order():
    a = _task("a")
    b = _task("b", ["a"])
    c = _task("c", ["a"])
    d = _task("d", ["b", "c"])

    sorted_tasks = topological_sort([d, c, b, a])
    names = [t.name for t in sorted_tasks]

    assert names.index("a") < names.index("b")
    assert names.index("a") < names.index("c")
    assert names.index("b") < names.index("d")
    assert names.index("c") < names.index("d")


def test_no_dependencies_preserves_input_order():
    a, b, c = _task("a"), _task("b"), _task("c")

    sorted_tasks = topological_sort([a, b, c])

    assert [t.name for t in sorted_tasks] == ["a", "b", "c"]


def test_cycle_raises_clear_error():
    a = _task("a", ["b"])
    b = _task("b", ["a"])

    with pytest.raises(TaskDependencyCycleError, match="a|b"):
        topological_sort([a, b])


def test_dangling_dependency_name_is_ignored_not_an_error():
    """A dependency naming a task that doesn't exist in this list is not this
    function's problem to flag (the Factory already prunes dangling deps at
    build time, `_task_dep_available`) — treat it as satisfied, not a cycle.
    """
    a = _task("a", ["does_not_exist"])

    sorted_tasks = topological_sort([a])

    assert [t.name for t in sorted_tasks] == ["a"]
