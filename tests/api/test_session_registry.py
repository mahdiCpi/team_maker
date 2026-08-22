"""`SessionRegistry` in isolation (AC 7) — the policy, without the HTTP.

The HTTP-level behaviour is covered in `test_compose_sessions.py`; this file
pins the policy itself with an injected clock, so idle eviction is tested in
microseconds rather than half an hour.
"""
from __future__ import annotations

import pytest

from api.deps import resolve_authoring_choice
from api.errors import ApiError
from api.sessions import (
    MAX_ACTIVE_SESSIONS,
    MAX_TURNS_PER_SESSION,
    SESSION_IDLE_TTL_SECONDS,
    SessionRegistry,
)


class FakeClock:
    """STUB clock. `SessionRegistry` takes it so eviction is deterministic."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def registry(clock) -> SessionRegistry:
    return SessionRegistry(clock=clock)


def _add(registry: SessionRegistry):
    return registry.create(object(), resolve_authoring_choice(None, None))  # type: ignore[arg-type]


def test_the_policy_constants_are_named_not_magic():
    """AC 7 requires both the cap and the TTL to be named constants.
    
    Assert that policy constants have expected values and relationships.
    These constants govern session registry behavior and should fail if changed.
    """
    from api.sessions import MAX_TURNS_PER_SESSION, SESSION_IDLE_TTL_SECONDS, MAX_ACTIVE_SESSIONS
    
    # Assert MAX_TURNS_PER_SESSION has a reasonable positive value
    assert MAX_TURNS_PER_SESSION > 0
    assert MAX_TURNS_PER_SESSION == 20  # Current expected value - change if the constant changes
    
    # Assert SESSION_IDLE_TTL_SECONDS has a reasonable positive value
    assert SESSION_IDLE_TTL_SECONDS > 0
    assert SESSION_IDLE_TTL_SECONDS == 30 * 60.0  # Current expected value: 30 minutes
    
    # Assert MAX_ACTIVE_SESSIONS has a reasonable positive value
    assert MAX_ACTIVE_SESSIONS > 0
    assert MAX_ACTIVE_SESSIONS == 32  # Current expected value - change if the constant changes
    
    # Assert relationships: idle TTL should be reasonable for a session
    assert SESSION_IDLE_TTL_SECONDS >= 60.0  # At least 1 minute
    assert SESSION_IDLE_TTL_SECONDS <= 3600.0  # At most 1 hour
    
    # Assert MAX_TURNS_PER_SESSION is reasonable
    assert MAX_TURNS_PER_SESSION >= 5  # At least 5 turns
    assert MAX_TURNS_PER_SESSION <= 100  # At most 100 turns


def test_created_sessions_are_retrievable_and_have_unique_ids(registry):
    first = _add(registry)
    second = _add(registry)

    assert first.session_id != second.session_id
    assert registry.get(first.session_id) is first
    assert registry.active_count() == 2


def test_unknown_id_raises_session_not_found(registry):
    with pytest.raises(ApiError) as caught:
        registry.get("no-such-session")

    assert caught.value.code == "session_not_found"
    assert caught.value.status_code == 404


def test_an_idle_session_is_evicted(registry, clock):
    entry = _add(registry)

    clock.advance(SESSION_IDLE_TTL_SECONDS + 1)

    with pytest.raises(ApiError) as caught:
        registry.get(entry.session_id)
    assert caught.value.code == "session_not_found"
    assert registry.active_count() == 0


def test_activity_keeps_a_session_alive(registry, clock):
    entry = _add(registry)

    for _ in range(4):
        clock.advance(SESSION_IDLE_TTL_SECONDS * 0.75)
        assert registry.get(entry.session_id) is entry

    assert registry.active_count() == 1


def test_eviction_does_not_take_a_busy_neighbour_with_it(registry, clock):
    stale = _add(registry)
    clock.advance(SESSION_IDLE_TTL_SECONDS * 0.9)
    fresh = _add(registry)
    clock.advance(SESSION_IDLE_TTL_SECONDS * 0.2)

    with pytest.raises(ApiError):
        registry.get(stale.session_id)
    assert registry.get(fresh.session_id) is fresh


def test_the_turn_cap_is_a_hard_stop(registry):
    entry = _add(registry)

    for turn in range(1, MAX_TURNS_PER_SESSION + 1):
        registry.begin_turn(entry)
        assert entry.turn == turn
        assert registry.turns_remaining(entry) == MAX_TURNS_PER_SESSION - turn

    with pytest.raises(ApiError) as caught:
        registry.begin_turn(entry)
    assert caught.value.code == "turn_cap_reached"
    assert caught.value.status_code == 409
    assert entry.turn == MAX_TURNS_PER_SESSION


def test_the_registry_does_not_grow_without_bound(clock):
    registry = SessionRegistry(clock=clock, max_sessions=3)

    entries = []
    for _ in range(6):
        entries.append(_add(registry))
        clock.advance(1)

    assert registry.active_count() <= 3
    assert registry.get(entries[-1].session_id) is entries[-1]
    with pytest.raises(ApiError):
        registry.get(entries[0].session_id)
