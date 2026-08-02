"""Port: executes a loaded team against a goal (Story 1.5, AD-6).

Distinct from ``ports/runtime_engine.py`` (Story 0.3's codegen-only port,
consumed by the Factory to render ``run_example.py``'s text) — this port is
about actually executing a team in-process. The two must never collide or
merge; the Factory's port and adapters stay untouched (AD-1).
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from team_maker.domain.models import GeneratedTeam, ResolvedCredential
from team_maker.runtime.results import RunResult


class ExecutionEngine(ABC):
    """Executes a ``GeneratedTeam`` against a goal and returns a ``RunResult``."""

    @abstractmethod
    def run(
        self,
        team: GeneratedTeam,
        credentials: dict[str, ResolvedCredential],
        goal: str,
    ) -> RunResult:
        """Run *team* toward *goal* using the pre-resolved per-agent credentials.

        Engines receive a ``{role: ResolvedCredential}`` map, never the
        ``KeyConfig`` (Story 1.6, AD-7). Resolution happens once, before the run
        is admitted, so an engine cannot re-resolve differently, cannot reach
        credentials for agents it is not running, and has no key material to
        fall back on if a lookup fails. Every role in *team* is guaranteed
        present in *credentials*.

        The returned ``RunResult`` carries an ordered ``transcript`` alongside
        the final and per-task outputs (Story 1.7, FR-27). Capture is
        unconditional — whether to surface it is the caller's decision, so an
        engine must not take a flag for it. Per AD-13 the transcript is the
        accumulated sequence of the units a v2 streaming engine would emit one
        at a time, which is why this signature does not change to add streaming.
        """
