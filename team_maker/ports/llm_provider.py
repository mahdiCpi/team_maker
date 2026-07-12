"""LLMProvider port — the single seam all structured LLM access flows through.

Spine invariants AD-2/AD-8: core code depends only on this Protocol; concrete
providers live under ``team_maker/adapters/providers/`` and are selected by data
(the ``create_provider`` registry), never by branching on provider name.

The method is ``complete_structured`` (system + user message → a parsed Pydantic
model). This is the real, in-use signature and supersedes the ``complete() -> str``
sketch in Story 1.2 Task 1; the Composer (Story 1.2) will call this method with a
Pydantic ``response_model``.
"""
from __future__ import annotations

from typing import Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


@runtime_checkable
class LLMProvider(Protocol):
    """Takes a system + user message and returns a parsed Pydantic model."""

    def complete_structured(self, system: str, user: str, response_model: type[T]) -> T:
        ...
