"""In-process compose-session registry with turn caps and idle eviction (AC 7).

`deferred-work.md:54` records that the CLI has "no cap on conversation turns or
consecutive failed-refinement attempts … a confused user or scripted stdin can
drive unbounded LLM spend with zero guardrail". An HTTP API makes that
materially worse — there is no human at a terminal to stop — so caps are
enforced here rather than inherited.

**Two caps, because one is not a spend ceiling.** `MAX_TURNS_PER_SESSION` bounds
one conversation. It does *not* bound spend, and an earlier version of this
docstring claimed it did: `POST /sessions` is unauthenticated and unlimited, and
each call performs 1–4 blocking LLM round-trips *before* any per-session cap can
apply, so a loop of session creations spends at line rate. The Story 2.0 code
review corrected the claim and added `MAX_TURNS_PER_WINDOW`, a process-wide
ceiling on authoring turns per rolling window. That is the real ceiling. Genuine
per-*client* limiting is impossible until authentication exists (Epic 4 owns the
public contract) — there is no client identity to attribute a turn to.

Sessions live in a plain dict, which makes the API **single-worker**: a second
uvicorn worker gets its own empty registry and every existing `session_id`
becomes a 404 in half the requests. `make api-serve` pins `--workers 1` and the
app logs a startup warning if it can tell otherwise (AD-3, "one deployable
process by default").
"""
from __future__ import annotations

import logging
import secrets
import threading
import time
from collections import deque
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field

from api.deps import AuthoringChoice
from api.errors import SESSION_BUSY, SESSION_NOT_FOUND, TURN_CAP_REACHED, ApiError
from team_maker.composer.session import ComposerSession

logger = logging.getLogger("api.sessions")

# How many authoring turns one conversation may spend. A "turn" is 1–4 blocking
# LLM round-trips (`composer.py:106-126`).
MAX_TURNS_PER_SESSION = 20

# The process-wide ceiling. Bounds total authoring spend across every session,
# including the turn that session creation itself performs — which is the hole
# the per-session cap cannot see.
MAX_TURNS_PER_WINDOW = 200
TURN_WINDOW_SECONDS = 60 * 60.0

# How long a conversation may sit untouched before its spec is dropped.
SESSION_IDLE_TTL_SECONDS = 30 * 60.0

# A ceiling on concurrent conversations, so an unbounded dict cannot become the
# next unbounded resource. The least-recently-used *idle* session is dropped
# first; a session with a turn in flight is never evicted.
MAX_ACTIVE_SESSIONS = 32

# How long a request will wait for another turn on the *same* conversation
# before giving up with a clean 409. Without a bound here a hung upstream holds
# the session lock and a FastAPI threadpool thread indefinitely, and every
# queued request holds another thread.
SESSION_LOCK_TIMEOUT_SECONDS = 5.0

# How many requests may be waiting on one conversation at once. Beyond this the
# answer is immediate rather than after a timeout, so a client hammering one
# session cannot occupy threads just by queueing.
MAX_WAITERS_PER_SESSION = 2


@dataclass
class ComposeSession:
    """One conversation: the core's session object plus the API's bookkeeping."""

    session_id: str
    conversation: ComposerSession
    choice: AuthoringChoice
    turn: int = 0
    last_seen: float = 0.0
    # The server-chosen output directory, frozen at session creation. See
    # `api/output.py` for why it is derived once rather than per turn.
    output_path: str | None = None
    # Requests currently holding or waiting for `lock`, guarded by the
    # registry's own lock rather than by this one.
    waiters: int = 0
    # Serialises turns *within* one conversation. `ComposerSession` mutates
    # `self.current` in place, so two concurrent refines on the same session
    # would interleave. Different sessions still run fully in parallel.
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    @property
    def busy(self) -> bool:
        """Whether a turn is in flight. Eviction must not take these."""
        return self.waiters > 0 or self.lock.locked()


