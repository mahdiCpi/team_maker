"""Unit tests for the research content team template."""
from __future__ import annotations

import pytest

from team_maker.domain.models import GeneratedTeam
from team_maker.schema.request import RoleDefinition, TeamCreationRequest
from team_maker.templates.registry import get_template


def test_research_content_template_is_registered():
    from team_maker.templates.registry import list_templates
    templates = list_templates()
    assert "research_content_team" in templates


def test_research_content_default_role_names():
    tmpl = get_template("research_content_team")
    roles = tmpl.default_role_names()
    assert "researcher" in roles
    assert "writer" in roles
    assert "fact_checker" in roles
    assert "editor" in roles


def test_research_content_default_task_names():
    tmpl = get_template("research_content_team")
    tasks = tmpl.default_task_names()
    assert "research_topic" in tasks
    assert "draft_content" in tasks
    assert "fact_check" in tasks
    assert "edit_content" in tasks


def test_research_content_generate_returns_generated_team(tmp_path):
    request = TeamCreationRequest(
        team_name="Research Team",
        purpose="Create research content.",
        output_path=str(tmp_path / "research"),
        desired_roles=[
            RoleDefinition(name="researcher", description="Gathers facts."),
            RoleDefinition(name="writer", description="Writes content."),
            RoleDefinition(name="fact_checker", description="Verifies facts."),
            RoleDefinition(name="editor", description="Edits content."),
        ],
    )
    tmpl = get_template("research_content_team")
    team = tmpl.generate(request)
    assert isinstance(team, GeneratedTeam)
    assert team.team_name == "Research Team"
    assert team.template_used == "research_content_team"
    assert len(team.agents) == 4
    assert len(team.tasks) == 4


def test_research_content_task_dag():
    """Test that research content tasks have the correct dependency order."""
    request = TeamCreationRequest(
        team_name="Research Team",
        purpose="Create research content.",
        output_path="/tmp/research",
        desired_roles=[
            RoleDefinition(name="researcher", description="Gathers facts."),
            RoleDefinition(name="writer", description="Writes content."),
            RoleDefinition(name="fact_checker", description="Verifies facts."),
            RoleDefinition(name="editor", description="Edits content."),
        ],
    )
    tmpl = get_template("research_content_team")
    team = tmpl.generate(request)
    
    # Build task name -> task map
    task_map = {t.name: t for t in team.tasks}
    
    # research_topic has no dependencies
    assert task_map["research_topic"].dependencies == []
    
    # draft_content depends on research_topic
    assert "research_topic" in task_map["draft_content"].dependencies
    
    # fact_check depends on draft_content
    assert "draft_content" in task_map["fact_check"].dependencies
    
    # edit_content depends on fact_check
    assert "fact_check" in task_map["edit_content"].dependencies


def test_research_content_editor_is_orchestrator():
    """Test that the editor role is marked as orchestrator."""
    request = TeamCreationRequest(
        team_name="Research Team",
        purpose="Create research content.",
        output_path="/tmp/research",
        desired_roles=[
            RoleDefinition(name="editor", description="Edits content."),
        ],
    )
    tmpl = get_template("research_content_team")
    team = tmpl.generate(request)
    
    editor = next(a for a in team.agents if a.role == "editor")
    assert editor.is_orchestrator is True
