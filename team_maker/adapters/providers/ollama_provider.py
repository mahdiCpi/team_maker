"""Ollama LLM adapter — local models via OpenAI-compatible API (implements the port)."""
from __future__ import annotations

import json
from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class OllamaProvider:
    """Calls a local Ollama server using the OpenAI-compatible /v1 endpoint."""

    def __init__(
        self,
        model: str = "llama3.2",
        base_url: str = "http://localhost:11434",
    ):
        self.model = model
        self.base_url = base_url.rstrip("/")

    def complete_structured(self, system: str, user: str, response_model: type[T]) -> T:
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError(
                "openai package is required for the Ollama provider (uses OpenAI-compatible API). "
                "Install with: pip install 'team_maker[openai]'"
            )

        client = OpenAI(
            base_url=f"{self.base_url}/v1",
            api_key="ollama",  # Ollama ignores the key but the client requires it
        )

        schema = response_model.model_json_schema()
        schema_str = json.dumps(schema, indent=2)

        augmented_system = (
            f"{system}\n\n"
            f"## Output format\n"
            f"Respond with a single JSON object that exactly matches this schema:\n"
            f"```json\n{schema_str}\n```\n"
            f"Do not include any text before or after the JSON."
        )

        response = client.chat.completions.create(
            model=self.model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": augmented_system},
                {"role": "user", "content": user},
            ],
        )

        raw = response.choices[0].message.content or ""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Ollama returned invalid JSON: {exc}\nRaw response:\n{raw}"
            ) from exc

        return response_model.model_validate(data)
