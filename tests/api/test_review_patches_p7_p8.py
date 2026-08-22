"""P7 and P8 tests from review patches.

P7 / P8 — task edits the core would have discarded silently

These tests verify that task and role edits are properly validated.
"""
from __future__ import annotations

from tests.api.test_review_patches_base import _start


# ---------------------------------------------------------------------------
# P7 / P8 — task edits the core would have discarded silently
# ---------------------------------------------------------------------------


def test_duplicate_task_names_are_rejected(make_client, spec_payload, tmp_path):
    """Both collapse onto one manifest key, so one file is written while
    `task_count` reports two."""
    harness = make_client([{"is_team": True}, spec_payload(tmp_path)])
    session_id = _start(harness).json()["session_id"]

    response = harness.client.put(
        f"/api/compose/sessions/{session_id}/spec",
        json={
            "desired_tasks": [
                {"name": "dup", "description": "First task here.", "agent_role": "writer"},
                {"name": "dup", "description": "Second task here.", "agent_role": "writer"},
            ]
        },
    )

    assert response.status_code == 422
    assert any("uniq" in f["message"].lower() for f in response.json()["error"]["fields"])



def test_renaming_a_role_no_longer_silently_orphans_its_tasks(
    make_client, spec_payload, tmp_path
):
    """The template drops a task whose `agent_role` is not an agent, and if
    *every* task drops it substitutes its own defaults — so the built package
    could contain tasks the user never authored."""
    harness = make_client(
        [
            {"is_team": True},
            spec_payload(
                tmp_path,
                desired_tasks=[
                    {
                        "name": "draft_guide",
                        "description": "Draft the onboarding guide.",
                        "agent_role": "writer",
                    }
                ],
            )
        ]
    )
    session_id = _start(harness).json()["session_id"]

    response = harness.client.put(
        f"/api/compose/sessions/{session_id}/spec",
        json={"desired_roles": [{"name": "editor", "description": "Edits docs."}]},
    )

    assert response.status_code == 422
    fields = response.json()["error"]["fields"]
    assert any("agent_role" in f["path"] for f in fields)
    assert any("editor" not in f["message"] and "writer" in f["message"] for f in fields)
