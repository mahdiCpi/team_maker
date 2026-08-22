"""RuntimeEngine port — the seam every code-generation framework flows through.

Spine invariants AD-2/AD-6: core code (``pipeline/runner.py``) depends only on this
port; concrete engines live under ``team_maker/adapters/runtime_engines/`` and are
selected by data (the ``get_runtime_engine`` registry), never by branching on name.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from team_maker.domain.models import GeneratedTeam


class RuntimeEngine(ABC):
    """Generates a framework-specific runner script for a generated team."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def render_runner(self, team: GeneratedTeam, notifications=None) -> str:
        """Return the full content of run_example.py for this framework."""
        ...

    @abstractmethod
    def extra_requirements(self) -> list[str]:
        """Additional pip packages beyond the base set."""
        ...

    def extra_modules(self) -> dict[str, str]:
        """Extra ``{relative_path: content}`` modules this runner imports.

        Concrete (not abstract) and empty by default: a framework whose runner
        is a single self-contained file needs no opt-in. `PipelineRunner`
        merges the result into the manifest, so these follow the same
        write/validate path as every other artifact — nothing here touches
        disk itself.

        Exists because a generated package runs *without* ``team_maker``
        installed, so a runner that needs non-trivial shared logic (crewai's
        transcript recorder, Story 4.4) cannot import it and must ship it. A
        separate module rather than more inline template text: it keeps
        ``run_example.py`` readable and gives the logic an import surface a
        test can execute.
        """
        return {}
