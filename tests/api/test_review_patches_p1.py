"""P1 tests from review patches.

P1 — liveness does not share the compose threadpool

These tests verify that liveness checks don't share the compose threadpool
and that new routes don't leak credentials.
"""
from __future__ import annotations

import inspect

from api.main import health
from api.routers import compose
from tests.api.test_review_patches_base import SENTINEL_VALUES, _start, assert_no_sentinels

# ---------------------------------------------------------------------------
# P1 — liveness does not share the compose threadpool
# ---------------------------------------------------------------------------


def test_health_is_a_coroutine_handler(make_client):
    """It does no I/O, so as `def` it consumed one of the same 40 anyio
    threadpool tokens the blocking compose handlers occupy — meaning enough
    concurrent turns could queue the liveness probe behind exactly the work it
    exists to report on. The compose handlers stay `def`; that is AC 3."""
    assert inspect.iscoroutinefunction(health)
    for handler in (
        compose.create_session,
        compose.send_message,
        compose.replace_spec,
        compose.build_session,
    ):
        assert not inspect.iscoroutinefunction(handler), f"{handler.__name__} must stay `def`"



def test_no_new_route_leaks_a_credential(make_client, spec_payload, tmp_path):
    """The AC 4 sweep, re-run against the paths these patches added."""
    harness = make_client([spec_payload(tmp_path)])

    responses = [
        _start(harness, authoring={"provider": "groq", "model": "x"}),
        _start(harness, authoring={"provider": "", "model": ""}),
        harness.client.delete("/api/health"),
    ]

    for response in responses:
        assert_no_sentinels(response.text, SENTINEL_VALUES)
