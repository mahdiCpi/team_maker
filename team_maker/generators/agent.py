"""Converts AgentSpec objects into YAML-serialisable dicts."""
from __future__ import annotations

from team_maker.domain.models import AgentSpec
from team_maker.utils.yaml_utils import dump_yaml


class AgentGenerator:
    """Renders one agent config file per AgentSpec."""

    def render(self, agent: AgentSpec) -> str:
        """Return YAML string for a single agent config file."""
        return dump_yaml(agent.to_dict())

    def filename(self, agent: AgentSpec) -> str:
        return f"{agent.role}.yaml"
