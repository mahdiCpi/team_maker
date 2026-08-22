"""Validates agent model names against live provider APIs and substitutes the nearest
available model when the requested one does not exist.

Called once during _build_manifest before routing_config.yaml is written.
Results are cached per provider so each API is queried at most once per run.
"""
from __future__ import annotations

import difflib
import os
import sys
from functools import lru_cache

from team_maker.adapters.providers.credential_utils import resolve_default_provider_key
from team_maker.adapters.providers.registry import PROVIDERS
from team_maker.domain.models import GeneratedTeam, ProviderRouting
from team_maker.keyconfig import KeyConfig

# Each provider's catalogued default env var (data, not branching — AD-1). Used to
# detect a per-agent *custom* api_key_env override so it is never shadowed by a
# KeyConfig entry that KeyConfig.from_file() auto-filled from the standard env var.
_DEFAULT_ENV_BY_PROVIDER: dict[str, str] = {p.name: p.env_var for p in PROVIDERS if p.env_var}

# ---------------------------------------------------------------------------
# Closest-match helper
# ---------------------------------------------------------------------------

def _closest(requested: str, available: list[str], fallback: str) -> tuple[str, bool]:
    """Return (chosen_model, was_substituted)."""
    if requested in available:
        return requested, False
    if not available:
        return fallback, True
    ranked = sorted(
        available,
        key=lambda m: difflib.SequenceMatcher(None, requested, m).ratio(),
        reverse=True,
    )
    return ranked[0], True


# ---------------------------------------------------------------------------
# Per-provider model list fetchers (lru_cache = one API call per provider)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=None)
def _anthropic_models(api_key: str) -> tuple[str, ...]:
    try:
        import anthropic
        if not api_key:
            return ()
        return tuple(m.id for m in anthropic.Anthropic(api_key=api_key).models.list())
    except Exception:
        return ()


@lru_cache(maxsize=None)
def _openai_models(api_key: str) -> tuple[str, ...]:
    try:
        from openai import OpenAI
        if not api_key:
            return ()
        return tuple(m.id for m in OpenAI(api_key=api_key).models.list())
    except Exception:
        return ()


@lru_cache(maxsize=None)
def _xai_models(api_key: str) -> tuple[str, ...]:
    try:
        from openai import OpenAI
        if not api_key:
            return ()
        client = OpenAI(base_url="https://api.x.ai/v1", api_key=api_key)
        return tuple(m.id for m in client.models.list())
    except Exception:
        return ()


@lru_cache(maxsize=None)
def _google_models(api_key: str) -> tuple[str, ...]:
    if not api_key:
        return ()
    # Try new google.genai SDK first, fall back to deprecated google.generativeai.
    try:
        import google.genai as genai_new
        client = genai_new.Client(api_key=api_key)
        return tuple(m.name.removeprefix("models/") for m in client.models.list())
    except Exception:
        pass
    try:
        import warnings

        import google.generativeai as genai
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            genai.configure(api_key=api_key)
            return tuple(
                m.name.removeprefix("models/")
                for m in genai.list_models()
                if "generateContent" in (m.supported_generation_methods or [])
            )
    except Exception:
        return ()


_FETCHER_MAP: dict[str, tuple] = {
    "anthropic": (_anthropic_models, "claude-sonnet-4-6"),
    "openai":    (_openai_models,    "gpt-4o"),
    "xai":       (_xai_models,       "grok-3"),
    "google":    (_google_models,    "gemini-1.5-pro"),
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _resolve_key(provider: str, api_key_env: str, config: KeyConfig) -> str:
    """Resolve a provider's key using the unified resolution policy (Story 4.2).

    A per-agent *custom* `api_key_env` (naming a non-default env var) always reads
    that env var directly — it must never be shadowed by a KeyConfig entry that
    was only auto-filled from the provider's standard env var. This override
    behavior is `ProviderRouting.api_key_env`-specific and is preserved as-is
    per Task 7's blocking design gate (no behavior change to that field pending
    its audit).

    For the standard (non-override) case, resolution delegates to
    `credential_utils.resolve_default_provider_key()` — the single shared
    implementation of the Key-Config-first, environment-fallback precedence
    rule — instead of reimplementing it here (AC1: no duplicated resolution
    policy across consumers).

    Args:
        provider: The provider name (canonical, from catalog)
        api_key_env: The environment variable name to use (from ProviderRouting)
        config: Loaded KeyConfig with provider credentials

    Returns:
        The resolved API key value as a string, or empty string if not available.
    """
    is_custom_override = bool(api_key_env) and api_key_env != _DEFAULT_ENV_BY_PROVIDER.get(
        provider
    )
    if is_custom_override:
        return os.environ.get(api_key_env, "")

    return resolve_default_provider_key(provider, config)


def resolve_routing(
    routing: ProviderRouting, config: KeyConfig
) -> tuple[ProviderRouting, str | None]:
    """Validate routing.model against the live provider API.

    Returns (updated_routing, substitution_message).
    substitution_message is None when the model was already valid or the
    provider could not be queried (in which case routing is returned unchanged).
    """
    provider = routing.provider.lower()
    fetcher_info = _FETCHER_MAP.get(provider)
    if fetcher_info is None:
        return routing, None  # ollama or unknown — skip

    fetcher, fallback = fetcher_info
    api_key = _resolve_key(provider, routing.api_key_env or "", config)
    available = list(fetcher(api_key))

    if not available:
        return routing, None  # API unreachable — trust the YAML

    chosen, substituted = _closest(routing.model, available, fallback)
    if not substituted:
        return routing, None

    updated = ProviderRouting(
        provider=routing.provider,
        model=chosen,
        api_key_env=routing.api_key_env,
    )
    return updated, f"{routing.provider}/{routing.model} → {chosen}"


def normalize_team_routings(team: GeneratedTeam, config: KeyConfig | None = None) -> None:
    """Resolve every agent's model in-place; print a substitution report."""
    config = config or KeyConfig.from_file()
    substitutions: list[str] = []
    for agent in team.agents:
        updated, msg = resolve_routing(agent.routing, config)
        if msg:
            agent.routing = updated
            substitutions.append(f"  {agent.role}: {msg}")

    if substitutions:
        print(
            "[team_maker] Model substitutions — requested model not found, using closest available:",
            file=sys.stderr,
        )
        for s in substitutions:
            print(s, file=sys.stderr)
