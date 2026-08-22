"""`RunRegistry` in isolation (Story 2.4 AC 3 / AC 4) — the policy, without HTTP.

Mirrors `test_session_registry.py`'s shape: an injected clock makes idle
eviction deterministic, and route-level behaviour belongs in `test_run.py`.

Each `work` callable here runs on a real background thread (that is the
contract `start()` makes), so tests that need to observe an in-flight run use
`threading.Event`s to synchronise rather than sleeping, and join the
registry's own thread before asserting on a terminal state.
"""
from __future__ import annotations

import threading

import pytest

from api.errors import ApiError
from api.runs import (
    GENERIC_FAILURE_REASON,
    RUN_IDLE_TTL_SECONDS,
    STATUS_COMPLETE,
    STATUS_FAILED,
    STATUS_RUNNING,
    RunRegistry,
    TaskPlanEntry,
)
from team_maker.runtime.results import RunResult


class FakeClock:
    """STUB clock. `RunRegistry` takes it so eviction is deterministic."""

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
def registry(clock) -> RunRegistry:
    return RunRegistry(clock=clock)


_PLAN = (TaskPlanEntry(name="draft", agent_role="writer", dependencies=()),)


def _blocking_work(started: threading.Event, release: threading.Event, *, result=None, error=None):
    def _work():
        started.set()
        assert release.wait(timeout=5), "test never released the blocked run"
        if error is not None:
            raise error
        return result

    return _work


def _immediate_work(*, result=None, error=None):
    def _work():
        if error is not None:
            raise error
        return result

    return _work


def _wait_for_completion(registry: RunRegistry, run_id: str) -> None:
    """Join the registry's own worker thread rather than polling or sleeping."""
    thread = registry._in_flight_thread
    assert thread is not None
    assert thread.join(timeout=5) is None
    assert not thread.is_alive(), "run did not finish within the test timeout"


def test_the_policy_constants_are_named_not_magic():
    """Assert that policy constants have expected values and relationships.
    
    This test ensures that constants governing run registry behavior are explicit
    and can fail if their values change unexpectedly. MAX_STORED_RUNS is the bound
    that the ghost-record finding showed could be exceeded.
    """
    from api.runs import MAX_STORED_RUNS
    
    # Assert MAX_STORED_RUNS has a reasonable positive value
    assert MAX_STORED_RUNS > 0
    assert MAX_STORED_RUNS == 32  # Current expected value - change this if the constant changes
    
    # Assert RUN_IDLE_TTL_SECONDS has a reasonable positive value
    assert RUN_IDLE_TTL_SECONDS > 0
    assert RUN_IDLE_TTL_SECONDS == 30 * 60.0  # Current expected value: 30 minutes
    
    # Assert that the idle TTL is long enough to be useful but not infinite
    assert RUN_IDLE_TTL_SECONDS >= 60.0  # At least 1 minute
    assert RUN_IDLE_TTL_SECONDS <= 3600.0  # At most 1 hour


def test_a_started_run_is_retrievable_with_a_unique_id(registry):
    first = registry.start(
        team_slug="a", team_name="A", tasks=_PLAN, work=_immediate_work(result=RunResult("x", []))
    )
    _wait_for_completion(registry, first.run_id)
    second = registry.start(
        team_slug="b", team_name="B", tasks=_PLAN, work=_immediate_work(result=RunResult("y", []))
    )
    _wait_for_completion(registry, second.run_id)

    assert first.run_id != second.run_id
    assert registry.get(first.run_id).team_slug == "a"
    assert registry.get(second.run_id).team_slug == "b"


def test_a_new_run_starts_in_the_running_status(registry):
    started = threading.Event()
    release = threading.Event()
    record = registry.start(
        team_slug="a", team_name="A", tasks=_PLAN, work=_blocking_work(started, release)
    )

    assert started.wait(timeout=2)
    assert registry.get(record.run_id).status == STATUS_RUNNING

    release.set()
    _wait_for_completion(registry, record.run_id)


def test_unknown_id_raises_run_not_found(registry):
    with pytest.raises(ApiError) as caught:
        registry.get("no-such-run")

    assert caught.value.code == "run_not_found"
    assert caught.value.status_code == 404


def test_a_second_run_is_refused_immediately_while_one_is_in_flight(registry):
    started = threading.Event()
    release = threading.Event()
    first = registry.start(
        team_slug="a", team_name="A", tasks=_PLAN, work=_blocking_work(started, release)
    )
    assert started.wait(timeout=2)

    with pytest.raises(ApiError) as caught:
        registry.start(team_slug="b", team_name="B", tasks=_PLAN, work=_immediate_work())

    assert caught.value.code == "run_in_progress"
    assert caught.value.status_code == 409

    release.set()
    _wait_for_completion(registry, first.run_id)


