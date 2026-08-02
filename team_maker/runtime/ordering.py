"""Framework-agnostic task dependency ordering (Story 1.5, AC 2).

This does not exist anywhere else in the codebase — the generated
``run_example.py`` runs tasks in declaration order and never reads
``dependencies`` at all. Pure Python, no CrewAI, no I/O.
"""
from __future__ import annotations

from team_maker.domain.models import TaskSpec


class TaskDependencyCycleError(Exception):
    """The task dependency graph contains a cycle."""


def topological_sort(tasks: list[TaskSpec]) -> list[TaskSpec]:
    """Return *tasks* ordered so a task never precedes one it depends on.

    Stable: among tasks whose dependencies are already resolved, relative
    input order is preserved. A dependency name not present in *tasks* is
    treated as already satisfied (the Factory already prunes dangling
    dependencies at build time; this is not this function's concern).
    """
    known_names = {t.name for t in tasks}
    remaining_deps = {t.name: [d for d in t.dependencies if d in known_names] for t in tasks}
    resolved: set[str] = set()
    ordered: list[TaskSpec] = []
    pending = list(tasks)

    while pending:
        ready = [t for t in pending if all(d in resolved for d in remaining_deps[t.name])]
        if not ready:
            stuck = ", ".join(sorted(t.name for t in pending))
            raise TaskDependencyCycleError(f"Task dependency cycle detected among: {stuck}")
        for t in ready:
            ordered.append(t)
            resolved.add(t.name)
            pending.remove(t)

    return ordered
