"""Tests for provider catalog consistency - Story 4.2 Task 5.2."""
from __future__ import annotations

import pytest

from team_maker.adapters.providers.registry import PROVIDERS


class TestCatalogConsistency:
    """Validate consistency constraints in the provider catalog."""

    def test_openrouter_slug_implies_openrouter_reachable(self) -> None:
        """If openrouter_slug is set, openrouter_reachable must be True.
        
        This ensures that providers with an OpenRouter vendor namespace are
        correctly marked as reachable via the gateway (deferred-work.md:186).
        """
        for provider in PROVIDERS:
            if provider.openrouter_slug is not None:
                assert provider.openrouter_reachable is True, (
                    f"Provider '{provider.name}' has openrouter_slug='{provider.openrouter_slug}' "
                    f"but openrouter_reachable={provider.openrouter_reachable}. "
                    f"This breaks catalog consistency: a provider with a vendor namespace "
                    f"must be marked as reachable via OpenRouter."
                )

    def test_xai_catalog_consistency(self) -> None:
        """xai provider must have both openrouter_slug and openrouter_reachable=True.
        
        Regression test for the specific xai inconsistency (deferred-work.md:186).
        """
        xai = next((p for p in PROVIDERS if p.name == "xai"), None)
        assert xai is not None, "xai provider not found in catalog"
        
        # Must have the vendor namespace
        assert xai.openrouter_slug == "x-ai", (
            f"xai provider must have openrouter_slug='x-ai', got {xai.openrouter_slug}"
        )
        
        # Must be marked as reachable
        assert xai.openrouter_reachable is True, (
            f"xai provider must have openrouter_reachable=True, got {xai.openrouter_reachable}"
        )

    def test_openrouter_model_prefix_uses_slug_or_name(self) -> None:
        """openrouter_model_prefix() must return openrouter_slug if set, else name."""
        for provider in PROVIDERS:
            expected = provider.openrouter_slug or provider.name
            actual = provider.openrouter_model_prefix()
            assert actual == expected, (
                f"Provider '{provider.name}': openrouter_model_prefix() returned "
                f"'{actual}', expected '{expected}'"
            )

    def test_openrouter_provider_has_no_slug(self) -> None:
        """The openrouter gateway provider itself should not have openrouter_reachable=True.
        
        This is a sanity check: the gateway doesn't route to itself.
        """
        openrouter = next((p for p in PROVIDERS if p.name == "openrouter"), None)
        assert openrouter is not None, "openrouter provider not found in catalog"
        
        # Gateway should not have openrouter_reachable=True (it IS the gateway)
        assert openrouter.openrouter_reachable is False, (
            f"openrouter provider should not have openrouter_reachable=True"
        )
        
        # Gateway should not have an openrouter_slug (it doesn't have a vendor namespace)
        assert openrouter.openrouter_slug is None, (
            f"openrouter provider should not have an openrouter_slug"
        )

    def test_keyless_local_providers_have_no_env_var(self) -> None:
        """Keyless-local providers must have env_var=None."""
        for provider in PROVIDERS:
            if provider.keyless_local:
                assert provider.env_var is None, (
                    f"Keyless-local provider '{provider.name}' must have env_var=None, "
                    f"got '{provider.env_var}'"
                )

    def test_all_providers_have_valid_names(self) -> None:
        """All provider names must be valid identifiers."""
        for provider in PROVIDERS:
            assert provider.name.isidentifier(), (
                f"Provider name '{provider.name}' is not a valid Python identifier"
            )
            assert provider.name.islower(), (
                f"Provider name '{provider.name}' should be lowercase"
            )

    def test_runtime_unsupported_providers_have_reason(self) -> None:
        """Providers with runtime_supported=False must have unsupported_reason."""
        for provider in PROVIDERS:
            if not provider.runtime_supported:
                assert provider.unsupported_reason is not None, (
                    f"Provider '{provider.name}' has runtime_supported=False but "
                    f"no unsupported_reason"
                )
                assert len(provider.unsupported_reason) > 0, (
                    f"Provider '{provider.name}' has empty unsupported_reason"
                )
