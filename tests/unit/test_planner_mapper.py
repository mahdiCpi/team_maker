"""Unit tests for the AgentPlan → GeneratedTeam mapper."""
from __future__ import annotations

import pytest

from team_maker.domain.models import GeneratedTeam
from team_maker.llm.mapper import map_plan_to_team, _infer_provider, _resolve_routing
from team_maker.llm.schemas import (
    AgentDesign,
    AgentPlan,
    CommunicationTopology,
    TaskDesign,
    ToolAssignment,
)
from team_maker.schema.request import ProviderConfig, TeamCreationRequest


def _make_request(**kwargs) -> TeamCreationRequest:
    defaults = dict(
        team_name="Test Team",
        purpose="A test team for unit testing the planner mapper.",
        output_path="/tmp/test_out",
    )
    defaults.update(kwargs)
    return TeamCreationRequest(**defaults)


def _make_plan(
    agents=None,
    tasks=None,
    pattern="sequential",
    framework="crewai",
) -> AgentPlan:
    if agents is None:
        agents = [
            AgentDesign(
                role="developer",
                display_name="Developer",
                goal="Write code.",
                backstory="An experienced developer.",
                tools=[ToolAssignment(name="code_writer", reason="writes code")],
                is_orchestrator=False,
                can_delegate=False,
            )
        ]
    if tasks is None:
        tasks = [
            TaskDesign(
                name="implement_feature",
                description="Implement the feature.",
                expected_output="Working code.",
                assigned_to="developer",
            )
        ]
    return AgentPlan(
        team_name="Test Team",
        agents=agents,
        tasks=tasks,
        communication=CommunicationTopology(pattern=pattern, description="test"),
        primary_framework=framework,
        reasoning="Test reasoning.",
    )


# ---------------------------------------------------------------------------
# _infer_provider
# ---------------------------------------------------------------------------

def test_infer_provider_openai():
    assert _infer_provider("gpt-4o") == "openai"
    assert _infer_provider("o1-preview") == "openai"
    assert _infer_provider("o3-mini") == "openai"


def test_infer_provider_anthropic():
    assert _infer_provider("claude-sonnet-4-6") == "anthropic"
    assert _infer_provider("claude-opus-4-7") == "anthropic"


def test_infer_provider_ollama_fallback():
    assert _infer_provider("llama3.2") == "ollama"
    assert _infer_provider("mistral") == "ollama"


# ---------------------------------------------------------------------------
# _resolve_routing
# ---------------------------------------------------------------------------

def test_resolve_routing_uses_llm_override():
    routing = _resolve_routing("gpt-4o", None)
    assert routing.provider == "openai"
    assert routing.model == "gpt-4o"
    assert routing.api_key_env == "OPENAI_API_KEY"


def test_resolve_routing_uses_default_llm_when_no_override():
    default = ProviderConfig(provider="anthropic", model="claude-sonnet-4-6", api_key_env="ANTHROPIC_API_KEY")
    routing = _resolve_routing(None, default)
    assert routing.provider == "anthropic"
    assert routing.model == "claude-sonnet-4-6"


def test_resolve_routing_falls_back_to_hardcoded_default():
    routing = _resolve_routing(None, None)
    assert routing.provider == "anthropic"
    assert routing.model == "claude-sonnet-4-6"


# ---------------------------------------------------------------------------
# map_plan_to_team
# ---------------------------------------------------------------------------

def test_map_returns_generated_team():
    plan = _make_plan()
    team = map_plan_to_team(plan, _make_request())
    assert isinstance(team, GeneratedTeam)


def test_map_preserves_team_name():
    plan = _make_plan()
    team = map_plan_to_team(plan, _make_request())
    assert team.team_name == "Test Team"


def test_map_converts_agents():
    plan = _make_plan()
    team = map_plan_to_team(plan, _make_request())
    assert len(team.agents) == 1
    agent = team.agents[0]
    assert agent.role == "developer"
    assert agent.goal == "Write code."
    assert "code_writer" in agent.tools


def test_map_converts_tasks():
    plan = _make_plan()
    team = map_plan_to_team(plan, _make_request())
    assert len(team.tasks) == 1
    task = team.tasks[0]
    assert task.name == "implement_feature"
    assert task.agent_role == "developer"


