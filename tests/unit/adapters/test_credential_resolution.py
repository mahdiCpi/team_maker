"""Story 1.6 Task 1 — data-driven per-agent credential resolution (AC 1, 3, 4, 5, 6).

`resolve_credential` is the single place that answers "how does this agent talk
to its model". Both the pre-run gate (`runtime/preflight.py`) and the execution
adapter consume it, so the gate and the run can never disagree — the split-brain
AD-7 exists to prevent.

Every case here is offline and dependency-free: no crewai, no network, no
filesystem. `KeyConfig` objects are constructed directly rather than loaded from
disk so the tests exercise resolution alone.
"""
from __future__ import annotations

import os

from pydantic import SecretStr

from team_maker.adapters.providers.resolution import (
    ResolvedCredential,
    resolve_credential,
)
from team_maker.domain.models import ProviderRouting
from team_maker.keyconfig import KeyConfig


def _routing(provider: str, model: str = "some-model", base_url: str | None = None) -> ProviderRouting:
    return ProviderRouting(provider=provider, model=model, base_url=base_url)


def test_own_key_present_resolves_to_own_provider_with_explicit_key():
    key_config = KeyConfig(keys={"anthropic": SecretStr("sk-ant-real")})

    resolved = resolve_credential(_routing("anthropic", "claude-sonnet-4-6"), key_config)

    assert resolved == ResolvedCredential(
        model="anthropic/claude-sonnet-4-6",
        api_key="sk-ant-real",
        base_url=None,
        via_openrouter=False,
    )


def test_keyless_local_provider_uses_catalog_default_base_url_and_no_key():
    """ollama's endpoint is catalog data (Provider.default_base_url), not an
    `if provider == "ollama"` branch in the engine."""
    resolved = resolve_credential(_routing("ollama", "llama3.2"), KeyConfig(keys={}))

    assert resolved == ResolvedCredential(
        model="ollama/llama3.2",
        api_key=None,
        base_url="http://localhost:11434",
        via_openrouter=False,
    )


def test_keyless_local_provider_honors_package_specified_base_url():
    """A package built for the docker-compose Ollama sidecar carries its own
    base_url; the catalog default must not clobber it (Story 1.5 review fix)."""
    resolved = resolve_credential(
        _routing("ollama", "llama3.2", base_url="http://ollama:11434"), KeyConfig(keys={})
    )

    assert resolved is not None
    assert resolved.base_url == "http://ollama:11434"


def test_openrouter_used_when_own_key_absent_but_provider_is_reachable():
    """AC 4: the registry counts this agent as usable `via-openrouter`, so the
    run must actually go through OpenRouter — not proceed with api_key=None."""
    key_config = KeyConfig(keys={"openrouter": SecretStr("sk-or-real")})

    resolved = resolve_credential(_routing("openai", "gpt-4o"), key_config)

    assert resolved == ResolvedCredential(
        model="openrouter/openai/gpt-4o",
        api_key="sk-or-real",
        base_url=None,
        via_openrouter=True,
    )


def test_own_key_wins_when_both_own_and_openrouter_keys_are_present():
    key_config = KeyConfig(
        keys={"openai": SecretStr("sk-openai-real"), "openrouter": SecretStr("sk-or-real")}
    )

    resolved = resolve_credential(_routing("openai", "gpt-4o"), key_config)

    assert resolved is not None
    assert resolved.via_openrouter is False
    assert resolved.model == "openai/gpt-4o"
    assert resolved.api_key == "sk-openai-real"


def test_openrouter_path_discards_the_providers_own_base_url():
    """A base_url pinned for the agent's own provider is meaningless once the
    call is routed through OpenRouter's gateway — sending OpenRouter-formatted
    requests to that host would fail confusingly."""
    key_config = KeyConfig(keys={"openrouter": SecretStr("sk-or-real")})

    resolved = resolve_credential(
        _routing("openai", "gpt-4o", base_url="https://my-openai-proxy.internal/v1"), key_config
    )

    assert resolved is not None
    assert resolved.via_openrouter is True
    assert resolved.base_url is None


def test_openrouter_vendor_slug_comes_from_the_catalog_not_the_provider_name():
    """xai's OpenRouter vendor slug is `x-ai`, not `xai` — the divergence is
    catalog data (Provider.openrouter_slug), never string surgery.

    Asserts the *behaviour* of `openrouter_model_prefix()`, not just the field:
    checking `openrouter_slug == "x-ai"` alone would still pass if the method
    ignored the slug entirely and returned `name`.
    """
    from team_maker.adapters.providers.registry import get_provider

    xai = get_provider("xai")
    assert xai is not None
    assert xai.openrouter_slug == "x-ai"
    assert xai.openrouter_model_prefix() == "x-ai"

    # ...and a provider with no slug falls back to its own name.
    anthropic = get_provider("anthropic")
    assert anthropic is not None
    assert anthropic.openrouter_slug is None
    assert anthropic.openrouter_model_prefix() == "anthropic"


