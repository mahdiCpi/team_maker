"""Story 0.4 — model_resolver.py consults KeyConfig before falling back to os.environ.

Proves the additive Key-Config-first resolution: resolve_routing() must resolve a
provider's key via a loaded KeyConfig first, and fall back to os.environ.get(api_key_env)
only when the KeyConfig has no entry for that provider (today's exact behavior,
unchanged).
"""
from __future__ import annotations

from pydantic import SecretStr

from team_maker.domain.models import ProviderRouting
from team_maker.keyconfig import KeyConfig
from team_maker.llm import model_resolver


def _patch_anthropic_fetcher(monkeypatch):
    calls: list[str] = []

    def fake_fetcher(api_key: str) -> tuple[str, ...]:
        calls.append(api_key)
        return ("claude-sonnet-4-6",)

    monkeypatch.setitem(
        model_resolver._FETCHER_MAP, "anthropic", (fake_fetcher, "claude-sonnet-4-6")
    )
    return calls


def test_resolve_routing_uses_keyconfig_key_when_no_env_var(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    calls = _patch_anthropic_fetcher(monkeypatch)
    config = KeyConfig(keys={"anthropic": SecretStr("sk-from-file")})
    routing = ProviderRouting(
        provider="anthropic", model="claude-sonnet-4-6", api_key_env="ANTHROPIC_API_KEY"
    )

    model_resolver.resolve_routing(routing, config)

    assert calls == ["sk-from-file"]


def test_resolve_routing_falls_back_to_environ_when_keyconfig_has_no_entry(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-from-env")
    calls = _patch_anthropic_fetcher(monkeypatch)
    config = KeyConfig()  # empty — config.has("anthropic") is False
    routing = ProviderRouting(
        provider="anthropic", model="claude-sonnet-4-6", api_key_env="ANTHROPIC_API_KEY"
    )

    model_resolver.resolve_routing(routing, config)

    assert calls == ["sk-from-env"]


def test_resolve_routing_honors_custom_api_key_env_override_over_keyconfig(monkeypatch):
    """Code review fix: a per-agent custom api_key_env (naming a non-default env var) must
    always read that exact env var, even when KeyConfig already has an entry for the
    provider auto-filled from the *standard* env var — the override must never be shadowed."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-standard-env")
    monkeypatch.setenv("ROLE_SPECIFIC_KEY", "sk-custom-override")
    calls = _patch_anthropic_fetcher(monkeypatch)
    # KeyConfig has an entry for "anthropic" (as it would if from_file() filled it from the
    # standard ANTHROPIC_API_KEY env var) — the custom override must win anyway.
    config = KeyConfig(keys={"anthropic": SecretStr("sk-standard-env")})
    routing = ProviderRouting(
        provider="anthropic", model="claude-sonnet-4-6", api_key_env="ROLE_SPECIFIC_KEY"
    )

    model_resolver.resolve_routing(routing, config)

    assert calls == ["sk-custom-override"]


def test_normalize_team_routings_accepts_explicit_config_without_reloading(monkeypatch):
    """normalize_team_routings must not reload KeyConfig.from_file() per agent when an
    explicit config is passed in (Task 3 — load once, pass to every resolve_routing call)."""
    load_calls = []
    monkeypatch.setattr(
        KeyConfig, "from_file", classmethod(lambda cls, *a, **kw: load_calls.append(1) or cls())
    )

    class _FakeTeam:
        agents: list = []

    config = KeyConfig(keys={"anthropic": SecretStr("sk-explicit")})
    model_resolver.normalize_team_routings(_FakeTeam(), config)

    assert load_calls == []
