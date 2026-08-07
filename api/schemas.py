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


# ---------------------------------------------------------------------------
# Key status (Story 2.3). Status only — never a key value (AD-9).
# ---------------------------------------------------------------------------


class ProviderKeyView(BaseModel):
    """One provider's availability. `status`/`detail` are the catalog's own words."""

    name: str
    # A `registry.STATUS_*` value, forwarded verbatim rather than re-spelled, so a
    # status added to `classify()` cannot silently become a different word here.
    status: str
    # What to tell the user: the catalog's status wording, replaced when the
    # credential came from somewhere other than the Key Config file.
    detail: str
    # The catalog's own word for the status, unmodified.
    status_detail: str
    usable: bool
    # The Key Config entry that would satisfy it. The *name* of the variable, never
    # its value (`preflight.py:12-13`). `None` for a keyless provider.
    env_var: str | None
    # `None` when there is nothing to fix.
    fix_hint: str | None
    # Which of the two documented sources answered — `key-config`, `environment`,
    # `startup-leftover`, or `none`. The *source*, never the value (AD-9).
    credential_source: str


class RoleKeyView(BaseModel):
    """One role's required provider, resolved server-side.

    `inherited_default` matters to the UI: a role that named no `llm` got its
    provider from `role.llm -> default_llm -> anthropic/claude-sonnet-4-6`, and the
    browser is forbidden from inventing that default (`spec-draft.ts:9-13`), so it
    needs telling which roles are showing an inherited choice rather than the
    user's own.
    """

    role: str
    provider: str
    model: str
    status: str
    detail: str
    usable: bool
    inherited_default: bool
    fix_hint: str | None
    credential_source: str
    # True for a role the build cannot proceed without, so the UI must not offer to
    # drop or route around it. The synthetic planner role is the only one today.
    required: bool


class KeyStatusView(BaseModel):
    """The provider-level read: `GET /api/keys/status`.

    `overall` is only ever `no-keys` or `has-keys`. A four-state verdict would be a
    guess: this route has no team, and the catalog permanently contains a provider
    the runtime cannot use (`groq`) and one that needs no key at all (`ollama`).
    """

    status: Literal["complete"] = "complete"
    overall: str
    providers: list[ProviderKeyView]
    # Not a secret, and the thing that makes "add it to your Key Config" actionable
    # (Story 1.6 precedent).
    key_config_path: str
    load_warnings: list[str]
    any_key_present: bool
    # Present in the file now, but not bridged at startup — so usable for a run and
    # not yet for composing. See `api/keystatus.needs_restart_to_author`.
    needs_restart_to_author: list[str]


class KeyCheckView(BaseModel):
    """The per-team check: `GET /api/keys/check/{session_id}`."""

    status: Literal["complete"] = "complete"
    overall: str
    blocked: bool
    blocking_reason: str | None
    roles: list[RoleKeyView]
    providers: list[ProviderKeyView]
    key_config_path: str
    load_warnings: list[str]
    any_key_present: bool
    needs_restart_to_author: list[str]
