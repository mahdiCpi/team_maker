"""Every AC 2 error code, and AC 8's containment rule for each of them.

The CLI's interactive loop catches only `ComposerError`, so any other exception
kills the conversation (`deferred-work.md:53`), and the repair loop retries only
on `pydantic.ValidationError`, so a network blip propagates raw
(`deferred-work.md:47`). This lane proves the API does neither: it catches
broadly, keeps the session alive, and never serialises an exception.

Error *copy* for the user is Story 2.3's job. Error *containment* is this
story's, and that is what is asserted here.
"""
from __future__ import annotations

import pytest

from api.sessions import MAX_TURNS_PER_SESSION
from tests.api.containment import assert_envelope, assert_no_exception_leak

# Planted inside injected exception messages. If any handler ever serialises
# `str(exc)`, this string appears in the response — which is precisely the
# `deferred-work.md:45` failure mode, where an SDK error echoes a secret.
POISON = "sk-POISONED-EXCEPTION-TEXT"


def _start(harness, intent="I need a team to write docs.", authoring=None):
    body = {"intent": intent}
    if authoring is not None:
        body["authoring"] = authoring
    return harness.client.post("/api/compose/sessions", json=body)


def test_session_not_found(make_client, spec_payload, tmp_path):
    harness = make_client([spec_payload(tmp_path)])

    response = harness.client.post(
        "/api/compose/sessions/nope/messages", json={"message": "hi"}
    )

    assert response.status_code == 404
    assert_envelope(response, "session_not_found")
    assert_no_exception_leak(response.text)


def test_turn_cap_reached(make_client, spec_payload, tmp_path):
    # Story 2.10: the first turn's `start()` also issues a classification call.
    harness = make_client(
        [{"is_team": True}] + [spec_payload(tmp_path) for _ in range(MAX_TURNS_PER_SESSION)]
    )
    session_id = _start(harness).json()["session_id"]
    for _ in range(MAX_TURNS_PER_SESSION - 1):
        harness.client.post(
            f"/api/compose/sessions/{session_id}/messages", json={"message": "again"}
        )

    response = harness.client.post(
        f"/api/compose/sessions/{session_id}/messages", json={"message": "one more"}
    )

    assert response.status_code == 409
    assert_envelope(response, "turn_cap_reached")
    assert_no_exception_leak(response.text)


