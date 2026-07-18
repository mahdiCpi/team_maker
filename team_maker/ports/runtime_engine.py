"""RuntimeEngine port — the seam every execution framework flows through.

Spine invariants AD-2/AD-4/AD-6: core code depends only on this Protocol; the
concrete engine (CrewAI in v1) lives under ``team_maker/adapters/runtime_crewai/``
and is never imported by core. Swapping execution engines in a future release is
an adapter change only.

This story (0.3) formalizes the *code-generation* (factory) seam only: an engine
knows its ``name``, can ``render_runner`` a framework-specific runner script, and
declares its ``extra_requirements``. A ``run()`` / ``execute()`` method for actual
team execution will be added in **Story 1.5** — it is intentionally absent here.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from team_maker.domain.models import GeneratedTeam


@runtime_checkable
class RuntimeEngine(Protocol):
    """Generates a framework-specific runner script for a generated team."""

    @property
    def name(self) -> str:
        ...

    def render_runner(self, team: GeneratedTeam, notifications=None) -> str:
        """Return the full content of run_example.py for this framework."""
        ...

    def extra_requirements(self) -> list[str]:
        """Additional pip packages beyond the base set."""
        ...
