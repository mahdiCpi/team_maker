"""OpenRouter LLM adapter — OpenAI-compatible gateway (implements the LLMProvider port).

Added by Story 2.0 (AC 11). The key catalog already knew OpenRouter
(`registry.py:105`), but only as a *routing gateway for team agents* — there
was no authoring adapter, so `create_provider(provider="openrouter")` raised.
AC 10 makes the API's authoring provider parametric, and a gateway is one of
the three shapes it must support (one key, many models), so this row exists.

Deliberately a near-copy of `xai_provider.py` rather than a new design: both
are the same OpenAI-SDK-over-`base_url` shape, and keeping them identical means
the next reader sees one pattern instead of two. Adding a provider is
adapter/config, never core (AD-8).
"""
from __future__ import annotations

import json
import os
import re
from typing import TypeVar

from pydantic import BaseModel

from team_maker.adapters.providers._timeouts import request_timeout

T = TypeVar("T", bound=BaseModel)


class OpenRouterProvider:
    """Calls OpenRouter's OpenAI-compatible API and validates JSON against a Pydantic model.

    Model ids are `<model-creator>/<model>` (e.g. `anthropic/claude-sonnet-4-6`)
    — the organisation that made the weights, not the company serving them.
    """

    def __init__(
        self,
        model: str = "anthropic/claude-sonnet-4-6",
        api_key_env: str = "OPENROUTER_API_KEY",
        base_url: str = "https://openrouter.ai/api/v1",
    ):
        self.model = model
        self.api_key_env = api_key_env
        self.base_url = base_url.rstrip("/")

    def complete_structured(self, system: str, user: str, response_model: type[T]) -> T:
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError(
                "openai package is required for the OpenRouter provider (uses "
                "OpenAI-compatible API). Install with: pip install 'team_maker[openai]'"
            )

        api_key = os.environ.get(self.api_key_env)
        if not api_key:
            raise EnvironmentError(
                f"Environment variable '{self.api_key_env}' is not set. "
                "Set it to your OpenRouter API key."
            )

        client = OpenAI(
            base_url=f"{self.base_url}",
            api_key=api_key,
            # Explicit timeout — see `_timeouts`; the SDK default is 10 minutes.
            timeout=request_timeout(),
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
                    f"OpenRouter provider returned invalid JSON: {exc}\n"
                    f"Raw response:\n{raw[:500]}"
                ) from exc
            data = json.loads(match.group())

        return response_model.model_validate(data)