def test_provider_not_reachable_via_openrouter_is_not_routed_there():
    """Only providers the catalog marks `openrouter_reachable` may fall back to
    the gateway; ollama is keyless-local and never needs it."""
    key_config = KeyConfig(keys={"openrouter": SecretStr("sk-or-real")})

    resolved = resolve_credential(_routing("xai", "grok-4"), key_config)

    assert resolved is None


def test_unknown_provider_resolves_to_none():
    """AC 5: a typo'd provider must be reported, not silently degraded to
    api_key=None as the pre-1.6 engine did."""
    assert resolve_credential(_routing("antropic", "claude"), KeyConfig(keys={})) is None


def test_missing_key_with_no_openrouter_resolves_to_none():
    assert resolve_credential(_routing("anthropic", "claude"), KeyConfig(keys={})) is None


def test_empty_key_value_counts_as_missing():
    """KeyConfig.has() treats an empty secret as absent; resolution must agree,
    or the gate would pass an agent that cannot authenticate."""
    key_config = KeyConfig(keys={"anthropic": SecretStr("")})

    assert resolve_credential(_routing("anthropic", "claude"), key_config) is None


def test_resolution_ignores_process_environment(monkeypatch):
    """AD-7: the resolved credential comes from the passed KeyConfig alone. A
    poisoned ambient env must not leak in, and nothing may be written back."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "POISONED-ENV")
    key_config = KeyConfig(keys={"anthropic": SecretStr("sk-from-key-config")})
    before = dict(os.environ)

    resolved = resolve_credential(_routing("anthropic", "claude-sonnet-4-6"), key_config)

    assert resolved is not None
    assert resolved.api_key == "sk-from-key-config"
    assert dict(os.environ) == before


def test_resolution_matches_an_independently_written_expectation_table():
    """AC 1: `keys status` must never bless a provider the gate then rejects.

    Comparing `resolve_credential` to `report_availability` proves nothing —
    both are `classify()` underneath, so the assertion reduces to `X == X` and
    holds even if the precedence order is inverted. This table is written out by
    hand from the *intended* rules instead, so it fails if `classify` changes:

      * ollama is keyless-local -> always usable, no key needed
      * groq / xai / google cannot be constructed by the pinned engine, so a
        direct key does NOT make them usable; only google is reachable via the
        OpenRouter gateway
      * everyone else: own key, else OpenRouter if reachable, else unusable
    """
    from team_maker.adapters.providers.registry import (
        PROVIDERS,
        is_usable,
        report_availability,
    )

    no_keys = KeyConfig(keys={})
    or_only = KeyConfig(keys={"openrouter": SecretStr("sk-or")})
    all_own = KeyConfig(
        keys={p.name: SecretStr(f"sk-{p.name}") for p in PROVIDERS if p.env_var}
    )

    # (provider, key_config, expected usable?)
    expectations = [
        ("ollama", no_keys, True),
        ("ollama", or_only, True),
        ("anthropic", no_keys, False),
        ("anthropic", or_only, True),
        ("openai", no_keys, False),
        ("openai", or_only, True),
        ("openrouter", no_keys, False),
        ("openrouter", or_only, True),
        # Direct keys present for every provider:
        ("anthropic", all_own, True),
        ("openai", all_own, True),
        ("openrouter", all_own, True),
        # ...but a key does not help these three; only the gateway can.
        ("groq", all_own, False),
        ("xai", all_own, False),
        ("google", all_own, True),  # all_own includes the OpenRouter key
        ("groq", or_only, False),  # inference host, no OpenRouter vendor namespace
        ("xai", or_only, False),  # not marked openrouter_reachable
        ("google", or_only, True),  # reachable via the gateway
    ]

    for provider_name, key_config, expected_usable in expectations:
        resolved = resolve_credential(_routing(provider_name), key_config)
        assert (resolved is not None) is expected_usable, (
            f"{provider_name} with keys {sorted(key_config.keys)}: "
            f"expected usable={expected_usable}"
        )
        # And the user-facing report must agree with what the gate just did.
        reported = {s.name: is_usable(s.status) for s in report_availability(key_config)}
        assert reported[provider_name] is expected_usable, (
            f"`keys status` disagrees with the gate for {provider_name}"
        )


def test_no_key_at_all_does_not_fall_back_to_process_environment(monkeypatch):
    """The stronger half of the same invariant: with an empty KeyConfig, an
    ambient ANTHROPIC_API_KEY must NOT rescue the agent — it resolves to None so
    the pre-run gate reports it."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "POISONED-ENV")

    assert resolve_credential(_routing("anthropic", "claude"), KeyConfig(keys={})) is None
