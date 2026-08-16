"""AC 3 and Task 2's credential race — the two failures that are invisible in
single-request manual testing.

Both tests here are written to *go red* against the naive implementation:

* `test_health_answers_while_a_compose_turn_is_in_flight` fails if any compose
  handler is declared `async def`, because a blocking Composer call inside an
  `async def` stalls the event loop and `/api/health` cannot be served.
* `test_two_concurrent_turns_both_keep_their_credential` fails if the
  credential is bridged per-request with `cli.py`'s `_bridged_credential`
  shape, because the first request to finish pops the env var out from under
  the second.

The providers here are STUBS. Nothing contacts a real LLM.
"""
from __future__ import annotations

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from tests.api.conftest import SENTINEL_KEYS
from tests.support.fake_llm import BlockingLLMProvider

# The health probe must come back promptly while a turn is blocked. Generous
# enough not to be flaky on a loaded machine, tight enough that a stalled event
# loop (which would wait out the blocker) cannot pass.
HEALTH_DEADLINE_SECONDS = 5.0


def test_health_answers_while_a_compose_turn_is_in_flight(
    make_client, spec_payload, tmp_path
):
    """AC 3: handlers are `def`, so FastAPI runs them in its threadpool.

    `Composer.compose()` performs up to four sequential blocking LLM
    round-trips (`composer.py:106-126`) and nothing in the core is async. A
    fake that returns instantly would pass against `async def` too, which is
    why this one blocks on a `threading.Event` and the health probe is timed.
    """
    blocker = BlockingLLMProvider(spec_payload(tmp_path))
    harness = make_client(provider=blocker)

    with ThreadPoolExecutor(max_workers=1) as pool:
        in_flight = pool.submit(
            harness.client.post,
            "/api/compose/sessions",
            json={"intent": "I need a team to write docs."},
        )
        assert blocker.entered.wait(timeout=10), "the compose turn never started"

        started = time.monotonic()
        health = harness.client.get("/api/health")
        elapsed = time.monotonic() - started

        blocker.release.set()
        created = in_flight.result(timeout=30)

    assert health.status_code == 200
    assert elapsed < HEALTH_DEADLINE_SECONDS, (
        f"/api/health took {elapsed:.1f}s while a compose turn was blocked — "
        "the event loop is stalled, so a handler is `async def`"
    )
    assert created.status_code == 201


class CredentialProbeProvider:
    """STUB. Records what the credential env var held *while* it was called.

    Both concurrent calls rendezvous on a barrier before reading, so the read
    happens with two turns genuinely in flight. That is the exact window in
    which `cli.py`'s `_bridged_credential` loses the value: request A enters
    with `previous=None`, request B enters with `previous=A's key`, A exits and
    pops the variable — and B, still mid-flight, reads `None`.
    """

    def __init__(self, payload: dict[str, Any], parties: int) -> None:
        self._payload = payload
        self._barrier = threading.Barrier(parties, timeout=15)
        self.observed: list[str | None] = []
        self._guard = threading.Lock()

    def complete_structured(self, system: str, user: str, response_model: type) -> Any:
        self._barrier.wait()
        seen = os.environ.get("ANTHROPIC_API_KEY")
        with self._guard:
            self.observed.append(seen)
        return response_model.model_validate(self._payload)


class _ClassificationShortCircuit:
    """Wraps a provider so Story 2.10's classification call — now made once,
    ahead of `Composer.compose()`, on every session's first turn — answers
    instantly with a fixed "is a team" verdict instead of reaching the
    wrapped provider.

    Without this, `CredentialProbeProvider`'s barrier (built for exactly
    `parties=2`, one call per concurrent turn) sees two calls per turn
    instead of one, doubling `observed` and desynchronising the rendezvous
    the test relies on. Detected structurally, by the response model's
    shape, so it stays correct regardless of call count or order.
    """

    def __init__(self, inner: Any) -> None:
        self._inner = inner

    def complete_structured(self, system: str, user: str, response_model: type) -> Any:
        if "is_team" in getattr(response_model, "model_fields", {}):
            return response_model.model_validate({"is_team": True})
        return self._inner.complete_structured(system, user, response_model)


def test_two_concurrent_turns_both_keep_their_credential(
    make_client, spec_payload, tmp_path
):
    """Task 2: the credential is bridged once at startup and held, so there is
    no window in which a concurrent request can lose it."""
    probe = CredentialProbeProvider(spec_payload(tmp_path), parties=2)
    harness = make_client(provider=_ClassificationShortCircuit(probe))

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(
                harness.client.post,
                "/api/compose/sessions",
                json={"intent": f"team number {index}"},
            )
            for index in range(2)
        ]
        responses = [future.result(timeout=30) for future in futures]

    assert [response.status_code for response in responses] == [201, 201]
    assert len(probe.observed) == 2
    assert probe.observed == [SENTINEL_KEYS["ANTHROPIC_API_KEY"]] * 2


def test_separate_sessions_do_not_share_a_spec(make_client, spec_payload, tmp_path):
    """Two conversations run in parallel; each keeps its own `session.current`."""
    harness = make_client(
        [
            {"is_team": True},
            spec_payload(tmp_path, team_name="Team One"),
            {"is_team": True},
            spec_payload(tmp_path, team_name="Team Two"),
        ]
    )

    first = harness.client.post("/api/compose/sessions", json={"intent": "one"}).json()
    second = harness.client.post("/api/compose/sessions", json={"intent": "two"}).json()

    assert first["session_id"] != second["session_id"]
    assert first["spec"]["team_name"] == "Team One"
    assert second["spec"]["team_name"] == "Team Two"

    readback = harness.client.put(
        f"/api/compose/sessions/{first['session_id']}/spec", json={}
    ).json()
    assert readback["spec"]["team_name"] == "Team One"
