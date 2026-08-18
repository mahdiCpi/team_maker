"""In-process run registry: one execution at a time, bounded, idle-evicted
(Story 2.4 AC 3 / AC 4).

A sibling of `api/sessions.py` — same shape, same comment discipline — not an
extension of it: a compose session and a run are different objects with
different lifetimes, and a run is not a conversation.

## The lock is process-wide on purpose

`deferred-work.md:102` measured, with a barrier during the Story 1.7 review,
that two concurrent `run_team_package` calls in one process corrupt each
other's transcripts three independent ways: handler fan-out on crewai's
process-global event bus, `emission_sequence` colliding across runs (it is
ContextVar-scoped and restarts at 1 per run, so sorting cannot separate two
runs), and `TranscriptRecorder.__exit__`'s `flush()` waiting on every
process-wide pending future. A process-wide lock is the only fix that closes
all three without touching `team_maker/`, and the API is already pinned
single-worker (`main.py:_warn_on_multiple_workers`), so a process-wide lock
*is* a system-wide lock. This registry is that lock's one home.

## Why a run's own idle clock starts only at completion

A `RunRecord` is never evicted while a run is in flight, however long it has
been running — mirroring `SessionRegistry`'s `busy` guard, which exists so
"an id that looks alive can never be swept out from under itself"
(`sessions.py:250`). The idle TTL here measures time since the run
*finished*, not time since it started, which is why `finished_at` — not
`created_at` — is the field eviction reads.
"""
from __future__ import annotations

import dataclasses
import logging
import threading
import time
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Optional

from api.errors import RUN_IN_PROGRESS, RUN_NOT_FOUND, ApiError
from team_maker.runtime.results import RunResult
from team_maker.utils.text_sanitizer import log_exception_safely

logger = logging.getLogger("api.runs")

# Mirrors `SESSION_IDLE_TTL_SECONDS` (`sessions.py:53`): how long a finished
# run's record survives before it is swept.
RUN_IDLE_TTL_SECONDS = 30 * 60.0

# Mirrors `MAX_ACTIVE_SESSIONS` (`sessions.py:58`): a ceiling on stored
# records, so a long-lived process cannot accumulate an unbounded number of
# finished runs each holding a full transcript.
MAX_STORED_RUNS = 32

STATUS_RUNNING = "running"
STATUS_COMPLETE = "complete"
STATUS_FAILED = "failed"

# A background failure's copy is fixed and causally neutral (`errors.py`'s
# rule: authored copy, never `str(exc)`). By the time a run reaches this
# thread, `POST /api/runs`'s synchronous gate (AC 7) has already run the same
# checks once — so anything reaching here is either that same check losing a
# race (a key removed mid-flight) or a genuine execution fault, and neither is
# safe to describe more specifically without risking `str(exc)`.
GENERIC_FAILURE_REASON = (
    "The run failed while in progress. Details have been logged on the server."
)


@dataclass(frozen=True)
class TaskPlanEntry:
    """One task's place in a team's plan — the shape `TeamPlanView` and
    `RunView` share, so the Workspace renders one task list before a run
    starts and while/after it runs (Story 2.4 AC 1 / AC 4)."""

    name: str
    agent_role: str
    dependencies: tuple[str, ...]


@dataclass
class RunRecord:
    """One run: its plan, snapshotted at start, plus its outcome.

    `tasks` is captured once, from the loaded team, rather than re-read from
    disk on every `GET` — so a run's reported plan cannot change under a
    client mid-poll, and a `GET` never depends on the package still existing
    on disk.
    """

    run_id: str
    team_slug: str
    team_name: str
    tasks: tuple[TaskPlanEntry, ...]
    status: str = STATUS_RUNNING
    result: Optional[RunResult] = None
    failure_reason: Optional[str] = None
    # `None` while running; set once the run reaches a terminal status. Idle
    # eviction reads this, never `created_at` — see the module docstring.
    finished_at: Optional[float] = None

    @property
    def busy(self) -> bool:
        """Whether this run is still in flight. Eviction must never take it."""
        return self.status == STATUS_RUNNING


