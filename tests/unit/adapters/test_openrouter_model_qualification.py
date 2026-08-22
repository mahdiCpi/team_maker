"""Tests for OpenRouter model qualification (Story 4.2, Task 6.1 / AC8).

Tests that direct `openrouter` routing entries with unqualified model strings
are properly qualified using catalog data, and that a model whose vendor
cannot be determined is rejected rather than guessed.

The AC/task text calls the rejection a "ValidationError" (see AC8, Task 6.1c,
Automated Test Matrix item 48); the concrete class implementing that is
`resolution.UnqualifiedModelError` (a `ValueError` subclass) rather than
pydantic's `ValidationError` -- the model string being qualified here is a
plain string, not a pydantic model field, so pydantic's exception type does
not apply.
"""
from __future__ import annotations

import pytest

from team_maker.adapters.providers.registry import (
    PROVIDERS,
    get_provider,
    infer_openrouter_vendor,
)
from team_maker.adapters.providers.resolution import (
    UnqualifiedModelError,
    _qualify_direct_openrouter_model,
    resolve_credential,
)
from team_maker.domain.models import ProviderRouting
from team_maker.keyconfig import KeyConfig
from pydantic import SecretStr


class TestOpenRouterModelQualification:
    """Test model qualification for OpenRouter providers."""

    def test_openrouter_model_prefix_uses_openrouter_slug(self):
        """Provider.openrouter_model_prefix() returns openrouter_slug if set."""
        provider = get_provider("xai")
        assert provider is not None
        assert provider.openrouter_slug == "x-ai"
        assert provider.openrouter_model_prefix() == "x-ai"

    def test_openrouter_model_prefix_uses_name_when_no_slug(self):
        """Provider.openrouter_model_prefix() returns name when openrouter_slug is None."""
        provider = get_provider("anthropic")
        assert provider is not None
        assert provider.openrouter_slug is None
        assert provider.openrouter_model_prefix() == "anthropic"

    def test_qualify_unqualified_model_gpt_4o(self):
        """Unqualified model 'gpt-4o' qualified to 'openrouter/openai/gpt-4o'."""
        assert _qualify_direct_openrouter_model("gpt-4o") == "openrouter/openai/gpt-4o"

    def test_qualify_unqualified_model_claude_3_sonnet(self):
        """Unqualified model 'claude-3-sonnet' qualified to 'openrouter/anthropic/claude-3-sonnet'."""
        assert (
            _qualify_direct_openrouter_model("claude-3-sonnet")
            == "openrouter/anthropic/claude-3-sonnet"
        )

    def test_qualify_unqualified_model_for_xai(self):
        """Unqualified xai model qualified to 'openrouter/x-ai/<model>'."""
        assert _qualify_direct_openrouter_model("grok-3") == "openrouter/x-ai/grok-3"

    def test_already_qualified_model_unchanged(self):
        """Already-qualified model 'openrouter/openai/gpt-4o' is not double-prefixed."""
        already_qualified = "openrouter/openai/gpt-4o"
        assert _qualify_direct_openrouter_model(already_qualified) == already_qualified

    def test_unknown_model_is_rejected_not_guessed(self):
        """An unqualified, unrecognized model raises rather than silently defaulting."""
        with pytest.raises(UnqualifiedModelError, match="nonexistent"):
            _qualify_direct_openrouter_model("nonexistent")


