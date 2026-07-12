"""xAI (Grok) LLM adapter — OpenAI-compatible API (implements the LLMProvider port)."""
from __future__ import annotations

import json
import os
import re
from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class XAIProvider:
    """Calls xAI's OpenAI-compatible API and validates JSON against a Pydantic model."""

    def __init__(
        self,
        model: str = "grok-2",
        api_key_env: str = "XAI_API_KEY",
        base_url: str = "https://api.x.ai/v1",
    ):
        self.model = model
        self.api_key_env = api_key_env
        self.base_url = base_url.rstrip("/")

    def complete_structured(self, system: str, user: str, response_model: type[T]) -> T:
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError(
                "openai package is required for the xAI provider (uses OpenAI-compatible API). "
                "Install with: pip install 'team_maker[openai]'"
            )

        api_key = os.environ.get(self.api_key_env)
        if not api_key:
            raise EnvironmentError(
                f"Environment variable '{self.api_key_env}' is not set. "
                "Set it to your xAI API key."
            )

        client = OpenAI(
            base_url=f"{self.base_url}",
            api_key=api_key,
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
        # Strip markdown fences if the model added them despite instructions.
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw.rstrip())
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if not match:
                raise ValueError(
                    f"xAI provider returned invalid JSON: {exc}\nRaw response:\n{raw[:500]}"
                ) from exc
            data = json.loads(match.group())

        return response_model.model_validate(data)
