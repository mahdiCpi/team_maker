"""`describe_unresolved_provider` — the one fix-hint generator (Story 2.3, Task 3).

Promoted from `preflight._describe` so the API's key check can reuse it instead of
re-deriving "what should this user actually do about it?" from catalog fields. The
hard-won behaviour it encodes is the *negative* cases: never ask for a key that
cannot help, and never offer OpenRouter to a provider it cannot reach.

`test_preflight.py` covers the credential gate that consumes this; these tests
cover the hint text itself.
"""
from __future__ import annotations

from team_maker.runtime.preflight import describe_unresolved_provider


def test_a_missing_direct_key_names_the_env_var_and_the_openrouter_alternative():
    hint = describe_unresolved_provider("anthropic", ["writer"])

    assert hint.provider == "anthropic"
    assert hint.expected_key == "ANTHROPIC_API_KEY"
    assert "ANTHROPIC_API_KEY" in hint.reason
    # anthropic IS openrouter-reachable, so the gateway is a real alternative.
    assert "OPENROUTER_API_KEY" in hint.reason


def test_an_unsupported_provider_is_not_told_to_add_a_key():
    """`groq` is the dead end that produced two false statements in a row before
    Story 2.0 fixed it: a 503 saying "add GROQ_API_KEY", then — once the user
    complied — "'groq' is not a known provider". A key genuinely cannot help."""
    hint = describe_unresolved_provider("groq", ["judge"])

    assert hint.expected_key is None
    assert "GROQ_API_KEY" not in hint.reason
    assert "no native groq provider" in hint.reason
    # groq is an inference host with no vendor namespace on OpenRouter, so the
    # gateway is NOT an escape hatch for it and must not be offered.
    assert "OpenRouter" not in hint.reason


def test_an_unsupported_but_gateway_reachable_provider_is_offered_the_gateway():
    """`google` cannot be called directly by the pinned engine, but its models do
    have an OpenRouter namespace — so unlike groq it has a real way forward."""
    hint = describe_unresolved_provider("google", ["researcher"])

    assert hint.expected_key is None
    assert "crewai[google-genai]" in hint.reason
    assert "OPENROUTER_API_KEY" in hint.reason


def test_an_unrecognized_provider_lists_the_ones_that_exist():
    hint = describe_unresolved_provider("not-a-provider", ["writer"])

    assert hint.expected_key is None
    assert "unrecognized provider" in hint.reason
    assert "anthropic" in hint.reason


def test_roles_are_carried_through_as_an_immutable_tuple():
    hint = describe_unresolved_provider("anthropic", ["writer", "editor"])

    assert hint.roles == ("writer", "editor")


def test_roles_are_optional_so_a_provider_level_caller_need_not_invent_them():
    """The key check reports provider status with no role attached (AC 1). It must
    not have to pass a fake role to get a hint."""
    hint = describe_unresolved_provider("anthropic")

    assert hint.roles == ()
    assert "ANTHROPIC_API_KEY" in hint.reason