def test_the_lock_releases_after_completion_so_a_new_run_can_start(registry):
    first = registry.start(
        team_slug="a", team_name="A", tasks=_PLAN, work=_immediate_work(result=RunResult("x", []))
    )
    _wait_for_completion(registry, first.run_id)

    second = registry.start(
        team_slug="b", team_name="B", tasks=_PLAN, work=_immediate_work(result=RunResult("y", []))
    )
    _wait_for_completion(registry, second.run_id)

    assert registry.get(second.run_id).status == STATUS_COMPLETE


def test_a_completed_run_carries_its_result(registry):
    result = RunResult(final_output="the final output", task_results=[])
    record = registry.start(
        team_slug="a", team_name="A", tasks=_PLAN, work=_immediate_work(result=result)
    )
    _wait_for_completion(registry, record.run_id)

    fetched = registry.get(record.run_id)
    assert fetched.status == STATUS_COMPLETE
    assert fetched.result is result
    assert fetched.failure_reason is None
    assert fetched.finished_at is not None


def test_a_failing_run_carries_an_authored_reason_never_the_exception_text(registry):
    record = registry.start(
        team_slug="a",
        team_name="A",
        tasks=_PLAN,
        work=_immediate_work(error=RuntimeError("sk-ant-SECRET-DO-NOT-LEAK")),
    )
    _wait_for_completion(registry, record.run_id)

    fetched = registry.get(record.run_id)
    assert fetched.status == STATUS_FAILED
    assert fetched.failure_reason == GENERIC_FAILURE_REASON
    assert "sk-ant-SECRET-DO-NOT-LEAK" not in fetched.failure_reason
    assert fetched.result is None


def test_the_lock_releases_after_a_failure_too(registry):
    first = registry.start(
        team_slug="a", team_name="A", tasks=_PLAN, work=_immediate_work(error=RuntimeError("boom"))
    )
    _wait_for_completion(registry, first.run_id)

    second = registry.start(
        team_slug="b", team_name="B", tasks=_PLAN, work=_immediate_work(result=RunResult("y", []))
    )
    _wait_for_completion(registry, second.run_id)

    assert registry.get(second.run_id).status == STATUS_COMPLETE


def test_a_finished_run_is_evicted_after_the_idle_ttl(registry, clock):
    record = registry.start(
        team_slug="a", team_name="A", tasks=_PLAN, work=_immediate_work(result=RunResult("x", []))
    )
    _wait_for_completion(registry, record.run_id)

    clock.advance(RUN_IDLE_TTL_SECONDS + 1)

    with pytest.raises(ApiError) as caught:
        registry.get(record.run_id)
    assert caught.value.code == "run_not_found"


def test_a_running_run_is_never_evicted_however_long_it_has_run(registry, clock):
    """The idle clock starts at completion, not at start — a run with no
    timeout (AC 4's own Dev Notes) must survive an arbitrarily long TTL while
    still in flight."""
    started = threading.Event()
    release = threading.Event()
    record = registry.start(
        team_slug="a", team_name="A", tasks=_PLAN, work=_blocking_work(started, release)
    )
    assert started.wait(timeout=2)

    clock.advance(RUN_IDLE_TTL_SECONDS * 10)

    assert registry.get(record.run_id).status == STATUS_RUNNING

    release.set()
    _wait_for_completion(registry, record.run_id)


def test_the_registry_does_not_grow_without_bound(clock):
    registry = RunRegistry(clock=clock, max_records=3)
    run_ids = []
    for index in range(6):
        record = registry.start(
            team_slug=f"team-{index}",
            team_name=f"Team {index}",
            tasks=_PLAN,
            work=_immediate_work(result=RunResult(f"output-{index}", [])),
        )
        _wait_for_completion(registry, record.run_id)
        run_ids.append(record.run_id)
        clock.advance(1)

    assert registry.get(run_ids[-1]).status == STATUS_COMPLETE
    with pytest.raises(ApiError):
        registry.get(run_ids[0])


def test_shutdown_is_a_no_op_when_nothing_is_running(registry):
    registry.shutdown(join_timeout=0.1)  # must not raise


def test_shutdown_waits_for_an_in_flight_run_up_to_its_bound(registry):
    started = threading.Event()
    release = threading.Event()
    record = registry.start(
        team_slug="a", team_name="A", tasks=_PLAN, work=_blocking_work(started, release)
    )
    assert started.wait(timeout=2)
    release.set()  # released immediately, so the bounded join has time to observe completion

    registry.shutdown(join_timeout=2.0)

    assert registry.get(record.run_id).status == STATUS_COMPLETE


def test_shutdown_logs_and_returns_rather_than_hanging_forever(registry, caplog):
    started = threading.Event()
    release = threading.Event()
    registry.start(team_slug="a", team_name="A", tasks=_PLAN, work=_blocking_work(started, release))
    assert started.wait(timeout=2)

    import logging

    with caplog.at_level(logging.WARNING):
        registry.shutdown(join_timeout=0.05)

    assert "still in progress" in caplog.text
    release.set()  # let the background thread finish so it does not outlive the test
    thread = registry._in_flight_thread
    assert thread is not None
    thread.join(timeout=5)


