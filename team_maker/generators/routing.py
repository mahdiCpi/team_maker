"""Generates the model/provider routing configuration file."""
from __future__ import annotations

from team_maker.domain.models import GeneratedTeam
from team_maker.utils.yaml_utils import dump_yaml


class RoutingGenerator:
    """Produces a routing config that maps each role to its LLM assignment."""

    def render(self, team: GeneratedTeam) -> str:
        routing: dict = {
            "team_name": team.team_name,
            "routing": {
                agent.role: agent.routing.to_dict() for agent in team.agents
            },
        }
        return dump_yaml(routing)
