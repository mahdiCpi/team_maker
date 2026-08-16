"""Tests for the input classifier (Story 2.10)."""
from __future__ import annotations

import pytest

from team_maker.composer.classifier import (
    InputClassifier,
    ClassificationResult,
    classify_input,
    _CLASSIFICATION_PROMPT,
)


class MockProvider:
    """Mock LLMProvider for testing."""

    def __init__(self, responses: dict[str, str]) -> None:
        self.responses = responses
        self.call_count = 0

    def complete(self, system: str, user: str) -> str:
        self.call_count += 1
        # Use user input as key, or return a default
        return self.responses.get(user, "team")


class TestInputClassifier:
    """Tests for InputClassifier."""

    def test_classify_team_input(self) -> None:
        """Test that clear team descriptions are classified as team."""
        provider = MockProvider({"I want a team that writes blog posts": "team"})
        classifier = InputClassifier(provider)
        result = classifier.classify("I want a team that writes blog posts")
        assert result.is_team is True

    def test_classify_non_team_input(self) -> None:
        """Test that non-team input is classified as not a team."""
        provider = MockProvider({"Hello": "not_team"})
        classifier = InputClassifier(provider)
        result = classifier.classify("Hello")
        assert result.is_team is False

    def test_classify_greeting(self) -> None:
        """Test that greetings are classified as not a team."""
        provider = MockProvider({"hi": "not_team", "hey": "not_team", "what is this app": "not_team"})
        classifier = InputClassifier(provider)
        
        assert classifier.classify("hi").is_team is False
        assert classifier.classify("hey").is_team is False
        assert classifier.classify("what is this app").is_team is False

    def test_classify_permissive_default(self) -> None:
        """Test that unexpected responses default to team (permissive)."""
        provider = MockProvider({"some input": "maybe"})
        classifier = InputClassifier(provider)
        result = classifier.classify("some input")
        # Permissive: when in doubt, it's a team
        assert result.is_team is True

    def test_classify_case_insensitive(self) -> None:
        """Test that classification is case-insensitive."""
        provider = MockProvider({"test": "TEAM"})
        classifier = InputClassifier(provider)
        result = classifier.classify("test")
        assert result.is_team is True

    def test_classify_whitespace_handling(self) -> None:
        """Test that whitespace is stripped from responses."""
        provider = MockProvider({"test": "  team  "})
        classifier = InputClassifier(provider)
        result = classifier.classify("test")
        assert result.is_team is True


class TestClassifyInput:
    """Tests for the classify_input convenience function."""

    def test_classify_input_team(self) -> None:
        """Test classify_input with team input."""
        provider = MockProvider({"build a team": "team"})
        assert classify_input(provider, "build a team") is True

    def test_classify_input_not_team(self) -> None:
        """Test classify_input with non-team input."""
        provider = MockProvider({"hello": "not_team"})
        assert classify_input(provider, "hello") is False


class TestClassificationPrompt:
    """Tests for the classification prompt itself."""

    def test_prompt_contains_guidelines(self) -> None:
        """Test that the prompt contains the key guidelines."""
        assert "team" in _CLASSIFICATION_PROMPT.lower()
        assert "not_team" in _CLASSIFICATION_PROMPT.lower()
        assert "permissive" in _CLASSIFICATION_PROMPT.lower() or "doubt" in _CLASSIFICATION_PROMPT.lower()

    def test_prompt_asks_for_single_word(self) -> None:
        """Test that the prompt asks for a single word response."""
        assert "one word" in _CLASSIFICATION_PROMPT.lower() or "only" in _CLASSIFICATION_PROMPT.lower()
