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

from team_maker.domain.models import GeneratedTeam, ProviderRouting


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
def _anthropic_models(api_key_env: str) -> tuple[str, ...]:
    try:
        import anthropic
        key = os.environ.get(api_key_env, "")
        if not key:
            return ()
        return tuple(m.id for m in anthropic.Anthropic(api_key=key).models.list())
    except Exception:
        return ()


@lru_cache(maxsize=None)
def _openai_models(api_key_env: str) -> tuple[str, ...]:
    try:
        from openai import OpenAI
        key = os.environ.get(api_key_env, "")
        if not key:
            return ()
        return tuple(m.id for m in OpenAI(api_key=key).models.list())
    except Exception:
        return ()


@lru_cache(maxsize=None)
def _xai_models(api_key_env: str) -> tuple[str, ...]:
    try:
        from openai import OpenAI
        key = os.environ.get(api_key_env, "")
        if not key:
            return ()
        client = OpenAI(base_url="https://api.x.ai/v1", api_key=key)
        return tuple(m.id for m in client.models.list())
    except Exception:
        return ()


@lru_cache(maxsize=None)
def _google_models(api_key_env: str) -> tuple[str, ...]:
    key = os.environ.get(api_key_env, "")
    if not key:
        return ()
    # Try new google.genai SDK first, fall back to deprecated google.generativeai.
    try:
        import google.genai as genai_new
        client = genai_new.Client(api_key=key)
        return tuple(m.name.removeprefix("models/") for m in client.models.list())
    except Exception:
        pass
    try:
        import warnings
        import google.generativeai as genai
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            genai.configure(api_key=key)
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

def resolve_routing(routing: ProviderRouting) -> tuple[ProviderRouting, str | None]:
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
    api_key_env = routing.api_key_env or ""
    available = list(fetcher(api_key_env))

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


def normalize_team_routings(team: GeneratedTeam) -> None:
    """Resolve every agent's model in-place; print a substitution report."""
    substitutions: list[str] = []
    for agent in team.agents:
        updated, msg = resolve_routing(agent.routing)
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
