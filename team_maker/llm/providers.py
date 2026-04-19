"""Pluggable LLM provider backends for the team planner."""
from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from typing import Type, TypeVar

from pydantic import BaseModel

from team_maker.schema.request import ProviderConfig

T = TypeVar("T", bound=BaseModel)


class LLMProvider(ABC):
    """Abstract base — takes messages, returns a parsed Pydantic model."""

    @abstractmethod
    def complete_structured(
        self,
        system: str,
        user: str,
        response_model: Type[T],
    ) -> T:
        ...


# ---------------------------------------------------------------------------
# Anthropic
# ---------------------------------------------------------------------------

class AnthropicProvider(LLMProvider):
    """Uses tool-use with forced tool call to guarantee structured JSON output."""

    def __init__(self, model: str = "claude-sonnet-4-6", api_key_env: str = "ANTHROPIC_API_KEY"):
        self.model = model
        self.api_key_env = api_key_env

    def complete_structured(self, system: str, user: str, response_model: Type[T]) -> T:
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


# ---------------------------------------------------------------------------
# OpenAI
# ---------------------------------------------------------------------------

class OpenAIProvider(LLMProvider):
    """Uses beta structured-output endpoint for Pydantic-native parsing."""

    def __init__(self, model: str = "gpt-4o", api_key_env: str = "OPENAI_API_KEY"):
        self.model = model
        self.api_key_env = api_key_env

    def complete_structured(self, system: str, user: str, response_model: Type[T]) -> T:
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


# ---------------------------------------------------------------------------
# Ollama  (local models via OpenAI-compatible API)
# ---------------------------------------------------------------------------

class OllamaProvider(LLMProvider):
    """Calls a local Ollama server using the OpenAI-compatible /v1 endpoint."""

    def __init__(
        self,
        model: str = "llama3.2",
        base_url: str = "http://localhost:11434",
    ):
        self.model = model
        self.base_url = base_url.rstrip("/")

    def complete_structured(self, system: str, user: str, response_model: Type[T]) -> T:
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


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def create_provider(config: ProviderConfig) -> LLMProvider:
    """Instantiate the correct provider from a ProviderConfig."""
    provider = config.provider.lower()

    if provider == "anthropic":
        return AnthropicProvider(
            model=config.model,
            api_key_env=config.api_key_env or "ANTHROPIC_API_KEY",
        )
    if provider == "openai":
        return OpenAIProvider(
            model=config.model,
            api_key_env=config.api_key_env or "OPENAI_API_KEY",
        )
    if provider == "ollama":
        return OllamaProvider(
            model=config.model,
            base_url=config.base_url or "http://localhost:11434",
        )

    raise ValueError(
        f"Unknown provider '{provider}'. Supported: anthropic | openai | ollama"
    )
