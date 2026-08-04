"""One request-timeout policy, shared by every provider adapter.

Added by the Story 2.0 code review as a declared exception to that story's
``team_maker/`` freeze.

Why this exists
---------------
Every adapter previously constructed its SDK client with the vendor default
timeout, which for both the Anthropic and OpenAI SDKs is **ten minutes**. Behind
a CLI that was invisible: a human watching a terminal gives up long before the
SDK does. Behind the HTTP seam Story 2.0 adds it is not, because a compose turn
runs inside a per-session lock held on a FastAPI threadpool thread — so one
unresponsive upstream holds a lock, a thread, and a session for ten minutes per
attempt, and ``Composer.compose`` makes up to four sequential attempts.

A single knob, read from the environment so an operator can raise it for a slow
local model without a code change. Kept deliberately small: this is a timeout
for one structured completion, not a budget for a whole conversation.
"""
from __future__ import annotations

import os

# Generous enough for a long structured completion from a hosted model, short
# enough that a hung upstream is reclaimed within one API request's patience.
DEFAULT_REQUEST_TIMEOUT_SECONDS = 120.0

_ENV_VAR = "TEAM_MAKER_LLM_TIMEOUT"


def request_timeout() -> float:
    """The per-request timeout every adapter passes to its SDK client.

    Falls back to the default for anything unparseable or non-positive rather
    than raising: a malformed environment variable must not make the whole
    factory unusable, and "no timeout" is not an option this returns.
    """
    raw = os.environ.get(_ENV_VAR)
    if not raw:
        return DEFAULT_REQUEST_TIMEOUT_SECONDS
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_REQUEST_TIMEOUT_SECONDS
    return value if value > 0 else DEFAULT_REQUEST_TIMEOUT_SECONDS
