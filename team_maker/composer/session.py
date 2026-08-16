"""Multi-turn conversational wrapper around Composer (Story 1.3).

Wraps the existing, unmodified ``Composer.compose()`` (Story 1.2) — never
duplicates its validate-and-repair loop and never adds a second LLM call path.
Statefulness here is just "what did the user originally ask for, and what's
the current spec" — kept in-memory for a single running process (AD-11: no
persistence across CLI invocations).

Story 2.10 addition: supports a pre-authoring classification step to detect
non-team input and avoid fabricating a team specification.
"""
from __future__ import annotations

import json

from team_maker.composer.classifier import classify_input
from team_maker.composer.composer import Composer
from team_maker.ports.llm_provider import LLMProvider
from team_maker.schema.request import TeamCreationRequest


class ComposerSession:
    """Tracks a conversation's current spec and lets it be refined turn by turn.

    Story 2.10: The provider is stored to enable classification calls without
    duplicating the Composer's own provider reference.
    """

    def __init__(self, composer: Composer) -> None:
        self._composer = composer
        self._provider = composer._provider
        self._intent: str | None = None
        self.current: TeamCreationRequest | None = None

    def start(self, intent: str) -> TeamCreationRequest | None:
        """Perform the first turn — equivalent to a one-shot ``compose()`` call.

        Story 2.10: First performs classification. If the input is not a team
        description, returns None instead of fabricating a spec.
        """
        self._intent = intent
        # Classification step (Story 2.10): check if this describes a team
        if not classify_input(self._provider, intent):
            # Not a team description - leave current as None
            self.current = None
            return None
        # Proceed with normal composition
        self.current = self._composer.compose(intent)
        return self.current

    def refine(self, message: str) -> TeamCreationRequest | None:
        """Apply one follow-up change on top of the current spec.

        Raises:
            ComposerError: the repair budget was exhausted for this turn.
                ``self.current`` is left untouched — a failed turn never
                corrupts the last known-good spec.

        Story 2.10: If current is None (first turn was not a team), subsequent
        turns also return None to maintain the needs_clarification state.
        """
        if self.current is None:
            # Story 2.10: If we never had a spec (first turn was not a team),
            # keep returning None for subsequent turns
            return None
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
