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


# UNIFIED CREDENTIAL-RESOLUTION POLICY (Story 4.2)
# ==============================================
# 
# This is the single source of truth for credential resolution policy that all
# components (CLI, API, runtime preflight, runtime execution, model resolver) must follow.
#
# 1. KEY LOADING
#    - Keys are loaded from the Key Config file first
#    - Process environment variables are used as fallback for providers not set in the file
#    - File values always override environment values (file wins)
#
# 2. PROVIDER-NAME AND ALIAS MAPPING
#    - Both canonical environment variable names (e.g., ANTHROPIC_API_KEY) and bare 
#      provider names (e.g., anthropic) map to provider catalog entries
#    - Alias support: GOOGLE_API_KEY -> google (per Story 2.9)
#    - Mapping is performed via env_to_provider() function in registry.py
#
# 3. RESOLUTION PRECEDENCE
#    - Key Config file values override environment fallback values (file wins)
#    - Within a Key Config file, duplicate recognized entries: last-recognized-entry wins
#      with a warning issued containing provider names and key names only (Story 4.2 AC 2)
#    - For environment fallback: canonical environment variable is checked first, 
#      then each alias in the order defined in the catalog
#
# 4. AVAILABILITY CLASSIFICATION
#    - Uses the single classify() function from registry.py
#    - Produces exactly one of: available, keyless-local, via-openrouter, 
#      unsupported-by-runtime, missing
#    - Classification order (highest priority first):
#      a) keyless_local=True -> STATUS_KEYLESS_LOCAL
#      b) runtime_supported=True AND config.has(provider) -> STATUS_AVAILABLE
#      c) openrouter_reachable=True AND config.has(OPENROUTER) -> STATUS_VIA_OPENROUTER
#      d) runtime_supported=False -> STATUS_UNSUPPORTED_BY_RUNTIME
#      e) Otherwise -> STATUS_MISSING
#
# 5. DIRECT-PROVIDER RESOLUTION
#    - Each provider's credential is resolved independently against the catalog
#    - Uses the provider's canonical name from the catalog
#    - Resolution via resolve_credential() which uses classify() for availability
#
# 6. GATEWAY/OPENROUTER RESOLUTION
#    - OpenRouter reachability determined by openrouter_reachable boolean flag 
#      on each Provider catalog entry (Story 4.2 AC 4)
#    - OPENROUTER constant in registry.py is the single hardcoded reference to gateway name
#    - Adding a second gateway: add catalog entry with openrouter_reachable=True and 
#      appropriate openrouter_slug
#    - No is_gateway flag; openrouter_reachable serves this purpose
#
# 7. MODEL QUALIFICATION
#    - Direct openrouter routing entries with unqualified model strings are 
#      qualified using provider.openrouter_model_prefix() method
#    - openrouter_model_prefix() returns openrouter_slug if set, else name
#    - Unqualified models qualified to: openrouter/<prefix>/<model>
#    - Already-qualified models (starting with "openrouter/") unchanged
#    - Unknown/unmappable models rejected with ValidationError
#
# 8. WARNING BEHAVIOR
#    - Duplicate keys: warning contains provider names and key names only, never values
#    - Keyless providers with supplied keys: warning contains provider name and key name only
#    - All warnings use safe formatting that never includes SecretStr values
#
# 9. SECURITY REQUIREMENTS
#    - No credential values may appear in any user-visible output
#    - No credential values may appear in any log output
#    - No credential values may appear in any exception message
#    - Secret-bearing objects (ResolvedCredential) remain non-serializable via repr=False
#    - All secret handling uses Story 4.1's sanitization utilities
#
# 10. API/CLI LIFECYCLE DISTINCTION
#     - CLI: May temporarily bridge credential into environment variable for command 
#       duration using context manager, must restore previous value afterward
#     - API: Must NOT mutate process environment variables per request; credentials 
#       resolved from Key Config and passed directly to adapter constructors
#     - Shared: Both use same resolution rules, produce identical results for same inputs
#     - Shared: Neither leaves credentials in environment unexpectedly after operations
#     - Shared: No request races or thread-safety issues introduced
#
# 11. PARITY REQUIREMENTS
#     - CLI keys status and API key-status endpoint must produce identical classifications
#     - Runtime preflight and execution must resolve identical credentials
#     - Both use the same classify() function from registry.py
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
    infer_openrouter_vendor,
    is_usable,
)
from team_maker.domain.models import ProviderRouting, ResolvedCredential
from team_maker.keyconfig import KeyConfig

# Re-exported so existing importers of this module keep working; the canonical
# home is `domain/models.py` (it is the type the ExecutionEngine port speaks, so
# it must not live in the adapter layer).
__all__ = ["ResolvedCredential", "resolve_credential", "UnqualifiedModelError"]


class UnqualifiedModelError(ValueError):
    """A direct `openrouter` routing entry's model cannot be safely qualified
    with a vendor namespace (Story 4.2 AC8's "validation error"): the model
    string does not match exactly one catalog vendor's known name prefixes, so
    guessing would risk silently routing to the wrong vendor.
    """


def _qualify_direct_openrouter_model(model: str) -> str:
    """Qualify a *direct* `openrouter` routing entry's model with its vendor
    namespace: ``gpt-4o`` -> ``openrouter/openai/gpt-4o`` (Story 4.2 AC8).

    Already-qualified models (starting with ``openrouter/``) pass through
    unchanged rather than being double-prefixed. Raises `UnqualifiedModelError`
    -- never a guess -- when the vendor cannot be determined unambiguously.
    """
    if model.startswith(f"{OPENROUTER}/"):
        return model
    vendor = infer_openrouter_vendor(model)
    if vendor is None:
        raise UnqualifiedModelError(
            f"Cannot determine the OpenRouter vendor namespace for model '{model}'. "
            f"Use the fully-qualified form 'openrouter/<vendor>/{model}' instead."
        )
    return f"{OPENROUTER}/{vendor.openrouter_model_prefix()}/{model}"


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
        # A *direct* `openrouter` routing entry (routing.provider == "openrouter")
        # needs the same vendor-namespace qualification the gateway-fallback
        # branch below applies -- `openrouter` is not itself a model vendor, so
        # an unqualified model string like "gpt-4o" is meaningless to it (AC8).
        model = (
            _qualify_direct_openrouter_model(routing.model)
            if provider.name == OPENROUTER
            else f"{provider.name}/{routing.model}"
        )
        return ResolvedCredential(
            model=model,
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
