"""Unit tests for the CrewAI execution adapter (Story 1.5, AC 2, 3, 4, 5).

Requires CrewAI installed (this repo's `.venv` has 1.14.5) — `Crew.kickoff` is
monkeypatched in every test so no real LLM/network call ever happens.
"""
from __future__ import annotations

import pytest

pytest.importorskip("crewai")

from crewai import Crew, Process  # noqa: E402
from pydantic import SecretStr  # noqa: E402

from team_maker.adapters.runtime_crewai.crewai_execution_engine import (  # noqa: E402
    CrewAIExecutionEngine,
)
from team_maker.domain.models import (  # noqa: E402
    AgentSpec,
    GeneratedTeam,
    ProviderRouting,
    TaskSpec,
)
from team_maker.keyconfig import KeyConfig  # noqa: E402
from team_maker.runtime.results import TaskResult  # noqa: E402


def _agent(
    role: str,
    *,
    provider: str = "anthropic",
    model: str = "claude-sonnet-4-6",
    api_key_env: str | None = "ANTHROPIC_API_KEY",
    base_url: str | None = None,
    is_orchestrator: bool = False,
) -> AgentSpec:
    return AgentSpec(
        role=role,
        display_name=role.title(),
        description=f"{role} description",
        goal=f"{role} goal",
        backstory=f"{role} backstory",
        capabilities=[],
        tools=[],
        routing=ProviderRouting(
            provider=provider, model=model, api_key_env=api_key_env, base_url=base_url
        ),
        is_orchestrator=is_orchestrator,
    )


def _task(name: str, agent_role: str, dependencies: list[str] | None = None) -> TaskSpec:
    return TaskSpec(
        name=name,
        description=f"do {name}",
        expected_output="an output",
        agent_role=agent_role,
        dependencies=dependencies or [],
    )


def _team(agents: list[AgentSpec], tasks: list[TaskSpec]) -> GeneratedTeam:
    return GeneratedTeam(
        team_name="Test Team",
        purpose="testing",
        template_used="software_delivery_team",
        agents=agents,
        tasks=tasks,
    )


class _FakeTaskOutput:
    def __init__(self, raw: str) -> None:
        self.raw = raw


class _FakeCrewOutput:
    def __init__(self, raw: str, tasks_output: list[_FakeTaskOutput]) -> None:
        self.raw = raw
        self.tasks_output = tasks_output


def _install_fake_kickoff(monkeypatch, captured_crews: list, output: _FakeCrewOutput) -> None:
    def _fake_kickoff(self, inputs=None):
        captured_crews.append(self)
        return output

    monkeypatch.setattr(Crew, "kickoff", _fake_kickoff)


def test_builds_agent_with_explicit_per_agent_credentials(monkeypatch):
    key_config = KeyConfig(keys={"anthropic": SecretStr("sk-test-key")})
    team = _team([_agent("architect")], [_task("design", "architect")])
    captured: list = []
    _install_fake_kickoff(
        monkeypatch, captured, _FakeCrewOutput(raw="final", tasks_output=[_FakeTaskOutput("design output")])
    )

    result = CrewAIExecutionEngine().run(team, key_config, "ship it")

    crew = captured[0]
    assert crew.process == Process.sequential
    [agent_obj] = crew.agents
    assert agent_obj.role == "architect"
    # CrewAI's LLM parses "provider/model" into separate attributes internally.
    assert agent_obj.llm.provider == "anthropic"
    assert agent_obj.llm.model == "claude-sonnet-4-6"
    assert agent_obj.llm.api_key == "sk-test-key"
    assert result.final_output == "final"
    assert result.task_results == [TaskResult(name="design", agent_role="architect", output="design output")]


def test_missing_key_passes_none_api_key_never_a_global_env_fallback(monkeypatch):
    key_config = KeyConfig(keys={})  # no key at all — AD-7: never fall back to global env
    team = _team([_agent("architect")], [_task("design", "architect")])
    captured: list = []
    _install_fake_kickoff(
        monkeypatch, captured, _FakeCrewOutput(raw="final", tasks_output=[_FakeTaskOutput("x")])
    )

    CrewAIExecutionEngine().run(team, key_config, "goal")

    [agent_obj] = captured[0].agents
    assert agent_obj.llm.api_key is None


def test_ollama_agent_gets_base_url_not_an_api_key(monkeypatch):
    key_config = KeyConfig(keys={})
    team = _team(
        [_agent("local_agent", provider="ollama", model="llama3.2", api_key_env=None)],
        [_task("design", "local_agent")],
    )
    captured: list = []
    _install_fake_kickoff(
        monkeypatch, captured, _FakeCrewOutput(raw="final", tasks_output=[_FakeTaskOutput("x")])
    )

    CrewAIExecutionEngine().run(team, key_config, "goal")

    [agent_obj] = captured[0].agents
    assert agent_obj.llm.provider == "ollama"
    assert agent_obj.llm.model == "llama3.2"
    assert "localhost:11434" in agent_obj.llm.base_url


