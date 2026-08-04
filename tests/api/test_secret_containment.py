"""AD-9 / AC 4: no endpoint returns a key, and no endpoint accepts one.

The Key Config the app boots against holds only sentinels
(`tests/api/conftest.py`), so a failure here prints a fake value, never a real
one. That isolation is the whole reason the fixture is autouse.
"""
from __future__ import annotations

import logging

from tests.api.conftest import SENTINEL_VALUES
from tests.api.containment import assert_no_sentinels


def _exercise_every_route(client, tmp_path, spec_payload) -> list:
    """Hit every authored route, in both its happy and unhappy shape."""
    responses = [
        client.get("/api/health"),
        client.get("/openapi.json"),
        client.post("/api/compose/sessions", json={"intent": "docs team"}),
    ]
    # Fail loudly rather than degrading: with `session_id = None` every
    # subsequent path became `/api/compose/sessions/None/...`, the templating
    # below still normalised them, and the "reached every route" test passed
    # while the sweep had only ever exercised 404s.
    created = responses[-1]
    assert created.status_code == 201, (
        f"session creation failed ({created.status_code}); the sweep below would "
        "silently exercise 404s instead of the real routes"
    )
    session_id = created.json()["session_id"]
    responses += [
        client.post(f"/api/compose/sessions/{session_id}/messages", json={"message": "more"}),
        client.put(f"/api/compose/sessions/{session_id}/spec", json={"team_name": "Renamed"}),
        client.put(f"/api/compose/sessions/{session_id}/spec", json={"desired_roles": []}),
        client.post(f"/api/compose/sessions/{session_id}/build"),
        client.post("/api/compose/sessions/unknown/messages", json={"message": "hi"}),
        # The attempt to smuggle a key in — the one request most likely to echo
        # a credential straight back through a validation error's `input`.
        client.post(
            "/api/compose/sessions",
            json={
                "intent": "docs team",
                "authoring": {
                    "provider": "anthropic",
                    "model": "claude-sonnet-4-6",
                    "api_key": SENTINEL_VALUES[0],
                },
            },
        ),
        client.post(
            "/api/compose/sessions",
            json={"intent": "docs team", "authoring": {"provider": "google", "model": "g"}},
        ),
    ]
    return responses


def test_no_response_body_or_header_contains_a_credential(
    make_client, spec_payload, tmp_path, offline_model_resolver, caplog
):
    harness = make_client(
        [spec_payload(tmp_path), spec_payload(tmp_path, team_name="Docs Squad")]
    )

    with caplog.at_level(logging.DEBUG):
        responses = _exercise_every_route(harness.client, tmp_path, spec_payload)

    for response in responses:
        assert_no_sentinels(response.text, SENTINEL_VALUES)
        for name, value in response.headers.items():
            assert_no_sentinels(f"{name}: {value}", SENTINEL_VALUES)

    assert_no_sentinels(caplog.text, SENTINEL_VALUES)


def test_the_sweep_actually_reached_every_route(
    make_client, spec_payload, tmp_path, offline_model_resolver
):
    """Story 2.1's review found a scanner whose scope was narrower than its
    claim. This pins the sweep to the authored route set, so a route added
    later without being swept fails here rather than passing silently."""
    harness = make_client(
        [spec_payload(tmp_path), spec_payload(tmp_path, team_name="Docs Squad")]
    )
    authored = {
        path
        for path in harness.client.get("/openapi.json").json()["paths"]
        if path.startswith("/api/")
    }

    responses = _exercise_every_route(harness.client, tmp_path, spec_payload)
    visited = {response.request.url.path for response in responses}

    def _template(path: str) -> str:
        parts = path.strip("/").split("/")
        if len(parts) == 5 and parts[:3] == ["api", "compose", "sessions"]:
            return f"/api/compose/sessions/{{session_id}}/{parts[4]}"
        return path

    assert authored <= {_template(path) for path in visited}


def test_the_key_config_the_app_loaded_holds_only_sentinels(make_client):
    """Guards the guard: if isolation ever broke, every assertion above would
    be comparing against a real credential."""
    harness = make_client()

    key_config = harness.client.app.state.team_maker_api.key_config

    assert set(key_config.keys) == {"anthropic", "openai", "openrouter"}
    for provider, secret in key_config.keys.items():
        assert secret.get_secret_value() in SENTINEL_VALUES, provider
