"""Story 0.1 — LLMProvider port location/shape + data-driven create_provider factory.

Verifies the ports-and-adapters migration: the port lives under team_maker/ports/,
concrete adapters satisfy it structurally, and create_provider resolves every known
provider via the registry (no branching on provider name) while rejecting unknowns.
"""
from __future__ import annotations

import pytest

from team_maker.adapters.providers import create_provider
from team_maker.ports.llm_provider import LLMProvider
from team_maker.schema.request import ProviderConfig


def test_port_lives_in_ports_package():
    assert LLMProvider.__module__ == "team_maker.ports.llm_provider"


def test_object_with_complete_structured_satisfies_port():
    class Fake:
        def complete_structured(self, system, user, response_model):  # noqa: ANN001, ANN201
            return response_model()

    assert isinstance(Fake(), LLMProvider)


def test_object_without_method_does_not_satisfy_port():
    class NotAProvider:
        pass

    assert not isinstance(NotAProvider(), LLMProvider)


@pytest.mark.parametrize("provider", ["anthropic", "openai", "xai", "google", "ollama"])
def test_create_provider_resolves_all_known_ids(provider):
    obj = create_provider(ProviderConfig(provider=provider, model="some-model"))
    # Structural: every adapter implements the port (has complete_structured).
    assert isinstance(obj, LLMProvider)


def test_create_provider_is_case_insensitive():
    obj = create_provider(ProviderConfig(provider="ANTHROPIC", model="claude-sonnet-4-6"))
    assert isinstance(obj, LLMProvider)


def test_create_provider_unknown_raises():
    with pytest.raises(ValueError, match="Unknown provider"):
        create_provider(ProviderConfig(provider="not_a_provider", model="x"))
