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
    assert RUN_IDLE_TTL_SECONDS > 0


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


