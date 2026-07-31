"""Unit tests for the Runtime's single public entry point (Story 1.5, AC 1, 2, 6).

Fully offline — uses a fake ExecutionEngine, no CrewAI needed for these tests.
"""
from __future__ import annotations

import pytest

from team_maker.keyconfig import KeyConfig
from team_maker.pipeline.runner import PipelineRunner
from team_maker.ports.execution_engine import ExecutionEngine
from team_maker.runtime.executor import UnsupportedFrameworkError, run_team_package
from team_maker.runtime.results import RunResult
from team_maker.schema.request import RoleDefinition, TeamCreationRequest


class _FakeEngine(ExecutionEngine):
    def __init__(self):
        self.calls = []

    def run(self, team, key_config, goal):
        self.calls.append((team, key_config, goal))
        return RunResult(final_output="fake result", task_results=[])


def test_run_team_package_loads_and_delegates_to_the_engine(minimal_request):
    build = PipelineRunner().run(minimal_request)
    engine = _FakeEngine()
    key_config = KeyConfig(keys={})

    result = run_team_package(build.output_path, "ship it", key_config, engine=engine)

    assert result.final_output == "fake result"
    assert len(engine.calls) == 1
    called_team, called_keys, called_goal = engine.calls[0]
    assert called_team.team_name == minimal_request.team_name
    assert called_keys is key_config
    assert called_goal == "ship it"


def test_run_team_package_rejects_non_crewai_framework(tmp_path):
    request = TeamCreationRequest(
        team_name="LangGraph Team",
        purpose="A team targeting a non-crewai framework for this test.",
        output_path=str(tmp_path / "lg_team"),
        framework="langgraph",
        desired_roles=[
            RoleDefinition(
                name="architect",
                description="Designs system architecture and makes technical decisions.",
            )
        ],
    )
    build = PipelineRunner().run(request)
    engine = _FakeEngine()

    with pytest.raises(UnsupportedFrameworkError, match="crewai"):
        run_team_package(build.output_path, "ship it", KeyConfig(keys={}), engine=engine)

    assert engine.calls == []


def test_run_team_package_defaults_to_the_crewai_execution_engine(minimal_request, monkeypatch):
    """When no engine is passed, run_team_package must default to
    CrewAIExecutionEngine — patch the class at its *source* module (where the
    lazy import in executor.py reads it from), not on executor.py itself
    (which has no such module-level attribute, by design)."""
    build = PipelineRunner().run(minimal_request)
    fake = _FakeEngine()
    monkeypatch.setattr(
        "team_maker.adapters.runtime_crewai.crewai_execution_engine.CrewAIExecutionEngine",
        lambda: fake,
    )

    result = run_team_package(build.output_path, "ship it", KeyConfig(keys={}))

    assert result.final_output == "fake result"
    assert len(fake.calls) == 1
