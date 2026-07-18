"""CrewAI runtime adapter (Story 0.3).

Concrete ``RuntimeEngine`` implementation. Core code depends only on
``team_maker.ports.runtime_engine.RuntimeEngine``; this package is reached via the
``team_maker.frameworks`` registry, never imported by core directly (AD-2/AD-4).
"""
from __future__ import annotations

from team_maker.adapters.runtime_crewai.crewai_engine import CrewAIAdapter


def get_crewai_adapter() -> CrewAIAdapter:
    """Return a CrewAI runtime engine instance."""
    return CrewAIAdapter()


__all__ = [
    "CrewAIAdapter",
    "get_crewai_adapter",
]
