"""Back-compat shim — ``CrewAIAdapter`` moved to ``team_maker.adapters.runtime_crewai``.

Story 0.3 put CrewAI behind the ``RuntimeEngine`` port: the concrete adapter now
lives in ``team_maker.adapters.runtime_crewai.crewai_engine`` and satisfies the
port structurally (no ``FrameworkAdapter`` ABC). New code should import from that
location. This module re-exports it so existing imports
(``from team_maker.frameworks.crewai_adapter import CrewAIAdapter``) keep working.
"""
from __future__ import annotations

from team_maker.adapters.runtime_crewai.crewai_engine import CrewAIAdapter as CrewAIAdapter

__all__ = ["CrewAIAdapter"]
