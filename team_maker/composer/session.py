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

    Story 2.10: also reuses the Composer's injected provider for a pre-authoring
    classification call, via ``Composer.provider`` rather than reaching into a
    private attribute.
    """

    def __init__(self, composer: Composer) -> None:
        self._composer = composer
        self._provider: LLMProvider = composer.provider
        self._intent: str | None = None
        # Distinguishes "start() was never called" (a programmer error refine()
        # must still raise on) from "start() was called but classified
        # non-team" (current is None, but that is a valid, already-started
        # state) — both looked like `current is None` before Story 2.10, which
        # is what caused the two to be conflated.
        self._started = False
        self.current: TeamCreationRequest | None = None

    def start(self, intent: str) -> TeamCreationRequest | None:
        """Perform the first turn — equivalent to a one-shot ``compose()`` call.

        Story 2.10: First performs classification. If the input is not a team
        description, returns None instead of fabricating a spec.
        """
        self._intent = intent
        self._started = True
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
            RuntimeError: ``start()`` was never called on this session.

        Story 2.10: If ``current`` is None because an earlier turn was
        classified non-team, this re-runs classification on ``message`` rather
        than unconditionally staying in ``needs_clarification`` — a user who
        opens with "hi" and then actually describes a team must still get a
        spec, not a session stuck until the turn cap runs out.
        """
        if not self._started:
            raise RuntimeError("ComposerSession.refine() called before start()")
        if self.current is None:
            if not classify_input(self._provider, message):
                return None
            self._intent = message
            self.current = self._composer.compose(message)
            return self.current
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

    def seed(self, spec: TeamCreationRequest, intent: str | None = None) -> None:
        """Initialize a session with a pre-built spec, enabling conversational edits.

        This method allows a session to start from an existing TeamCreationRequest
        (e.g., a starter team) without invoking the LLM. It sets the session's
        current spec, marks it as started, and sets a synthetic intent so that
        subsequent refine() calls can build proper refinement prompts.

        This is essential for Story 3.2's "Adapt with Composer" flow, where a
        starter team's spec is loaded and the user can then tweak it through
        the normal chat interface. Without setting _started=True and _intent,
        refine() would raise RuntimeError on the first chat message.

        Credential-free by construction, and deliberately so: this method never
        touches `self._composer`/`self._provider` (unlike `start()`), so seeding
        a session needs no usable authoring credential — that gate is an `api/`
        layer concern, checked lazily by `api/routers/compose.py::send_message`
        only once `refine()` is actually about to be called. Nothing here needs
        to know that; the boundary is enforced by simply never calling into the
        provider until `refine()` does.

        Args:
            spec: The TeamCreationRequest to seed the session with.
            intent: Optional intent string. If not provided, a synthetic intent
                    will be generated describing the loaded spec.
        """
        self.current = spec
        self._started = True
        if intent is None:
            self._intent = f"Start from the existing '{spec.team_name}' team specification."
        else:
            self._intent = intent
