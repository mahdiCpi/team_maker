"""Abstract base class that all team templates must implement."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from team_maker.domain.models import GeneratedTeam
from team_maker.schema.request import TeamCreationRequest


class BaseTeamTemplate(ABC):
    """Contract that every template must satisfy."""

    template_id: str = ""
    description: str = ""

    @abstractmethod
    def generate(self, request: TeamCreationRequest) -> GeneratedTeam:
        """Transform a validated request into a fully-resolved GeneratedTeam."""
        ...

    @abstractmethod
    def default_role_names(self) -> List[str]:
        """Canonical role names this template covers when the user omits them."""
        ...

    @abstractmethod
    def default_task_names(self) -> List[str]:
        """Canonical task names this template emits."""
        ...
