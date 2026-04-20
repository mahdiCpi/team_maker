"""Generates the model/provider routing configuration file."""
from __future__ import annotations

from team_maker.domain.models import GeneratedTeam
from team_maker.utils.yaml_utils import dump_yaml

# Hostname of the Ollama sidecar inside the generated docker-compose network.
_OLLAMA_COMPOSE_URL = "http://ollama:11434"


class RoutingGenerator:
    """Produces a routing config that maps each role to its LLM assignment."""

    def render(self, team: GeneratedTeam, *, in_compose: bool = False) -> str:
        """Render routing_config.yaml.

        When ``in_compose`` is True, any Ollama-routed agent has its
        ``base_url`` rewritten to ``http://ollama:11434`` so the generated
        runner talks to the sidecar service instead of the host.
        """
        routing_entries: dict = {}
        for agent in team.agents:
            entry = agent.routing.to_dict()
            if in_compose and entry.get("provider") == "ollama":
                entry["base_url"] = _OLLAMA_COMPOSE_URL
            routing_entries[agent.role] = entry

        return dump_yaml(
            {
                "team_name": team.team_name,
                "routing": routing_entries,
            }
        )
