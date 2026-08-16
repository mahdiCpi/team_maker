"""Tests for ComposerSession classification integration (Story 2.10).

Uses `FakeLLMProvider` (`tests/support/fake_llm.py`), the same offline stand-in
`Composer`'s own tests use, seeded with real `TeamCreationRequest` payloads and
`{"is_team": ...}` classification responses in call order — not an invented
provider shape. `ComposerSession.start()` always issues a classification call
before an authoring call, so every scripted session below queues one
`{"is_team": ...}` response per turn that needs it.
"""
from __future__ import annotations

from team_maker.composer.composer import Composer
from team_maker.composer.session import ComposerSession
from tests.support.fake_llm import FakeLLMProvider
from tests.unit.test_composer import _valid_payload


class TestComposerSessionClassification:
    """Tests for ComposerSession with classification (Story 2.10)."""

    def test_start_with_team_input(self, tmp_path) -> None:
        """Test that start() with team input returns a TeamCreationRequest."""
        payload = _valid_payload(tmp_path)
        fake = FakeLLMProvider([{"is_team": True}, payload])
        session = ComposerSession(Composer(fake))

        result = session.start("build a team")

        assert result is not None
        assert session.current is result
        assert len(fake.calls) == 2

    def test_start_with_non_team_input(self) -> None:
        """Test that start() with non-team input returns None without composing."""
        fake = FakeLLMProvider([{"is_team": False}])
        session = ComposerSession(Composer(fake))

        result = session.start("Hello")

        assert result is None
        assert session.current is None
        assert len(fake.calls) == 1

    def test_refine_with_existing_spec_does_not_reclassify(self, tmp_path) -> None:
        """Once a spec exists, refine() composes directly — classification is a
        first-turn (or still-stuck) concern only, per Open Question 3."""
        first = _valid_payload(tmp_path)
        second = _valid_payload(
            tmp_path,
            desired_roles=[{"name": "writer", "description": "Writes documentation."}],
        )
        fake = FakeLLMProvider([{"is_team": True}, first, second])
        session = ComposerSession(Composer(fake))

        session.start("build a team")
        result = session.refine("add more roles")

        assert result is not None
        # classify, start-compose, refine-compose — no second classification call.
        assert len(fake.calls) == 3

    def test_refine_without_existing_spec_reclassifies_and_can_recover(self, tmp_path) -> None:
        """A session stuck in needs_clarification after turn 1 must recover once
        the user actually describes a team — it must not be stuck for the rest
        of the conversation."""
        payload = _valid_payload(tmp_path)
        fake = FakeLLMProvider([{"is_team": False}, {"is_team": True}, payload])
        session = ComposerSession(Composer(fake))

        session.start("Hello")
        assert session.current is None

        result = session.refine("build me a 3-person marketing team")

        assert result is not None
        assert session.current is result

    def test_consecutive_non_team_turns_keep_current_none(self) -> None:
        """Test that consecutive non-team turns keep current as None."""
        fake = FakeLLMProvider([{"is_team": False}, {"is_team": False}, {"is_team": False}])
        session = ComposerSession(Composer(fake))

        session.start("Hello")
        assert session.current is None
        session.refine("hi")
        assert session.current is None
        session.refine("what?")
        assert session.current is None
        assert len(fake.calls) == 3

    def test_classification_called_before_compose(self, tmp_path) -> None:
        """Test that classification is called before compose for start()."""
        payload = _valid_payload(tmp_path)
        fake = FakeLLMProvider([{"is_team": True}, payload])
        session = ComposerSession(Composer(fake))

        session.start("build a team")

        assert len(fake.calls) == 2
        assert fake.calls[0]["user"] == "build a team"
        assert "is_team" in fake.calls[0]["response_model"].model_fields

    def test_classification_not_called_again_after_a_successful_start(self, tmp_path) -> None:
        """Once a spec exists, further turns skip classification entirely."""
        payload = _valid_payload(tmp_path)
        fake = FakeLLMProvider([{"is_team": True}, payload, payload])
        session = ComposerSession(Composer(fake))

        session.start("build a team")
        session.refine("add a reviewer")

        assert len(fake.calls) == 3  # classify, start-compose, refine-compose
