"""Unit tests for model_registry resolution, stack flattening, and auxiliary_resources_dir alias."""
from __future__ import annotations

import pytest
from pydantic import ValidationError
from unittest.mock import MagicMock, patch

from team_maker.schema.request import ProviderConfig, RoleDefinition, TeamCreationRequest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REGISTRY = {
    "claude_opus_47": {
        "provider": "anthropic",
        "model": "claude-opus-4-7",
        "api_key_env": "ANTHROPIC_API_KEY",
        "context_window": 200000,           # extra — must be stripped
        "strengths": ["architecture"],       # extra — must be stripped
        "primary_use_in_this_team": "coding", # extra — must be stripped
    },
    "gpt_4o": {
        "provider": "openai",
        "model": "gpt-4o",
        "api_key_env": "OPENAI_API_KEY",
    },
    "gemini_pro": {
        "provider": "google",
        "model": "gemini-1.5-pro",
        "api_key_env": "GOOGLE_AI_API_KEY",
    },
}


def _base() -> dict:
    return dict(
        team_name="Registry Team",
        purpose="A team for testing model registry resolution across multiple providers.",
        output_path="/tmp/registry_out",
        desired_roles=[
            {"name": "architect", "description": "Designs the system architecture."}
        ],
        model_registry=_REGISTRY,
    )


# ---------------------------------------------------------------------------
# model_registry — default_llm resolution
# ---------------------------------------------------------------------------

def test_default_llm_string_resolved_via_registry():
    req = TeamCreationRequest.model_validate({**_base(), "default_llm": "claude_opus_47"})
    assert req.default_llm is not None
    assert req.default_llm.provider == "anthropic"
    assert req.default_llm.model == "claude-opus-4-7"
    assert req.default_llm.api_key_env == "ANTHROPIC_API_KEY"


def test_registry_extra_fields_stripped_from_resolved_llm():
    req = TeamCreationRequest.model_validate({**_base(), "default_llm": "claude_opus_47"})
    d = req.default_llm.model_dump()
    assert "context_window" not in d
    assert "strengths" not in d
    assert "primary_use_in_this_team" not in d


def test_planning_llm_string_resolved_via_registry():
    req = TeamCreationRequest.model_validate({**_base(), "planning_llm": "gpt_4o"})
    assert req.planning_llm.provider == "openai"
    assert req.planning_llm.model == "gpt-4o"


def test_inline_provider_config_unchanged_when_registry_present():
    """An already-inline ProviderConfig dict should pass through untouched."""
    req = TeamCreationRequest.model_validate({
        **_base(),
        "default_llm": {"provider": "openai", "model": "gpt-4o-mini", "api_key_env": "OPENAI_API_KEY"},
    })
    assert req.default_llm.model == "gpt-4o-mini"


def test_unknown_registry_key_left_as_is_and_fails_validation():
    """An unresolvable string reference stays as-is and fails ProviderConfig validation."""
    with pytest.raises(ValidationError) as exc_info:
        TeamCreationRequest.model_validate({**_base(), "default_llm": "nonexistent_model"})
    assert "default_llm" in str(exc_info.value)


# ---------------------------------------------------------------------------
# model_registry — per-role llm resolution
# ---------------------------------------------------------------------------

def test_role_llm_string_resolved_via_registry():
    raw = {
        **_base(),
        "desired_roles": [
            {
                "name": "backend_engineer",
                "description": "Builds APIs and services.",
                "llm": "claude_opus_47",
            }
        ],
    }
    req = TeamCreationRequest.model_validate(raw)
    role = req.desired_roles[0]
    assert role.llm is not None
    assert role.llm.provider == "anthropic"
    assert role.llm.model == "claude-opus-4-7"


def test_multiple_roles_each_resolved_to_correct_provider():
    raw = {
        **_base(),
        "desired_roles": [
            {"name": "architect", "description": "Designs system.", "llm": "claude_opus_47"},
            {"name": "engineer", "description": "Implements features.", "llm": "gpt_4o"},
            {"name": "analyst", "description": "Analyses data.", "llm": "gemini_pro"},
        ],
    }
    req = TeamCreationRequest.model_validate(raw)
    assert req.desired_roles[0].llm.provider == "anthropic"
    assert req.desired_roles[1].llm.provider == "openai"
    assert req.desired_roles[2].llm.provider == "google"


