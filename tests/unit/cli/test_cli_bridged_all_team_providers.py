"""Unit tests for `_bridged_all_team_providers` (Task 2, Story 4.5, AC 2).

Exercises the helper directly rather than through the full `compose --build`
CLI flow, since these are regressions in its own provider-collection and
context-management logic:
- `request.default_llm` (the documented `role.llm -> default_llm -> planning_llm`
  fallback, per api/routings.py) was silently skipped.
- Manual `ctx.__enter__()` looping left already-entered contexts unbridged on a
  later entry failure, instead of using `contextlib.ExitStack`.
- A `set` of `(provider, env_var)` pairs made bridging non-deterministic when
  two roles referenced the same provider with different `api_key_env`
  overrides.
"""
from __future__ import annotations

import os

from pydantic import SecretStr

from team_maker.cli import _bridged_all_team_providers
from team_maker.keyconfig import KeyConfig
from team_maker.schema.request import ProviderConfig, RoleDefinition, TeamCreationRequest


def _key_config(**provider_to_secret: str) -> KeyConfig:
    return KeyConfig(keys={name: SecretStr(value) for name, value in provider_to_secret.items()})


def _request(tmp_path, **overrides) -> TeamCreationRequest:
    payload = {
        "team_name": "Docs Team",
        "purpose": "Write and maintain product documentation.",
        "output_path": str(tmp_path / "docs_team"),
        "desired_roles": [{"name": "writer", "description": "Writes documentation."}],
    }
    payload.update(overrides)
    return TeamCreationRequest(**payload)


def test_bridges_role_llm_provider(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    request = _request(
        tmp_path,
        desired_roles=[
            {
                "name": "writer",
                "description": "Writes documentation.",
                "llm": {"provider": "openai", "model": "gpt-4o", "api_key_env": "OPENAI_API_KEY"},
            }
        ],
    )
    key_config = _key_config(openai="sk-role-secret")

    with _bridged_all_team_providers(key_config, request):
        assert os.environ["OPENAI_API_KEY"] == "sk-role-secret"
    assert "OPENAI_API_KEY" not in os.environ


def test_bridges_default_llm_when_role_has_no_override(tmp_path, monkeypatch):
    """Regression: default_llm is the documented role.llm -> default_llm fallback
    (api/routings.py) and must be bridged even though no role sets `llm` directly."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    request = _request(
        tmp_path,
        default_llm={"provider": "openai", "model": "gpt-4o", "api_key_env": "OPENAI_API_KEY"},
        desired_roles=[{"name": "writer", "description": "Writes documentation."}],
    )
    key_config = _key_config(openai="sk-default-secret")

    with _bridged_all_team_providers(key_config, request):
        assert os.environ["OPENAI_API_KEY"] == "sk-default-secret"
    assert "OPENAI_API_KEY" not in os.environ


def test_bridges_planning_llm_and_role_llm_together(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    request = _request(
        tmp_path,
        planning_llm={"provider": "anthropic", "model": "claude-sonnet-4-6", "api_key_env": "ANTHROPIC_API_KEY"},
        desired_roles=[
            {
                "name": "writer",
                "description": "Writes documentation.",
                "llm": {"provider": "openai", "model": "gpt-4o", "api_key_env": "OPENAI_API_KEY"},
            }
        ],
    )
    key_config = _key_config(anthropic="sk-plan-secret", openai="sk-role-secret")

    with _bridged_all_team_providers(key_config, request):
        assert os.environ["ANTHROPIC_API_KEY"] == "sk-plan-secret"
        assert os.environ["OPENAI_API_KEY"] == "sk-role-secret"
    assert "ANTHROPIC_API_KEY" not in os.environ
    assert "OPENAI_API_KEY" not in os.environ


def test_same_provider_from_two_roles_bridges_deterministically(tmp_path, monkeypatch):
    """Regression: previously a `set[tuple[provider, env_var]]` made the outcome
    depend on non-deterministic set-iteration order when two roles referenced
    the same provider with different `api_key_env` overrides. First role in
    request order must win, every run."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY_2", raising=False)
    request = _request(
        tmp_path,
        desired_roles=[
            RoleDefinition(
                name="writer",
                description="Writes documentation.",
                llm=ProviderConfig(provider="openai", model="gpt-4o", api_key_env="OPENAI_API_KEY"),
            ),
            RoleDefinition(
                name="editor",
                description="Edits documentation.",
                llm=ProviderConfig(provider="openai", model="gpt-4o", api_key_env="OPENAI_API_KEY_2"),
            ),
        ],
    )
    key_config = _key_config(openai="sk-shared-secret")

    with _bridged_all_team_providers(key_config, request):
        assert os.environ["OPENAI_API_KEY"] == "sk-shared-secret"
        assert "OPENAI_API_KEY_2" not in os.environ


def test_restores_previous_env_values_on_exit(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "pre-existing-value")
    request = _request(
        tmp_path,
        desired_roles=[
            {
                "name": "writer",
                "description": "Writes documentation.",
                "llm": {"provider": "openai", "model": "gpt-4o", "api_key_env": "OPENAI_API_KEY"},
            }
        ],
    )
    key_config = _key_config(openai="sk-role-secret")

    with _bridged_all_team_providers(key_config, request):
        assert os.environ["OPENAI_API_KEY"] == "sk-role-secret"
    assert os.environ["OPENAI_API_KEY"] == "pre-existing-value"


def test_no_providers_to_bridge_is_a_no_op(tmp_path):
    request = _request(tmp_path)
    key_config = _key_config()

    with _bridged_all_team_providers(key_config, request):
        pass  # must not raise
