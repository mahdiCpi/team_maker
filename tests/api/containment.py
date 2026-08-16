"""Assertions shared by the AC 4 and AC 8 containment tests.

These are the story's highest-risk guards, and Story 2.1's review found that a
guard protecting a self-declared highest-risk decision can still catch nothing.
So each one has a companion test in `test_containment_guards.py` that feeds it a
deliberately violating payload and asserts it goes red.
"""
from __future__ import annotations

import re

# Substrings that only ever appear when a Python traceback has been serialised.
_TRACEBACK_MARKERS = ("Traceback", '  File "', "most recent call last")

# Exception class names that could plausibly reach a response if any handler
# ever serialised `repr(exc)` or `str(exc)` instead of authored copy.
#
# The SDK block is the important half and was missing: the original list held
# only builtins and this repo's own classes, so a regression that serialised,
# say, `anthropic.AuthenticationError` — whose repr is exactly the kind that
# embeds request context — would have passed every containment assertion in the
# suite. Those are the classes closest to a credential, so they are the ones a
# guard claiming "no exception class name" most needs to cover.
_EXCEPTION_CLASS_NAMES = (
    # This repo and the standard library
    "ComposerError",
    "ValidationError",
    "RuntimeError",
    "FileExistsError",
    "FileNotFoundError",
    "EnvironmentError",
    "ValueError",
    "KeyError",
    "TypeError",
    "AttributeError",
    "OSError",
    "ImportError",
    "ApiError",
    "HTTPException",
    # Provider SDKs (anthropic / openai share this exception vocabulary)
    "APIError",
    "APIStatusError",
    "APIConnectionError",
    "APITimeoutError",
    "AuthenticationError",
    "PermissionDeniedError",
    "BadRequestError",
    "RateLimitError",
    "InternalServerError",
    "UnprocessableEntityError",
)

_ENVELOPE_KEYS = {"code", "message", "fields"}


def assert_envelope(response, expected_code: str) -> dict:
    """The body is exactly the AC 2 envelope, and `fields` obeys its rule."""
    body = response.json()
    assert set(body) == {"error"}, f"body has keys outside the envelope: {sorted(body)}"
    error = body["error"]
    assert set(error) <= _ENVELOPE_KEYS, f"unexpected envelope members: {sorted(error)}"
    assert error["code"] == expected_code
    assert isinstance(error["message"], str) and error["message"].strip()
    if "fields" in error:
        assert expected_code == "spec_invalid", "`fields` appears only for spec_invalid"
        for field in error["fields"]:
            assert set(field) == {"path", "message"}
    return error


def assert_no_exception_leak(text: str, *, extra: tuple[str, ...] = ()) -> None:
    """No traceback, no exception class name, no injected secret marker."""
    for marker in _TRACEBACK_MARKERS:
        assert marker not in text, f"response leaked a traceback marker: {marker!r}"
    for name in _EXCEPTION_CLASS_NAMES:
        assert not re.search(rf"\b{name}\b", text), f"response leaked an exception class: {name}"
    for marker in extra:
        assert marker not in text, f"response leaked {marker!r}"


def assert_no_sentinels(text: str, sentinels) -> None:
    """No credential value appears anywhere in `text` (AD-9, AC 4)."""
    for sentinel in sentinels:
        assert sentinel not in text, "a credential value reached the client"
