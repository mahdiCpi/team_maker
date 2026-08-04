"""`POST /api/compose/sessions/{id}/build` and its response mapping (AC 2).

These run the *real* `PipelineRunner` against `tmp_path` — a local integration
test, not a unit test — with one stub: `offline_model_resolver` replaces the
live `models.list()` calls the pipeline makes (`model_resolver.py:106-111`).
No LLM is contacted: every spec here comes from `FakeLLMProvider`.
"""
from __future__ import annotations

import pytest


@pytest.fixture
def built(make_client, spec_payload, tmp_path, offline_model_resolver):
    """Start a session and build it, returning the build response."""

    def _build(**role_overrides):
        payload = spec_payload(tmp_path, **role_overrides)
        harness = make_client([payload])
        session_id = harness.client.post(
            "/api/compose/sessions", json={"intent": "docs team"}
        ).json()["session_id"]
        return harness, harness.client.post(f"/api/compose/sessions/{session_id}/build")

    return _build


def test_build_returns_the_ac2_shape(built, tmp_path):
    _, response = built()

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "status",
        "team_name",
        "output_path",
        "agent_count",
        "task_count",
        "written_file_count",
        "model_substitutions",
        "validation",
    }
    assert body["team_name"] == "Docs Team"
    assert body["output_path"] == str((tmp_path / "docs_team").resolve())
    assert body["agent_count"] == 1
    # `writer` is not one of the template's default roles, and a default task is
    # only emitted when its owning role is present — so an unhinted spec yields
    # no tasks. `test_declared_tasks_are_counted` covers the other side.
    assert body["task_count"] == 0
    assert body["written_file_count"] > 0
    assert set(body["validation"]) == {"passed", "issues", "warnings"}
    assert body["validation"]["passed"] is True


def test_the_package_is_actually_written(built, tmp_path):
    _, response = built()

    output = tmp_path / "docs_team"
    assert (output / "README.md").is_file()
    assert (output / "team_config.yaml").is_file()
    assert (output / "generation_report.md").is_file()
    written = response.json()["written_file_count"]
    assert written == len(list(output.rglob("*"))) - len(
        [p for p in output.rglob("*") if p.is_dir()]
    )


def test_declared_tasks_are_counted(built):
    _, response = built(
        desired_tasks=[
            {
                "name": "draft_guide",
                "description": "Draft the onboarding guide end to end.",
                "agent_role": "writer",
                "dependencies": [],
            }
        ]
    )

    assert response.json()["task_count"] == 1


def test_no_substitution_is_reported_when_the_model_exists(built):
    """`claude-sonnet-4-6` is in the stub catalog, so nothing is swapped."""
    _, response = built(
        desired_roles=[
            {
                "name": "writer",
                "description": "Writes documentation.",
                "llm": {"provider": "anthropic", "model": "claude-sonnet-4-6"},
            }
        ]
    )

    assert response.json()["model_substitutions"] == []


def test_a_silent_model_swap_is_surfaced(built):
    """The reason `model_substitutions` exists: `normalize_team_routings` may
    swap the chosen model for a fuzzy nearest match and report it only to
    stderr (`model_resolver.py:156-185`). Without this the UI would claim it
    built the model the user picked."""
    _, response = built(
        desired_roles=[
            {
                "name": "writer",
                "description": "Writes documentation.",
                "llm": {"provider": "anthropic", "model": "claude-3-opus-20240229"},
            }
        ]
    )

    substitutions = response.json()["model_substitutions"]
    assert len(substitutions) == 1
    swap = substitutions[0]
    assert swap["role"] == "writer"
    assert swap["requested"] == "anthropic/claude-3-opus-20240229"
    assert swap["resolved"].startswith("anthropic/")
    assert swap["resolved"] != swap["requested"]


def test_build_does_not_consume_a_turn(built):
    harness, response = built()
    assert response.status_code == 200

    # A build is not an authoring call, so the spend cap is untouched.
    registry = harness.client.app.state.team_maker_api.registry
    entry = next(iter(registry._sessions.values()))
    assert entry.turn == 1


def test_build_on_an_unknown_session_is_a_clean_404(make_client):
    harness = make_client()

    response = harness.client.post("/api/compose/sessions/nope/build")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "session_not_found"