def test_ollama_agent_uses_package_specified_base_url_when_present(monkeypatch):
    """A package built with the Ollama sidecar compose stack rewrites
    base_url to the in-network service hostname — that must be honored, not
    silently overridden by the hardcoded localhost default."""
    key_config = KeyConfig(keys={})
    team = _team(
        [
            _agent(
                "local_agent",
                provider="ollama",
                model="llama3.2",
                api_key_env=None,
                base_url="http://ollama:11434",
            )
        ],
        [_task("design", "local_agent")],
    )
    captured: list = []
    _install_fake_kickoff(
        monkeypatch, captured, _FakeCrewOutput(raw="final", tasks_output=[_FakeTaskOutput("x")])
    )

    CrewAIExecutionEngine().run(team, key_config, "goal")

    [agent_obj] = captured[0].agents
    assert "ollama:11434" in agent_obj.llm.base_url


def test_downstream_task_receives_upstream_task_as_context(monkeypatch):
    team = _team(
        [_agent("architect"), _agent("backend_engineer")],
        [
            _task("backend_implementation", "backend_engineer", ["architecture_design"]),
            _task("architecture_design", "architect"),
        ],
    )
    captured: list = []
    _install_fake_kickoff(
        monkeypatch,
        captured,
        _FakeCrewOutput(raw="final", tasks_output=[_FakeTaskOutput("a"), _FakeTaskOutput("b")]),
    )

    result = CrewAIExecutionEngine().run(team, KeyConfig(keys={}), "goal")

    crew = captured[0]
    # topologically sorted: architecture_design (no deps) before backend_implementation
    assert [t.description for t in crew.tasks] == ["do architecture_design", "do backend_implementation"]
    assert crew.tasks[1].context == [crew.tasks[0]]
    assert [tr.name for tr in result.task_results] == ["architecture_design", "backend_implementation"]


def test_task_with_no_dependencies_has_no_context(monkeypatch):
    team = _team([_agent("architect")], [_task("design", "architect")])
    captured: list = []
    _install_fake_kickoff(
        monkeypatch, captured, _FakeCrewOutput(raw="final", tasks_output=[_FakeTaskOutput("x")])
    )

    CrewAIExecutionEngine().run(team, KeyConfig(keys={}), "goal")

    assert captured[0].tasks[0].context is None


def test_orchestrator_agent_selects_hierarchical_process_with_manager(monkeypatch):
    team = _team(
        [_agent("coordinator", is_orchestrator=True), _agent("engineer")],
        [_task("build", "engineer")],
    )
    captured: list = []
    _install_fake_kickoff(
        monkeypatch, captured, _FakeCrewOutput(raw="final", tasks_output=[_FakeTaskOutput("x")])
    )

    CrewAIExecutionEngine().run(team, KeyConfig(keys={}), "goal")

    crew = captured[0]
    assert crew.process == Process.hierarchical
    assert crew.manager_agent.role == "coordinator"
    # CrewAI>=1.x rejects a manager also present in `agents` — only workers here.
    assert [a.role for a in crew.agents] == ["engineer"]


def test_goal_is_passed_through_kickoff_inputs(monkeypatch):
    team = _team([_agent("architect")], [_task("design", "architect")])
    captured_inputs = {}

    def _fake_kickoff(self, inputs=None):
        captured_inputs.update(inputs or {})
        return _FakeCrewOutput(raw="final", tasks_output=[_FakeTaskOutput("x")])

    monkeypatch.setattr(Crew, "kickoff", _fake_kickoff)

    CrewAIExecutionEngine().run(team, KeyConfig(keys={}), "a very specific goal")

    assert captured_inputs == {"goal": "a very specific goal"}


def test_task_output_count_mismatch_raises_clear_error_instead_of_silent_truncation(monkeypatch):
    """CrewAI returning fewer task outputs than tasks submitted must not
    silently drop results via zip()'s truncation — it must fail loudly."""
    team = _team(
        [_agent("architect")],
        [_task("design", "architect"), _task("review", "architect")],
    )
    captured: list = []
    _install_fake_kickoff(
        monkeypatch, captured, _FakeCrewOutput(raw="final", tasks_output=[_FakeTaskOutput("only one")])
    )

    with pytest.raises(RuntimeError, match="task output"):
        CrewAIExecutionEngine().run(team, KeyConfig(keys={}), "goal")
