"""The OpenRouter authoring adapter (Story 2.0, AC 11) — offline, no network.

Constructed through `create_provider` on purpose: AC 11's point is that adding
a provider is a registry row, not a code branch (AD-8), so the test that
matters is "does the factory resolve it", not "does the class exist".
"""
from __future__ import annotations

import pytest

from team_maker.adapters.providers import OpenRouterProvider, create_provider
from team_maker.adapters.providers.registry import OPENROUTER, get_provider
from team_maker.schema.request import ProviderConfig


def test_create_provider_resolves_openrouter():
    provider = create_provider(
        ProviderConfig(provider="openrouter", model="anthropic/claude-sonnet-4-6")
    )

    assert isinstance(provider, OpenRouterProvider)
    assert provider.model == "anthropic/claude-sonnet-4-6"
    assert provider.api_key_env == "OPENROUTER_API_KEY"
    assert provider.base_url == "https://openrouter.ai/api/v1"


def test_explicit_overrides_win():
    provider = create_provider(
        ProviderConfig(
            provider="openrouter",
            model="openai/gpt-4o",
            api_key_env="MY_GATEWAY_KEY",
            base_url="https://gateway.internal/v1/",
        )
    )

    assert provider.api_key_env == "MY_GATEWAY_KEY"
    assert provider.base_url == "https://gateway.internal/v1"  # trailing slash stripped


def test_the_provider_name_is_normalised():
    provider = create_provider(ProviderConfig(provider="  OpenRouter  ", model="x/y"))

    assert isinstance(provider, OpenRouterProvider)


def test_the_key_catalog_and_the_adapter_registry_agree():
    """The catalog already knew OpenRouter as a routing gateway
    (`registry.py:105`); this story makes it selectable as an *authoring*
    provider too. The env var must be the same one in both places."""
    row = get_provider(OPENROUTER)

    assert row is not None
    assert row.env_var == "OPENROUTER_API_KEY"
    assert create_provider(ProviderConfig(provider=OPENROUTER, model="x/y")).api_key_env == (
        row.env_var
    )


def test_a_missing_credential_is_reported_without_a_network_call(monkeypatch):
    """The adapter checks its env var before constructing a client, so this
    stays offline."""
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    provider = create_provider(ProviderConfig(provider="openrouter", model="openai/gpt-4o"))

    with pytest.raises(EnvironmentError, match="OPENROUTER_API_KEY"):
        provider.complete_structured("system", "user", ProviderConfig)


def test_an_unknown_provider_still_raises():
    """AC 10 relies on this: selection is data, and an unknown id raises the
    factory's own `ValueError` rather than being branched on."""
    with pytest.raises(ValueError, match="Unknown provider"):
        create_provider(ProviderConfig(provider="not-a-provider", model="x"))