def test_role_without_llm_unaffected_by_registry():
    raw = {
        **_base(),
        "desired_roles": [
            {"name": "coordinator", "description": "Coordinates the team."},
        ],
    }
    req = TeamCreationRequest.model_validate(raw)
    assert req.desired_roles[0].llm is None


def test_registry_absent_and_inline_llm_still_works():
    """Without a registry, inline ProviderConfig dicts should still validate."""
    raw = {
        "team_name": "No Registry Team",
        "purpose": "A team without a model registry, using inline provider configs.",
        "output_path": "/tmp/no_registry",
        "desired_roles": [
            {
                "name": "developer",
                "description": "Writes code.",
                "llm": {"provider": "anthropic", "model": "claude-sonnet-4-6", "api_key_env": "ANTHROPIC_API_KEY"},
            }
        ],
    }
    req = TeamCreationRequest.model_validate(raw)
    assert req.desired_roles[0].llm.model == "claude-sonnet-4-6"


# ---------------------------------------------------------------------------
# stack dict → string flattening
# ---------------------------------------------------------------------------

def test_stack_dict_flattened_to_string():
    raw = {
        **_base(),
        "stack": {
            "language": "Python 3.11",
            "backend_framework": "FastAPI",
            "database": "PostgreSQL 15",
            "stock_integration": "deferred_to_m3",
            "vector_db_decision_owner": "product_architect_tech_lead",
        },
    }
    req = TeamCreationRequest.model_validate(raw)
    assert isinstance(req.stack, str)
    assert "Python 3.11" in req.stack
    assert "FastAPI" in req.stack
    assert "PostgreSQL 15" in req.stack


def test_stack_dict_excludes_deferred_values():
    raw = {
        **_base(),
        "stack": {"primary": "Python 3.11", "secondary": "deferred_to_m3"},
    }
    req = TeamCreationRequest.model_validate(raw)
    assert "deferred_to_m3" not in req.stack


def test_stack_dict_excludes_bare_identifier_values():
    """Values that look like role names (bare snake_case) should be excluded."""
    raw = {
        **_base(),
        "stack": {"tool": "FastAPI", "owner": "product_architect_tech_lead"},
    }
    req = TeamCreationRequest.model_validate(raw)
    assert "product_architect_tech_lead" not in req.stack
    assert "FastAPI" in req.stack


def test_stack_string_passes_through_unchanged():
    raw = {**_base(), "stack": "Python 3.11, FastAPI"}
    req = TeamCreationRequest.model_validate(raw)
    assert req.stack == "Python 3.11, FastAPI"


# ---------------------------------------------------------------------------
# auxiliary_resources_dir → context_dir alias
# ---------------------------------------------------------------------------

def test_auxiliary_resources_dir_maps_to_context_dir(tmp_path):
    raw = {**_base(), "auxiliary_resources_dir": str(tmp_path)}
    req = TeamCreationRequest.model_validate(raw)
    assert req.context_dir == str(tmp_path.resolve())


def test_context_dir_takes_precedence_over_auxiliary_resources_dir(tmp_path):
    other = tmp_path / "other"
    other.mkdir()
    raw = {
        **_base(),
        "context_dir": str(tmp_path),
        "auxiliary_resources_dir": str(other),
    }
    req = TeamCreationRequest.model_validate(raw)
    assert req.context_dir == str(tmp_path.resolve())


def test_auxiliary_resources_dir_nonexistent_raises(tmp_path):
    raw = {**_base(), "auxiliary_resources_dir": str(tmp_path / "missing")}
    with pytest.raises(ValidationError) as exc_info:
        TeamCreationRequest.model_validate(raw)
    assert "context_dir" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Google provider — create_provider factory
# ---------------------------------------------------------------------------

