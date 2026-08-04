"""`PUT /api/compose/sessions/{id}/spec` — the review-mode edit route (AC 2).

The contract under test: the client owns three dimensions, the server owns
everything else, and an invalid edit changes nothing.
"""
from __future__ import annotations

import pytest


@pytest.fixture
def session(make_client, spec_payload, tmp_path):
    """A started session whose spec pins a per-role model and an output path."""
    payload = spec_payload(
        tmp_path,
        desired_roles=[
            {
                "name": "writer",
                "description": "Writes documentation.",
                "goal": "Ship clear docs.",
                "llm": {"provider": "anthropic", "model": "claude-sonnet-4-6"},
            }
        ],
    )
    harness = make_client([payload])
    created = harness.client.post(
        "/api/compose/sessions", json={"intent": "I need a team to write docs."}
    ).json()
    return harness, created["session_id"], created["spec"]


def test_edit_replaces_the_client_owned_dimensions(session):
    harness, session_id, _ = session

    response = harness.client.put(
        f"/api/compose/sessions/{session_id}/spec",
        json={
            "team_name": "Renamed Team",
            "purpose": "A different purpose, stated at length.",
            "desired_roles": [
                {"name": "writer", "description": "Writes and edits documentation."},
                {"name": "reviewer", "description": "Reviews documentation."},
            ],
            "desired_tasks": [
                {
                    "name": "draft_guide",
                    "description": "Draft the onboarding guide end to end.",
                    "agent_role": "writer",
                    "dependencies": [],
                }
            ],
        },
    )

    assert response.status_code == 200
    spec = response.json()["spec"]
    assert spec["team_name"] == "Renamed Team"
    assert [role["name"] for role in spec["desired_roles"]] == ["writer", "reviewer"]
    assert [task["name"] for task in spec["desired_tasks"]] == ["draft_guide"]


def test_edit_does_not_consume_a_turn(session):
    harness, session_id, _ = session

    body = harness.client.put(
        f"/api/compose/sessions/{session_id}/spec",
        json={"team_name": "Renamed Team"},
    ).json()

    assert body["turn"] == 1  # no LLM call happened, so no spend to cap
    assert len(harness.provider.calls) == 1


def test_server_owned_fields_are_carried_not_read_from_the_body(session):
    harness, session_id, original = session

    body = harness.client.put(
        f"/api/compose/sessions/{session_id}/spec", json={"team_name": "Renamed Team"}
    ).json()

    spec = body["spec"]
    assert spec["output_path"] == original["output_path"]
    assert spec["planning_llm"] == original["planning_llm"]
    assert spec["framework"] == original["framework"]
    assert spec["state_backend"] == original["state_backend"]
    assert spec["sandbox"] == original["sandbox"]


@pytest.mark.parametrize(
    "forbidden",
    [
        {"output_path": "/tmp/somewhere-else"},
        {"overwrite": True},
        {"planning_llm": {"provider": "openai", "model": "gpt-4o"}},
        {"framework": "langgraph"},
        {"state_backend": "vector"},
        {"api_key_env": "ANTHROPIC_API_KEY"},
    ],
)
def test_server_owned_fields_are_rejected_outright(session, forbidden):
    """A browser-settable `overwrite` would turn `FileExistsError` — the only
    guard against clobbering an existing directory — into a browser-controlled
    switch. `extra="forbid"` is what makes that a 422 rather than a shrug."""
    harness, session_id, _ = session

    response = harness.client.put(
        f"/api/compose/sessions/{session_id}/spec", json=forbidden
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "spec_invalid"


def test_invalid_edit_leaves_the_current_spec_unchanged(session):
    harness, session_id, original = session

    rejected = harness.client.put(
        f"/api/compose/sessions/{session_id}/spec",
        json={"desired_roles": [{"name": "Not Snake Case", "description": "Nope."}]},
    )

    assert rejected.status_code == 422
    body = rejected.json()
    assert body["error"]["code"] == "spec_invalid"
    assert any("desired_roles" in field["path"] for field in body["error"]["fields"])

    readback = harness.client.put(f"/api/compose/sessions/{session_id}/spec", json={})
    assert readback.json()["spec"] == original


def test_empty_roles_list_is_rejected(session):
    """An empty `desired_roles` flips the build into a second LLM call through
    `planning_llm` — a different provider config, and silent cost
    (`runner.py:66-69`)."""
    harness, session_id, _ = session

    response = harness.client.put(
        f"/api/compose/sessions/{session_id}/spec", json={"desired_roles": []}
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "spec_invalid"
    assert [field["path"] for field in body["error"]["fields"]] == ["desired_roles"]


def test_role_merge_preserves_fields_the_edit_shape_cannot_express(session):
    """`RoleEdit` carries 3 of `RoleDefinition`'s 9 fields. A role whose name
    still matches must not silently lose its `goal`."""
    harness, session_id, _ = session

    body = harness.client.put(
        f"/api/compose/sessions/{session_id}/spec",
        json={"desired_roles": [{"name": "writer", "description": "Writes docs, better."}]},
    ).json()

    writer = body["spec"]["desired_roles"][0]
    assert writer["description"] == "Writes docs, better."
    assert writer["goal"] == "Ship clear docs."
    assert writer["llm"]["model"] == "claude-sonnet-4-6"


def test_role_llm_can_be_changed_and_explicitly_cleared(session):
    harness, session_id, _ = session

    changed = harness.client.put(
        f"/api/compose/sessions/{session_id}/spec",
        json={
            "desired_roles": [
                {
                    "name": "writer",
                    "description": "Writes documentation.",
                    "llm": {"provider": "openai", "model": "gpt-4o"},
                }
            ]
        },
    ).json()
    assert changed["spec"]["desired_roles"][0]["llm"]["provider"] == "openai"

    cleared = harness.client.put(
        f"/api/compose/sessions/{session_id}/spec",
        json={
            "desired_roles": [
                {"name": "writer", "description": "Writes documentation.", "llm": None}
            ]
        },
    ).json()
    assert "llm" not in cleared["spec"]["desired_roles"][0]


def test_the_returned_spec_is_the_servers_not_the_clients(make_client, spec_payload, tmp_path):
    """`TeamCreationRequest._pre_process` (`request.py:271-354`) silently
    rewrites input — here, a dict-valued `stack` is flattened to a string. The
    response must be the re-serialised server spec, so a client re-renders from
    it rather than from its own local edit."""
    harness = make_client(
        [spec_payload(tmp_path, stack={"language": "Python 3.13", "web": "FastAPI"})]
    )

    spec = harness.client.post(
        "/api/compose/sessions", json={"intent": "docs team"}
    ).json()["spec"]

    assert isinstance(spec["stack"], str)
    assert "Python 3.13" in spec["stack"]