def test_needs_clarification_turns_still_count_against_the_turn_cap(make_client):
    """AC 4/AC 6 (Story 2.10): a `needs_clarification` turn must consume the
    same turn budget as any other turn, so repeatedly sending non-team
    messages converges to `turn_cap_reached` rather than opening an unbounded
    free-chat loop. Every turn here — including the first — classifies as
    non-team, so no compose response is ever queued.
    """
    harness = make_client([{"is_team": False}] * MAX_TURNS_PER_SESSION)
    session_id = _start(harness, intent="hi").json()["session_id"]

    for _ in range(MAX_TURNS_PER_SESSION - 1):
        response = harness.client.post(
            f"/api/compose/sessions/{session_id}/messages",
            json={"message": "still not a team"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "needs_clarification"

    capped = harness.client.post(
        f"/api/compose/sessions/{session_id}/messages", json={"message": "one more"}
    )

    assert capped.status_code == 409
    assert_envelope(capped, "turn_cap_reached")


def test_spec_invalid_from_an_exhausted_repair_budget(make_client, spec_payload, tmp_path):
    harness = make_client([{"is_team": True}, spec_payload(tmp_path), {}, {}, {}, {}])
    session_id = _start(harness).json()["session_id"]

    response = harness.client.post(
        f"/api/compose/sessions/{session_id}/messages", json={"message": "break it"}
    )

    assert response.status_code == 422
    error = assert_envelope(response, "spec_invalid")
    assert error["fields"]
    assert_no_exception_leak(response.text)


def test_authoring_unavailable(make_client, spec_payload, tmp_path):
    harness = make_client([spec_payload(tmp_path)])

    response = _start(harness, authoring={"provider": "google", "model": "gemini-1.5-pro"})

    assert response.status_code == 503
    assert_envelope(response, "authoring_unavailable")
    assert_no_exception_leak(response.text)


def test_compose_failed_from_an_arbitrary_adapter_exception(
    make_client, spec_payload, tmp_path
):
    """The repair loop gives zero retries to anything that is not a
    `ValidationError` (`deferred-work.md:47`), so this reaches the route raw."""
    harness = make_client([RuntimeError(f"upstream exploded: {POISON}")])

    response = _start(harness)

    assert response.status_code == 502
    assert_envelope(response, "compose_failed")
    assert_no_exception_leak(response.text, extra=(POISON, "upstream exploded"))


def test_output_exists(make_client, spec_payload, tmp_path, offline_model_resolver):
    output = tmp_path / "docs_team"
    output.mkdir()
    (output / "already-here.txt").write_text("occupied", encoding="utf-8")
    harness = make_client([{"is_team": True}, spec_payload(tmp_path)])
    session_id = _start(harness).json()["session_id"]

    response = harness.client.post(f"/api/compose/sessions/{session_id}/build")

    assert response.status_code == 409
    assert_envelope(response, "output_exists")
    # `str(FileExistsError(...))` carries the errno text and the *path*, not the
    # class name — so the generic sweep alone would pass even if the handler
    # serialised the exception. Name the path explicitly, or this test proves
    # nothing about the one leak it is positioned to catch.
    assert_no_exception_leak(response.text, extra=(str(output), output.name))


def test_build_failed(make_client, spec_payload, tmp_path, monkeypatch):
    """STUB: `api.build.PipelineRunner` is replaced so the build raises
    something that is not a `FileExistsError`. Only this module's reference is
    patched — nothing under `team_maker/` is touched."""

    class ExplodingRunner:
        def run(self, request):
            raise RuntimeError(f"pipeline exploded: {POISON}")

    harness = make_client([{"is_team": True}, spec_payload(tmp_path)])
    session_id = _start(harness).json()["session_id"]
    monkeypatch.setattr("api.build.PipelineRunner", ExplodingRunner)

    response = harness.client.post(f"/api/compose/sessions/{session_id}/build")

    assert response.status_code == 500
    assert_envelope(response, "build_failed")
    assert_no_exception_leak(response.text, extra=(POISON, "pipeline exploded"))


def test_a_failed_turn_keeps_the_session_alive(make_client, spec_payload, tmp_path):
    """AC 8: catch broadly, keep the session, keep `session.current` intact."""
    harness = make_client(
        [
            {"is_team": True},
            spec_payload(tmp_path),
            RuntimeError(f"transient: {POISON}"),
            spec_payload(tmp_path, team_name="Docs Squad"),
        ]
    )
    session_id = _start(harness).json()["session_id"]

    failed = harness.client.post(
        f"/api/compose/sessions/{session_id}/messages", json={"message": "boom"}
    )
    assert failed.status_code == 502

    recovered = harness.client.post(
        f"/api/compose/sessions/{session_id}/messages", json={"message": "try again"}
    )
    assert recovered.status_code == 200
    assert recovered.json()["spec"]["team_name"] == "Docs Squad"


def test_the_exception_is_logged_server_side(make_client, spec_payload, tmp_path, caplog):
    """"Log the exception server-side; never serialise it" — both halves.

    Story 4.1's review (decision D3) tightened "log it" further: a server log
    is still a leak vector (aggregation services, log file access), so the
    logging path now redacts secret-shaped content exactly like the client-
    facing display path does — `POISON` is shaped like a leaked API key, and
    must now be redacted in the log too, not merely kept out of the response.
    The surrounding message is still logged verbatim, so a real fault stays
    diagnosable; only the secret-shaped span is replaced.
    """
    import logging

    harness = make_client([RuntimeError(f"upstream exploded: {POISON}")])

    with caplog.at_level(logging.ERROR):
        response = _start(harness)

    assert response.status_code == 502
    assert "upstream exploded" in caplog.text, "the exception must still be diagnosable in the server log"
    assert "RuntimeError" in caplog.text
    assert POISON not in caplog.text, "secret-shaped content must be redacted even server-side (D3)"
    assert "[REDACTED]" in caplog.text
    assert POISON not in response.text


@pytest.mark.parametrize(
    "method,path",
    [("get", "/api/compose/sessions"), ("delete", "/api/health")],
)
def test_framework_level_errors_also_use_the_envelope(make_client, method, path):
    harness = make_client()

    response = getattr(harness.client, method)(path)

    assert response.status_code in (404, 405)
    body = response.json()
    assert set(body) == {"error"}
    assert_no_exception_leak(response.text)


def test_an_unhandled_fault_still_answers_with_the_envelope(
    make_client, spec_payload, tmp_path, monkeypatch
):
    """Defence in depth: every authored route catches broadly, so this can only
    fire for a fault outside them. `raise_server_exceptions=False` models what
    a real client sees — uvicorn sends the handler's response and logs the
    exception; TestClient re-raises it by default purely as a convenience."""
    harness = make_client([{"is_team": True}, spec_payload(tmp_path)], raise_server_exceptions=False)

    def exploding_view(*args, **kwargs):
        raise RuntimeError(f"serializer exploded: {POISON}")

    monkeypatch.setattr("api.routers.compose._session_view", exploding_view)

    response = _start(harness)

    assert response.status_code == 500
    assert_envelope(response, "internal_error")
    assert_no_exception_leak(response.text, extra=(POISON,))
