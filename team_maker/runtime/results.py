"""Batch results contract for a Runtime run (Story 1.5, AD-13).

Plain dataclasses, dependency-free, same style as ``domain/models.py`` — but a
distinct concept from the Factory's ``PipelineResult`` (a build result), kept
in ``runtime/`` rather than ``domain/`` since results are a Runtime-only idea.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TaskResult:
    """One task's output from a run."""

    name: str
    agent_role: str
    output: str


@dataclass
class RunResult:
    """The final output plus every task's individual output, in batch."""

    final_output: str
    task_results: list[TaskResult]
