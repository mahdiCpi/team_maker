"""LLM provider adapters + the data-driven ``create_provider`` factory (Story 0.1).

Provider selection is driven by the ``_ADAPTERS`` registry (data), not an
``if provider == ...`` chain — adding a provider is a registry entry, never a new
code branch (AD-1/AD-8).

Note: this package (LLM *adapters*) is a different concern from
``team_maker/providers/`` (Story 1.1's key-availability *catalog*). They are not
merged here; that reconciliation is Story 0.4.
"""
from __future__ import annotations

from collections.abc import Callable

from team_maker.adapters.providers.anthropic_provider import AnthropicProvider
from team_maker.adapters.providers.google_provider import GoogleProvider
from team_maker.adapters.providers.ollama_provider import OllamaProvider
from team_maker.adapters.providers.openai_provider import OpenAIProvider
from team_maker.adapters.providers.xai_provider import XAIProvider
from team_maker.ports.llm_provider import LLMProvider
from team_maker.schema.request import ProviderConfig

# Registry: provider id (lowercased) -> builder. Data, not control flow.
_ADAPTERS: dict[str, Callable[[ProviderConfig], LLMProvider]] = {
    "anthropic": lambda c: AnthropicProvider(
        model=c.model, api_key_env=c.api_key_env or "ANTHROPIC_API_KEY"
    ),
    "openai": lambda c: OpenAIProvider(
        model=c.model, api_key_env=c.api_key_env or "OPENAI_API_KEY"
    ),
    "xai": lambda c: XAIProvider(
        model=c.model,
        api_key_env=c.api_key_env or "XAI_API_KEY",
        base_url=c.base_url or "https://api.x.ai/v1",
    ),
    "google": lambda c: GoogleProvider(
        model=c.model, api_key_env=c.api_key_env or "GOOGLE_AI_API_KEY"
    ),
    "ollama": lambda c: OllamaProvider(
        model=c.model, base_url=c.base_url or "http://localhost:11434"
    ),
}


def create_provider(config: ProviderConfig) -> LLMProvider:
    """Instantiate the correct provider adapter from a ProviderConfig (data-driven)."""
    provider = config.provider.lower()
    builder = _ADAPTERS.get(provider)
    if builder is None:
        raise ValueError(
            f"Unknown provider '{provider}'. Supported: {' | '.join(_ADAPTERS)}"
        )
    return builder(config)


__all__ = [
    "AnthropicProvider",
    "OpenAIProvider",
    "XAIProvider",
    "OllamaProvider",
    "GoogleProvider",
    "create_provider",
]
