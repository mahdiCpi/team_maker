"""Per-agent credential resolution (Story 1.6, AD-7/AD-8/AD-9).

Answers one question — *how does this agent talk to its model* — and answers it
in exactly one place. The pre-run gate (`team_maker/runtime/preflight.py`) and
the execution adapter both consume this, so a run can never be admitted on one
set of credentials and then executed on another.

Every provider difference is read from the `Provider` catalog row, never from a
`provider == "..."` comparison (project-context: "never branch on provider
name"; AD-8: adding a provider is a catalog entry, not code).

This module is deliberately dependency-free: no crewai, no network, no
filesystem, and — critically for AD-7 — no `os.environ` access. The only
credential source is the `KeyConfig` passed in.
"""
from __future__ import annotations

from typing import Optional

from team_maker.adapters.providers.registry import (
    OPENROUTER,
    STATUS_AVAILABLE,
    STATUS_KEYLESS_LOCAL,
    STATUS_VIA_OPENROUTER,
    classify,
    get_provider,
    is_usable,
)
from team_maker.domain.models import ProviderRouting, ResolvedCredential
from team_maker.keyconfig import KeyConfig

# Re-exported so existing importers of this module keep working; the canonical
# home is `domain/models.py` (it is the type the ExecutionEngine port speaks, so
# it must not live in the adapter layer).
__all__ = ["ResolvedCredential", "resolve_credential"]


def resolve_credential(
    routing: ProviderRouting, key_config: KeyConfig
) -> Optional[ResolvedCredential]:
    """Resolve one agent's routing entry against the available keys.

    Returns ``None`` when the agent has no usable credential — the caller (the
    pre-run gate) owns turning that into a plain-language message naming the
    provider, so this stays a pure lookup.
    """
    provider = get_provider(routing.provider)
    if provider is None:
        return None

    # Availability precedence lives in exactly one place (registry.classify), so
    # what `keys status` reports as usable and what actually receives a
    # credential here cannot drift apart.
    status = classify(provider, key_config)
    if not is_usable(status):
        return None

    if status == STATUS_KEYLESS_LOCAL:
        return ResolvedCredential(
            model=f"{provider.name}/{routing.model}",
            api_key=None,
            base_url=routing.base_url or provider.default_base_url,
            via_openrouter=False,
        )

    if status == STATUS_AVAILABLE:
        return ResolvedCredential(
            model=f"{provider.name}/{routing.model}",
            api_key=key_config.keys[provider.name].get_secret_value(),
            # Only the package's own pin applies here. `default_base_url` is the
            # keyless-local fallback above; letting it leak into the hosted path
            # would silently redirect a keyed provider to a local endpoint.
            base_url=routing.base_url,
            via_openrouter=False,
        )

    if status == STATUS_VIA_OPENROUTER:
        return ResolvedCredential(
            model=f"{OPENROUTER}/{provider.openrouter_model_prefix()}/{routing.model}",
            api_key=key_config.keys[OPENROUTER].get_secret_value(),
            # A base_url pinned for the agent's own provider does not apply once
            # the call goes through the gateway — the engine uses OpenRouter's.
            base_url=None,
            via_openrouter=True,
        )

    # Not an `assert`: asserts vanish under `python -O`, which would drop a new
    # usable status straight into the OpenRouter branch and raise KeyError on a
    # missing gateway key instead of failing here, clearly.
    raise ValueError(
        f"{provider.name} classified usable as '{status}', which resolve_credential "
        "does not know how to turn into a credential — add a branch here when "
        "adding a usable status to the registry."
    )
