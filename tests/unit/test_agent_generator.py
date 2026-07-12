"""Unit tests for AgentGenerator."""
from __future__ import annotations

import yaml

from team_maker.domain.models import AgentSpec, ProviderRouting
from team_maker.generators.agent import AgentGenerator


def _make_agent(**kwargs) -> AgentSpec:
    defaults = dict(
        role="architect",
        display_name="Software Architect",
        description="Designs the system.",
        goal="Produce a clear architecture.",
        backstory="Experienced architect.",
        capabilities=["system_design", "api_design"],
        tools=["code_reader"],
        routing=ProviderRouting(provider="anthropic", model="claude-sonnet-4-6"),
        is_optional=False,
    )
    defaults.update(kwargs)
    return AgentSpec(**defaults)


def test_render_returns_valid_yaml():
    gen = AgentGenerator()
    agent = _make_agent()
    rendered = gen.render(agent)
    parsed = yaml.safe_load(rendered)
    assert parsed["role"] == "architect"


def test_render_includes_all_required_fields():
    gen = AgentGenerator()
    agent = _make_agent()
    parsed = yaml.safe_load(gen.render(agent))
    for field in ("role", "display_name", "description", "goal", "backstory",
                  "capabilities", "tools", "is_optional", "is_orchestrator"):
        assert field in parsed, f"Missing field: {field}"


def test_render_does_not_include_llm():
    # LLM config lives in routing_config.yaml — agents/*.yaml must not duplicate it.
    gen = AgentGenerator()
    agent = _make_agent()
    parsed = yaml.safe_load(gen.render(agent))
    assert "llm" not in parsed


def test_render_optional_flag():
    gen = AgentGenerator()
    agent = _make_agent(is_optional=True)
    parsed = yaml.safe_load(gen.render(agent))
    assert parsed["is_optional"] is True


def test_render_orchestrator_flag():
    gen = AgentGenerator()
    agent = _make_agent(is_orchestrator=True)
    parsed = yaml.safe_load(gen.render(agent))
    assert parsed["is_orchestrator"] is True


def test_filename_uses_role():
    gen = AgentGenerator()
    agent = _make_agent(role="backend_engineer")
    assert gen.filename(agent) == "backend_engineer.yaml"
