"""D3 and D4 tests from review patches.

D3 — the per-conversation lock is bounded
D3/P2 — eviction never takes a live conversation
D4 — the process-wide spend ceiling

These tests verify session locking, eviction protection, and spend ceilings.
"""
from __future__ import annotations

import threading

import pytest

from api.errors import STATUS_BY_CODE
from api.sessions import SessionRegistry
from tests.api.test_review_patches_base import _choice, _FakeClock

# ---------------------------------------------------------------------------
# D3 — the per-conversation lock is bounded
# ---------------------------------------------------------------------------


def test_a_busy_session_answers_rather_than_blocking():
    """Before the fix `entry.lock` was acquired with no timeout while wrapping
    network calls, so a hung provider held the lock, the session and a
    threadpool thread indefinitely, and every queued request held another."""
    registry = SessionRegistry(lock_timeout=0.05)
    entry = registry.create(object(), _choice())  # type: ignore[arg-type]

    holder_has_it = threading.Event()
    release = threading.Event()

    def hold_it():
        with registry.hold(entry):
            holder_has_it.set()
            release.wait(timeout=5)

    worker = threading.Thread(target=hold_it)
    worker.start()
    try:
        assert holder_has_it.wait(timeout=5)
        with pytest.raises(Exception) as caught:
            with registry.hold(entry):
                pass
        assert caught.value.code == "session_busy"
        assert caught.value.status_code == 409
    finally:
        release.set()
        worker.join(timeout=5)



def test_the_waiter_queue_is_bounded():
    registry = SessionRegistry(lock_timeout=5.0, max_waiters=1)
    entry = registry.create(object(), _choice())  # type: ignore[arg-type]

    with registry.hold(entry):
        # The second request does not even wait out the timeout — there is
        # already one holder, and max_waiters is 1.
        with pytest.raises(Exception) as caught:
            with registry.hold(entry):
                pass
    assert caught.value.code == "session_busy"



def test_session_busy_is_a_real_code_with_a_status():
    assert STATUS_BY_CODE["session_busy"] == 409


# ---------------------------------------------------------------------------
# D3/P2 — eviction never takes a live conversation
# ---------------------------------------------------------------------------


def test_an_in_flight_session_is_not_evicted_when_idle(monkeypatch):
    """A turn can outlast the idle TTL (four sequential LLM calls, each with a
    two-minute ceiling). Before the fix the sweeper deleted it mid-call and the
    handler then returned 200 with a `session_id` that 404s immediately."""
    clock = _FakeClock()
    registry = SessionRegistry(clock=clock, idle_ttl=10.0)
    entry = registry.create(object(), _choice())  # type: ignore[arg-type]

    with registry.hold(entry):
        clock.advance(1_000)
        registry.create(object(), _choice())  # type: ignore[arg-type]  # triggers the sweep
        assert registry.get(entry.session_id) is entry



def test_an_in_flight_session_is_not_evicted_by_overflow():
    registry = SessionRegistry(max_sessions=2)
    entry = registry.create(object(), _choice())  # type: ignore[arg-type]

    with registry.hold(entry):
        for _ in range(5):
            registry.create(object(), _choice())  # type: ignore[arg-type]
        assert registry.get(entry.session_id) is entry



def test_a_zero_capacity_registry_does_not_explode():
    """`while len >= 0` used to reach `min()` on an empty dict."""
    registry = SessionRegistry(max_sessions=0)

    entry = registry.create(object(), _choice())  # type: ignore[arg-type]

    assert registry.get(entry.session_id) is entry


# ---------------------------------------------------------------------------
# D4 — the process-wide spend ceiling
# ---------------------------------------------------------------------------


def test_the_window_cap_bounds_turns_across_sessions():
    """The per-session cap is not a spend ceiling: `POST /sessions` is
    unlimited and each call costs 1-4 LLM round-trips. This is the cap that
    actually bounds it."""
    registry = SessionRegistry(max_turns_per_window=3)
    entries = [registry.create(object(), _choice()) for _ in range(4)]  # type: ignore[arg-type]

    for entry in entries[:3]:
        registry.begin_turn(entry)

    with pytest.raises(Exception) as caught:
        registry.begin_turn(entries[3])
    assert caught.value.code == "turn_cap_reached"
    assert "server" in caught.value.message.lower()



def test_the_window_rolls_forward():
    clock = _FakeClock()
    registry = SessionRegistry(max_turns_per_window=1, window_seconds=100.0, clock=clock)
    first = registry.create(object(), _choice())  # type: ignore[arg-type]
    second = registry.create(object(), _choice())  # type: ignore[arg-type]

    registry.begin_turn(first)
    with pytest.raises(Exception):
        registry.begin_turn(second)

    clock.advance(101)
    registry.begin_turn(second)  # the window has moved on
