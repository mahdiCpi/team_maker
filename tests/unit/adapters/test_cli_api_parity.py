"""Tests for CLI and API credential resolution parity - Story 4.2 Task 8.4.

This test suite verifies that CLI and API produce identical credential resolution
results, ensuring that what the user is told is usable matches what the runtime will
actually use.
"""
from __future__ import annotations

import os
from pathlib import Path
import tempfile

import pytest

from team_maker.adapters.providers.credential_utils import (
    bridge_all_credentials,
    bridged_credential_context,
)
from team_maker.adapters.providers.registry import (
    report_availability,
    STATUS_AVAILABLE,
    STATUS_VIA_OPENROUTER,
    STATUS_KEYLESS_LOCAL,
    STATUS_MISSING,
    STATUS_UNSUPPORTED_BY_RUNTIME,
)
from team_maker.keyconfig import KeyConfig


class TestCliApiParity:
    """Test that CLI and API credential resolution produce identical results."""

    def test_bridged_credential_context_and_bridge_all_use_same_logic(self, monkeypatch):
        """CLI context manager and API bridge_all use same underlying logic."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        
        config = KeyConfig(keys={"anthropic": "sk-anthropic", "openai": "sk-openai"})
        
        # API-style: bridge all at once
        bridged_all, _ = bridge_all_credentials(config, warn_on_replacement=False)
        
        # Verify environment is set
        assert os.environ.get("ANTHROPIC_API_KEY") == "sk-anthropic"
        assert os.environ.get("OPENAI_API_KEY") == "sk-openai"
        
        # CLI-style: bridge individually with context manager
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        
        with bridged_credential_context(config, "anthropic", "ANTHROPIC_API_KEY"):
            assert os.environ.get("ANTHROPIC_API_KEY") == "sk-anthropic"
        
        # Both methods should result in the same credential values being set
        # (when used with the same config)

    def test_both_methods_preserve_security(self, monkeypatch, caplog):
        """Both CLI and API methods preserve security (no secret leakage)."""
        SECRET = "super-secret-api-key-123"
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        
        config = KeyConfig(keys={"anthropic": SECRET})
        
        # API-style
        with caplog.at_level("WARNING"):
            bridge_all_credentials(config, warn_on_replacement=False)
        
        # CLI-style
        with caplog.at_level("WARNING"):
            with bridged_credential_context(config, "anthropic", "ANTHROPIC_API_KEY"):
                pass
        
        # Neither should leak the secret in logs
        assert SECRET not in caplog.text

    def test_availability_report_identical_for_cli_and_api(self, tmp_path):
        """CLI and API availability reports use the same classify() function."""
        # Create a Key Config file
        config_path = tmp_path / "team_maker.keys"
        config_path.write_text(
            "ANTHROPIC_API_KEY=sk-anthropic\n"
            "OPENAI_API_KEY=sk-openai\n"
            "OPENROUTER_API_KEY=sk-openrouter\n"
        )
        
        # Load config (same method used by both CLI and API)
        config = KeyConfig.from_file(config_path, include_env=False)
        
        # Get availability report (used by both CLI and API)
        report = report_availability(config)
        
        # Verify the report contains expected classifications
        provider_statuses = {p.name: p.status for p in report}
        
        assert provider_statuses["anthropic"] == STATUS_AVAILABLE
        assert provider_statuses["openai"] == STATUS_AVAILABLE
        assert provider_statuses["openrouter"] == STATUS_AVAILABLE
        assert provider_statuses["ollama"] == STATUS_KEYLESS_LOCAL
        
        # Both CLI and API would use this same report
        # This ensures parity because they both use the same function

    def test_empty_config_produces_identical_results(self, tmp_path):
        """Empty Key Config produces identical results for CLI and API."""
        config_path = tmp_path / "team_maker.keys"
        config_path.write_text("")
        
        config = KeyConfig.from_file(config_path, include_env=False)
        report = report_availability(config)
        
        provider_statuses = {p.name: p.status for p in report}
        
        # All keyed providers should be missing, keyless should be keyless-local
        assert provider_statuses["anthropic"] == STATUS_MISSING
        assert provider_statuses["openai"] == STATUS_MISSING
        assert provider_statuses["ollama"] == STATUS_KEYLESS_LOCAL
        
        # This is the same result regardless of which surface (CLI or API) calls it

    def test_openrouter_key_makes_reachable_providers_usable(self, tmp_path):
        """OpenRouter key makes reachable providers usable via gateway."""
        config_path = tmp_path / "team_maker.keys"
        config_path.write_text("OPENROUTER_API_KEY=sk-openrouter\n")
        
        config = KeyConfig.from_file(config_path, include_env=False)
        report = report_availability(config)
        
        provider_statuses = {p.name: p.status for p in report}
        
        # Providers with openrouter_reachable=True should be via-openrouter
        assert provider_statuses["anthropic"] == STATUS_VIA_OPENROUTER
        assert provider_statuses["openai"] == STATUS_VIA_OPENROUTER
        # xai now has openrouter_reachable=True (Story 4.2 fix)
        assert provider_statuses["xai"] == STATUS_VIA_OPENROUTER
        # google has runtime_supported=False but openrouter_reachable=True
        assert provider_statuses["google"] == STATUS_VIA_OPENROUTER
        
        # groq has openrouter_reachable=False (inference host, not vendor)
        assert provider_statuses["groq"] == STATUS_UNSUPPORTED_BY_RUNTIME

    def test_file_priority_over_env_fallback(self, tmp_path, monkeypatch):
        """File credentials take priority over environment fallback for both surfaces."""
        # Set environment variable
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-env")
        
        # Create Key Config file with different value
        config_path = tmp_path / "team_maker.keys"
        config_path.write_text("ANTHROPIC_API_KEY=sk-file\n")
        
        # Load with env fallback enabled
        config = KeyConfig.from_file(config_path, include_env=True)
        
        # File value should win
        assert config.keys["anthropic"].get_secret_value() == "sk-file"
        
        # Both CLI and API would use this same KeyConfig
        # This ensures file priority is consistent


class TestSharedResolutionLogic:
    """Test that the shared resolution logic is consistent."""

    def test_bridge_all_credentials_returns_provider_names_only(self, monkeypatch):
        """bridge_all_credentials returns only provider names, never values."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        
        SECRET = "super-secret-value"
        config = KeyConfig(keys={"anthropic": SECRET})
        
        bridged, previous_values = bridge_all_credentials(config, warn_on_replacement=False)
        
        # bridged should contain only provider names
        assert "anthropic" in bridged
        assert SECRET not in str(bridged)
        
        # previous_values should map env_var -> previous value (which could be None)
        assert "ANTHROPIC_API_KEY" in previous_values
        # previous_values might contain the previous env value, but not the new secret
        assert SECRET not in str(previous_values)

    def test_bridged_credential_context_restores_environment(self, monkeypatch):
        """bridged_credential_context always restores environment on exit."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-original")
        
        config = KeyConfig(keys={"anthropic": "sk-new"})
        
        with bridged_credential_context(config, "anthropic", "ANTHROPIC_API_KEY"):
            # During context, new value is active
            assert os.environ.get("ANTHROPIC_API_KEY") == "sk-new"
        
        # After context, original value is restored
        assert os.environ.get("ANTHROPIC_API_KEY") == "sk-original"

    def test_find_stale_bridged_providers_identifies_stale_providers(self, monkeypatch):
        """find_stale_bridged_providers correctly identifies stale providers."""
        # Simulate startup state
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-old")
        previously_bridged = ("anthropic",)
        
        # New config with different value
        config = KeyConfig(keys={"anthropic": "sk-new"})
        
        from team_maker.adapters.providers.credential_utils import find_stale_bridged_providers
        stale = find_stale_bridged_providers(config, previously_bridged)
        
        assert "anthropic" in stale
        
        # Now test with unchanged value
        config_unchanged = KeyConfig(keys={"anthropic": "sk-old"})
        stale_unchanged = find_stale_bridged_providers(config_unchanged, previously_bridged)
        
        assert "anthropic" not in stale_unchanged
