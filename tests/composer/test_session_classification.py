"""Tests for ComposerSession classification integration (Story 2.10)."""
from __future__ import annotations

import pytest

from team_maker.composer.composer import Composer, ComposerError
from team_maker.composer.session import ComposerSession
from team_maker.schema.request import TeamCreationRequest


class MockProvider:
    """Mock LLMProvider that returns controlled responses."""

    def __init__(
        self,
        *,
        classification_responses: dict[str, str] | None = None,
        compose_responses: list[TeamCreationRequest] | None = None,
        should_fail_compose: bool = False,
    ) -> None:
        self.classification_responses = classification_responses or {}
        self.compose_responses = compose_responses
        self.compose_index = 0
        self.should_fail_compose = should_fail_compose
        self.classification_calls: list[str] = []
        self.compose_calls: list[str] = []

    def complete(self, system: str, user: str) -> str:
        # This is for classification
        self.classification_calls.append(user)
        return self.classification_responses.get(user, "team")

    def complete_structured(self, system: str, user: str, response_model: type) -> TeamCreationRequest:
        # This is for compose
        self.compose_calls.append(user)
        if self.should_fail_compose:
            raise ValueError("Validation error")
        if self.compose_responses and self.compose_index < len(self.compose_responses):
            result = self.compose_responses[self.compose_index]
            self.compose_index += 1
            return result
        # Return a default valid response
        return TeamCreationRequest(
            team_name="test_team",
            purpose="test purpose with enough characters",
            output_path="./output/test_team",
            desired_roles=[{"name": "test_role", "description": "test description with enough"}],
        )


class TestComposerSessionClassification:
    """Tests for ComposerSession with classification (Story 2.10)."""

    def test_start_with_team_input(self) -> None:
        """Test that start() with team input returns a TeamCreationRequest."""
        provider = MockProvider(
            classification_responses={"build a team": "team"},
            compose_responses=[
                TeamCreationRequest(
                    team_name="test_team",
                    purpose="test purpose with enough characters",
                    output_path="./output/test_team",
                    desired_roles=[{"name": "role1", "description": "description with enough chars"}],
                )
            ],
        )
        composer = Composer(provider)
        session = ComposerSession(composer)
        
        result = session.start("build a team")
        
        assert result is not None
        assert isinstance(result, TeamCreationRequest)
        assert session.current is not None

    def test_start_with_non_team_input(self) -> None:
        """Test that start() with non-team input returns None."""
        provider = MockProvider(
            classification_responses={"Hello": "not_team"},
        )
        composer = Composer(provider)
        session = ComposerSession(composer)
        
        result = session.start("Hello")
        
        assert result is None
        assert session.current is None

    def test_refine_with_existing_spec(self) -> None:
        """Test that refine() with existing spec works normally."""
        provider = MockProvider(
            classification_responses={},
            compose_responses=[
                TeamCreationRequest(
                    team_name="test_team",
                    purpose="test purpose with enough characters",
                    output_path="./output/test_team",
                    desired_roles=[{"name": "role1", "description": "description with enough chars"}],
                ),
                TeamCreationRequest(
                    team_name="test_team",
                    purpose="updated purpose with enough chars",
                    output_path="./output/test_team",
                    desired_roles=[{"name": "role1", "description": "description with enough chars"}],
                ),
            ],
        )
        composer = Composer(provider)
        session = ComposerSession(composer)
        
        # Start with a team
        session.start("build a team")
        assert session.current is not None
        
        # Refine
        result = session.refine("add more roles")
        
        assert result is not None
        assert isinstance(result, TeamCreationRequest)

    def test_refine_without_existing_spec(self) -> None:
        """Test that refine() without existing spec (from non-team start) returns None."""
        provider = MockProvider(
            classification_responses={"Hello": "not_team"},
        )
        composer = Composer(provider)
        session = ComposerSession(composer)
        
        # Start with non-team
        session.start("Hello")
        assert session.current is None
        
        # Refine without spec
        result = session.refine("another message")
        
        assert result is None
        assert session.current is None

    def test_consecutive_non_team_turns(self) -> None:
        """Test that consecutive non-team turns keep current as None."""
        provider = MockProvider(
            classification_responses={
                "Hello": "not_team",
                "hi": "not_team",
                "what?": "not_team",
            },
        )
        composer = Composer(provider)
        session = ComposerSession(composer)
        
        # First turn: non-team
        session.start("Hello")
        assert session.current is None
        
        # Second turn: still non-team
        session.refine("hi")
        assert session.current is None
        
        # Third turn: still non-team
        session.refine("what?")
        assert session.current is None

    def test_classification_called_before_compose(self) -> None:
        """Test that classification is called before compose for start()."""
        provider = MockProvider(
            classification_responses={"build a team": "team"},
            compose_responses=[
                TeamCreationRequest(
                    team_name="test_team",
                    purpose="test purpose with enough characters",
                    output_path="./output/test_team",
                    desired_roles=[{"name": "role1", "description": "description with enough chars"}],
                )
            ],
        )
        composer = Composer(provider)
        session = ComposerSession(composer)
        
        session.start("build a team")
        
        # Classification should have been called
        assert len(provider.classification_calls) > 0
        assert "build a team" in provider.classification_calls
        # Compose should have been called
        assert len(provider.compose_calls) > 0

    def test_classification_not_called_when_not_team(self) -> None:
        """Test that compose is NOT called when classification returns not_team."""
        provider = MockProvider(
            classification_responses={"Hello": "not_team"},
        )
        composer = Composer(provider)
        session = ComposerSession(composer)
        
        session.start("Hello")
        
        # Classification should have been called
        assert len(provider.classification_calls) > 0
        # Compose should NOT have been called
        assert len(provider.compose_calls) == 0
