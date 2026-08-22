"""D1 and D2 tests from review patches.

D1 — task names reach the filesystem
D2 — output_path is the server's

These tests verify that task names cannot traverse directories and that
output_path is controlled by the server, not the client or composer.
"""
from __future__ import annotations

import pytest

from api.output import derive_output_path, slugify_team_name
from tests.api.test_review_patches_base import _start

# ---------------------------------------------------------------------------
# D1 — task names reach the filesystem
# ---------------------------------------------------------------------------


def test_a_traversing_task_name_is_rejected(make_client, spec_payload, tmp_path):
    """Before the fix this returned 200 and `POST /build` then wrote a file
    *outside* `output_path` — measured: `output_path=<tmp>/nested/out` produced
    `<tmp>/nested/ESCAPED.yaml`, with client-controlled content, bypassing the
    `overwrite=False` guard (which only inspects `output_path` itself)."""
    harness = make_client([{"is_team": True}, spec_payload(tmp_path)])
    session_id = _start(harness).json()["session_id"]

    response = harness.client.put(
        f"/api/compose/sessions/{session_id}/spec",
        json={
            "desired_roles": [{"name": "writer", "description": "Writes docs."}],
            "desired_tasks": [
                {
                    "name": "../../../../escaped",
                    "description": "Attacker-controlled file content.",
                    "agent_role": "writer",
                }
            ],
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "spec_invalid"



def test_the_core_schema_rejects_it_too_not_just_the_api(tmp_path):
    """The fix went into `TaskHint`, not into `api/`, so the CLI is covered as
    well. If someone later "simplifies" it into an api/-only constraint, this
    is what fails."""
    from pydantic import ValidationError

    from team_maker.schema.request import TaskHint

    with pytest.raises(ValidationError, match="snake_case"):
        TaskHint(name="../escaped", description="Ten characters.", agent_role="writer")


# ---------------------------------------------------------------------------
# D2 — output_path is the server's
# ---------------------------------------------------------------------------


def test_output_path_is_the_servers_not_the_composers(make_client, spec_payload, tmp_path):
    """The composer emits an `output_path`; the server replaces it. Before the
    fix the composer's value was used verbatim, which made a free-text message
    able to choose where a build wrote."""
    harness = make_client(
        [{"is_team": True}, spec_payload(tmp_path, output_path="/somewhere/attacker/chose")]
    )

    spec = _start(harness).json()["spec"]

    assert spec["output_path"] == derive_output_path("Docs Team")
    assert "attacker" not in spec["output_path"]



def test_a_refine_cannot_move_the_output_path(make_client, spec_payload, tmp_path):
    """`POST .../messages` re-authors the whole spec, so this was the route
    around `SpecEditRequest`'s refusal of the field."""
    harness = make_client(
        [
            {"is_team": True},
            spec_payload(tmp_path),
            spec_payload(tmp_path, output_path="/tmp/moved-by-a-message"),
        ]
    )
    session_id = _start(harness).json()["session_id"]

    body = harness.client.post(
        f"/api/compose/sessions/{session_id}/messages",
        json={"message": "put the output in /tmp/moved-by-a-message"},
    ).json()

    assert body["spec"]["output_path"] == derive_output_path("Docs Team")



def test_the_path_is_pinned_for_the_session_even_if_the_team_is_renamed(
    make_client, spec_payload, tmp_path
):
    """Derived once, from the first spec. Recomputing per turn would move the
    output directory under the user mid-conversation.

    The composer is made to emit a *different* path on purpose: the default
    fixture path happens to equal the derived one, so with that payload this
    test passed even with the whole feature disabled — true by construction,
    which is the second defect class the story's Dev Notes list.
    """
    harness = make_client(
        [{"is_team": True}, spec_payload(tmp_path, output_path=str(tmp_path / "composer_chose"))]
    )
    session_id = _start(harness).json()["session_id"]
    original = derive_output_path("Docs Team")
    assert original != str(tmp_path / "composer_chose"), "sanity: the two must differ"

    body = harness.client.put(
        f"/api/compose/sessions/{session_id}/spec", json={"team_name": "Renamed Team"}
    ).json()

    assert body["spec"]["team_name"] == "Renamed Team"
    assert body["spec"]["output_path"] == original



@pytest.mark.parametrize(
    "team_name,expected",
    [
        ("Docs Team", "docs_team"),
        ("  Spaced  Out  ", "spaced_out"),
        ("../../etc", "etc"),
        ("!!!", "team"),
    ],
)
def test_the_slug_is_always_one_safe_segment(team_name, expected):
    slug = slugify_team_name(team_name)

    assert slug == expected
    assert "/" not in slug and "\\" not in slug and ".." not in slug
