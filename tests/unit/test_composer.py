"""Composer tests (Story 1.2) — fully offline against a FakeLLMProvider, no network."""
from __future__ import annotations

from typing import Any

import pytest
from pydantic import SecretStr

from team_maker.composer.composer import Composer, ComposerError
from team_maker.keyconfig import KeyConfig
from team_maker.schema.request import TeamCreationRequest

# Promoted to tests/support/ in Story 2.0 when tests/api/ became a third
# consumer. Imported here because this module's own tests use it — the
# re-export shim that briefly lived here had no consumers, since both former
# importers were re-pointed at tests.support in the same change.
from tests.support.fake_llm import FakeLLMProvider


def _valid_payload(tmp_path, **overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "team_name": "Docs Team",
        "purpose": "Write and maintain product documentation.",
        "output_path": str(tmp_path / "docs_team"),
        "desired_roles": [{"name": "writer", "description": "Writes documentation."}],
    }
    payload.update(overrides)
    return payload


def test_compose_happy_path_returns_valid_request(tmp_path):
    fake = FakeLLMProvider([_valid_payload(tmp_path)])
    composer = Composer(fake)

    request = composer.compose("I need a team to write docs.")

    assert isinstance(request, TeamCreationRequest)
    assert request.team_name == "Docs Team"
    assert len(fake.calls) == 1
    assert fake.calls[0]["response_model"] is TeamCreationRequest


def test_compose_reflects_named_roles_models_and_tasks(tmp_path):
    payload = _valid_payload(
        tmp_path,
        desired_roles=[
            {
                "name": "architect",
                "description": "Designs the system.",
                "llm": {"provider": "anthropic", "model": "claude-sonnet-4-6"},
            },
            {
                "name": "writer",
                "description": "Writes content.",
                "llm": {"provider": "google", "model": "gemini-1.5-pro"},
            },
        ],
        desired_tasks=[
            {
                "name": "design",
                "description": "Produce the architecture design.",
                "agent_role": "architect",
                "dependencies": [],
            },
            {
                "name": "write_docs",
                "description": "Write the documentation.",
                "agent_role": "writer",
                "dependencies": ["design"],
            },
        ],
    )
    fake = FakeLLMProvider([payload])
    composer = Composer(fake)

    request = composer.compose(
        "an architect on Claude and a writer on Gemini, writer depends on architect"
    )

    roles = {role.name: role for role in request.desired_roles}
    assert roles["architect"].llm.provider == "anthropic"
    assert roles["writer"].llm.provider == "google"
    tasks = {task.name: task for task in request.desired_tasks}
    assert tasks["write_docs"].dependencies == ["design"]
    assert tasks["write_docs"].agent_role == "writer"


def test_compose_repairs_after_validation_error(tmp_path):
    invalid_payload = _valid_payload(
        tmp_path,
        desired_roles=[
            {"name": "Not Snake Case!", "description": "x"},  # bad name + short description
        ],
    )
    valid_payload = _valid_payload(tmp_path)
    fake = FakeLLMProvider([invalid_payload, valid_payload])
    composer = Composer(fake, max_repair_attempts=3)

    request = composer.compose("build me a team")

    assert isinstance(request, TeamCreationRequest)
    assert len(fake.calls) == 2
    assert "validation" in fake.calls[1]["user"].lower()


def test_compose_raises_after_exhausting_repair_budget(tmp_path):
    bad_payload = _valid_payload(
        tmp_path,
        desired_roles=[
            {"name": "writer", "description": "Writes content."},
            {"name": "writer", "description": "Writes more content."},  # duplicate name
        ],
    )
    fake = FakeLLMProvider([bad_payload, bad_payload, bad_payload, bad_payload])
    composer = Composer(fake, max_repair_attempts=3)

    with pytest.raises(ComposerError) as exc_info:
        composer.compose("build me a team")

    assert len(fake.calls) == 4  # 1 initial attempt + 3 repairs, all exhausted
    assert exc_info.value.errors
    assert "team specification" in str(exc_info.value).lower()


def test_compose_honors_stated_preference_routing(tmp_path):
    payload = _valid_payload(tmp_path, default_llm={"provider": "ollama", "model": "llama3.2"})
    fake = FakeLLMProvider([payload])
    composer = Composer(fake)

    request = composer.compose("build a team", preferences="use local/cheap models")

    assert request.default_llm is not None
    assert request.default_llm.provider == "ollama"
    assert "local" in fake.calls[0]["user"].lower()


def test_compose_leaves_routing_unset_without_preference(tmp_path):
    payload = _valid_payload(tmp_path)
    fake = FakeLLMProvider([payload])
    composer = Composer(fake)

    request = composer.compose("build a team")

    assert request.default_llm is None
    assert all(role.llm is None for role in request.desired_roles)


def test_composer_accepts_a_non_sdk_fake_provider(tmp_path):
    """Constructor injection (AD-2/AD-8): no concrete SDK is imported anywhere here."""
    payload = _valid_payload(tmp_path)
    fake = FakeLLMProvider([payload])

    composer = Composer(fake)
    request = composer.compose("build a team")

    assert isinstance(request, TeamCreationRequest)


def test_compose_can_produce_a_request_equivalent_to_the_minimal_fixture(minimal_request):
    payload = minimal_request.model_dump(mode="json", exclude_none=True)
    fake = FakeLLMProvider([payload])
    composer = Composer(fake)

    request = composer.compose("a minimal test team")

    assert request.team_name == minimal_request.team_name
    assert [role.name for role in request.desired_roles] == [
        role.name for role in minimal_request.desired_roles
    ]


def test_compose_can_produce_a_request_equivalent_to_the_full_fixture(full_request):
    payload = full_request.model_dump(mode="json", exclude_none=True)
    fake = FakeLLMProvider([payload])
    composer = Composer(fake)

    request = composer.compose("a full software delivery team")

    assert request.team_name == full_request.team_name
    assert [role.name for role in request.desired_roles] == [
        role.name for role in full_request.desired_roles
    ]
    assert request.default_llm.provider == full_request.default_llm.provider


def test_compose_includes_available_providers_hint_when_key_config_given(tmp_path):
    payload = _valid_payload(tmp_path)
    fake = FakeLLMProvider([payload])
    key_config = KeyConfig(keys={"anthropic": SecretStr("sk-test-not-real")})
    composer = Composer(fake, key_config=key_config)

    composer.compose("build a team")

    assert "anthropic" in fake.calls[0]["system"].lower()
