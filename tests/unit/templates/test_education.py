"""Unit tests for the education team template."""
from __future__ import annotations

import pytest

from team_maker.domain.models import GeneratedTeam
from team_maker.schema.request import RoleDefinition, TeamCreationRequest
from team_maker.templates.registry import get_template


def test_education_template_is_registered():
    from team_maker.templates.registry import list_templates
    templates = list_templates()
    assert "baseline_education_team" in templates


def test_education_default_role_names():
    tmpl = get_template("baseline_education_team")
    roles = tmpl.default_role_names()
    assert "tutor" in roles
    assert "researcher" in roles
    assert "clarity_reviewer" in roles


def test_education_default_task_names():
    tmpl = get_template("baseline_education_team")
    tasks = tmpl.default_task_names()
    assert "research_topic" in tasks
    assert "draft_explanation" in tasks
    assert "review_for_clarity" in tasks


def test_education_generate_returns_generated_team(tmp_path):
    request = TeamCreationRequest(
        team_name="Education Team",
        purpose="Create educational content.",
        output_path=str(tmp_path / "education"),
        desired_roles=[
            RoleDefinition(name="tutor", description="Explains topics."),
            RoleDefinition(name="researcher", description="Gathers facts."),
            RoleDefinition(name="clarity_reviewer", description="Reviews for clarity."),
        ],
    )
    tmpl = get_template("baseline_education_team")
    team = tmpl.generate(request)
    assert isinstance(team, GeneratedTeam)
    assert team.team_name == "Education Team"
    assert team.template_used == "baseline_education_team"
    assert len(team.agents) == 3
    assert len(team.tasks) == 3


def test_education_task_dag():
    """Test that education tasks have the correct dependency order."""
    request = TeamCreationRequest(
        team_name="Education Team",
        purpose="Create educational content.",
        output_path="/tmp/education",
        desired_roles=[
            RoleDefinition(name="tutor", description="Explains topics."),
            RoleDefinition(name="researcher", description="Gathers facts."),
            RoleDefinition(name="clarity_reviewer", description="Reviews for clarity."),
        ],
    )
    tmpl = get_template("baseline_education_team")
    team = tmpl.generate(request)
    
    # Build task name -> task map
    task_map = {t.name: t for t in team.tasks}
    
    # research_topic has no dependencies
    assert task_map["research_topic"].dependencies == []
    
    # draft_explanation depends on research_topic
    assert "research_topic" in task_map["draft_explanation"].dependencies
    
    # review_for_clarity depends on draft_explanation
    assert "draft_explanation" in task_map["review_for_clarity"].dependencies


def test_education_tutor_is_orchestrator():
    """Test that the tutor role is marked as orchestrator."""
    request = TeamCreationRequest(
        team_name="Education Team",
        purpose="Create educational content.",
        output_path="/tmp/education",
        desired_roles=[
            RoleDefinition(name="tutor", description="Explains topics."),
        ],
    )
    tmpl = get_template("baseline_education_team")
    team = tmpl.generate(request)
    
    tutor = next(a for a in team.agents if a.role == "tutor")
    assert tutor.is_orchestrator is True
