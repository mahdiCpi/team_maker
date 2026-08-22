"""Base utilities and shared code for review patches tests.

This module contains shared fixtures and helpers used by the split test files.
See test_review_patches_*.py for the actual tests.
"""
from __future__ import annotations

from tests.api.conftest import SENTINEL_VALUES
from tests.api.containment import assert_envelope, assert_no_exception_leak, assert_no_sentinels

# Re-exported for the split test_review_patches_*.py files (see their imports
# `from tests.api.test_review_patches_base import ...`) — declared explicitly
# so a lint pass that removes "unused" imports doesn't silently break them.
__all__ = [
    "NEUTRAL_COMPOSE_FAILURE",
    "SENTINEL_VALUES",
    "_FakeClock",
    "_choice",
    "_start",
    "assert_envelope",
    "assert_no_exception_leak",
    "assert_no_sentinels",
]

# The exact copy the 502 must carry. Pinned as a literal so a well-meaning
# rewrite back towards "the provider could not be reached" fails here.
NEUTRAL_COMPOSE_FAILURE = (
    "The team specification could not be created. Retry once; if the "
    "problem repeats, stop and report it."
)


def _start(harness, intent="I need a team to write docs.", authoring=None):
    body = {"intent": intent}
    if authoring is not None:
        body["authoring"] = authoring
    return harness.client.post("/api/compose/sessions", json=body)


class _FakeClock:
    """STUB clock, so window and TTL behaviour is tested in microseconds."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _choice():
    from api.deps import resolve_authoring_choice

    return resolve_authoring_choice(None, None)
