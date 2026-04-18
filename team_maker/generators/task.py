"""Converts TaskSpec objects into YAML-serialisable dicts."""
from __future__ import annotations

from team_maker.domain.models import TaskSpec
from team_maker.utils.yaml_utils import dump_yaml


class TaskGenerator:
    """Renders one task config file per TaskSpec."""

    def render(self, task: TaskSpec) -> str:
        return dump_yaml(task.to_dict())

    def filename(self, task: TaskSpec) -> str:
        return f"{task.name}.yaml"
