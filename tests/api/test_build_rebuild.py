"""Rebuilding a session after a successful build (Task 6, Story 4.5, AC 6).

Before this fix, a second `POST .../build` on the same session always 409'd
with `output_exists`, because the first build already wrote the (pinned)
output directory. `ComposeSession.build_succeeded` now allows a rebuild to
overwrite that directory once a build has already succeeded there.
"""
from __future__ import annotations


def _start_and_build(make_client, spec_payload, tmp_path):
    payload = spec_payload(tmp_path)
    harness = make_client([{"is_team": True}, payload])
    session_id = harness.client.post(
        "/api/compose/sessions", json={"intent": "docs team"}
    ).json()["session_id"]
    response = harness.client.post(f"/api/compose/sessions/{session_id}/build")
    return harness, session_id, response


def test_second_build_in_the_same_session_succeeds(make_client, spec_payload, tmp_path, offline_model_resolver):
    harness, session_id, first = _start_and_build(make_client, spec_payload, tmp_path)
    assert first.status_code == 200

    second = harness.client.post(f"/api/compose/sessions/{session_id}/build")

    assert second.status_code == 200
    assert second.json()["output_path"] == first.json()["output_path"]


def test_a_build_that_never_succeeded_still_gets_the_output_exists_guard(
    make_client, spec_payload, tmp_path, offline_model_resolver
):
    """The overwrite allowance is keyed on a *successful* prior build, not
    merely on having attempted one. A pre-existing directory from something
    else must still 409 on the first build."""
    output = tmp_path / "docs_team"
    output.mkdir()
    (output / "already-here.txt").write_text("occupied", encoding="utf-8")

    harness, session_id, first = _start_and_build(make_client, spec_payload, tmp_path)

    assert first.status_code == 409
