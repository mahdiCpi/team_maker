"""Multi-turn conversational wrapper around Composer (Story 1.3).

Wraps the existing, unmodified ``Composer.compose()`` (Story 1.2) — never
duplicates its validate-and-repair loop and never adds a second LLM call path.
Statefulness here is just "what did the user originally ask for, and what's
the current spec" — kept in-memory for a single running process (AD-11: no
persistence across CLI invocations).
"""
from __future__ import annotations

import json

from team_maker.composer.composer import Composer
from team_maker.schema.request import TeamCreationRequest


class ComposerSession:
    """Tracks a conversation's current spec and lets it be refined turn by turn."""

    def __init__(self, composer: Composer) -> None:
        self._composer = composer
        self._intent: str | None = None
        self.current: TeamCreationRequest | None = None

    def start(self, intent: str) -> TeamCreationRequest:
        """Perform the first turn — equivalent to a one-shot ``compose()`` call."""
        self._intent = intent
        self.current = self._composer.compose(intent)
        return self.current

    def refine(self, message: str) -> TeamCreationRequest:
        """Apply one follow-up change on top of the current spec.

        Raises:
            ComposerError: the repair budget was exhausted for this turn.
                ``self.current`` is left untouched — a failed turn never
                corrupts the last known-good spec.
        """
        if self.current is None:
            raise RuntimeError("ComposerSession.refine() called before start()")
        combined_intent = self._build_refinement_intent(message)
        updated = self._composer.compose(combined_intent)
        self.current = updated
        return updated

    def _build_refinement_intent(self, message: str) -> str:
        current_spec = json.dumps(self.current.model_dump(mode="json", exclude_none=True))
        return (
            f"Original request: {self._intent}\n\n"
            "Current team specification (JSON):\n"
            f"{current_spec}\n\n"
            f"Requested change: {message}\n\n"
            "Apply ONLY this change and keep everything else from the current "
            "specification the same. Re-emit the complete, updated team "
            "specification."
        )
