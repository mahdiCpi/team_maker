"""Compose session lifecycle over HTTP (Story 2.0, AC 2 / AC 7 / AC 8).

All LLM behaviour here is `FakeLLMProvider`, a STUB. These are mocked
integration tests of the HTTP seam, not evidence that any real provider works.
"""
from __future__ import annotations

from api.sessions import MAX_TURNS_PER_SESSION


def _start(harness, intent: str = "I need a team to write docs."):
    return harness.client.post("/api/compose/sessions", json={"intent": intent})


def test_create_session_returns_the_first_turn(make_client, spec_payload, tmp_path):
    harness = make_client([{"is_team": True}, spec_payload(tmp_path)])

    response = _start(harness)

    assert response.status_code == 201
    body = response.json()
    assert body["turn"] == 1
    assert body["turns_remaining"] == MAX_TURNS_PER_SESSION - 1
    assert body["spec"]["team_name"] == "Docs Team"
    assert body["session_id"]
    assert body["status"] == "complete"


def test_create_session_has_no_validation_field(make_client, spec_payload, tmp_path):
    """AC 2: a returned spec is schema-valid by construction (AD-10).

    An always-`passed: true` field here would be a value true by construction —
    the defect class the story's Dev Notes call out. `validation` belongs to the
    build response alone, where a real `ValidationResult` exists.
    """
    harness = make_client([{"is_team": True}, spec_payload(tmp_path)])

    body = _start(harness).json()

    assert "validation" not in body
    assert "validation" not in body["spec"]


def test_refine_increments_the_turn_and_replaces_the_spec(make_client, spec_payload, tmp_path):
    harness = make_client(
        [
            {"is_team": True},
            spec_payload(tmp_path),
            spec_payload(tmp_path, team_name="Docs Squad"),
        ]
    )
    session_id = _start(harness).json()["session_id"]

    response = harness.client.post(
        f"/api/compose/sessions/{session_id}/messages", json={"message": "rename it"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["turn"] == 2
    assert body["turns_remaining"] == MAX_TURNS_PER_SESSION - 2
    assert body["spec"]["team_name"] == "Docs Squad"


def test_refinement_carries_the_earlier_turns_facts(make_client, spec_payload, tmp_path):
    """The core keeps no chat history: each turn re-sends the original intent
    plus the whole current spec (`session.py:46-56`). Prove the API does not
    break that by, say, starting a fresh conversation per request."""
    harness = make_client([{"is_team": True}, spec_payload(tmp_path), spec_payload(tmp_path)])
    session_id = _start(harness, "I need a team to write docs.").json()["session_id"]

    harness.client.post(
        f"/api/compose/sessions/{session_id}/messages", json={"message": "add a reviewer"}
    )

    second_turn_prompt = harness.provider.calls[2]["user"]
    assert "I need a team to write docs." in second_turn_prompt
    assert "Docs Team" in second_turn_prompt
    assert "add a reviewer" in second_turn_prompt


def test_failed_refine_leaves_the_current_spec_intact(make_client, spec_payload, tmp_path):
    """Story 1.3's AC 6 contract, preserved across the HTTP seam.

    The four `{}` responses exhaust the Composer's repair budget (1 attempt + 3
    repairs), which is how a *real* `ComposerError` is produced — the fake
    returns invalid payloads and the real `TeamCreationRequest` rejects them.
    """
    harness = make_client([{"is_team": True}, spec_payload(tmp_path), {}, {}, {}, {}])
    session_id = _start(harness).json()["session_id"]

    failed = harness.client.post(
        f"/api/compose/sessions/{session_id}/messages", json={"message": "break it"}
    )

    assert failed.status_code == 422
    assert failed.json()["error"]["code"] == "spec_invalid"

    # Read the spec back through an empty edit — the only route that returns
    # the stored spec without changing it.
    readback = harness.client.put(f"/api/compose/sessions/{session_id}/spec", json={})
    assert readback.status_code == 200
    assert readback.json()["spec"]["team_name"] == "Docs Team"


def test_failed_refine_reports_field_addressable_errors(make_client, spec_payload, tmp_path):
    """AC 2 / Task 3: `ComposerError.errors` is a `list[str]` shaped
    `"a → b → c: msg"`. The envelope must turn that into dotted paths."""
    harness = make_client([{"is_team": True}, spec_payload(tmp_path), {}, {}, {}, {}])
    session_id = _start(harness).json()["session_id"]

    body = harness.client.post(
        f"/api/compose/sessions/{session_id}/messages", json={"message": "break it"}
    ).json()

    fields = body["error"]["fields"]
    assert fields, "spec_invalid must carry field-addressable errors"
    paths = {field["path"] for field in fields}
    assert "team_name" in paths
    assert all("→" not in path for path in paths)
    assert all(field["message"] for field in fields)


def test_failed_first_turn_does_not_leave_a_half_born_session(
    make_client, spec_payload, tmp_path
):
    """A session whose first turn failed has no spec, so a follow-up would hit
    `refine() before start()`. It is discarded instead."""
    harness = make_client([{"is_team": True}, {}, {}, {}, {}])

    failed = _start(harness)

    assert failed.status_code == 422
    assert harness.client.app.state.team_maker_api.registry.active_count() == 0


def test_unknown_session_id_is_a_clean_404(make_client, spec_payload, tmp_path):
    """AC 7: an unknown or evicted id returns `session_not_found`, never a 500."""
    harness = make_client([spec_payload(tmp_path)])

    response = harness.client.post(
        "/api/compose/sessions/does-not-exist/messages", json={"message": "hello"}
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "session_not_found"


def test_evicted_session_is_indistinguishable_from_an_unknown_one(
    make_client, spec_payload, tmp_path
):
    """AC 7 idle eviction, driven through the real registry.

    `last_seen` is pushed past the TTL rather than sleeping for half an hour;
    the sweep itself is the real code path.
    """
    harness = make_client([{"is_team": True}, spec_payload(tmp_path)])
    session_id = _start(harness).json()["session_id"]
    registry = harness.client.app.state.team_maker_api.registry

    registry._sessions[session_id].last_seen -= 10_000  # far past SESSION_IDLE_TTL_SECONDS

    response = harness.client.post(
        f"/api/compose/sessions/{session_id}/messages", json={"message": "still there?"}
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "session_not_found"
    assert registry.active_count() == 0


def test_turn_cap_is_enforced(make_client, spec_payload, tmp_path):
    """AC 7: an HTTP API makes unbounded LLM spend materially worse than a CLI
    (`deferred-work.md:54`), so the cap is a hard stop, not advice."""
    payloads = [spec_payload(tmp_path) for _ in range(MAX_TURNS_PER_SESSION + 1)]
    harness = make_client([{"is_team": True}, *payloads])
    session_id = _start(harness).json()["session_id"]

    for _ in range(MAX_TURNS_PER_SESSION - 1):
        assert (
            harness.client.post(
                f"/api/compose/sessions/{session_id}/messages", json={"message": "again"}
            ).status_code
            == 200
        )

    capped = harness.client.post(
        f"/api/compose/sessions/{session_id}/messages", json={"message": "one more"}
    )

    assert capped.status_code == 409
    assert capped.json()["error"]["code"] == "turn_cap_reached"
    # The capped turn must not have reached the provider.
    assert harness.provider.calls, "sanity: the fake was used"
    assert len(harness.provider.calls) == MAX_TURNS_PER_SESSION + 1
