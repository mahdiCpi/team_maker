"""Request/response models for the compose seam (Story 2.0, AC 2).

Two deliberate shapes here:

* **No raw ``TeamCreationRequest`` is ever accepted as a request body.** The
  edit route takes only the three dimensions Story 2.2's review mode edits;
  everything else on the spec is server-owned (see ``SpecEditRequest``).
* **The spec is returned as an opaque ``dict``**, produced by dumping the real
  ``TeamCreationRequest``. There is deliberately no hand-written mirror model
  of the spec: a second source of truth for that shape would drift, and
  ``TeamCreationRequest`` already normalises input in five ways
  (``_pre_process``), so the server's re-serialised spec is the only honest
  answer to "what did you actually store".

Responses carry a ``status`` discriminator so AD-13's later streaming retrofit
can add a variant instead of breaking the contract.

Note what is *absent*: the session responses have no ``validation`` field.
AD-10 and ``composer.py:110-126`` mean a returned spec is schema-valid by
construction — ``compose()`` either returns a valid ``TeamCreationRequest`` or
raises. An always-``passed: true`` field would be a value true by construction.
The only ``ValidationResult`` in the system is produced after a *build*, and it
appears on the build response alone.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# `extra="forbid"` is a security control, not tidiness: it is what makes a
# request carrying an API key a rejection rather than a silently ignored field
# (AC 10 — "a request carrying a key value is rejected, not honoured").
_STRICT = ConfigDict(extra="forbid")

# Every client-supplied string is bounded. Nothing upstream bounds them:
# Starlette applies no default body-size limit, so an unbounded `intent` is
# accepted, held in memory, and forwarded to the LLM as prompt tokens — which
# turns a text field into a spend amplifier. The limits are generous enough that
# no legitimate request meets them and small enough that no single request can
# be used as a payload.
_MAX_PROMPT = 8_000
_MAX_NAME = 120
_MAX_TEXT = 2_000
_MAX_PROVIDER_ID = 64
_MAX_MODEL_ID = 200
_MAX_LIST = 64


class AuthoringSelection(BaseModel):
    """Which provider/model should author the spec. Never carries a key (AD-9)."""

    model_config = _STRICT

    # `min_length=1` rather than defaulting an empty string: `{"provider": ""}`
    # used to become `anthropic` and `{"model": ""}` used to become
    # `claude-sonnet-4-6`, so asking `openai` for an empty model silently
    # produced `openai` + a Claude model id and failed later as an unactionable
    # 502. An empty selection is a malformed request, not an unstated one.
    provider: str | None = Field(None, min_length=1, max_length=_MAX_PROVIDER_ID)
    model: str | None = Field(None, min_length=1, max_length=_MAX_MODEL_ID)


class CreateSessionRequest(BaseModel):
    model_config = _STRICT

    intent: str = Field(..., min_length=1, max_length=_MAX_PROMPT)
    authoring: AuthoringSelection | None = None


class MessageRequest(BaseModel):
    model_config = _STRICT

    message: str = Field(..., min_length=1, max_length=_MAX_PROMPT)


class ProviderSelection(BaseModel):
    model_config = _STRICT

    provider: str = Field(..., min_length=1, max_length=_MAX_PROVIDER_ID)
    model: str = Field(..., min_length=1, max_length=_MAX_MODEL_ID)


class RoleEdit(BaseModel):
    model_config = _STRICT

    name: str = Field(..., min_length=1, max_length=_MAX_NAME)
    description: str = Field(..., min_length=1, max_length=_MAX_TEXT)
    llm: ProviderSelection | None = None


class TaskEdit(BaseModel):
    model_config = _STRICT

    name: str = Field(..., min_length=1, max_length=_MAX_NAME)
    description: str = Field(..., min_length=1, max_length=_MAX_TEXT)
    agent_role: str = Field(..., min_length=1, max_length=_MAX_NAME)
    dependencies: list[str] = Field(
        default_factory=list, max_length=_MAX_LIST
    )


class SpecEditRequest(BaseModel):
    """The only three dimensions a client may edit.

    ``output_path``, ``overwrite``, ``api_key_env``, ``planning_llm``,
    ``framework``, ``state_backend`` and ``sandbox`` are server-owned and are
    carried from ``session.current``, never read from the body. ``output_path``
    is schema-required so a partial body could not validate alone anyway; and a
    browser-settable ``overwrite`` would turn ``FileExistsError`` — the only
    guard against clobbering an existing directory — into a browser-controlled
    switch.

    Every field is optional: an omitted field means "leave it as it is".
    """

    model_config = _STRICT

    team_name: str | None = Field(None, min_length=1, max_length=_MAX_NAME)
    purpose: str | None = Field(None, min_length=1, max_length=_MAX_TEXT)
    desired_roles: list[RoleEdit] | None = Field(None, max_length=_MAX_LIST)
    desired_tasks: list[TaskEdit] | None = Field(None, max_length=_MAX_LIST)


class SessionView(BaseModel):
    """The session envelope returned by create / message / spec-edit."""

    status: Literal["complete"] = "complete"
    session_id: str
    spec: dict[str, Any]
    turn: int
    turns_remaining: int


class ValidationView(BaseModel):
    passed: bool
    issues: list[str]
    warnings: list[str]


class ModelSubstitution(BaseModel):
    """One agent whose model was silently swapped during the build.

    ``normalize_team_routings`` may replace a chosen model with a fuzzy nearest
    match and reports it only to stderr (`model_resolver.py:156-185`). Without
    this the UI would claim it built the model the user picked.
    """

    role: str
    requested: str
    resolved: str


class BuildView(BaseModel):
    status: Literal["complete"] = "complete"
    team_name: str
    output_path: str
    agent_count: int
    task_count: int
    written_file_count: int
    model_substitutions: list[ModelSubstitution]
    validation: ValidationView


class HealthView(BaseModel):
    status: Literal["ok"] = "ok"
