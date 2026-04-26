"""AutoGen adapter — delegates to autogen_runner.py.j2 (Phase 7: 0.2 + 0.4 compat)."""
from __future__ import annotations

from team_maker.codegen import render_template
from team_maker.domain.models import GeneratedTeam
from team_maker.frameworks.base import FrameworkAdapter


class AutoGenAdapter(FrameworkAdapter):
    @property
    def name(self) -> str:
        return "autogen"

    def extra_requirements(self) -> list[str]:
        return [
            # supports both pyautogen 0.2 and autogen-agentchat 0.4+
            "pyautogen>=0.2.0",
        ]

    def render_runner(self, team: GeneratedTeam, notifications=None) -> str:
        orchestrator = next((a for a in team.agents if a.is_orchestrator), None)
        return render_template(
            "autogen_runner.py.j2",
            team=team,
            orchestrator_role=orchestrator.role if orchestrator else None,
            topology_pattern=team.topology_pattern,
            notifications=notifications,
        )
