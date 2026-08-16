"""A scripted, offline stand-in for the `LLMProvider` port.

Promoted here in Story 2.0 from `tests/unit/test_composer.py`, where Story 1.2
first wrote it, because a third consumer (`tests/api/`) appeared. This is the
same directory pattern Stories 1.6 and 1.7 used for `crewai_interception.py`
and `team_factories.py`: the next test reuses a proven helper instead of
copying it (CLAUDE.md test organization).

THIS IS A STUB. It implements the port structurally — no SDK, no network, no
key. A test that passes against it says nothing about whether the real
Anthropic/OpenAI/Ollama adapters work.
"""
from __future__ import annotations

import threading
from typing import Any


class FakeLLMProvider:
    """Implements the LLMProvider port structurally — no SDK, no network.

    Each scripted response is either a raw dict (validated by the real
    `response_model`, mirroring how the concrete adapters behave) or an
    Exception instance to raise verbatim.

    Thread-safe, because the API harness shares one instance across every
    session and FastAPI runs the sync handlers in a threadpool: `pop(0)` and
    `append` on shared lists from two turns at once would interleave and hand
    the same scripted response to both, or drop one — a nondeterministic flake
    in whichever test happened to run concurrently.
    """

    def __init__(self, responses: list[Any]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []
        self._guard = threading.Lock()

    def complete_structured(self, system: str, user: str, response_model: type) -> Any:
        with self._guard:
            self.calls.append({"system": system, "user": user, "response_model": response_model})
            response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response_model.model_validate(response)


class BlockingLLMProvider:
    """A fake that blocks inside `complete_structured` until released.

    Exists for one job: proving AC 3 — that a path operation declared `def`
    runs in FastAPI's threadpool, so a multi-second blocking Composer turn does
    not stall the event loop. A fake that returns instantly cannot prove that,
    because `TestClient.get()` is synchronous and would pass against an
    `async def` handler too.
    """

    def __init__(self, response: Any) -> None:
        self._response = response
        self.entered = threading.Event()
        self.release = threading.Event()
        self.calls = 0
        self._guard = threading.Lock()

    def complete_structured(self, system: str, user: str, response_model: type) -> Any:
        with self._guard:
            self.calls += 1
        self.entered.set()
        # Bounded so a broken test fails instead of hanging the whole suite.
        self.release.wait(timeout=30)
        return response_model.model_validate(self._response)
