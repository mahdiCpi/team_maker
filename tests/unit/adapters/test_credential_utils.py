"""Tests for shared credential utilities - Story 4.2 Task 8."""
from __future__ import annotations

import os

import pytest

from team_maker.adapters.providers.credential_utils import (
    bridge_all_credentials,
    bridge_provider_credential,
    bridged_credential_context,
    find_stale_bridged_providers,
)
from team_maker.keyconfig import KeyConfig


class TestBridgeProviderCredential:
    """Test individual provider credential bridging."""

    def test_bridges_provider_credential_into_env_var(self, monkeypatch):
        """Bridge a single provider's credential into its environment variable."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        
        config = KeyConfig(keys={"anthropic": "sk-anthropic-test"})
        
        previous, was_bridged = bridge_provider_credential(
            config, "anthropic", "ANTHROPIC_API_KEY", warn_on_replacement=False
        )
        
        assert was_bridged is True
        assert previous is None
        assert os.environ.get("ANTHROPIC_API_KEY") == "sk-anthropic-test"

    def test_returns_previous_value_when_replacing(self, monkeypatch):
        """Return the previous value when replacing an existing credential."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-existing")
        
        config = KeyConfig(keys={"anthropic": "sk-new"})
        
        previous, was_bridged = bridge_provider_credential(
            config, "anthropic", "ANTHROPIC_API_KEY", warn_on_replacement=False
        )
        
        assert was_bridged is True
        assert previous == "sk-existing"
        assert os.environ.get("ANTHROPIC_API_KEY") == "sk-new"

    def test_no_bridge_when_no_key_present(self):
        """Don't bridge when provider has no key in config."""
        config = KeyConfig(keys={})  # Empty config
        
        previous, was_bridged = bridge_provider_credential(
            config, "anthropic", "ANTHROPIC_API_KEY", warn_on_replacement=False
        )
        
        assert was_bridged is False
        assert previous is None

    def test_no_bridge_when_env_var_none(self):
        """Don't bridge when env_var is None (keyless providers)."""
        config = KeyConfig(keys={"ollama": "sk-ollama"})
        
        previous, was_bridged = bridge_provider_credential(
            config, "ollama", None, warn_on_replacement=False
        )
        
        assert was_bridged is False
        assert previous is None

    def test_warning_on_replacement(self, monkeypatch, caplog):
        """Log warning when replacing existing credential value."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-existing")
        
        config = KeyConfig(keys={"anthropic": "sk-new"})
        
        with caplog.at_level("WARNING"):
            bridge_provider_credential(
                config, "anthropic", "ANTHROPIC_API_KEY", warn_on_replacement=True
            )
        
        assert "ANTHROPIC_API_KEY was already set" in caplog.text
        assert "anthropic" in caplog.text
        assert "sk-existing" not in caplog.text  # Never log the actual values
        assert "sk-new" not in caplog.text


class TestBridgedCredentialContext:
    """Test context manager for temporary credential bridging."""

    def test_context_manager_bridges_credential(self, monkeypatch):
        """Context manager bridges credential for duration of context."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        
        config = KeyConfig(keys={"anthropic": "sk-anthropic-test"})
        
        with bridged_credential_context(config, "anthropic", "ANTHROPIC_API_KEY"):
            assert os.environ.get("ANTHROPIC_API_KEY") == "sk-anthropic-test"

    def test_context_manager_restores_previous_value(self, monkeypatch):
        """Context manager restores previous value on exit."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-previous")
        
        config = KeyConfig(keys={"anthropic": "sk-new"})
        
        with bridged_credential_context(config, "anthropic", "ANTHROPIC_API_KEY"):
            assert os.environ.get("ANTHROPIC_API_KEY") == "sk-new"
        
        # After context exit, previous value is restored
        assert os.environ.get("ANTHROPIC_API_KEY") == "sk-previous"

    def test_context_manager_removes_env_var_if_was_not_set(self, monkeypatch):
        """Context manager removes env var if it was not set before."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        
        config = KeyConfig(keys={"anthropic": "sk-new"})
        
        with bridged_credential_context(config, "anthropic", "ANTHROPIC_API_KEY"):
            assert os.environ.get("ANTHROPIC_API_KEY") == "sk-new"
        
        # After context exit, env var is removed
        assert os.environ.get("ANTHROPIC_API_KEY") is None

    def test_context_manager_no_op_when_no_key(self, monkeypatch):
        """Context manager does nothing when no key is present."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        
        config = KeyConfig(keys={})  # Empty config
        
        with bridged_credential_context(config, "anthropic", "ANTHROPIC_API_KEY"):
            # No change should occur
            assert os.environ.get("ANTHROPIC_API_KEY") is None
        
        # Still no change after exit
        assert os.environ.get("ANTHROPIC_API_KEY") is None


class TestBridgeAllCredentials:
    """Test bridging all provider credentials at once."""

    def test_bridges_all_available_providers(self, monkeypatch):
        """Bridge all providers that have credentials in config."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        
        config = KeyConfig(keys={"anthropic": "sk-anthropic", "openai": "sk-openai"})
        
        bridged, previous_values = bridge_all_credentials(config, warn_on_replacement=False)
        
        assert "anthropic" in bridged
        assert "openai" in bridged
        assert os.environ.get("ANTHROPIC_API_KEY") == "sk-anthropic"
        assert os.environ.get("OPENAI_API_KEY") == "sk-openai"

    def test_returns_provider_names_only(self, monkeypatch):
        """Return only provider names, never credential values."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        
        config = KeyConfig(keys={"anthropic": "sk-anthropic-secret"})
        
        bridged, previous_values = bridge_all_credentials(config, warn_on_replacement=False)
        
        # bridged contains only provider names
        assert "anthropic" in bridged
        assert "sk-anthropic-secret" not in bridged
        assert "sk-anthropic-secret" not in str(bridged)

    def test_skips_providers_without_env_var(self, monkeypatch):
        """Skip providers that don't have an env_var (keyless providers)."""
        config = KeyConfig(keys={"ollama": "sk-ollama"})
        
        bridged, previous_values = bridge_all_credentials(config, warn_on_replacement=False)
        
        # ollama has env_var=None, so it shouldn't be bridged
        assert "ollama" not in bridged


