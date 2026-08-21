"""Shared credential resolution utilities (Story 4.2, Task 8).

This module provides shared utilities for credential resolution that both CLI
and API can use, eliminating duplication while preserving surface-specific
behaviors:
- CLI: Temporary environment variable mutation with restoration
- API: No per-request mutation, credentials resolved once at startup

All credential values are wrapped in SecretStr and only unwrapped at the
point of use (AD-9). No secret values appear in logs, warnings, or output.
"""
from __future__ import annotations

import contextlib
import logging
import os
from typing import Iterator, Optional

from team_maker.adapters.providers.registry import PROVIDERS, get_provider
from team_maker.keyconfig import KeyConfig

logger = logging.getLogger(__name__)


def resolve_default_provider_key(provider_name: str, key_config: KeyConfig) -> str:
    """Resolve a provider's key via its *default* env var, Key-Config-first.

    This is the single implementation of the standard (non-override) key
    lookup policy component 1/3 of the unified resolution policy
    (`resolution.py`'s module docstring): Key Config file wins, then the
    catalog's canonical env var, then its aliases, in that order. It exists so
    consumers that need a raw key string for a provider's *own* API (e.g. the
    model resolver validating a model name against the live vendor API) do not
    reimplement this precedence independently (Story 4.2 AC1).

    This is deliberately narrower than `resolve_credential()`: it never routes
    through OpenRouter and knows nothing about a per-agent custom
    `api_key_env` override -- callers that need either of those keep handling
    them themselves.

    Returns "" when no credential is available via either source.
    """
    if key_config.has(provider_name):
        return key_config.keys[provider_name].get_secret_value()

    provider = get_provider(provider_name)
    if provider is None:
        return ""
    for candidate in (provider.env_var, *provider.env_var_aliases):
        if not candidate:
            continue
        value = os.environ.get(candidate)
        if value:
            return value
    return ""


def bridge_provider_credential(
    key_config: KeyConfig,
    provider_name: str,
    env_var: Optional[str],
    *,
    warn_on_replacement: bool = True,
) -> tuple[Optional[str], bool]:
    """Bridge a single provider's credential into its environment variable.
    
    This is the shared core logic for both CLI and API credential bridging.
    
    Args:
        key_config: Loaded Key Config with provider credentials
        provider_name: Canonical provider name from the catalog
        env_var: Environment variable name to set (from provider catalog)
        warn_on_replacement: If True, log warning when replacing existing value
        
    Returns:
        Tuple of (previous_value, was_bridged) where:
        - previous_value: The value that was in env_var before, or None. This may
          itself be a credential (e.g. a real key an operator exported directly),
          so callers must treat a non-None previous_value as secret and never log,
          serialize, or otherwise surface it.
        - was_bridged: True if a credential was actually bridged

    Security:
        Logs/warnings emitted by this function itself contain only provider names
        and env var names, never credential values (AD-9). The *returned*
        previous_value is not redacted -- it is whatever was already in the
        environment, which callers must handle as a secret.
    """
    if not env_var or not key_config.has(provider_name):
        return None, False

    provider = get_provider(provider_name)
    if provider is None or provider.env_var != env_var:
        return None, False

    secret_value = key_config.keys[provider_name].get_secret_value()
    previous = os.environ.get(env_var)
    
    if previous is not None and previous != secret_value and warn_on_replacement:
        logger.warning(
            "%s was already set to a different value in the environment and has "
            "been replaced by the Key Config entry for '%s' for the lifetime of "
            "this process",
            env_var,
            provider_name,
        )
    
    os.environ[env_var] = secret_value
    return previous, True


@contextlib.contextmanager
def bridged_credential_context(
    key_config: KeyConfig,
    provider_name: str,
    env_var: Optional[str],
) -> Iterator[None]:
    """Context manager for temporary credential bridging (CLI-specific).
    
    This provides the CLI's temporary environment mutation behavior:
    - Bridges the credential for the duration of the context
    - Restores the previous value (or removes if was None) on exit
    - Never leaves credentials in the environment unexpectedly
    
    Args:
        key_config: Loaded Key Config with provider credentials
        provider_name: Canonical provider name from the catalog
        env_var: Environment variable name to temporarily set
        
    Example:
        with bridged_credential_context(key_config, "anthropic", "ANTHROPIC_API_KEY"):
            # credential is available in os.environ here
            perform_operation()
        # credential is restored/removed here
    """
    previous, was_bridged = bridge_provider_credential(
        key_config, provider_name, env_var, warn_on_replacement=False
    )
    
    if not was_bridged:
        yield
        return
    
    try:
        yield
    finally:
        # Always restore the previous state
        if previous is None:
            os.environ.pop(env_var, None)
        else:
            os.environ[env_var] = previous


def bridge_all_credentials(
    key_config: KeyConfig,
    *,
    warn_on_replacement: bool = True,
) -> tuple[list[str], dict[str, Optional[str]]]:
    """Bridge all available provider credentials into environment variables.
    
    This is the API's credential bridging logic:
    - Bridges every provider that has a credential in the Key Config
    - Returns list of bridged provider names (for logging)
    - Returns dict of previous values for potential restoration
    - No automatic restoration (API bridges once at startup for process lifetime)
    
    Args:
        key_config: Loaded Key Config with provider credentials
        warn_on_replacement: If True, log warning when replacing existing values
        
    Returns:
        Tuple of (bridged_providers, previous_values) where:
        - bridged_providers: List of provider names that were bridged (identifiers only)
        - previous_values: Dict mapping env_var -> whatever value was already in that
          env var before bridging, or None. Like `bridge_provider_credential`'s
          `previous_value`, this may itself be a real credential (e.g. one an
          operator exported directly) -- callers must treat non-None entries as
          secret and never log, serialize, or otherwise surface them.

    Security:
        Logs emitted by this function contain only provider names and env var
        names, never credential values. `bridged_providers` is identifiers only.
        `previous_values` is NOT redacted; see the note above.
    """
    bridged: list[str] = []
    previous_values: dict[str, Optional[str]] = {}
    
    for provider in PROVIDERS:
        if not provider.env_var:
            continue
        
        previous, was_bridged = bridge_provider_credential(
            key_config, provider.name, provider.env_var, 
            warn_on_replacement=warn_on_replacement
        )
        
        if was_bridged:
            bridged.append(provider.name)
            previous_values[provider.env_var] = previous
    
    return bridged, previous_values


def find_stale_bridged_providers(
    key_config: KeyConfig,
    previously_bridged: tuple[str, ...],
) -> list[str]:
    """Determine which providers need restart to pick up new Key Config values.
    
    This implements the same logic as api/deps.py:providers_needing_restart()
    but using the shared utilities.
    
    Args:
        key_config: Current Key Config (may have been edited since startup)
        previously_bridged: Provider names that were bridged at startup
        
    Returns:
        List of provider names that need a restart to pick up new values.
        Contains only provider names, never credential values.
    """
    stale: list[str] = []
    
    for provider in PROVIDERS:
        if not provider.env_var or not key_config.has(provider.name):
            continue
            
        if provider.name not in previously_bridged:
            # Added since startup
            stale.append(provider.name)
            continue
        
        # Check if value changed since startup
        current_value = key_config.keys[provider.name].get_secret_value()
        env_value = os.environ.get(provider.env_var)
        
        if env_value != current_value:
            stale.append(provider.name)
    
    return stale
