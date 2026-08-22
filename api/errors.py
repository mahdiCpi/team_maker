"""The one error envelope every non-2xx response uses (Story 2.0, AC 2 / AC 8).

Two rules hold everywhere in this module, and AC 8 has tests for both:

1. ``message`` is authored copy, never ``str(exc)``. `deferred-work.md:45`
   records that an SDK exception string can echo an embedded secret, and the
   Composer's repair loop re-raises adapter errors untouched. Exceptions are
   logged server-side and never serialised.
2. ``fields`` is present only for ``spec_invalid``. Every other code omits the
   key entirely rather than sending an empty list.
"""
from __future__ import annotations

import logging
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError
from team_maker.utils.text_sanitizer import log_exception_safely

logger = logging.getLogger("api.errors")

# ---------------------------------------------------------------------------
# Error message catalog for user-friendly error messages (Task 7, Story 4.5)
# ---------------------------------------------------------------------------
# Maps technical/pydantic error message patterns to user-facing, authored copy.
# These are deliberately plain-language, actionable messages.

# Pydantic wraps every custom `@field_validator`/`@model_validator` `ValueError`
# in this fixed prefix, so it must be stripped before pattern matching or none
# of `team_maker/schema/request.py`'s custom validator messages (role/task/tool
# name shape, duplicate role names, output_path, ...) ever match below.
_PYDANTIC_VALUE_ERROR_PREFIX = "Value error, "

# Used when no pattern matches. Deliberately fixed and content-free — Tier 3
# used to "clean up" the original message with unscoped substring replacement
# (`"str"` -> `"text"`), which mangled ordinary words like "constraint" and
# "string" and could still leak raw technical/interpolated text (AC 7 forbids
# both). A fixed fallback can never do either.
_GENERIC_FALLBACK_MESSAGE = "This value is invalid. Please check it and try again."

# Ordered by specificity: earlier patterns win. Matched with `search`, not
# `match`, since the message may still carry other pydantic wrapper text.
_ERROR_MESSAGE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"(Role|Task|Tool) name must be snake_case", re.IGNORECASE),
        r"\1 names must use lowercase letters, numbers, and underscores only (e.g., 'researcher', 'engineer_1').",
    ),
    (re.compile(r"Duplicate role names"), "Role names must be unique within a team."),
    (re.compile(r"output_path must not be empty"), "Please provide an output path."),
    (re.compile(r"String should have at least (\d+) character"), r"This field must be at least \1 characters long."),
    (re.compile(r"String should have at most (\d+) character"), r"This field must be at most \1 characters long."),
    (re.compile(r"String should match regex pattern"), "This field has an invalid format."),
    (re.compile(r"Input should be less than or equal to"), "This value is too large."),
    (re.compile(r"Input should be greater than or equal to"), "This value is too small."),
    (re.compile(r"Input should be a valid dictionary"), "Please provide a properly formatted object."),
    (re.compile(r"Input should be a valid list"), "Please provide a properly formatted list."),
    (re.compile(r"Input should be a valid UUID"), "Please provide a valid UUID."),
    (re.compile(r"Input should be a valid integer"), "Please provide a whole number."),
    (re.compile(r"Input should be a valid number"), "Please provide a numeric value."),
    (re.compile(r"Input should be a valid boolean"), "Please provide true or false."),
    (re.compile(r"Input should be a valid (\w+)"), r"Please provide a valid \1."),
    (re.compile(r"Field required"), "This field is required and cannot be empty."),
    (re.compile(r"Extra inputs are not permitted"), "An unexpected field was provided. Please remove it."),
    (re.compile(r"none is not an allowed value", re.IGNORECASE), "This field cannot be empty."),
]


def _authored_message(technical_msg: str) -> str:
    """Map a technical error message to a user-friendly, authored message.

    Per AC 7: fields[].message must contain authored copy, not pydantic-derived
    text or SDK error messages. A message that matches no known pattern falls
    back to a fixed generic string rather than any transformation of the
    original — there is no safe general-purpose way to "clean up" arbitrary
    technical text without either leaking it or corrupting it.

    Args:
        technical_msg: The raw error message from pydantic or composer

    Returns:
        A user-friendly, authored error message
    """
    msg = technical_msg
    if msg.startswith(_PYDANTIC_VALUE_ERROR_PREFIX):
        msg = msg[len(_PYDANTIC_VALUE_ERROR_PREFIX) :]

    for pattern, replacement in _ERROR_MESSAGE_PATTERNS:
        match = pattern.search(msg)
        if match:
            # `match.expand`, not `pattern.sub`: `sub` only replaces the matched
            # span and leaves the rest of `msg` (e.g. a trailing "got: <value>")
            # attached, which re-leaks the technical/interpolated text this
            # function exists to strip out.
            return match.expand(replacement) if pattern.groups > 0 else replacement

    return _GENERIC_FALLBACK_MESSAGE

