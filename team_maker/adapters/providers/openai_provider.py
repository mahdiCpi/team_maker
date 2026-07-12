"""OpenAI LLM adapter (implements the LLMProvider port structurally)."""
from __future__ import annotations

import os
from typing import TypeVar

from pydantic import BaseModel

from team_maker.adapters.providers._model_match import _closest_model

T = TypeVar("T", bound=BaseModel)


class OpenAIProvider:
    """Uses beta structured-output endpoint for Pydantic-native parsing."""

    def __init__(self, model: str = "gpt-4o", api_key_env: str = "OPENAI_API_KEY"):
        self.model = model
        self.api_key_env = api_key_env
        self._model_resolved = False

    def _maybe_resolve_model(self, client) -> None:
        if self._model_resolved:
            return
        self._model_resolved = True
        try:
            available = [m.id for m in client.models.list()]
            self.model = _closest_model(self.model, available, "gpt-4o")
        except Exception:
            pass

    def complete_structured(self, system: str, user: str, response_model: type[T]) -> T:
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError(
                "openai package is required for the OpenAI provider. "
                "Install with: pip install 'team_maker[openai]'"
            )

        api_key = os.environ.get(self.api_key_env)
        if not api_key:
            raise EnvironmentError(
                f"Environment variable '{self.api_key_env}' is not set."
            )

        client = OpenAI(api_key=api_key)
        self._maybe_resolve_model(client)

        response = client.beta.chat.completions.parse(
            model=self.model,
            response_format=response_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )

        parsed = response.choices[0].message.parsed
        if parsed is None:
            raise ValueError(
                "OpenAI returned a refusal or empty parsed response. "
                f"Refusal: {response.choices[0].message.refusal}"
            )
        return parsed
