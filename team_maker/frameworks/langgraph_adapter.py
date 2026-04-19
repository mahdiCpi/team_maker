"""LangGraph adapter — delegates to langgraph_runner.py.j2 (Phase 7: conditional edges)."""
from __future__ import annotations

from team_maker.codegen import render_template
from team_maker.domain.models import GeneratedTeam
from team_maker.frameworks.base import FrameworkAdapter


class LangGraphAdapter(FrameworkAdapter):
    @property
    def name(self) -> str:
        return "langgraph"

    def extra_requirements(self) -> list[str]:
        return [
            "langgraph>=0.2.0",
            "langchain-core>=0.3.0",
            "langchain-anthropic>=0.3.0",
            "langchain-openai>=0.3.0",
            "langchain-ollama>=0.2.0",
        ]

    def render_runner(self, team: GeneratedTeam) -> str:
        orchestrator = next((a for a in team.agents if a.is_orchestrator), None)
        return render_template(
            "langgraph_runner.py.j2",
            team=team,
            orchestrator_role=orchestrator.role if orchestrator else None,
            topology_pattern=team.topology_pattern,
            topology_edges=team.topology_edges,
        )