# --- AC 2's authored codes. Adding a row here is a contract change. ----------
SESSION_NOT_FOUND = "session_not_found"
TURN_CAP_REACHED = "turn_cap_reached"
SPEC_INVALID = "spec_invalid"
AUTHORING_UNAVAILABLE = "authoring_unavailable"
COMPOSE_FAILED = "compose_failed"
OUTPUT_EXISTS = "output_exists"
BUILD_FAILED = "build_failed"
AUTHENTICATION_REQUIRED = "authentication_required"

# Added by the Story 2.0 code review (D3). Not in AC 2's original table: it
# exists because taking the per-conversation lock is now bounded, and a request
# that cannot get it needs an answer that is neither a hang nor a 500.
SESSION_BUSY = "session_busy"

# Added by Story 2.4 (the `run` group, `epics.md:335`). Not in AC 2's original
# table: a run names a Team Package by slug rather than a session, so a slug
# that resolves to nothing needs its own code — `session_not_found` names a
# conversation, and a run is not one.
TEAM_NOT_FOUND = "team_not_found"
# Added by Story 2.4. Not in AC 2's original table: AD-9's pre-run gate now
# runs synchronously over HTTP, and a run that cannot start (bad credentials,
# an internally inconsistent package, or an unrunnable framework) needs an
# answer distinct from `run_in_progress` — the three causes share this code
# but never its copy (see `api/routers/run.py`).
RUN_BLOCKED = "run_blocked"
# Added by Story 2.4. Not in AC 2's original table: runs are serialised
# process-wide (`deferred-work.md:102`'s concurrent-transcript corruption),
# so a second run request needs an answer that is neither a queue nor a hang.
RUN_IN_PROGRESS = "run_in_progress"
# Added by Story 2.4. Not in AC 2's original table: the run registry evicts
# completed runs on a bounded TTL (mirroring `session_not_found`), so an
# unknown or evicted `run_id` is a normal outcome, not an anomaly, and needs
# its own code — a run is not a conversation, so `session_not_found` is wrong
# for it in both name and precedent.
RUN_NOT_FOUND = "run_not_found"

# --- Framework-level codes ---------------------------------------------------
# Not raisable by any authored route: these exist so that a 404 on an unknown
# path, a 405, or a fault escaping the handlers still answers with the envelope
# instead of Starlette's `{"detail": ...}` or a bare text body. AC 2's table
# describes what the *routes* raise; these keep the *shape* promise total.
NOT_FOUND = "not_found"
METHOD_NOT_ALLOWED = "method_not_allowed"
INTERNAL_ERROR = "internal_error"
# Catch-all for a 4xx raised by something other than an authored route (a future
# dependency, middleware, or a body-size limit). Its nominal status here is 400,
# but `_handle_http_exception` sends the exception's real status — the point of
# this code is to keep the envelope's *shape* promise without also flattening
# every 401/403/413/429 into one status.
REQUEST_REJECTED = "request_rejected"

STATUS_BY_CODE: dict[str, int] = {
    SESSION_NOT_FOUND: 404,
    TURN_CAP_REACHED: 409,
    SPEC_INVALID: 422,
    AUTHORING_UNAVAILABLE: 503,
    COMPOSE_FAILED: 502,
    OUTPUT_EXISTS: 409,
    BUILD_FAILED: 500,
    SESSION_BUSY: 409,
    TEAM_NOT_FOUND: 404,
    RUN_BLOCKED: 409,
    RUN_IN_PROGRESS: 409,
    RUN_NOT_FOUND: 404,
    NOT_FOUND: 404,
    AUTHENTICATION_REQUIRED: 401,
    METHOD_NOT_ALLOWED: 405,
    INTERNAL_ERROR: 500,
    REQUEST_REJECTED: 400,
}


