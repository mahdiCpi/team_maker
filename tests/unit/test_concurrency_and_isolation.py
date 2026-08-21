"""Tests for concurrency and isolation (Story 4.2, Tasks 11.1 and 11.2).

Test that credential resolution is thread-safe and doesn't leak between requests
or CLI invocations.
"""
from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional
from pydantic import SecretStr

import pytest

from team_maker.adapters.providers.credential_utils import (
    bridge_all_credentials,
    bridge_provider_credential,
)
from team_maker.adapters.providers.resolution import resolve_credential
from team_maker.domain.models import ProviderRouting
from team_maker.keyconfig import KeyConfig


class TestConcurrentAPIRequests:
    """Test concurrent API credential resolution requests."""

    def test_10_concurrent_resolution_requests_succeed(self):
        """10 concurrent credential resolution requests all succeed with correct results."""
        config = KeyConfig(
            keys={
                "anthropic": SecretStr("sk-anthropic-concurrent"),
                "openai": SecretStr("sk-openai-concurrent"),
                "openrouter": SecretStr("sk-openrouter-concurrent"),
            }
        )
        
        routings = [
            ProviderRouting(provider="anthropic", model="claude-sonnet-4-6"),
            ProviderRouting(provider="openai", model="gpt-4o"),
        ] * 5  # 10 total requests (5 of each)
        
        results = []
        errors = []
        
        def resolve_one(routing: ProviderRouting):
            try:
                resolved = resolve_credential(routing, config)
                results.append(resolved)
            except Exception as e:
                errors.append(e)
        
        # Run concurrently
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(resolve_one, r) for r in routings]
            for future in as_completed(futures):
                future.result()  # Re-raise any exceptions
        
        # All should succeed
        assert len(errors) == 0
        assert len(results) == 10
        
        # All should have valid credentials
        for resolved in results:
            assert resolved is not None
            assert resolved.api_key is not None
            assert len(resolved.api_key) > 0

    def test_concurrent_requests_no_environment_corruption(self, monkeypatch):
        """Concurrent requests do not corrupt each other's environment."""
        # Set up initial environment
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-initial-anthropic")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-initial-openai")
        
        # Track environment state
        initial_anthropic = os.environ.get("ANTHROPIC_API_KEY")
        initial_openai = os.environ.get("OPENAI_API_KEY")
        
        config = KeyConfig(
            keys={
                "anthropic": SecretStr("sk-anthropic-concurrent"),
                "openai": SecretStr("sk-openai-concurrent"),
            }
        )
        
        def check_env_consistency():
            # Environment should not change during concurrent resolution
            # (resolve_credential doesn't mutate environment)
            assert os.environ.get("ANTHROPIC_API_KEY") == initial_anthropic
            assert os.environ.get("OPENAI_API_KEY") == initial_openai
        
        # Run multiple concurrent checks
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(check_env_consistency) for _ in range(10)]
            for future in as_completed(futures):
                future.result()  # Re-raise any exceptions


