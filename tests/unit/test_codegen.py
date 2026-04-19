"""Unit tests for the Jinja2 codegen engine and runner templates."""
from __future__ import annotations

import pytest

from team_maker.codegen import render_template
from team_maker.domain.models import AgentSpec, GeneratedTeam, ProviderRouting, TaskSpec
from team_maker.schema.request import SandboxConfig


def _make_team(
    *,
    with_orchestrator: bool = False,
    topology_pattern: str = "sequential",
    topology_edges: list[list[str]] | None = None,
) -> GeneratedTeam:
    routing = ProviderRouting(provider="openai", model="gpt-4o", api_key_env="OPENAI_API_KEY")
    agents = [
        AgentSpec(
            role="coordinator",
            display_name="Coordinator",
            description="Leads the team.",
            goal="Plan and delegate.",
            backstory="Experienced PM.",
            capabilities=["planning"],
            tools=["state_writer"],
            routing=routing,
            is_orchestrator=with_orchestrator,
        ),
        AgentSpec(
            role="engineer",
            display_name="Engineer",
            description="Writes code.",
            goal="Deliver working code.",
            backstory="Senior engineer.",
            capabilities=["coding"],
            tools=["code_writer", "shell"],
            routing=routing,
        ),
    ]
    tasks = [
        TaskSpec(
            name="plan",
            description="Plan the work.",
            expected_output="A plan.",
            agent_role="coordinator",
        ),
        TaskSpec(
            name="build",
            description="Build the thing.",
            expected_output="Working code.",
            agent_role="engineer",
            dependencies=["plan"],
        ),
    ]
    return GeneratedTeam(
        team_name="Test Team",
        purpose="Testing codegen",
        template_used="unit_test",
        agents=agents,
        tasks=tasks,
        primary_framework="crewai",
        topology_pattern=topology_pattern,
        topology_edges=topology_edges or [],
    )


# ---------------------------------------------------------------------------
# tools.py template
# ---------------------------------------------------------------------------


def test_tools_template_renders_default_sandbox():
    out = render_template("tools.py.j2", sandbox=SandboxConfig())
    assert "SANDBOX_IMAGE = \"python:3.12-slim\"" in out
    assert "SANDBOX_NETWORK = \"bridge\"" in out
    assert "SANDBOX_EXTRA_ENV: dict[str, str] = {}" in out
    assert "def shell_command_tool" in out
    assert "def state_reader_tool" in out
    assert "TOOL_REGISTRY" in out
    assert "get_tools_for" in out


def test_tools_template_renders_extra_env():
    sandbox = SandboxConfig(extra_env={"FOO": "bar", "ACCESS_TOKEN": ""})
    out = render_template("tools.py.j2", sandbox=sandbox)
    assert '"FOO": os.environ.get("FOO", "bar")' in out
    assert '"ACCESS_TOKEN": os.environ.get("ACCESS_TOKEN", "")' in out


def test_tools_template_is_valid_python():
    out = render_template("tools.py.j2", sandbox=SandboxConfig())
    compile(out, "<tools.py>", "exec")


# ---------------------------------------------------------------------------
# state_store.py template
# ---------------------------------------------------------------------------


def test_state_store_file_only():
    out = render_template("state_store.py.j2", use_vector=False, use_file=True)
    assert "def read_state" in out
    assert "def write_state" in out
    assert "chromadb" not in out
    assert "vector_upsert" not in out


def test_state_store_with_vector():
    out = render_template("state_store.py.j2", use_vector=True, use_file=True)
    assert "import chromadb" in out
    assert "vector_upsert" in out
    assert "vector_search" in out


def test_state_store_is_valid_python():
    for use_vector in (False, True):
        out = render_template("state_store.py.j2", use_vector=use_vector, use_file=True)
        compile(out, "<state_store.py>", "exec")


# ---------------------------------------------------------------------------
# crewai_runner.py template
# ---------------------------------------------------------------------------


def test_crewai_runner_sequential():
    team = _make_team()
    out = render_template(
        "crewai_runner.py.j2",
        team=team,
        orchestrator_role=None,
        topology_pattern="sequential",
    )
    assert "from crewai import Agent, Task, Crew, Process" in out
    assert "Process.sequential" in out
    assert "Process.hierarchical" not in out
    assert '"coordinator"' in out and '"engineer"' in out


def test_crewai_runner_hierarchical():
    team = _make_team(with_orchestrator=True)
    out = render_template(
        "crewai_runner.py.j2",
        team=team,
        orchestrator_role="coordinator",
        topology_pattern="hierarchical",
    )
    assert "Process.hierarchical" in out
    assert 'manager_agent=agents["coordinator"]' in out


def test_crewai_runner_is_valid_python():
    team = _make_team()
    out = render_template(
        "crewai_runner.py.j2",
        team=team,
        orchestrator_role=None,
        topology_pattern="sequential",
    )
    compile(out, "<run_example.py>", "exec")


# ---------------------------------------------------------------------------
# langgraph_runner.py template
# ---------------------------------------------------------------------------


def test_langgraph_runner_sequential():
    team = _make_team()
    out = render_template(
        "langgraph_runner.py.j2",
        team=team,
        orchestrator_role=None,
        topology_pattern="sequential",
        topology_edges=[],
    )
    assert "from langgraph.graph import StateGraph, END" in out
    assert "ROUTE_TO" not in out
    assert 'workflow.add_node("coordinator"' in out
    assert 'workflow.add_node("engineer"' in out


def test_langgraph_runner_graph_with_conditional_edges():
    team = _make_team(
        topology_pattern="graph",
        topology_edges=[["coordinator", "engineer"], ["engineer", "coordinator"]],
    )
    out = render_template(
        "langgraph_runner.py.j2",
        team=team,
        orchestrator_role=None,
        topology_pattern="graph",
        topology_edges=[["coordinator", "engineer"], ["engineer", "coordinator"]],
    )
    assert "ROUTE_TO" in out
    assert "make_router" in out
    assert "add_conditional_edges" in out
    assert "_EDGE_MAP" in out


def test_langgraph_runner_is_valid_python():
    team = _make_team()
    out = render_template(
        "langgraph_runner.py.j2",
        team=team,
        orchestrator_role=None,
        topology_pattern="sequential",
        topology_edges=[],
    )
    compile(out, "<run_example.py>", "exec")


# ---------------------------------------------------------------------------
# autogen_runner.py template
# ---------------------------------------------------------------------------


def test_autogen_runner_contains_dual_compat():
    team = _make_team()
    out = render_template(
        "autogen_runner.py.j2",
        team=team,
        orchestrator_role=None,
        topology_pattern="round_robin",
    )
    assert "def _run_v4" in out
    assert "def _run_v2" in out
    assert "autogen_agentchat" in out
    assert "import autogen" in out


def test_autogen_runner_is_valid_python():
    team = _make_team(with_orchestrator=True)
    out = render_template(
        "autogen_runner.py.j2",
        team=team,
        orchestrator_role="coordinator",
        topology_pattern="round_robin",
    )
    compile(out, "<run_example.py>", "exec")


# ---------------------------------------------------------------------------
# Strict undefined — ensure missing context vars fail loudly
# ---------------------------------------------------------------------------


def test_strict_undefined_raises_on_missing_context():
    with pytest.raises(Exception):
        render_template("tools.py.j2")  # missing `sandbox`