class TestModelQualificationInResolution:
    """Test that resolve_credential properly qualifies OpenRouter models."""

    def test_openrouter_status_returns_qualified_model(self):
        """When STATUS_VIA_OPENROUTER, model is qualified with provider prefix."""
        # openai has no key of its own, so it must resolve via the OpenRouter gateway.
        config = KeyConfig(keys={"openrouter": SecretStr("sk-openrouter-test")})
        routing = ProviderRouting(provider="openai", model="gpt-4o")

        resolved = resolve_credential(routing, config)

        assert resolved is not None
        assert resolved.via_openrouter is True
        assert resolved.model == "openrouter/openai/gpt-4o"
        assert resolved.api_key == "sk-openrouter-test"

    def test_direct_openrouter_routing_qualifies_unqualified_model(self):
        """A routing entry whose provider IS 'openrouter' also gets its model
        qualified (AC8) -- `openrouter` is not itself a model vendor."""
        config = KeyConfig(keys={"openrouter": SecretStr("sk-openrouter-test")})
        routing = ProviderRouting(provider="openrouter", model="claude-3-sonnet")

        resolved = resolve_credential(routing, config)

        assert resolved is not None
        assert resolved.model == "openrouter/anthropic/claude-3-sonnet"
        assert resolved.api_key == "sk-openrouter-test"

    def test_direct_openrouter_routing_with_already_qualified_model_unchanged(self):
        """A direct `openrouter` routing entry whose model is already fully
        qualified is not double-prefixed."""
        config = KeyConfig(keys={"openrouter": SecretStr("sk-openrouter-test")})
        routing = ProviderRouting(provider="openrouter", model="openrouter/openai/gpt-4o")

        resolved = resolve_credential(routing, config)

        assert resolved is not None
        assert resolved.model == "openrouter/openai/gpt-4o"

    def test_direct_openrouter_routing_with_unqualifiable_model_raises(self):
        """A direct `openrouter` routing entry with an unrecognized model raises
        `UnqualifiedModelError` instead of guessing (AC8, Task 6.1c)."""
        config = KeyConfig(keys={"openrouter": SecretStr("sk-openrouter-test")})
        routing = ProviderRouting(provider="openrouter", model="nonexistent")

        with pytest.raises(UnqualifiedModelError):
            resolve_credential(routing, config)


class TestCatalogDrivenQualification:
    """Test that all qualification is data-driven from the catalog."""

    def test_all_providers_with_openrouter_slug_have_prefix(self):
        """All providers with openrouter_slug can provide a model prefix."""
        for provider in PROVIDERS:
            if provider.openrouter_slug:
                prefix = provider.openrouter_model_prefix()
                assert prefix == provider.openrouter_slug

    def test_all_openrouter_reachable_providers_have_valid_prefix(self):
        """All providers with openrouter_reachable=True have a non-empty model prefix."""
        for provider in PROVIDERS:
            if provider.openrouter_reachable:
                prefix = provider.openrouter_model_prefix()
                assert prefix
                assert prefix == (provider.openrouter_slug or provider.name)

    def test_xai_has_consistent_openrouter_config(self):
        """xai provider has consistent openrouter_reachable and openrouter_slug."""
        provider = get_provider("xai")
        assert provider is not None
        # Fixed in Story 4.2 Task 5.1
        assert provider.openrouter_reachable is True
        assert provider.openrouter_slug == "x-ai"

    def test_infer_openrouter_vendor_matches_exactly_one_provider(self):
        """Each catalogued model-name prefix resolves to exactly one vendor."""
        assert infer_openrouter_vendor("gpt-4o").name == "openai"
        assert infer_openrouter_vendor("claude-3-opus").name == "anthropic"
        assert infer_openrouter_vendor("grok-3").name == "xai"
        assert infer_openrouter_vendor("gemini-1.5-pro").name == "google"

    def test_infer_openrouter_vendor_returns_none_for_unrecognized_model(self):
        """An unrecognized model name returns None rather than a wrong guess."""
        assert infer_openrouter_vendor("some-unheard-of-model") is None

    def test_infer_openrouter_vendor_never_matches_a_non_reachable_provider(self):
        """A provider without openrouter_reachable=True is never inferred, even
        if it defined name prefixes (none do today, but the guard must hold)."""
        for provider in PROVIDERS:
            if not provider.openrouter_reachable:
                for prefix in provider.openrouter_model_name_prefixes:
                    assert infer_openrouter_vendor(prefix) is None or infer_openrouter_vendor(
                        prefix
                    ).name != provider.name
