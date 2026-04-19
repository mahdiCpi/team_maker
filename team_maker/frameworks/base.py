"""Abstract interface every framework adapter must implement."""
from __future__ import annotations

from abc import ABC, abstractmethod

from team_maker.domain.models import GeneratedTeam


class FrameworkAdapter(ABC):
    """Generates a framework-specific runner script for a generated team."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def render_runner(self, team: GeneratedTeam) -> str:
        """Return the full content of run_example.py for this framework."""
        ...

    @abstractmethod
    def extra_requirements(self) -> list[str]:
        """Additional pip packages beyond the base set."""
        ...
