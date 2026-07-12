"""Google (Gemini) LLM adapter (implements the LLMProvider port structurally)."""
from __future__ import annotations

import json
import os
import re
from typing import TypeVar

from pydantic import BaseModel

from team_maker.adapters.providers._model_match import _closest_model

T = TypeVar("T", bound=BaseModel)


class GoogleProvider:
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

    def complete_structured(self, system: str, user: str, response_model: type[T]) -> T:
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