class TestGetPreviousValuesForRestart:
    """Test detection of providers needing restart."""

    def test_added_provider_needs_restart(self, monkeypatch):
        """Provider added since startup needs restart."""
        # Simulate startup state: no keys bridged initially
        previously_bridged = ()
        
        # Now config has a new provider
        config = KeyConfig(keys={"anthropic": "sk-new"})
        
        stale = find_stale_bridged_providers(config, previously_bridged)
        
        assert "anthropic" in stale

    def test_changed_provider_needs_restart(self, monkeypatch):
        """Provider with changed value needs restart."""
        # Simulate startup: anthropic was bridged
        previously_bridged = ("anthropic",)
        
        # Set current env to old value
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-old")
        
        # Config has new value
        config = KeyConfig(keys={"anthropic": "sk-new"})
        
        stale = find_stale_bridged_providers(config, previously_bridged)
        
        assert "anthropic" in stale

    def test_unchanged_provider_does_not_need_restart(self, monkeypatch):
        """Provider with unchanged value does not need restart."""
        # Simulate startup: anthropic was bridged
        previously_bridged = ("anthropic",)
        
        # Set current env to same value as in config
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-same")
        
        # Config has same value
        config = KeyConfig(keys={"anthropic": "sk-same"})
        
        stale = find_stale_bridged_providers(config, previously_bridged)
        
        assert "anthropic" not in stale

    def test_returns_provider_names_only(self, monkeypatch):
        """Return only provider names, never credential values."""
        previously_bridged = ()
        
        config = KeyConfig(keys={"anthropic": "sk-secret-value"})
        
        stale = find_stale_bridged_providers(config, previously_bridged)
        
        assert "anthropic" in stale
        assert "sk-secret-value" not in stale
        assert "sk-secret-value" not in str(stale)


class TestCLIAPIParity:
    """Test that CLI and API produce identical results."""

    def test_bridged_credential_context_produces_same_result_as_bridge_all(self, monkeypatch):
        """CLI and API should use same underlying resolution logic."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        
        config = KeyConfig(keys={"anthropic": "sk-test"})
        
        # API-style: bridge all
        bridged_all, _ = bridge_all_credentials(config, warn_on_replacement=False)
        
        # CLI-style: bridge individual
        with bridged_credential_context(config, "anthropic", "ANTHROPIC_API_KEY"):
            assert os.environ.get("ANTHROPIC_API_KEY") == "sk-test"
        
        # Both should result in the same environment state
        assert "anthropic" in bridged_all
        assert os.environ.get("ANTHROPIC_API_KEY") == "sk-test"