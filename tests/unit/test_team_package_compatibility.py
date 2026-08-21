"""Tests for Team Package compatibility (Story 4.2, Tasks 10.1 and 10.2).

Ensure existing Team Packages with ProviderRouting.api_key_env continue to work
and new packages work correctly with unified resolution.
"""
from __future__ import annotations

import pytest
from pydantic import SecretStr

from team_maker.adapters.providers.resolution import resolve_credential
from team_maker.domain.models import ProviderRouting
from team_maker.keyconfig import KeyConfig


class TestLegacyTeamPackageCompatibility:
    """Test loading and using existing Team Packages with api_key_env field."""

    def test_load_legacy_package_with_api_key_env(self):
        """Existing Team Package with ProviderRouting.api_key_env loads successfully."""
        # Simulate a legacy package with api_key_env field
        legacy_routing = ProviderRouting(
            provider="anthropic",
            model="claude-sonnet-4-6",
            api_key_env="ANTHROPIC_API_KEY",  # Legacy field
        )
        
        # Should load without errors
        assert legacy_routing.provider == "anthropic"
        assert legacy_routing.model == "claude-sonnet-4-6"
        assert legacy_routing.api_key_env == "ANTHROPIC_API_KEY"

    def test_legacy_package_resolves_to_correct_credential(self):
        """Legacy package resolves to correct credential ignoring api_key_env."""
        config = KeyConfig(
            keys={
                "anthropic": SecretStr("sk-anthropic-legacy"),
            }
        )
        
        # Legacy routing with api_key_env
        legacy_routing = ProviderRouting(
            provider="anthropic",
            model="claude-sonnet-4-6",
            api_key_env="ANTHROPIC_API_KEY",
        )
        
        # Resolution should use the Key Config value
        resolved = resolve_credential(legacy_routing, config)
        
        assert resolved is not None
        assert resolved.api_key == "sk-anthropic-legacy"
        assert resolved.via_openrouter is False

    def test_legacy_package_without_api_key_env_also_works(self):
        """Legacy package without api_key_env field works correctly."""
        config = KeyConfig(
            keys={
                "openai": SecretStr("sk-openai-legacy"),
            }
        )
        
        # Routing without api_key_env (newer packages)
        routing = ProviderRouting(
            provider="openai",
            model="gpt-4o",
            api_key_env=None,
        )
        
        resolved = resolve_credential(routing, config)
        
        assert resolved is not None
        assert resolved.api_key == "sk-openai-legacy"

    def test_legacy_package_resolves_same_as_without_field(self):
        """Legacy package with api_key_env resolves to same credential as if field were absent."""
        config = KeyConfig(
            keys={
                "anthropic": SecretStr("sk-anthropic-test"),
            }
        )
        
        # With api_key_env
        routing_with = ProviderRouting(
            provider="anthropic",
            model="claude-sonnet-4-6",
            api_key_env="ANTHROPIC_API_KEY",
        )
        
        # Without api_key_env
        routing_without = ProviderRouting(
            provider="anthropic",
            model="claude-sonnet-4-6",
            api_key_env=None,
        )
        
        resolved_with = resolve_credential(routing_with, config)
        resolved_without = resolve_credential(routing_without, config)
        
        # Both should resolve to the same credential
        assert resolved_with is not None
        assert resolved_without is not None
        assert resolved_with.api_key == resolved_without.api_key
        assert resolved_with.model == resolved_without.model


class TestNewTeamPackageGeneration:
    """Test that new Team Package generation works with unified resolution."""

    def test_new_package_with_unified_resolution(self):
        """New packages work correctly with unified credential resolution."""
        config = KeyConfig(
            keys={
                "anthropic": SecretStr("sk-anthropic-new"),
                "openai": SecretStr("sk-openai-new"),
            }
        )
        
        # New package routing (no api_key_env field)
        routing = ProviderRouting(
            provider="anthropic",
            model="claude-sonnet-4-6",
        )
        
        resolved = resolve_credential(routing, config)
        
        assert resolved is not None
        assert resolved.api_key == "sk-anthropic-new"
        assert resolved.model == "anthropic/claude-sonnet-4-6"

    def test_new_package_with_openrouter_fallback(self):
        """New packages with missing direct key use OpenRouter fallback."""
        config = KeyConfig(
            keys={
                "openrouter": SecretStr("sk-openrouter-new"),
            }
        )
        
        # openai doesn't have its own key, should use OpenRouter
        routing = ProviderRouting(
            provider="openai",
            model="gpt-4o",
        )
        
        resolved = resolve_credential(routing, config)
        
        assert resolved is not None
        assert resolved.api_key == "sk-openrouter-new"
        assert resolved.via_openrouter is True
        # Model should be qualified with openrouter prefix
        assert resolved.model == "openrouter/openai/gpt-4o"

    def test_new_package_with_custom_base_url(self):
        """New packages with custom base_url are preserved."""
        config = KeyConfig(
            keys={
                "anthropic": SecretStr("sk-anthropic-new"),
            }
        )
        
        routing = ProviderRouting(
            provider="anthropic",
            model="claude-sonnet-4-6",
            base_url="https://custom.anthropic.com/v1",
        )
        
        resolved = resolve_credential(routing, config)
        
        assert resolved is not None
        assert resolved.api_key == "sk-anthropic-new"
        assert resolved.base_url == "https://custom.anthropic.com/v1"

    def test_new_package_multiple_providers(self):
        """New packages with multiple providers resolve correctly."""
        config = KeyConfig(
            keys={
                "anthropic": SecretStr("sk-anthropic-new"),
                "openai": SecretStr("sk-openai-new"),
                "openrouter": SecretStr("sk-openrouter-new"),
            }
        )
        
        # Test multiple routings
        routings = [
            ProviderRouting(provider="anthropic", model="claude-sonnet-4-6"),
            ProviderRouting(provider="openai", model="gpt-4o"),
            ProviderRouting(provider="xai", model="grok-3"),
        ]
        
        for routing in routings:
            resolved = resolve_credential(routing, config)
            assert resolved is not None
            # Each should have a valid credential
            assert resolved.api_key is not None
            assert len(resolved.api_key) > 0