def _snapshot(record: RunRecord) -> RunRecord:
    """A detached copy of *record*, for handing outside the registry's lock.

    Callers must only ever be given one of these: every mutable field on a
    `RunRecord` is written by the run's own thread, so a caller holding the
    live object reads a moving target field by field. Taken while `_guard` is
    held, this copy is internally consistent by construction.
    """
    return dataclasses.replace(record)


class RunRegistry:
    """Thread-safe, and so are the records it hands out.

    Every public method is safe to call from the threadpool, and every record
    returned is a `_snapshot` — a caller can never observe a partially
    published terminal state.
    """

    def __init__(
        self,
        *,
        idle_ttl: float = RUN_IDLE_TTL_SECONDS,
        max_records: int = MAX_STORED_RUNS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._records: dict[str, RunRecord] = {}
        self._guard = threading.Lock()
        # The AC 3 lock. `acquire(blocking=False)` is the whole contract: a
        # second run request is refused immediately, never queued and never
        # left waiting on a thread.
        self._run_lock = threading.Lock()
        self._idle_ttl = idle_ttl
        self._max_records = max_records
        self._clock = clock
        self._in_flight_thread: Optional[threading.Thread] = None

    def start(
        self,
        *,
        team_slug: str,
        team_name: str,
        tasks: Sequence[TaskPlanEntry],
        work: Callable[[], RunResult],
    ) -> RunRecord:
        """Reserve the process-wide lock and start *work* on its own thread.

        Raises `run_in_progress` (AC 3) immediately, without blocking, if
        another run already holds the lock. *work* is a zero-argument
        callable the caller builds (typically a closure over
        `run_team_package(...)`) — this registry has no `team_maker` import
        beyond the dependency-free `RunResult` type, so it stays agnostic of
        how a run is actually performed (AD-6/AD-8).
        """
        # Built before the lock is taken so nothing between `acquire()` and the
        # `try` can raise and strand it.
        record = RunRecord(
            run_id=uuid.uuid4().hex,
            team_slug=team_slug,
            team_name=team_name,
            tasks=tuple(tasks),
        )
        if not self._run_lock.acquire(blocking=False):
            raise ApiError(
                RUN_IN_PROGRESS,
                "Another run is already in progress. Wait for it to finish "
                "before starting another — this server runs one at a time.",
            )
        try:
            with self._guard:
                self._evict_idle_locked()
                self._evict_overflow_locked()
                self._records[record.run_id] = record
            thread = threading.Thread(
                target=self._execute,
                args=(record, work),
                name=f"run-{record.run_id}",
                # A daemon thread never blocks process exit by itself; the
                # lifespan shutdown branch (`main.py`) still gives it a
                # bounded join so a fast run's result is not needlessly
                # dropped on a routine restart.
                daemon=True,
            )
            self._in_flight_thread = thread
            # Snapshotted before the thread can touch the record, so the
            # response to `POST /api/runs` cannot observe a half-published
            # terminal state (see `get`). A freshly built record is
            # definitionally `running` with no result, which is exactly what
            # AC 1 says this route returns.
            published = _snapshot(record)
            thread.start()
        except BaseException:
            # The record is in `_records` but no thread will ever carry it to a
            # terminal status, so `busy` would stay True forever — and both
            # eviction rules skip a busy record, so it would never be swept and
            # would count against `MAX_STORED_RUNS` permanently. Remove it.
            with self._guard:
                self._records.pop(record.run_id, None)
            self._in_flight_thread = None
            self._run_lock.release()
            raise
        return published

    def get(self, run_id: str) -> RunRecord:
        """Look up a run, or raise the AC 4 clean 404.

        Idle records are swept on every lookup, exactly as
        `SessionRegistry.get` does — so an evicted `run_id` is
        indistinguishable from one that never existed, which is the point.

        **Returns a snapshot, never the live record.** The run thread mutates
        `status`/`result`/`failure_reason`/`finished_at` under `_guard`, and a
        caller that read those fields off the live object would be reading them
        one at a time with no lock: it could see `status == "complete"` while
        `result` was still `None`, because the reader's field order is the
        reverse of the writer's. The client stops polling on a terminal status,
        so that torn pair is not a transient glitch — it is the final state the
        user is left with. Copying under the guard is what makes "thread-safe"
        in this class's own docstring true of the values as well as the dict.
        """
        with self._guard:
            self._evict_idle_locked()
            entry = self._records.get(run_id)
            if entry is None:
                raise ApiError(
                    RUN_NOT_FOUND,
                    "That run is no longer available. It may have finished "
                    "long enough ago to be cleared. Start a new run to see "
                    "fresh results.",
                )
            return _snapshot(entry)

    def shutdown(self, *, join_timeout: float = 2.0) -> None:
        """Give an in-flight run a bounded chance to finish, then let go.

        The lifespan has no shutdown branch before Story 2.4; a run's
        background thread is the first thing in this process that can
        outlive the app. Joining without a bound would hang an ordinary
        restart for as long as an LLM-driven run cares to take (minutes, no
        timeout — AC 4's own Dev Notes); not joining at all silently drops a
        run's result moments from completion. This is the declared middle
        ground: wait briefly, then log and let the daemon thread be
        terminated with the process.
        """
        thread = self._in_flight_thread
        if thread is None or not thread.is_alive():
            return
        thread.join(timeout=join_timeout)
        if thread.is_alive():
            logger.warning(
                "shutting down with a run still in progress after waiting %.1fs; "
                "its result will be lost",
                join_timeout,
            )

    # -- internals; callers already hold `self._guard` unless noted ---------

    def _execute(self, record: RunRecord, work: Callable[[], RunResult]) -> None:
        # `BaseException`, not `Exception`, and for the same reason `start`
        # above uses it: anything that escapes `work()` without being recorded
        # leaves this record `running` with `finished_at is None` forever, and
        # both eviction rules skip a busy record — so a single escape is a
        # permanent leak that also defeats `MAX_STORED_RUNS`. This is not
        # hypothetical: `tests/support/crewai_interception.py` raises a
        # deliberate `BaseException` subclass precisely so application code
        # cannot swallow it, and `SystemExit` from library code is the same
        # shape. A non-`Exception` is re-raised once recorded, so the thread
        # still dies loudly rather than being quietly downgraded.
        try:
            result = work()
        except BaseException as exc:
            # Use safe logging to prevent sensitive data (document text, etc.) from leaking
            # Per AD-9: keys and sensitive data must never be logged
            log_exception_safely(logger, f"run {record.run_id} failed", exc)
            with self._guard:
                record.failure_reason = GENERIC_FAILURE_REASON
                record.finished_at = self._clock()
                record.status = STATUS_FAILED
            if not isinstance(exc, Exception):
                raise
        else:
            with self._guard:
                # `status` is assigned *last*, after the fields a terminal
                # status promises are already in place. Readers go through
                # `get`, which copies under this same lock, so ordering is
                # belt-and-braces — but it keeps the invariant true for any
                # future reader that does not.
                record.result = result
                record.finished_at = self._clock()
                record.status = STATUS_COMPLETE
        finally:
            self._run_lock.release()

    def _evict_idle_locked(self) -> None:
        cutoff = self._clock() - self._idle_ttl
        stale = [
            run_id
            for run_id, entry in self._records.items()
            if not entry.busy and entry.finished_at is not None and entry.finished_at < cutoff
        ]
        for run_id in stale:
            del self._records[run_id]
        if stale:
            logger.info("evicted %d idle run record(s)", len(stale))

    def _evict_overflow_locked(self) -> None:
        if self._max_records <= 0:
            return
        while len(self._records) >= self._max_records:
            finished = [item for item in self._records.items() if not item[1].busy]
            if not finished:
                # The lock already caps in-flight runs at one, so this can
                # only mean every stored record is that one running run —
                # nothing idle exists yet to evict.
                logger.warning(
                    "run registry is at capacity (%d) with no finished run to "
                    "evict; admitting one more",
                    self._max_records,
                )
                return
            oldest = min(finished, key=lambda item: item[1].finished_at or 0.0)[0]
            del self._records[oldest]
            logger.info("evicted least-recently-finished run (registry full)")