def test_create_provider_returns_google_provider():
    from team_maker.llm.providers import create_provider, GoogleProvider
    cfg = ProviderConfig(provider="google", model="gemini-1.5-pro", api_key_env="GOOGLE_AI_API_KEY")
    provider = create_provider(cfg)
    assert isinstance(provider, GoogleProvider)
    assert provider.model == "gemini-1.5-pro"
    assert provider.api_key_env == "GOOGLE_AI_API_KEY"


def test_create_provider_google_defaults():
    from team_maker.llm.providers import create_provider, GoogleProvider
    cfg = ProviderConfig(provider="google", model="gemini-1.5-pro")
    provider = create_provider(cfg)
    assert isinstance(provider, GoogleProvider)
    assert provider.api_key_env == "GOOGLE_AI_API_KEY"


def test_create_provider_xai_defaults():
    from team_maker.llm.providers import create_provider, XAIProvider
    cfg = ProviderConfig(provider="xai", model="grok-2")
    provider = create_provider(cfg)
    assert isinstance(provider, XAIProvider)
    assert provider.api_key_env == "XAI_API_KEY"
    assert provider.base_url == "https://api.x.ai/v1"


def test_create_provider_unknown_raises():
    from team_maker.llm.providers import create_provider
    cfg = ProviderConfig(provider="unknown_provider", model="some-model")
    with pytest.raises(ValueError, match="Unknown provider"):
        create_provider(cfg)


def test_google_provider_missing_api_key_raises(monkeypatch):
    from team_maker.llm.providers import GoogleProvider
    from team_maker.llm.schemas import AgentPlan
    monkeypatch.delenv("GOOGLE_AI_API_KEY", raising=False)
    provider = GoogleProvider(model="gemini-1.5-pro", api_key_env="GOOGLE_AI_API_KEY")
    mock_genai = MagicMock()
    with patch.dict("sys.modules", {"google.generativeai": mock_genai}):
        with pytest.raises(EnvironmentError, match="GOOGLE_AI_API_KEY"):
            provider.complete_structured("sys", "user", AgentPlan)


def test_google_provider_sdk_not_installed_raises(monkeypatch):
    from team_maker.llm.providers import GoogleProvider
    from team_maker.llm.schemas import AgentPlan
    monkeypatch.setenv("GOOGLE_AI_API_KEY", "fake-key")
    provider = GoogleProvider()
    with patch.dict("sys.modules", {"google.generativeai": None}):
        with pytest.raises(ImportError):
            provider.complete_structured("sys", "user", AgentPlan)


def test_google_provider_parses_json_response(monkeypatch):
    """GoogleProvider correctly parses a valid JSON response from the SDK."""
    from team_maker.llm.providers import GoogleProvider
    from team_maker.llm.schemas import AgentPlan, AgentDesign, TaskDesign, CommunicationTopology

    monkeypatch.setenv("GOOGLE_AI_API_KEY", "fake-key")

    minimal_plan = {
        "team_name": "Test",
        "agents": [{"role": "dev", "display_name": "Dev", "goal": "Build.", "backstory": "A dev."}],
        "tasks": [{"name": "build", "description": "Build it.", "expected_output": "Code.", "assigned_to": "dev"}],
        "communication": {"pattern": "sequential", "description": "One by one."},
        "primary_framework": "crewai",
        "reasoning": "Simple team.",
    }

    import json as _json
    mock_response = MagicMock()
    mock_response.text = _json.dumps(minimal_plan)

    mock_model = MagicMock()
    mock_model.generate_content.return_value = mock_response

    mock_genai = MagicMock()
    mock_genai.GenerativeModel.return_value = mock_model
    mock_genai.types.GenerationConfig.return_value = {}

    with patch.dict("sys.modules", {"google.generativeai": mock_genai}):
        provider = GoogleProvider(model="gemini-1.5-pro", api_key_env="GOOGLE_AI_API_KEY")
        result = provider.complete_structured("system prompt", "user prompt", AgentPlan)

    assert result.team_name == "Test"
    assert result.agents[0].role == "dev"
