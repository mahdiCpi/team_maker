"""The Runtime's single public entry point (Story 1.5, AD-5; Story 4.4 Task 2).

Loads an already-built Team Package and executes it. Never mutates the
package, never decides team membership/roles — Runtime executes only.

The default CrewAI engine is imported lazily, inside the function body, not
at module scope — so importing this module (and, transitively,
``team_maker.cli``) never requires CrewAI to be installed. Only calling
``run_team_package`` without an explicit ``engine`` does.

## Process-wide run lock (Story 4.4 Task 2)

The crewai event bus is a process-global singleton with a shared worker pool,
so two simultaneous run() calls in one process interleave into each other's
transcript. The corruption has three independent causes:
1. Handler fan-out on the global bus
2. emission_sequence being ContextVar-scoped and restarting at 1 per run,
   so sorting cannot separate two runs
3. TranscriptRecorder.__exit__'s crewai_event_bus.flush() waiting on *all*
   process-wide pending futures

A process-wide lock serializing all runs in one process is the only option
that fixes all three (Story 2.4 review). The API is already pinned single-worker
(Makefile:57-58, main.py:208-252), so a process-wide lock is a system-wide lock.

`api/runs.py`'s `RunRegistry` holds a second, independent lock over the same
invariant — that one is non-blocking, so a concurrent `POST /api/runs` fails
fast with `run_blocked` instead of waiting; this one blocks with no timeout
and guards every caller of `run_team_package`, including ones that never go
through that registry (e.g. Epic 5's planned non-API embedding). Both are
kept deliberately (Story 4.4 review) rather than merged into one.
"""
from __future__ import annotations

import threading
from collections.abc import Sequence
from pathlib import Path
from typing import Optional

from team_maker.domain.models import GeneratedTeam
from team_maker.keyconfig import KeyConfig
from team_maker.ports.execution_engine import ExecutionEngine
from team_maker.runtime.loader import load_team_package
from team_maker.runtime.preflight import check_credentials
from team_maker.runtime.results import RunResult
from team_maker.runtime.run_context import RunDocument, augment_team_for_run

_SUPPORTED_FRAMEWORK = "crewai"

# Process-wide lock to serialize runs (Story 4.4 Task 2)
# This prevents concurrent runs in one process from corrupting each other's
# transcripts via the crewai event bus (process-global singleton).
_run_lock = threading.Lock()


class UnsupportedFrameworkError(Exception):
    """The package's ``primary_framework`` is not executable by the v1 Runtime.

    Carries the offending value as ``framework`` so a caller can author its own
    sentence from the structured field instead of re-rendering ``str(exc)``.
    ``primary_framework`` is read verbatim from ``team_config.yaml`` with no
    validation (``loader.py``), so a caller that puts it in an HTTP response
    needs to sanitise it — which it can only do if it can reach the value.
    """

    def __init__(self, framework: str) -> None:
        self.framework = framework
        super().__init__(
            f"Only 'crewai' packages can be run in v1 (this package targets '{framework}')."
        )


def check_runnable(team: GeneratedTeam) -> None:
    """Raise ``UnsupportedFrameworkError`` if *team* targets a framework this
    Runtime cannot execute.

    Public and separated from `run_team_package` (Story 2.4 AC 7) so the API's
    synchronous pre-run gate can run the exact same check, on the exact same
    loaded team, before spawning a run's background thread — rather than
    re-encoding the ``"crewai"`` comparison a second time.
    """
    if team.primary_framework != _SUPPORTED_FRAMEWORK:
        raise UnsupportedFrameworkError(team.primary_framework)


def run_team_package(
    package_path: Path,
    goal: str,
    key_config: KeyConfig,
    engine: Optional[ExecutionEngine] = None,
    *,
    documents: Sequence[RunDocument] = (),
) -> RunResult:
    """Load the Team Package at *package_path* and run it toward *goal*.

    ``documents`` is keyword-only and defaults to empty, so every existing
    caller (the CLI, the pre-2.4 test suite) is unaffected (Story 2.4 AC 6).
    """
    # AC 2: Fix concurrent run transcript corruption (Story 4.4 Task 2)
    # The crewai event bus is a process-global singleton. Without a lock,
    # two simultaneous runs corrupt each other's transcripts. The lock
    # serializes all runs in one process, which is acceptable for v1 since
    # the API is already pinned single-worker.
    with _run_lock:
        team = load_team_package(package_path)
        check_runnable(team)

        # The goal and any documents are woven into the task descriptions of a
        # *new* team object before the engine ever sees it (Story 2.4 AC 5) — see
        # `run_context.py` for why, and for why this happens here rather than
        # inside an engine.
        team = augment_team_for_run(team, goal, documents=documents)

        # AD-9: resolve every agent's credential before any work begins. Raises
        # MissingCredentialsError naming every unusable provider. Doing it here —
        # rather than inside an engine — means every caller (CLI today, API in
        # Epic 4) inherits fail-fast, and no engine can re-resolve differently.
        credentials = check_credentials(team, key_config)

        if engine is None:
            from team_maker.adapters.runtime_crewai.crewai_execution_engine import (
                CrewAIExecutionEngine,
            )

            engine = CrewAIExecutionEngine()

        return engine.run(team, credentials, goal)
