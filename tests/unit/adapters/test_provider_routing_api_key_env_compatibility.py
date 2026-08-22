"""Tests for ProviderRouting.api_key_env backward compatibility - Story 4.2 Task 7.

This test suite ensures that existing Team Packages with ProviderRouting.api_key_env
continue to work correctly even though the field is not used by runtime resolution.
"""
from __future__ import annotations

from team_maker.adapters.providers.resolution import resolve_credential
from team_maker.domain.models import ProviderRouting
from team_maker.keyconfig import KeyConfig


class TestProviderRoutingApiKeyEnvCompatibility:
    """Test backward compatibility for ProviderRouting.api_key_env field."""

    def test_legacy_package_with_api_key_env_loads_successfully(self) -> None:
        """Existing Team Packages with ProviderRouting.api_key_env must load."""
        # Simulate a legacy package with api_key_env set
        legacy_routing = ProviderRouting(
            provider="anthropic",
            model="claude-sonnet-4-6",
            api_key_env="ANTHROPIC_API_KEY"  # Legacy field
        )
        
        # This should not raise any errors
        assert legacy_routing.provider == "anthropic"
        assert legacy_routing.model == "claude-sonnet-4-6"
        assert legacy_routing.api_key_env == "ANTHROPIC_API_KEY"

    def test_legacy_package_api_key_env_ignored_by_resolve_credential(self) -> None:
        """ProviderRouting.api_key_env is ignored by resolve_credential (current behavior).
        
        This documents the current "dead data" behavior: resolve_credential uses
        the provider name from the catalog, not the api_key_env field.
        """
        # Create a KeyConfig with anthropic key
        config = KeyConfig(keys={"anthropic": "sk-anthropic-test"})
        
        # Create routing with api_key_env set to a different value
        routing_with_custom_env = ProviderRouting(
            provider="anthropic",
            model="claude-sonnet-4-6",
            api_key_env="CUSTOM_ANTHROPIC_KEY"  # This should be ignored
        )
        
        # Resolution should use the catalog (provider name), not api_key_env
        resolved = resolve_credential(routing_with_custom_env, config)
        
        # The resolved credential should be based on the catalog's anthropic provider
        assert resolved is not None
        assert resolved.api_key == "sk-anthropic-test"
        assert resolved.model == "anthropic/claude-sonnet-4-6"
        assert resolved.via_openrouter is False

    def test_legacy_package_without_api_key_env_also_works(self) -> None:
        """Packages without api_key_env (None) must also work."""
        routing = ProviderRouting(
            provider="anthropic",
            model="claude-sonnet-4-6",
            api_key_env=None
        )
        
        config = KeyConfig(keys={"anthropic": "sk-anthropic-test"})
        resolved = resolve_credential(routing, config)
        
        assert resolved is not None
        assert resolved.api_key == "sk-anthropic-test"

    def test_legacy_package_resolves_to_same_credential_as_if_field_absent(self) -> None:
        """Legacy package resolves to same credential as if api_key_env field were absent.
        
        This proves that the presence of api_key_env doesn't change resolution.
        """
        config = KeyConfig(keys={"anthropic": "sk-anthropic-test"})
        
        # With api_key_env
        routing_with_env = ProviderRouting(
            provider="anthropic",
            model="claude-sonnet-4-6",
            api_key_env="ANTHROPIC_API_KEY"
        )
        
        # Without api_key_env
        routing_without_env = ProviderRouting(
            provider="anthropic",
            model="claude-sonnet-4-6",
            api_key_env=None
        )
        
        resolved_with = resolve_credential(routing_with_env, config)
        resolved_without = resolve_credential(routing_without_env, config)
        
        # Both should resolve to the same credential
        assert resolved_with == resolved_without

    def test_api_key_env_field_preserved_in_to_dict(self) -> None:
        """ProviderRouting.to_dict() preserves api_key_env when present.
        
        This ensures that when generating new packages, the field is still
        written (for backward compatibility), even though it's not used at runtime.
        """
        routing = ProviderRouting(
            provider="anthropic",
            model="claude-sonnet-4-6",
            api_key_env="ANTHROPIC_API_KEY"
        )
        
        data = routing.to_dict()
        
        assert data["provider"] == "anthropic"
        assert data["model"] == "claude-sonnet-4-6"
        assert data["api_key_env"] == "ANTHROPIC_API_KEY"

    def test_api_key_env_none_not_included_in_to_dict(self) -> None:
        """ProviderRouting.to_dict() omits api_key_env when None.
        
        This ensures clean serialization when the field is not set.
        """
        routing = ProviderRouting(
            provider="anthropic",
            model="claude-sonnet-4-6",
            api_key_env=None
        )
        
        data = routing.to_dict()
        
        assert data["provider"] == "anthropic"
        assert data["model"] == "claude-sonnet-4-6"
        assert "api_key_env" not in data

    def test_api_key_env_empty_string_not_included_in_to_dict(self) -> None:
        """ProviderRouting.to_dict() omits api_key_env when empty string."""
        routing = ProviderRouting(
            provider="anthropic",
            model="claude-sonnet-4-6",
            api_key_env=""
        )
        
        data = routing.to_dict()
        
        assert "api_key_env" not in data


class TestFieldDisposition:
    """Document the decision on ProviderRouting.api_key_env field disposition."""
    
    def test_field_disposition_decision(self) -> None:
        """Document that api_key_env field is kept for backward compatibility.
        
        DECISION (Story 4.2 Task 7.3):
        - Field is KEPT (not removed in Story 4.2)
        - Reason: Backward compatibility for existing Team Packages
        - Status: Dead data for runtime resolution (not read by resolve_credential)
        - Future: May be deprecated/removed in separate story after migration plan
        
        This test documents the decision and ensures it's not accidentally removed.
        """
        # The field must still exist in the dataclass
        routing = ProviderRouting(
            provider="test",
            model="test",
            api_key_env="test_env"
        )
        
        # Must be accessible
        assert routing.api_key_env == "test_env"
        
        # Must be in the dataclass fields
        assert "api_key_env" in ProviderRouting.__dataclass_fields__
