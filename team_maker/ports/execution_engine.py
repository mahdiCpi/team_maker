"""Port: executes a loaded team against a goal (Story 1.5, AD-6).

Distinct from ``ports/runtime_engine.py`` (Story 0.3's codegen-only port,
consumed by the Factory to render ``run_example.py``'s text) — this port is
about actually executing a team in-process. The two must never collide or
merge; the Factory's port and adapters stay untouched (AD-1).
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from team_maker.domain.models import GeneratedTeam
from team_maker.keyconfig import KeyConfig
from team_maker.runtime.results import RunResult


class ExecutionEngine(ABC):
    """Executes a ``GeneratedTeam`` against a goal and returns a ``RunResult``."""

    @abstractmethod
    def run(self, team: GeneratedTeam, key_config: KeyConfig, goal: str) -> RunResult:
        """Run *team* toward *goal*, resolving credentials from *key_config*."""
