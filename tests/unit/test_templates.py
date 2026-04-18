"""Unit tests for the template registry and software delivery template."""
from __future__ import annotations

import pytest

import team_maker.templates  # noqa: F401 — registers templates
from team_maker.domain.models import GeneratedTeam
from team_maker.schema.request import ProviderConfig, RoleDefinition, TeamCreationRequest
from team_maker.templates.registry import get_template, list_templates
from team_maker.templates.software_delivery.template import SoftwareDeliveryTemplate


def test_software_delivery_template_is_registered():
    templates = list_templates()
    assert "software_delivery_team" in templates


def test_unknown_template_raises():
    with pytest.raises(ValueError, match="Unknown template"):
        get_template("nonexistent_template")


def test_get_template_returns_instance():
    tmpl = get_template("software_delivery_team")
    assert isinstance(tmpl, SoftwareDeliveryTemplate)


def test_software_delivery_default_role_names():
    tmpl = SoftwareDeliveryTemplate()
    roles = tmpl.default_role_names()
    assert "architect" in roles
    assert "backend_engineer" in roles
    assert "devops" in roles


def test_generate_returns_generated_team(full_request):
    tmpl = get_template("software_delivery_team")
    team = tmpl.generate(full_request)
    assert isinstance(team, GeneratedTeam)
    assert team.team_name == full_request.team_name
    assert team.template_used == "software_delivery_team"


def test_generate_creates_correct_agent_count(full_request):
    tmpl = get_template("software_delivery_team")
    team = tmpl.generate(full_request)
    assert len(team.agents) == 5  # 5 roles in full_request


def test_generate_fills_in_default_goal(full_request):
    tmpl = get_template("software_delivery_team")
    team = tmpl.generate(full_request)
    architect = next(a for a in team.agents if a.role == "architect")
    assert architect.goal  # should not be empty
    assert "architect" in architect.goal.lower() or "architecture" in architect.goal.lower()


def test_generate_uses_per_role_llm_override(tmp_path):
    request = TeamCreationRequest(
        team_name="Override Team",
        purpose="Testing per-role LLM override for the generator pipeline.",
        output_path=str(tmp_path / "out"),
        desired_roles=[
            RoleDefinition(
                name="architect",
                description="Designs architecture.",
                llm=ProviderConfig(provider="openai", model="gpt-4o"),
            )
        ],
        default_llm=ProviderConfig(provider="anthropic", model="claude-sonnet-4-6"),
    )
    tmpl = get_template("software_delivery_team")
    team = tmpl.generate(request)
    architect = team.agents[0]
    assert architect.routing.provider == "openai"
    assert architect.routing.model == "gpt-4o"


def test_generate_falls_back_to_default_llm(full_request):
    tmpl = get_template("software_delivery_team")
    team = tmpl.generate(full_request)
    for agent in team.agents:
        assert agent.routing.provider == "anthropic"
        assert agent.routing.model == "claude-sonnet-4-6"


def test_generate_only_creates_tasks_for_present_roles(tmp_path):
    """If frontend_engineer is absent, frontend tasks should not appear."""
    request = TeamCreationRequest(
        team_name="Backend Only",
        purpose="Backend-only team without frontend for API service development.",
        output_path=str(tmp_path / "out"),
        desired_roles=[
            RoleDefinition(name="architect", description="Designs architecture."),
            RoleDefinition(name="backend_engineer", description="Builds APIs."),
        ],
    )
    tmpl = get_template("software_delivery_team")
    team = tmpl.generate(request)
    task_roles = {t.agent_role for t in team.tasks}
    assert "frontend_engineer" not in task_roles


def test_generate_propagates_constraints(full_request):
    full_request.constraints = ["no_third_party_storage", "gdpr_compliant"]
    tmpl = get_template("software_delivery_team")
    team = tmpl.generate(full_request)
    assert team.constraints == ["no_third_party_storage", "gdpr_compliant"]
