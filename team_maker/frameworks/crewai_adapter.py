"""CrewAI framework adapter — delegates runner generation to crewai_runner.py.j2."""
from __future__ import annotations

from team_maker.codegen import render_template
from team_maker.domain.models import GeneratedTeam
from team_maker.frameworks.base import FrameworkAdapter


class CrewAIAdapter(FrameworkAdapter):
    @property
    def name(self) -> str:
        return "crewai"

    def extra_requirements(self) -> list[str]:
        return [
            "crewai>=0.80.0",
            "crewai-tools>=0.25.0",
            "langchain-anthropic>=0.3.0",
            "langchain-openai>=0.3.0",
            "langchain-ollama>=0.2.0",
        ]

    def render_runner(self, team: GeneratedTeam) -> str:
        orchestrator = next((a for a in team.agents if a.is_orchestrator), None)
        return render_template(
            "crewai_runner.py.j2",
            team=team,
            orchestrator_role=orchestrator.role if orchestrator else None,
        )
