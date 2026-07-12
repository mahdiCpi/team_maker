"""Anthropic LLM adapter (implements the LLMProvider port structurally)."""
from __future__ import annotations

import os
from typing import TypeVar

from pydantic import BaseModel

from team_maker.adapters.providers._model_match import _closest_model

T = TypeVar("T", bound=BaseModel)


class AnthropicProvider:
    """Uses tool-use with forced tool call to guarantee structured JSON output."""

    def __init__(self, model: str = "claude-sonnet-4-6", api_key_env: str = "ANTHROPIC_API_KEY"):
        self.model = model
        self.api_key_env = api_key_env
        self._model_resolved = False

    def _maybe_resolve_model(self, client) -> None:
        if self._model_resolved:
            return
        self._model_resolved = True
        try:
            available = [m.id for m in client.models.list()]
            self.model = _closest_model(self.model, available, "claude-sonnet-4-6")
        except Exception:
            pass

    def complete_structured(self, system: str, user: str, response_model: type[T]) -> T:
        try:
            import anthropic
        except ImportError:
            raise ImportError(
                "anthropic package is required for the Anthropic provider. "
                "Install with: pip install 'team_maker[anthropic]'"
            )

        api_key = os.environ.get(self.api_key_env)
        if not api_key:
            raise EnvironmentError(
                f"Environment variable '{self.api_key_env}' is not set. "
                "Set it to your Anthropic API key."
            )

        client = anthropic.Anthropic(api_key=api_key)
        self._maybe_resolve_model(client)

        schema = response_model.model_json_schema()
        # Anthropic requires additionalProperties to be absent or false on object schemas
        schema.setdefault("additionalProperties", False)

        response = client.messages.create(
            model=self.model,
            max_tokens=8192,
            system=system,
            tools=[
                {
                    "name": "output_plan",
                    "description": "Output the structured team plan",
                    "input_schema": schema,
                }
            ],
            tool_choice={"type": "tool", "name": "output_plan"},
            messages=[{"role": "user", "content": user}],
        )

        tool_block = next(
            (b for b in response.content if b.type == "tool_use"),
            None,
        )
        if tool_block is None:
            raise ValueError(
                f"Anthropic did not return a tool_use block. "
                f"Stop reason: {response.stop_reason}. "
                f"Content: {response.content}"
            )

        return response_model.model_validate(tool_block.input)