# ---------------------------------------------------------------------------
# Story 2.4 review patches — the states these prove cannot occur, not the
# happy path. Each is falsifiable: reverting the corresponding line in
# `api/runs.py` turns exactly one of these red.
# ---------------------------------------------------------------------------


class _EscapedBaseException(BaseException):
    """A deliberate `BaseException`, mirroring `tests/support/crewai_interception.py`'s
    `_NetworkEscaped` — which exists in this repo precisely so application code
    cannot swallow it with `except Exception`."""


def test_a_baseexception_still_reaches_a_terminal_status_and_is_not_swallowed(
    registry, clock, monkeypatch
):
    """A record left `running` with `finished_at is None` is skipped by both
    eviction rules forever, so one escape permanently leaks a record *and*
    erodes `MAX_STORED_RUNS`. Recording it must not mean swallowing it either:
    a non-`Exception` still has to kill its thread loudly."""
    seen: list = []
    monkeypatch.setattr(threading, "excepthook", lambda args: seen.append(args.exc_type))

    record = registry.start(
        team_slug="a",
        team_name="A",
        tasks=_PLAN,
        work=_immediate_work(error=_EscapedBaseException("escaped")),
    )
    _wait_for_completion(registry, record.run_id)

    stored = registry.get(record.run_id)
    assert stored.status == STATUS_FAILED
    assert stored.failure_reason == GENERIC_FAILURE_REASON
    assert stored.finished_at is not None
    assert not stored.busy, "a permanently-busy record is never evicted by either rule"
    assert seen == [_EscapedBaseException], "a non-Exception must still surface on the thread"

    # And, being terminal, it is genuinely evictable rather than immortal.
    clock.advance(RUN_IDLE_TTL_SECONDS + 1)
    with pytest.raises(ApiError):
        registry.get(record.run_id)


def test_a_run_whose_thread_cannot_start_leaves_no_ghost_and_frees_the_lock(
    registry, monkeypatch
):
    """`thread.start()` can raise (`RuntimeError: can't start new thread`). The
    record is already in the registry by then and no thread will ever carry it
    to a terminal status, so it must be withdrawn — otherwise it reports
    `running` to every future poll and can never be swept."""

    def _refuse(self):
        raise RuntimeError("can't start new thread")

    monkeypatch.setattr(threading.Thread, "start", _refuse)
    with pytest.raises(RuntimeError, match="can't start new thread"):
        registry.start(
            team_slug="doomed",
            team_name="Doomed",
            tasks=_PLAN,
            work=_immediate_work(result=RunResult("x", [])),
        )
    monkeypatch.undo()

    assert registry._records == {}, "the withdrawn run left a ghost record behind"

    # The lock was released, so the registry is still usable.
    record = registry.start(
        team_slug="b", team_name="B", tasks=_PLAN, work=_immediate_work(result=RunResult("y", []))
    )
    _wait_for_completion(registry, record.run_id)
    assert registry.get(record.run_id).status == STATUS_COMPLETE
    assert len(registry._records) == 1


def test_get_hands_out_a_snapshot_that_cannot_change_under_the_caller(registry):
    """The torn read: a route reads `result` then `status` off the record while
    the run thread writes `status` then `result`, so a poll could return
    `status="complete"` with `result=null` — and since the client stops polling
    on a terminal status, that is the final state the user is left with.
    Returning a copy taken under the lock is what makes that unobservable."""
    started, release = threading.Event(), threading.Event()
    record = registry.start(
        team_slug="a",
        team_name="A",
        tasks=_PLAN,
        work=_blocking_work(started, release, result=RunResult("done", [])),
    )
    assert started.wait(timeout=5), "the run never started"

    observed = registry.get(record.run_id)
    assert observed.status == STATUS_RUNNING
    assert observed.result is None

    release.set()
    _wait_for_completion(registry, record.run_id)

    # The object the caller is still holding must not have mutated underneath
    # it. This is the assertion that goes red if `get` returns the live record.
    assert observed.status == STATUS_RUNNING
    assert observed.result is None

    fresh = registry.get(record.run_id)
    assert fresh.status == STATUS_COMPLETE
    assert fresh.result is not None
    assert fresh.finished_at is not None


def test_start_hands_out_a_snapshot_not_the_live_record(registry):
    """`POST /api/runs` renders the record `start()` returns. The run thread is
    already running by then, so that value must be detached too."""
    published = registry.start(
        team_slug="a", team_name="A", tasks=_PLAN, work=_immediate_work(result=RunResult("x", []))
    )
    _wait_for_completion(registry, published.run_id)

    assert published.status == STATUS_RUNNING
    assert published.result is None
    assert registry.get(published.run_id).status == STATUS_COMPLETE