def test_map_sets_primary_framework():
    plan = _make_plan(framework="langgraph")
    team = map_plan_to_team(plan, _make_request())
    assert team.primary_framework == "langgraph"


def test_map_sets_topology_pattern():
    plan = _make_plan(pattern="hierarchical")
    team = map_plan_to_team(plan, _make_request())
    assert team.topology_pattern == "hierarchical"


def test_map_sets_orchestrator_flag():
    agents = [
        AgentDesign(
            role="coordinator",
            display_name="Coordinator",
            goal="Coordinate.",
            backstory="An orchestrator.",
            is_orchestrator=True,
            can_delegate=True,
        ),
        AgentDesign(
            role="worker",
            display_name="Worker",
            goal="Work.",
            backstory="A worker.",
        ),
    ]
    plan = _make_plan(agents=agents)
    team = map_plan_to_team(plan, _make_request())
    coordinator = next(a for a in team.agents if a.role == "coordinator")
    worker = next(a for a in team.agents if a.role == "worker")
    assert coordinator.is_orchestrator is True
    assert worker.is_orchestrator is False


def test_map_uses_default_llm_from_request():
    plan = _make_plan()
    request = _make_request(
        default_llm=ProviderConfig(provider="openai", model="gpt-4o", api_key_env="OPENAI_API_KEY")
    )
    team = map_plan_to_team(plan, request)
    assert team.agents[0].routing.provider == "openai"
    assert team.agents[0].routing.model == "gpt-4o"


def test_map_agent_llm_override_takes_priority():
    agents = [
        AgentDesign(
            role="dev",
            display_name="Dev",
            goal="Code.",
            backstory="Coder.",
            llm_override="gpt-4o",
        )
    ]
    plan = _make_plan(agents=agents)
    request = _make_request(
        default_llm=ProviderConfig(provider="anthropic", model="claude-sonnet-4-6")
    )
    team = map_plan_to_team(plan, request)
    assert team.agents[0].routing.provider == "openai"
    assert team.agents[0].routing.model == "gpt-4o"


def test_map_preserves_task_dependencies():
    tasks = [
        TaskDesign(name="task_a", description="A", expected_output="out_a", assigned_to="developer"),
        TaskDesign(name="task_b", description="B", expected_output="out_b", assigned_to="developer", depends_on=["task_a"]),
    ]
    plan = _make_plan(tasks=tasks)
    team = map_plan_to_team(plan, _make_request())
    task_b = next(t for t in team.tasks if t.name == "task_b")
    assert "task_a" in task_b.dependencies


def test_map_template_used_is_llm_planner():
    plan = _make_plan()
    team = map_plan_to_team(plan, _make_request())
    assert team.template_used == "llm_planner"


def test_map_stores_planner_reasoning():
    plan = _make_plan()
    team = map_plan_to_team(plan, _make_request())
    assert team.planner_reasoning == "Test reasoning."


# ---------------------------------------------------------------------------
# build_system_prompt
# ---------------------------------------------------------------------------


def test_build_system_prompt_default_contains_catalog():
    from team_maker.llm.prompts import build_system_prompt, AVAILABLE_TOOLS

    prompt = build_system_prompt()
    for name in AVAILABLE_TOOLS:
        assert name in prompt


def test_build_system_prompt_merges_extra_tools():
    from team_maker.llm.prompts import build_system_prompt

    extra = {"slack_notifier": "Send a Slack message to a channel."}
    prompt = build_system_prompt(extra_tools=extra)
    assert "slack_notifier" in prompt
    assert "Send a Slack message" in prompt
    # built-in tools still present
    assert "git_account" in prompt


def test_build_system_prompt_extra_tools_note():
    from team_maker.llm.prompts import build_system_prompt

    extra = {"stripe_tool": "Charge a credit card via Stripe API."}
    prompt = build_system_prompt(extra_tools=extra)
    assert "User-supplied tools" in prompt
    assert "`stripe_tool`" in prompt


def test_build_system_prompt_no_extra_same_as_constant():
    from team_maker.llm.prompts import build_system_prompt, SYSTEM_PROMPT

    assert build_system_prompt() == SYSTEM_PROMPT
