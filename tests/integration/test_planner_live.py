"""Live integration test: calls real OpenAI API to plan a team, then runs full pipeline.

Skipped automatically when OPENAI_API_KEY is not set.
Run manually with: pytest tests/integration/test_planner_live.py -v -s
"""
from __future__ import annotations

import os
import yaml
import pytest
from pathlib import Path

from team_maker.llm.planner import TeamPlanner
from team_maker.llm.mapper import map_plan_to_team
from team_maker.pipeline.runner import PipelineRunner
from team_maker.schema.request import ProviderConfig, TeamCreationRequest

pytestmark = pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set",
)

_PLANNING_LLM = ProviderConfig(
    provider="openai",
    model="gpt-4o",
    api_key_env="OPENAI_API_KEY",
)


# ---------------------------------------------------------------------------
# Planner unit: AgentPlan structure
# ---------------------------------------------------------------------------

def test_planner_returns_valid_agent_plan():
    request = TeamCreationRequest(
        team_name="API Gateway Team",
        purpose=(
            "Build a secure REST API gateway that routes requests to microservices, "
            "enforces authentication, and logs all traffic."
        ),
        output_path="/tmp/planner_test_out",
        stack="Python, FastAPI, Redis",
        planning_llm=_PLANNING_LLM,
    )
    planner = TeamPlanner.from_request(request)
    plan = planner.plan(request)

    assert plan.team_name == "API Gateway Team"
    assert len(plan.agents) >= 2
    assert len(plan.tasks) >= 2
    assert plan.communication.pattern in ("sequential", "hierarchical", "graph", "group_chat")
    assert plan.primary_framework in ("crewai", "langgraph", "autogen")
    assert plan.reasoning


def test_planner_assigns_tools_to_agents():
    request = TeamCreationRequest(
        team_name="CICD Automation Team",
        purpose="Automate the CI/CD pipeline: build, test, deploy to staging, run smoke tests.",
        output_path="/tmp/planner_cicd_out",
        stack="Python, Docker, GitHub Actions",
        planning_llm=_PLANNING_LLM,
    )
    planner = TeamPlanner.from_request(request)
    plan = planner.plan(request)

    # At least one agent should have tools assigned
    all_tools = [t.name for agent in plan.agents for t in agent.tools]
    assert len(all_tools) > 0


def test_planner_respects_role_hints():
    request = TeamCreationRequest(
        team_name="Data Pipeline Team",
        purpose="Build an ETL pipeline that ingests CSV data, transforms it, and loads it into PostgreSQL.",
        output_path="/tmp/planner_etl_out",
        stack="Python, pandas, PostgreSQL",
        planning_llm=_PLANNING_LLM,
        desired_roles=[],  # empty so planner infers all
    )
    planner = TeamPlanner.from_request(request)
    plan = planner.plan(request)

    roles = [a.role for a in plan.agents]
    assert len(roles) >= 2


# ---------------------------------------------------------------------------
# Full pipeline: planner → GeneratedTeam → disk
# ---------------------------------------------------------------------------

def test_full_pipeline_with_planner(tmp_path):
    """End-to-end: empty desired_roles → planner path → files on disk."""
    request = TeamCreationRequest(
        team_name="Blog Engine Team",
        purpose=(
            "Build a simple blog engine with a REST API, markdown rendering, "
            "user authentication, and an admin dashboard."
        ),
        output_path=str(tmp_path / "blog_team"),
        stack="Python, FastAPI, SQLite",
        planning_llm=_PLANNING_LLM,
        overwrite=True,
    )

    runner = PipelineRunner()
    result = runner.run(request)

    assert result.output_path.exists()
    assert len(result.team.agents) >= 2
    assert len(result.team.tasks) >= 2

    # Core files exist
    for f in ("README.md", "routing_config.yaml", "tools.py", "state_store.py",
              "run_example.py", "requirements.txt", "team_config.yaml"):
        assert (result.output_path / f).exists(), f"Missing: {f}"

    # routing_config.yaml has every agent
    routing = yaml.safe_load((result.output_path / "routing_config.yaml").read_text())["routing"]
    for agent in result.team.agents:
        assert agent.role in routing, f"Agent {agent.role} missing from routing_config"

    # team_config.yaml carries framework info
    tc = yaml.safe_load((result.output_path / "team_config.yaml").read_text())
    assert tc["primary_framework"] in ("crewai", "langgraph", "autogen")
    assert tc["template"] == "llm_planner"


def test_planner_path_used_when_no_roles(tmp_path):
    """Verify template_used == 'llm_planner' when desired_roles is empty."""
    request = TeamCreationRequest(
        team_name="Search Engine Team",
        purpose="Build a web crawler and full-text search engine using inverted index.",
        output_path=str(tmp_path / "search_team"),
        planning_llm=_PLANNING_LLM,
        overwrite=True,
    )
    runner = PipelineRunner()
    result = runner.run(request)
    assert result.team.template_used == "llm_planner"


def test_template_path_used_when_roles_provided(tmp_path):
    """Verify template_used == 'software_delivery_team' when desired_roles given."""
    from team_maker.schema.request import RoleDefinition
    request = TeamCreationRequest(
        team_name="Template Path Team",
        purpose="A simple team to verify the template path is taken when roles are provided.",
        output_path=str(tmp_path / "tmpl_team"),
        desired_roles=[
            RoleDefinition(name="architect", description="Designs architecture."),
            RoleDefinition(name="backend_engineer", description="Builds APIs."),
        ],
        overwrite=True,
    )
    runner = PipelineRunner()
    result = runner.run(request)
    assert result.team.template_used == "software_delivery_team"
