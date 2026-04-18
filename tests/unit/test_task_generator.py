"""Unit tests for TaskGenerator."""
from __future__ import annotations

import yaml

from team_maker.domain.models import TaskSpec
from team_maker.generators.task import TaskGenerator


def _make_task(**kwargs) -> TaskSpec:
    defaults = dict(
        name="backend_implementation",
        description="Implement backend services and APIs.",
        expected_output="Working backend with tests.",
        agent_role="backend_engineer",
        dependencies=["architecture_design"],
        is_optional=False,
    )
    defaults.update(kwargs)
    return TaskSpec(**defaults)


def test_render_returns_valid_yaml():
    gen = TaskGenerator()
    task = _make_task()
    rendered = gen.render(task)
    parsed = yaml.safe_load(rendered)
    assert parsed["name"] == "backend_implementation"


def test_render_includes_all_fields():
    gen = TaskGenerator()
    task = _make_task()
    parsed = yaml.safe_load(gen.render(task))
    for field in ("name", "description", "expected_output", "agent_role",
                  "dependencies", "is_optional"):
        assert field in parsed


def test_render_dependencies_list():
    gen = TaskGenerator()
    task = _make_task(dependencies=["architecture_design", "code_review"])
    parsed = yaml.safe_load(gen.render(task))
    assert parsed["dependencies"] == ["architecture_design", "code_review"]


def test_render_empty_dependencies():
    gen = TaskGenerator()
    task = _make_task(dependencies=[])
    parsed = yaml.safe_load(gen.render(task))
    assert parsed["dependencies"] == []


def test_filename_uses_task_name():
    gen = TaskGenerator()
    task = _make_task(name="deployment_guidance")
    assert gen.filename(task) == "deployment_guidance.yaml"
