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
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

logger = logging.getLogger("api.errors")

# --- AC 2's authored codes. Adding a row here is a contract change. ----------
SESSION_NOT_FOUND = "session_not_found"
TURN_CAP_REACHED = "turn_cap_reached"
SPEC_INVALID = "spec_invalid"
AUTHORING_UNAVAILABLE = "authoring_unavailable"
COMPOSE_FAILED = "compose_failed"
OUTPUT_EXISTS = "output_exists"
BUILD_FAILED = "build_failed"

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

    The exception object never leaves this function. ``exc_info=True`` puts the
    traceback in the server log, which is the only place AC 8 permits it.
    """
    logger.exception("%s: %s", code, exc.__class__.__name__, exc_info=exc)
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
    """
    parsed: list[FieldError] = []
    for raw in errors:
        # The loc segment never contains a colon (it is joined role names and
        # list indices), so the first ": " is unambiguously the separator.
        location, separator, message = raw.partition(": ")
        if not separator:
            parsed.append(FieldError("(root)", raw.strip()))
            continue
        segments = [segment.strip() for segment in location.split("→")]
        path = ".".join(segment for segment in segments if segment)
        parsed.append(FieldError(path or "(root)", message.strip()))
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
    """
    parsed: list[FieldError] = []
    for error in errors:
        path = ".".join(str(part) for part in error.get("loc", ()))
        if strip_prefix and path.startswith(strip_prefix):
            path = path[len(strip_prefix) :]
        parsed.append(FieldError(path or "(root)", str(error.get("msg", "Invalid value."))))
    return parsed


def fields_from_validation_error(exc: ValidationError) -> list[FieldError]:
    """``fields_from_error_list`` for a pydantic ``ValidationError``."""
    return fields_from_error_list(exc.errors())
