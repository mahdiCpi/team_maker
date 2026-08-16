"""Classification step for detecting team vs non-team input (Story 2.10).

This module provides a lightweight classification call that determines whether
a user's input describes a team to build, before invoking the full Composer.

Spine invariants:
  - AD-2/AD-8: depends only on the ``LLMProvider`` port, never a concrete SDK,
    never branches on provider name.
  - The classification is permissive: when in doubt, classify as team-shaped to
    minimize false negatives (rejecting valid team descriptions).
"""
from __future__ import annotations

from team_maker.ports.llm_provider import LLMProvider


# Classification prompt: permissive by design — when in doubt, say "yes, it's a team".
# This minimizes false negatives (rejecting valid team descriptions).
_CLASSIFICATION_PROMPT = """\
You are a classifier for a team-building assistant. Your job is to determine
whether the user's message describes a team they want to build.

Guidelines:
- If the message describes work to be done, a project, a goal, roles to fill,
  or any kind of collaborative effort, classify it as a team description.
- If the message is a greeting, a question about the app, random text,
  or clearly not about building a team, classify it as NOT a team description.
- WHEN IN DOUBT, classify as a team description (be permissive).

Respond with ONLY one of these two words:
- "team" if the message describes a team to build
- "not_team" if the message does NOT describe a team to build

Do not add any explanation, commentary, or additional text. Just one word."""


class ClassificationResult:
    """Result of classifying user input."""

    def __init__(self, is_team: bool, confidence: str | None = None) -> None:
        self.is_team = is_team
        self.confidence = confidence


class InputClassifier:
    """Classifies whether user input describes a team to build."""

    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    def classify(self, intent: str) -> ClassificationResult:
        """Classify whether the intent describes a team.

        Returns:
            ClassificationResult with is_team=True if the input describes a team.
        """
        response = self._provider.complete(
            system=_CLASSIFICATION_PROMPT,
            user=intent,
        )
        # Normalize the response to handle case and whitespace
        normalized = response.strip().lower()
        if normalized == "team":
            return ClassificationResult(is_team=True)
        elif normalized == "not_team":
            return ClassificationResult(is_team=False)
        else:
            # Permissive default: when in doubt, it's a team
            # This handles any unexpected response from the LLM
            return ClassificationResult(is_team=True)


def classify_input(provider: LLMProvider, intent: str) -> bool:
    """Convenience function to classify input as team or not.

    Args:
        provider: The LLM provider to use for classification.
        intent: The user's input message.

    Returns:
        True if the input describes a team, False otherwise.
    """
    classifier = InputClassifier(provider)
    return classifier.classify(intent).is_team
