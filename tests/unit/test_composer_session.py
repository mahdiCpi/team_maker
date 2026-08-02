"""ComposerSession tests (Story 1.3) — fully offline, reusing Story 1.2's FakeLLMProvider."""
from __future__ import annotations

import pytest

from team_maker.composer.composer import Composer, ComposerError
from team_maker.composer.session import ComposerSession
from team_maker.schema.request import TeamCreationRequest
from tests.unit.test_composer import FakeLLMProvider, _valid_payload


def test_start_then_refine_produces_a_second_valid_spec(tmp_path):
    first = _valid_payload(tmp_path)
    second = _valid_payload(
        tmp_path,
        desired_roles=[
            {
                "name": "writer",
                "description": "Writes documentation.",
                "llm": {"provider": "google", "model": "gemini-1.5-pro"},
            }
        ],
    )
    fake = FakeLLMProvider([first, second])
    session = ComposerSession(Composer(fake))

    initial = session.start("I need a team to write docs.")
    refined = session.refine("put the writer on Gemini")

    assert isinstance(initial, TeamCreationRequest)
    assert isinstance(refined, TeamCreationRequest)
    assert refined.desired_roles[0].llm.provider == "google"
    assert session.current is refined
    assert len(fake.calls) == 2


def test_refine_message_carries_the_current_spec_state(tmp_path):
    """AC2: refinement must reference the current spec so unrelated facts survive."""
    first = _valid_payload(tmp_path, team_name="Docs Team")
    second = _valid_payload(tmp_path, team_name="Docs Team")
    fake = FakeLLMProvider([first, second])
    session = ComposerSession(Composer(fake))

    session.start("I need a team to write docs.")
    session.refine("add a reviewer role")

    second_call_user_message = fake.calls[1]["user"]
    assert "Docs Team" in second_call_user_message
    assert "add a reviewer role" in second_call_user_message


def test_multiple_successive_refinements_each_build_on_the_last(tmp_path):
    first = _valid_payload(tmp_path)
    second = _valid_payload(
        tmp_path,
        desired_roles=[
            {
                "name": "writer",
                "description": "Writes documentation.",
                "llm": {"provider": "google", "model": "gemini-1.5-pro"},
            }
        ],
    )
    third = _valid_payload(
        tmp_path,
        desired_roles=[
            {
                "name": "writer",
                "description": "Writes documentation.",
                "llm": {"provider": "google", "model": "gemini-1.5-pro"},
            },
            {"name": "reviewer", "description": "Reviews drafts."},
        ],
    )
    fake = FakeLLMProvider([first, second, third])
    session = ComposerSession(Composer(fake))

    session.start("I need a team to write docs.")
    after_first_refine = session.refine("put the writer on Gemini")
    after_second_refine = session.refine("add a reviewer role")

    assert len(after_first_refine.desired_roles) == 1
    assert len(after_second_refine.desired_roles) == 2
    assert after_second_refine.desired_roles[0].llm.provider == "google"
    assert session.current is after_second_refine
    assert len(fake.calls) == 3
    # The third call's prompt must carry forward the second turn's state
    # (Gemini routing), proving refinements compound rather than resetting.
    assert "gemini-1.5-pro" in fake.calls[2]["user"]


def test_refine_before_start_raises(tmp_path):
    fake = FakeLLMProvider([])
    session = ComposerSession(Composer(fake))

    with pytest.raises(RuntimeError):
        session.refine("add a reviewer role")


def test_refine_failure_leaves_current_spec_intact(tmp_path):
    """AC6: an exhausted repair budget mid-conversation must not corrupt session.current."""
    first = _valid_payload(tmp_path)
    duplicate_roles_payload = _valid_payload(
        tmp_path,
        desired_roles=[
            {"name": "writer", "description": "Writes content."},
            {"name": "writer", "description": "Writes more content."},
        ],
    )
    fake = FakeLLMProvider([first] + [duplicate_roles_payload] * 4)
    session = ComposerSession(Composer(fake, max_repair_attempts=3))

    initial = session.start("I need a team to write docs.")

    with pytest.raises(ComposerError):
        session.refine("add a reviewer role")

    assert session.current is initial
