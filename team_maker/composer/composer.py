"""Composer core — plain-language intent -> validated TeamCreationRequest.

Spine invariants this module upholds:
  - AD-2/AD-4/AD-8: depends only on the ``LLMProvider`` port (never a concrete
    SDK, never branches on provider name); the concrete adapter is injected by
    the caller (CLI today, Story 1.3's conversational wrapper later).
  - AD-5: authors the spec only — building is ``PipelineRunner``'s job, not
    this module's.
  - AD-10: only a spec that passes ``TeamCreationRequest`` validation is ever
    returned; a bounded validate-and-repair loop re-prompts the same LLM with
    the concrete validation errors, and exhausting the budget raises
    ``ComposerError`` instead of surfacing an invalid spec.
"""
from __future__ import annotations

from pydantic import ValidationError

from team_maker.adapters.providers.registry import is_usable, report_availability
from team_maker.keyconfig import KeyConfig
from team_maker.ports.llm_provider import LLMProvider
from team_maker.schema.request import TeamCreationRequest

# Word -> provider id mapping surfaced to the authoring LLM (data, not control
# flow — AD-1/AD-8). Extend this table, never branch on provider name in code.
_PROVIDER_ALIASES: dict[str, str] = {
    "claude": "anthropic",
    "chatgpt": "openai",
    "gpt": "openai",
    "gemini": "google",
    "grok": "xai",
    "llama": "ollama",
}

_SCHEMA_RULES = """\
Required top-level fields:
  - `team_name` (>=2 chars).
  - `purpose` (>=10 chars) — what the team must build.
  - `output_path` — a directory path. Invent a short relative one such as
    `./output/<team_name_in_snake_case>` if the user did not state one.
`desired_roles` must contain at least one role. Each role has:
  - `name`: snake_case, matching ^[a-z][a-z0-9_]*$, unique within the request.
  - `description`: >=5 characters — what the role does.
  - `llm` (optional): a ProviderConfig. Set it ONLY if the user named a
    model/provider for this specific role; otherwise omit the field entirely
    so the system default applies.
Each ProviderConfig has `provider` (one of: anthropic, openai, xai, google,
ollama — lowercase) and `model` (the model id string). Map common model words
to provider ids: {aliases}.
`default_llm` (optional): a fallback ProviderConfig for roles without a
specific one. Set it ONLY if the user stated an overall preference (e.g.
"use local/cheap models", "use Claude"); otherwise omit it so the factory
default (`role.llm -> default_llm -> anthropic/claude-sonnet-4-6`) applies.
`desired_tasks` (optional): capture explicit task intent as TaskHint items —
`name` (snake_case), `description` (>=10 chars), `agent_role` (must match a
role name), `dependencies` (list of other task names).
Never invent an `api_key_env` unless the user explicitly names one.
Emit ONLY the fields defined by the schema — no extra commentary.\
"""


class ComposerError(Exception):
    """Raised when no schema-valid spec was produced within the repair budget.

    Carries the last set of concrete validation errors (``loc: msg`` strings)
    so callers can surface them without ever surfacing the invalid spec itself.
    """

    def __init__(self, message: str, errors: list[str] | None = None) -> None:
        super().__init__(message)
        self.errors: list[str] = errors or []


class Composer:
    """Turns a plain-language intent into a validated ``TeamCreationRequest``.

    Stateless and re-invokable: each ``compose()`` call is independent (Story
    1.3 wraps this per conversational turn; there is no conversation loop or
    "run now" here).
    """

    def __init__(
        self,
        provider: LLMProvider,
        *,
        max_repair_attempts: int = 3,
        key_config: KeyConfig | None = None,
    ) -> None:
        if max_repair_attempts < 0:
            raise ValueError(f"max_repair_attempts must be >= 0, got {max_repair_attempts}")
        self._provider = provider
        self._max_repair_attempts = max_repair_attempts
        self._available_providers = (
            _usable_provider_names(key_config) if key_config is not None else None
        )

    @property
    def provider(self) -> LLMProvider:
        """The injected ``LLMProvider``, for wrappers that need to reuse the same
        provider instance (e.g. ``ComposerSession``'s classification step) without
        reaching past this class's encapsulation boundary."""
        return self._provider

    def compose(self, intent: str, *, preferences: str | None = None) -> TeamCreationRequest:
        """Author a schema-valid ``TeamCreationRequest`` from ``intent``.

        Raises:
            ComposerError: the repair budget was exhausted without producing
                a schema-valid spec. No invalid spec is ever returned.
        """
        system = _build_system_prompt(self._available_providers)
        user = _build_user_message(intent, preferences)

        total_attempts = self._max_repair_attempts + 1
        errors: list[str] = []
        for attempt in range(1, total_attempts + 1):
            try:
                return self._provider.complete_structured(
                    system=system,
                    user=user,
                    response_model=TeamCreationRequest,
                )
            except ValidationError as exc:
                errors = _format_errors(exc)
                if attempt == total_attempts:
                    break
                user = _build_repair_message(intent, preferences, errors)

        raise ComposerError(
            "Could not produce a valid team specification after "
            f"{self._max_repair_attempts} repair attempt(s). "
            "Try rephrasing your request or simplifying the requirements.",
            errors,
        )


def _usable_provider_names(key_config: KeyConfig) -> list[str]:
    return sorted(
        status.name for status in report_availability(key_config) if is_usable(status.status)
    )


def _build_system_prompt(available_providers: list[str] | None) -> str:
    rules = _SCHEMA_RULES.format(
        aliases=", ".join(f"{word}->{provider}" for word, provider in _PROVIDER_ALIASES.items())
    )
    parts = [
        "You are the team_maker Composer. Turn a plain-language request into a "
        "single, schema-valid team specification.",
        rules,
    ]
    if available_providers:
        parts.append(
            "Providers with a configured API key (prefer these when the user "
            "states no preference): " + ", ".join(available_providers)
        )
    return "\n\n".join(parts)


def _build_user_message(intent: str, preferences: str | None) -> str:
    if preferences:
        return f"{intent}\n\nStated preferences: {preferences}"
    return intent


def _build_repair_message(intent: str, preferences: str | None, errors: list[str]) -> str:
    error_block = "\n".join(f"  • {error}" for error in errors)
    return (
        f"{_build_user_message(intent, preferences)}\n\n"
        "Your previous attempt failed schema validation with these errors:\n"
        f"{error_block}\n\n"
        "Fix ONLY these errors and re-emit the complete, corrected team "
        "specification (all fields, not just the corrected ones)."
    )


def _format_errors(exc: ValidationError) -> list[str]:
    return [
        f"{' → '.join(str(part) for part in error['loc']) or '(root)'}: {error['msg']}"
        for error in exc.errors()
    ]
