"""CrewAI runtime engine — delegates runner generation to crewai_runner.py.j2.

Satisfies the ``RuntimeEngine`` port structurally (no ABC subclassing). The core
never imports this module directly; it is reached via the ``frameworks`` registry.
No top-level ``crewai`` import — crewai appears only as a version string in
``extra_requirements()`` (AD-6).
"""
from __future__ import annotations

from team_maker.codegen import render_template
from team_maker.domain.models import GeneratedTeam


class CrewAIAdapter:
    @property
    def name(self) -> str:
        return "crewai"

    def extra_requirements(self) -> list[str]:
        return [
            "crewai[google-genai]==1.14.6",
            "crewai-tools>=0.25.0",
            "langchain-anthropic>=0.3.0",
            "langchain-openai>=0.3.0",
            "langchain-ollama>=0.2.0",
        ]

    def render_runner(self, team: GeneratedTeam, notifications=None) -> str:
        orchestrator = next((a for a in team.agents if a.is_orchestrator), None)
        return render_template(
            "crewai_runner.py.j2",
            team=team,
            orchestrator_role=orchestrator.role if orchestrator else None,
            notifications=notifications,
        )