class SessionRegistry:
    """Thread-safe registry. Every public method is safe from the threadpool."""

    def __init__(
        self,
        *,
        max_turns: int = MAX_TURNS_PER_SESSION,
        idle_ttl: float = SESSION_IDLE_TTL_SECONDS,
        max_sessions: int = MAX_ACTIVE_SESSIONS,
        max_turns_per_window: int = MAX_TURNS_PER_WINDOW,
        window_seconds: float = TURN_WINDOW_SECONDS,
        lock_timeout: float = SESSION_LOCK_TIMEOUT_SECONDS,
        max_waiters: int = MAX_WAITERS_PER_SESSION,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._sessions: dict[str, ComposeSession] = {}
        self._guard = threading.Lock()
        self._max_turns = max_turns
        self._idle_ttl = idle_ttl
        self._max_sessions = max_sessions
        self._max_turns_per_window = max_turns_per_window
        self._window_seconds = window_seconds
        self._lock_timeout = lock_timeout
        self._max_waiters = max_waiters
        self._clock = clock
        # Timestamps of authoring turns, pruned to the rolling window.
        self._turn_times: deque[float] = deque()

    @property
    def max_turns(self) -> int:
        return self._max_turns

    def create(self, conversation: ComposerSession, choice: AuthoringChoice) -> ComposeSession:
        entry = ComposeSession(
            session_id=secrets.token_urlsafe(16),
            conversation=conversation,
            choice=choice,
            last_seen=self._clock(),
        )
        with self._guard:
            self._evict_idle_locked()
            self._evict_overflow_locked()
            self._sessions[entry.session_id] = entry
        return entry

    def get(self, session_id: str) -> ComposeSession:
        """Look up a live session, or raise the AC 7 clean 404.

        Idle sessions are swept on every lookup, so an evicted id is
        indistinguishable from one that never existed — which is the point: a
        client must get `session_not_found`, not a 500 from a half-dead object.
        """
        with self._guard:
            self._evict_idle_locked()
            entry = self._sessions.get(session_id)
            if entry is None:
                raise ApiError(
                    SESSION_NOT_FOUND,
                    "That conversation is no longer available. It may have expired "
                    "after a period of inactivity. Start a new one to continue.",
                )
            entry.last_seen = self._clock()
            return entry

    @contextmanager
    def hold(self, entry: ComposeSession) -> Iterator[ComposeSession]:
        """Take the per-conversation lock, bounded in both wait and queue depth.

        Replaces a bare `with entry.lock:`. That version was acquired without a
        timeout while wrapping calls that block on the network, so one
        unresponsive provider pinned the lock, the session and a threadpool
        thread for as long as the upstream cared to hang — and every queued
        request pinned another thread behind it.
        """
        with self._guard:
            if entry.waiters >= self._max_waiters:
                raise ApiError(
                    SESSION_BUSY,
                    "This conversation is already busy with another request. "
                    "Wait for it to finish before sending another.",
                )
            entry.waiters += 1
        try:
            if not entry.lock.acquire(timeout=self._lock_timeout):
                raise ApiError(
                    SESSION_BUSY,
                    "This conversation is still working on a previous request. "
                    "Try again in a moment.",
                )
            try:
                # Refresh liveness on both edges so a long turn cannot be swept
                # out from under itself by the idle sweeper.
                self._touch(entry)
                yield entry
            finally:
                self._touch(entry)
                entry.lock.release()
        finally:
            with self._guard:
                entry.waiters -= 1

    def begin_turn(self, entry: ComposeSession) -> None:
        """Reserve one authoring turn against both caps, or raise AC 2's 409."""
        with self._guard:
            now = self._clock()
            self._prune_window_locked(now)
            if len(self._turn_times) >= self._max_turns_per_window:
                raise ApiError(
                    TURN_CAP_REACHED,
                    "This server has reached its limit of "
                    f"{self._max_turns_per_window} authoring turns for now. "
                    "Wait a few minutes and try again.",
                )
            if entry.turn >= self._max_turns:
                raise ApiError(
                    TURN_CAP_REACHED,
                    f"This conversation has reached its limit of {self._max_turns} turns. "
                    "Build the team as it stands, or start a new conversation.",
                )
            entry.turn += 1
            self._turn_times.append(now)

    def turns_remaining(self, entry: ComposeSession) -> int:
        return max(0, self._max_turns - entry.turn)

    def discard(self, session_id: str) -> None:
        with self._guard:
            self._sessions.pop(session_id, None)

    def active_count(self) -> int:
        with self._guard:
            return len(self._sessions)

    # -- internals; callers already hold `self._guard` unless noted ---------

    def _touch(self, entry: ComposeSession) -> None:
        with self._guard:
            entry.last_seen = self._clock()

    def _prune_window_locked(self, now: float) -> None:
        cutoff = now - self._window_seconds
        while self._turn_times and self._turn_times[0] < cutoff:
            self._turn_times.popleft()

    def _evict_idle_locked(self) -> None:
        cutoff = self._clock() - self._idle_ttl
        stale = [
            sid
            for sid, entry in self._sessions.items()
            # A session with a turn in flight is not idle, however long the
            # provider has been silent. Evicting one returns a 200 carrying a
            # `session_id` that 404s on the client's very next call.
            if entry.last_seen < cutoff and not entry.busy
        ]
        for session_id in stale:
            del self._sessions[session_id]
        if stale:
            logger.info("evicted %d idle compose session(s)", len(stale))

    def _evict_overflow_locked(self) -> None:
        if self._max_sessions <= 0:
            return
        while len(self._sessions) >= self._max_sessions:
            # Only idle sessions are candidates, so a full registry of busy
            # conversations grows slightly rather than dropping a live one.
            idle = [item for item in self._sessions.items() if not item[1].busy]
            if not idle:
                logger.warning(
                    "compose registry is at capacity (%d) and every session is busy; "
                    "admitting one more rather than evicting a live conversation",
                    self._max_sessions,
                )
                return
            oldest = min(idle, key=lambda item: item[1].last_seen)[0]
            del self._sessions[oldest]
            logger.info("evicted least-recently-used compose session (registry full)")
