"""Tests for the input classifier (Story 2.10).

Uses `FakeLLMProvider` (`tests/support/fake_llm.py`), the same offline stand-in
for the real `LLMProvider` port that `Composer`'s own tests use — not an ad hoc
mock shaped to match the classifier's implementation. That is deliberate: an
earlier version of this module called a `complete()` method that does not
exist anywhere on the real port or its adapters, and a mock that invented the
same nonexistent method let the bug ship undetected.
"""
from __future__ import annotations

from team_maker.composer.classifier import (
    ClassificationResult,
    InputClassifier,
    classify_input,
)
from tests.support.fake_llm import FakeLLMProvider


class TestInputClassifier:
    """Tests for InputClassifier."""

    def test_classify_team_input(self) -> None:
        """Test that clear team descriptions are classified as team."""
        provider = FakeLLMProvider([{"is_team": True}])
        classifier = InputClassifier(provider)
        result = classifier.classify("I want a team that writes blog posts")
        assert result.is_team is True

    def test_classify_non_team_input(self) -> None:
        """Test that non-team input is classified as not a team."""
        provider = FakeLLMProvider([{"is_team": False}])
        classifier = InputClassifier(provider)
        result = classifier.classify("Hello")
        assert result.is_team is False

    def test_classify_greeting(self) -> None:
        """Test that greetings are classified as not a team."""
        provider = FakeLLMProvider(
            [{"is_team": False}, {"is_team": False}, {"is_team": False}]
        )
        classifier = InputClassifier(provider)

        assert classifier.classify("hi").is_team is False
        assert classifier.classify("hey").is_team is False
        assert classifier.classify("what is this app").is_team is False

    def test_classify_permissive_default_on_unparseable_response(self) -> None:
        """An unparseable structured response defaults to permissive (is_team=True)."""
        provider = FakeLLMProvider([{}])  # missing the required `is_team` field
        classifier = InputClassifier(provider)
        result = classifier.classify("some input")
        assert result.is_team is True

    def test_classify_uses_the_real_llm_provider_port(self) -> None:
        """Classification must go through `complete_structured`, the only method
        `LLMProvider` actually declares — not an invented `complete()` string
        API. A regression here breaks every real compose call, not just this
        classifier."""
        provider = FakeLLMProvider([{"is_team": True}])
        InputClassifier(provider).classify("build a team")

        assert len(provider.calls) == 1
        assert "is_team" in provider.calls[0]["response_model"].model_fields


class TestClassifyInput:
    """Tests for the classify_input convenience function."""

    def test_classify_input_team(self) -> None:
        """Test classify_input with team input."""
        provider = FakeLLMProvider([{"is_team": True}])
        assert classify_input(provider, "build a team") is True

    def test_classify_input_not_team(self) -> None:
        """Test classify_input with non-team input."""
        provider = FakeLLMProvider([{"is_team": False}])
        assert classify_input(provider, "hello") is False


def test_classification_result_holds_is_team() -> None:
    assert ClassificationResult(is_team=True).is_team is True
    assert ClassificationResult(is_team=False).is_team is False
