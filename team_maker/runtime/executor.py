"""The Runtime's single public entry point (Story 1.5, AD-5).

Loads an already-built Team Package and executes it. Never mutates the
package, never decides team membership/roles — Runtime executes only.

The default CrewAI engine is imported lazily, inside the function body, not
at module scope — so importing this module (and, transitively,
``team_maker.cli``) never requires CrewAI to be installed. Only calling
``run_team_package`` without an explicit ``engine`` does.
"""
from __future__ import annotations

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


class UnsupportedFrameworkError(Exception):
    """The package's ``primary_framework`` is not executable by the v1 Runtime."""


def check_runnable(team: GeneratedTeam) -> None:
    """Raise ``UnsupportedFrameworkError`` if *team* targets a framework this
    Runtime cannot execute.

    Public and separated from `run_team_package` (Story 2.4 AC 7) so the API's
    synchronous pre-run gate can run the exact same check, on the exact same
    loaded team, before spawning a run's background thread — rather than
    re-encoding the ``"crewai"`` comparison a second time.
    """
    if team.primary_framework != _SUPPORTED_FRAMEWORK:
        raise UnsupportedFrameworkError(
            f"Only 'crewai' packages can be run in v1 (this package targets "
            f"'{team.primary_framework}')."
        )


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
