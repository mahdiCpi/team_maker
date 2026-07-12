"""Back-compat shim — provider adapters moved to ``team_maker.adapters.providers``.

Story 0.1 migrated the LLM providers onto the ports-and-adapters spine:
- the ``LLMProvider`` port now lives in ``team_maker.ports.llm_provider``
- the concrete adapters + ``create_provider`` live in ``team_maker.adapters.providers``

New code should import from those locations. This module re-exports them so existing
imports (``from team_maker.llm.providers import ...``) keep working.
"""
from __future__ import annotations

from team_maker.adapters.providers import (
    AnthropicProvider,
    GoogleProvider,
    OllamaProvider,
    OpenAIProvider,
    XAIProvider,
    create_provider,
)
from team_maker.adapters.providers._model_match import _closest_model  # noqa: F401  (back-compat)
from team_maker.ports.llm_provider import (
    LLMProvider,
    T,  # noqa: F401  (back-compat)
)

__all__ = [
    "LLMProvider",
    "AnthropicProvider",
    "OpenAIProvider",
    "XAIProvider",
    "OllamaProvider",
    "GoogleProvider",
    "create_provider",
]
