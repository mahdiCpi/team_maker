"""The Runtime's single public entry point (Story 1.5, AD-5).

Loads an already-built Team Package and executes it. Never mutates the
package, never decides team membership/roles — Runtime executes only.

The default CrewAI engine is imported lazily, inside the function body, not
at module scope — so importing this module (and, transitively,
``team_maker.cli``) never requires CrewAI to be installed. Only calling
``run_team_package`` without an explicit ``engine`` does.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from team_maker.keyconfig import KeyConfig
from team_maker.ports.execution_engine import ExecutionEngine
from team_maker.runtime.loader import load_team_package
from team_maker.runtime.results import RunResult

_SUPPORTED_FRAMEWORK = "crewai"


class UnsupportedFrameworkError(Exception):
    """The package's ``primary_framework`` is not executable by the v1 Runtime."""


def run_team_package(
    package_path: Path,
    goal: str,
    key_config: KeyConfig,
    engine: Optional[ExecutionEngine] = None,
) -> RunResult:
    """Load the Team Package at *package_path* and run it toward *goal*."""
    team = load_team_package(package_path)
    if team.primary_framework != _SUPPORTED_FRAMEWORK:
        raise UnsupportedFrameworkError(
            f"Only 'crewai' packages can be run in v1 (this package targets "
            f"'{team.primary_framework}')."
        )

    if engine is None:
        from team_maker.adapters.runtime_crewai.crewai_execution_engine import (
            CrewAIExecutionEngine,
        )

        engine = CrewAIExecutionEngine()

    return engine.run(team, key_config, goal)