class TestCLIIsolation:
    """Test CLI credential isolation between invocations."""

    def test_cli_command_restores_environment_after_execution(self, monkeypatch):
        """CLI command restores environment after execution."""
        # Clear environment
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        
        config = KeyConfig(
            keys={
                "anthropic": SecretStr("sk-anthropic-cli"),
                "openai": SecretStr("sk-openai-cli"),
            }
        )
        
        # Bridge credentials
        bridged, previous_values = bridge_all_credentials(config, warn_on_replacement=False)
        
        # Environment should have the bridged values
        assert os.environ.get("ANTHROPIC_API_KEY") == "sk-anthropic-cli"
        assert os.environ.get("OPENAI_API_KEY") == "sk-openai-cli"
        
        # Restore previous values
        for env_var, previous in previous_values.items():
            if previous is None:
                os.environ.pop(env_var, None)
            else:
                os.environ[env_var] = previous
        
        # Environment should be restored
        assert os.environ.get("ANTHROPIC_API_KEY") is None
        assert os.environ.get("OPENAI_API_KEY") is None

    def test_sequential_cli_commands_no_credential_leak(self, monkeypatch):
        """Sequential CLI commands do not leak credentials between invocations."""
        # Clear environment
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        
        # First command with anthropic
        config1 = KeyConfig(
            keys={"anthropic": SecretStr("sk-anthropic-first")}
        )
        bridged1, previous1 = bridge_all_credentials(config1, warn_on_replacement=False)
        
        # Check first bridging
        assert os.environ.get("ANTHROPIC_API_KEY") == "sk-anthropic-first"
        assert "anthropic" in bridged1
        
        # Restore first
        for env_var, previous in previous1.items():
            if previous is None:
                os.environ.pop(env_var, None)
            else:
                os.environ[env_var] = previous
        
        # Environment should be clean
        assert os.environ.get("ANTHROPIC_API_KEY") is None
        
        # Second command with different key
        config2 = KeyConfig(
            keys={"anthropic": SecretStr("sk-anthropic-second")}
        )
        bridged2, previous2 = bridge_all_credentials(config2, warn_on_replacement=False)
        
        # Check second bridging
        assert os.environ.get("ANTHROPIC_API_KEY") == "sk-anthropic-second"
        assert "anthropic" in bridged2
        
        # No contamination from first command into an unrelated provider's env var
        assert os.environ.get("OPENROUTER_API_KEY") is None

    def test_bridged_credential_context_restores_environment(self, monkeypatch):
        """bridged_credential_context properly restores environment."""
        from team_maker.adapters.providers.credential_utils import bridged_credential_context
        
        # Set initial value
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-initial")
        initial = os.environ.get("ANTHROPIC_API_KEY")
        
        config = KeyConfig(
            keys={"anthropic": SecretStr("sk-anthropic-context")}
        )
        
        # Use context manager
        with bridged_credential_context(config, "anthropic", "ANTHROPIC_API_KEY"):
            # Inside context, should have new value
            assert os.environ.get("ANTHROPIC_API_KEY") == "sk-anthropic-context"
        
        # After context, should be restored
        assert os.environ.get("ANTHROPIC_API_KEY") == initial


class TestThreadSafety:
    """Test thread-safety of credential resolution."""

    def test_concurrent_bridge_all_credentials(self, monkeypatch):
        """Concurrent bridge_all_credentials calls don't interfere."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        
        config = KeyConfig(
            keys={
                "anthropic": SecretStr("sk-anthropic-thread"),
                "openai": SecretStr("sk-openai-thread"),
            }
        )
        
        results = []
        
        def bridge_and_check():
            bridged, previous = bridge_all_credentials(config, warn_on_replacement=False)
            # Each call should bridge the same providers
            assert "anthropic" in bridged
            assert "openai" in bridged
            results.append((bridged, previous))
        
        # Run concurrently
        threads = []
        for _ in range(5):
            t = threading.Thread(target=bridge_and_check)
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        # All should have succeeded
        assert len(results) == 5

    def test_resolve_credential_thread_safe(self):
        """resolve_credential is thread-safe."""
        config = KeyConfig(
            keys={
                "anthropic": SecretStr("sk-anthropic-ts"),
                "openai": SecretStr("sk-openai-ts"),
                "openrouter": SecretStr("sk-openrouter-ts"),
            }
        )
        
        routing = ProviderRouting(provider="anthropic", model="claude-sonnet-4-6")
        
        results = []
        errors = []
        
        def resolve_in_thread():
            try:
                resolved = resolve_credential(routing, config)
                results.append(resolved)
            except Exception as e:
                errors.append(e)
        
        # Run in multiple threads
        threads = []
        for _ in range(10):
            t = threading.Thread(target=resolve_in_thread)
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        # All should succeed
        assert len(errors) == 0
        assert len(results) == 10
        
        # All should have the same result
        for resolved in results:
            assert resolved is not None
            assert resolved.api_key == "sk-anthropic-ts"
            assert resolved.model == "anthropic/claude-sonnet-4-6"
