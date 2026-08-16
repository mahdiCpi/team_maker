"""A scripted, offline stand-in for the `ExecutionEngine` port (Story 2.4).

THIS IS A STUB. No crewai, no network, no key. A test that passes against it
says nothing about whether a real run works — that is `tests/conformance/`'s
job (`importorskip("crewai")`) and a manual live check.
"""
from __future__ import annotations

import threading
from typing import Optional

from team_maker.domain.models import GeneratedTeam, ResolvedCredential
from team_maker.ports.execution_engine import ExecutionEngine
from team_maker.runtime.results import RunResult


class FakeExecutionEngine(ExecutionEngine):
    """Returns a scripted `RunResult`, or raises a scripted exception.

    Records every call it receives, so a test can assert on what a run
    surface actually handed the engine (team, credentials, goal) without any
    real crewai object ever being built.
    """

    def __init__(self, result: Optional[RunResult] = None, *, error: Optional[Exception] = None) -> None:
        self._result = result
        self._error = error
        self.calls: list[tuple[GeneratedTeam, dict[str, ResolvedCredential], str]] = []
        self._guard = threading.Lock()

    def run(
        self,
        team: GeneratedTeam,
        credentials: dict[str, ResolvedCredential],
        goal: str,
    ) -> RunResult:
        with self._guard:
            self.calls.append((team, credentials, goal))
        if self._error is not None:
            raise self._error
        return self._result if self._result is not None else RunResult(final_output="fake result", task_results=[])


class BlockingExecutionEngine(ExecutionEngine):
    """A fake that blocks inside `run` until released.

    Exists for one job: proving AC 3's concurrency lock end to end over HTTP —
    that a second `POST /api/runs` is refused while a first run genuinely has
    not finished yet, not merely "before FastAPI got around to it".
    """

    def __init__(self, result: Optional[RunResult] = None) -> None:
        self._result = result
        self.entered = threading.Event()
        self.release = threading.Event()

    def run(
        self,
        team: GeneratedTeam,
        credentials: dict[str, ResolvedCredential],
        goal: str,
    ) -> RunResult:
        self.entered.set()
        # Bounded so a broken test fails instead of hanging the whole suite.
        assert self.release.wait(timeout=30), "test never released the blocked run"
        return self._result if self._result is not None else RunResult(final_output="fake result", task_results=[])
