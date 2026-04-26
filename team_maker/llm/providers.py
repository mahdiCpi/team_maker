"""Pluggable LLM provider backends for the team planner."""
from __future__ import annotations

import difflib
import json
import os
import re
import sys
from abc import ABC, abstractmethod
from typing import Type, TypeVar

from pydantic import BaseModel

from team_maker.schema.request import ProviderConfig

T = TypeVar("T", bound=BaseModel)


def _closest_model(requested: str, available: list[str], fallback: str) -> str:
    """Return the available model closest to `requested`, or `fallback` if list is empty."""
    if not available:
        return fallback
    if requested in available:
        return requested
    ranked = sorted(
        available,
        key=lambda m: difflib.SequenceMatcher(None, requested, m).ratio(),
        reverse=True,
    )
    chosen = ranked[0]
    print(
        f"[team_maker] WARNING: model '{requested}' not available. "
        f"Using closest match: '{chosen}'",
        file=sys.stderr,
    )
    return chosen


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


# ---------------------------------------------------------------------------
# OpenAI
# ---------------------------------------------------------------------------

class OpenAIProvider(LLMProvider):
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


# ---------------------------------------------------------------------------
# xAI (Grok) — OpenAI-compatible API
# ---------------------------------------------------------------------------

class XAIProvider(LLMProvider):
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

    def complete_structured(self, system: str, user: str, response_model: Type[T]) -> T:
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
# Google (Gemini)
# ---------------------------------------------------------------------------

class GoogleProvider(LLMProvider):
    """Uses google-generativeai with JSON response mode for structured output."""

    def __init__(self, model: str = "gemini-1.5-pro", api_key_env: str = "GOOGLE_AI_API_KEY"):
        self.model = model
        self.api_key_env = api_key_env
        self._model_resolved = False

    def _maybe_resolve_model(self, genai) -> None:
        if self._model_resolved:
            return
        self._model_resolved = True
        try:
            # Model names come back as "models/gemini-1.5-pro"; strip the prefix for comparison.
            available = [
                m.name.removeprefix("models/")
                for m in genai.list_models()
                if "generateContent" in (m.supported_generation_methods or [])
            ]
            self.model = _closest_model(self.model, available, "gemini-1.5-pro")
        except Exception:
            pass

    def complete_structured(self, system: str, user: str, response_model: Type[T]) -> T:
        try:
            import google.generativeai as genai
        except ImportError:
            raise ImportError(
                "google-generativeai package is required for the Google provider. "
                "Install with: pip install 'team_maker[google]'"
            )

        api_key = os.environ.get(self.api_key_env)
        if not api_key:
            raise EnvironmentError(
                f"Environment variable '{self.api_key_env}' is not set. "
                "Set it to your Google AI API key."
            )

        genai.configure(api_key=api_key)
        self._maybe_resolve_model(genai)

        schema = response_model.model_json_schema()
        schema_str = json.dumps(schema, indent=2)

        # Gemini does not have a separate system role in the basic SDK — fold it in.
        full_prompt = (
            f"{system}\n\n"
            f"---\n\n"
            f"{user}\n\n"
            f"---\n\n"
            f"Respond with a single JSON object that exactly matches this schema "
            f"(output ONLY the JSON, no markdown fences, no explanation):\n{schema_str}"
        )

        model_instance = genai.GenerativeModel(
            model_name=self.model,
            generation_config=genai.types.GenerationConfig(
                temperature=0.2,
                response_mime_type="application/json",
            ),
        )

        response = model_instance.generate_content(full_prompt)
        raw = response.text.strip()

        # Strip markdown fences if the model added them despite instructions.
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw.rstrip())

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if not match:
                raise ValueError(
                    f"Google provider returned non-JSON response.\nRaw: {raw[:500]}"
                )
            data = json.loads(match.group())

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
    if provider == "xai":
        return XAIProvider(
            model=config.model,
            api_key_env=config.api_key_env or "XAI_API_KEY",
            base_url=config.base_url or "https://api.x.ai/v1",
        )
    if provider == "google":
        return GoogleProvider(
            model=config.model,
            api_key_env=config.api_key_env or "GOOGLE_AI_API_KEY",
        )
    if provider == "ollama":
        return OllamaProvider(
            model=config.model,
            base_url=config.base_url or "http://localhost:11434",
        )

    raise ValueError(
        f"Unknown provider '{provider}'. Supported: anthropic | openai | xai | google | ollama"
    )
