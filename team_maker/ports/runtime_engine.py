"""RuntimeEngine port — the seam every code-generation framework flows through.

Spine invariants AD-2/AD-6: core code (``pipeline/runner.py``) depends only on this
port; concrete engines live under ``team_maker/adapters/runtime_engines/`` and are
selected by data (the ``get_runtime_engine`` registry), never by branching on name.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from team_maker.domain.models import GeneratedTeam


class RuntimeEngine(ABC):
    """Generates a framework-specific runner script for a generated team."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def render_runner(self, team: GeneratedTeam, notifications=None) -> str:
        """Return the full content of run_example.py for this framework."""
        ...

    @abstractmethod
    def extra_requirements(self) -> list[str]:
        """Additional pip packages beyond the base set."""
        ...