@dataclass(frozen=True)
class FieldError:
    """One field-addressable validation problem, with a dotted path."""

    path: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"path": self.path, "message": self.message}


class ApiError(Exception):
    """An error that is safe to serialise, because every part of it is authored."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        fields: list[FieldError] | None = None,
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(message)
        if code not in STATUS_BY_CODE:
            raise ValueError(f"Unknown error code '{code}'")
        if fields and code != SPEC_INVALID:
            raise ValueError(f"'fields' is only valid for '{SPEC_INVALID}', not '{code}'")
        self.code = code
        self.message = message
        self.fields = fields or []
        self.status_code = STATUS_BY_CODE[code]
        self.cause = cause

    def envelope(self) -> dict[str, Any]:
        error: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.fields:
            error["fields"] = [f.to_dict() for f in self.fields]
        return {"error": error}


def log_and_wrap(
    code: str,
    message: str,
    exc: BaseException,
    *,
    fields: list[FieldError] | None = None,
) -> ApiError:
    """Log ``exc`` server-side and return the authored envelope for the client.

    The exception object never leaves this function. The traceback is logged
    server-side with sanitized exception message to prevent sensitive data
    leakage (AD-9).
    """
    # Use safe logging to prevent sensitive data from leaking
    # Per AD-9: keys and sensitive data must never be logged
    log_exception_safely(logger, f"{code}: {exc.__class__.__name__}", exc)
    return ApiError(code, message, fields=fields, cause=exc)


# ---------------------------------------------------------------------------
# Field extraction
# ---------------------------------------------------------------------------


def fields_from_composer_errors(errors: list[str]) -> list[FieldError]:
    """Turn ``ComposerError.errors`` into field-addressable entries.

    The core hands back a ``list[str]`` shaped ``"a → b → c: message"``
    (`composer.py:169-173`) — human-readable, not structured — so this is the
    parser Story 2.2's inline validation reasons need. `_format_errors` emits
    the literal ``(root)`` for an error with an empty ``loc``; that is kept
    verbatim as the path, since a root-level error has no input to attach to
    and a sentinel is more useful to a client than an empty string.
    
    Task 7, Story 4.5: Uses _authored_message to map technical composer messages
    to user-friendly, authored copy.
    """
    parsed: list[FieldError] = []
    for raw in errors:
        # The loc segment never contains a colon (it is joined role names and
        # list indices), so the first ": " is unambiguously the separator.
        location, separator, message = raw.partition(": ")
        if not separator:
            authored_msg = _authored_message(raw.strip())
            parsed.append(FieldError("(root)", authored_msg))
            continue
        segments = [segment.strip() for segment in location.split("→")]
        path = ".".join(segment for segment in segments if segment)
        # Map technical message to user-friendly copy (AC 7)
        authored_msg = _authored_message(message.strip())
        parsed.append(FieldError(path or "(root)", authored_msg))
    return parsed


def fields_from_error_list(
    errors: Iterable[Mapping[str, Any]], *, strip_prefix: str = ""
) -> list[FieldError]:
    """Turn pydantic-shaped error dicts into field-addressable entries.

    Only ``loc`` and ``msg`` are read. ``input`` is deliberately never touched:
    for an ``extra_forbidden`` error it holds the rejected value, which is
    exactly how a request that tried to smuggle an API key would get that key
    echoed back into a response body (AD-9, AC 4).

    Takes the raw list rather than the exception so it serves both pydantic's
    ``ValidationError`` and FastAPI's ``RequestValidationError``, which is not a
    subclass of it but exposes the same ``errors()`` payload.
    
    Task 7, Story 4.5: Uses _authored_message to map technical pydantic messages
    to user-friendly, authored copy.
    """
    parsed: list[FieldError] = []
    for error in errors:
        path = ".".join(str(part) for part in error.get("loc", ()))
        if strip_prefix and path.startswith(strip_prefix):
            path = path[len(strip_prefix) :]
        raw_msg = str(error.get("msg", "Invalid value."))
        # Map technical message to user-friendly copy (AC 7)
        authored_msg = _authored_message(raw_msg)
        parsed.append(FieldError(path or "(root)", authored_msg))
    return parsed


def fields_from_validation_error(exc: ValidationError) -> list[FieldError]:
    """``fields_from_error_list`` for a pydantic ``ValidationError``."""
    return fields_from_error_list(exc.errors())
