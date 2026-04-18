"""Unit tests for DocsGenerator."""
from __future__ import annotations

from team_maker.domain.models import AgentSpec, GeneratedTeam, ProviderRouting, TaskSpec
from team_maker.generators.docs import DocsGenerator


def _make_team(name: str = "Test Team") -> GeneratedTeam:
    agents = [
        AgentSpec(
            role="architect",
            display_name="Software Architect",
            description="Designs architecture.",
            goal="Produce clear architecture.",
            backstory="Experienced architect.",
            capabilities=["system_design"],
            tools=["code_reader"],
            routing=ProviderRouting(
                provider="anthropic", model="claude-sonnet-4-6", api_key_env="ANTHROPIC_API_KEY"
            ),
        ),
        AgentSpec(
            role="backend_engineer",
            display_name="Backend Engineer",
            description="Builds APIs.",
            goal="Build robust APIs.",
            backstory="Pragmatic backend dev.",
            capabilities=["api_development"],
            tools=["code_writer"],
            routing=ProviderRouting(provider="openai", model="gpt-4o", api_key_env="OPENAI_API_KEY"),
        ),
    ]
    tasks = [
        TaskSpec(
            name="architecture_design",
            description="Design architecture.",
            expected_output="Architecture doc.",
            agent_role="architect",
            dependencies=[],
        ),
        TaskSpec(
            name="backend_implementation",
            description="Build backend.",
            expected_output="Backend code.",
            agent_role="backend_engineer",
            dependencies=["architecture_design"],
        ),
    ]
    return GeneratedTeam(
        team_name=name,
        purpose="Build software end to end.",
        template_used="software_delivery_team",
        agents=agents,
        tasks=tasks,
        stack="Python, PostgreSQL",
    )


def test_readme_contains_team_name():
    gen = DocsGenerator()
    readme = gen.render_readme(_make_team("Alpha Team"))
    assert "Alpha Team" in readme


def test_readme_contains_agent_roles():
    gen = DocsGenerator()
    readme = gen.render_readme(_make_team())
    assert "architect" in readme
    assert "backend_engineer" in readme


def test_readme_contains_quick_start_section():
    gen = DocsGenerator()
    readme = gen.render_readme(_make_team())
    assert "Quick Start" in readme


def test_how_to_run_contains_prerequisites():
    gen = DocsGenerator()
    doc = gen.render_how_to_run(_make_team())
    assert "Prerequisites" in doc


def test_how_to_run_contains_env_vars():
    gen = DocsGenerator()
    doc = gen.render_how_to_run(_make_team())
    assert "ANTHROPIC_API_KEY" in doc
    assert "OPENAI_API_KEY" in doc


def test_how_to_extend_contains_agent_section():
    gen = DocsGenerator()
    doc = gen.render_how_to_extend(_make_team())
    assert "Adding a New Agent" in doc


def test_how_to_extend_contains_task_section():
    gen = DocsGenerator()
    doc = gen.render_how_to_extend(_make_team())
    assert "Adding a New Task" in doc


def test_model_routing_contains_all_roles():
    gen = DocsGenerator()
    doc = gen.render_model_routing(_make_team())
    assert "architect" in doc
    assert "backend_engineer" in doc


def test_model_routing_contains_provider_table():
    gen = DocsGenerator()
    doc = gen.render_model_routing(_make_team())
    assert "anthropic" in doc
    assert "openai" in doc


def test_model_routing_contains_routing_table_headers():
    gen = DocsGenerator()
    doc = gen.render_model_routing(_make_team())
    assert "Provider" in doc
    assert "Model" in doc
    assert "API Key Env Var" in doc


def test_docs_are_non_empty():
    gen = DocsGenerator()
    team = _make_team()
    for render_fn in (gen.render_readme, gen.render_how_to_run,
                      gen.render_how_to_extend, gen.render_model_routing):
        content = render_fn(team)
        assert len(content) > 100
