"""AD-9 / AC 4: no endpoint returns a key, and no endpoint accepts one.

The Key Config the app boots against holds only sentinels
(`tests/api/conftest.py`), so a failure here prints a fake value, never a real
one. That isolation is the whole reason the fixture is autouse.
"""
from __future__ import annotations

import logging
from pathlib import Path

from tests.api.conftest import SENTINEL_VALUES
from tests.api.containment import assert_no_sentinels
from tests.support.fake_execution_engine import FakeExecutionEngine


def _template(path: str) -> str:
    """Normalise a visited path back to its authored template shape.

    Explicit, ordered branches per shape — a naive by-segment-count rule
    cannot tell `/api/runs/teams/{team_slug}` and `/api/runs/{run_id}/transcript`
    apart, since both are four segments under `/runs` (Story 2.4). Collapsing
    two distinct routes into one template would make the coverage assertion
    below pass while covering less; `test_the_templating_is_unambiguous`
    pins that this does not happen.
    """
    parts = path.strip("/").split("/")
    if len(parts) == 5 and parts[:3] == ["api", "compose", "sessions"]:
        return f"/api/compose/sessions/{{session_id}}/{parts[4]}"
    # `/api/keys/check/{session_id}` is four segments, so the rule above does
    # not reach it. Story 2.1's review found a scanner narrower than its claim;
    # leaving this out would have been the same defect, and the assertion below
    # would have failed rather than passed silently.
    if len(parts) == 4 and parts[:3] == ["api", "keys", "check"]:
        return "/api/keys/check/{session_id}"
    if len(parts) == 4 and parts[:3] == ["api", "runs", "teams"]:
        return "/api/runs/teams/{team_slug}"
    if len(parts) == 4 and parts[:2] == ["api", "runs"] and parts[3] == "transcript":
        return "/api/runs/{run_id}/transcript"
    if len(parts) == 3 and parts[:2] == ["api", "runs"]:
        return "/api/runs/{run_id}"
    return path


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
    ]
    build_response = client.post(f"/api/compose/sessions/{session_id}/build")
    responses.append(build_response)
    assert build_response.status_code == 200, (
        f"build failed ({build_response.status_code}); the run-route sweep below "
        "would silently exercise 404s instead of the real routes"
    )
    team_slug = Path(build_response.json()["output_path"]).name
    responses += [
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
        # The key-status group (Story 2.3). These are the routes closest to a
        # credential in the whole app — they read the Key Config on every call —
        # so the sweep matters more here than anywhere else.
        client.get("/api/keys/status"),
        client.get(f"/api/keys/check/{session_id}"),
        client.get("/api/keys/check/unknown"),
        # The run group (Story 2.4). A run response carries raw LLM output,
        # which no other route in `api/` does — and `check_credentials`
        # hands the engine real `ResolvedCredential` objects, so this is the
        # closest any route comes to a live credential besides the key group.
        client.get(f"/api/runs/teams/{team_slug}"),
        client.get("/api/runs/teams/unknown-team"),
        client.post("/api/runs", json={"team_slug": team_slug, "goal": "ship it"}),
        client.post("/api/runs", json={"team_slug": "unknown-team", "goal": "ship it"}),
        client.get("/api/runs/unknown-run-id"),
        client.get("/api/runs/unknown-run-id/transcript"),
    ]
    return responses


def test_no_response_body_or_header_contains_a_credential(
    make_client, spec_payload, tmp_path, offline_model_resolver, caplog
):
    harness = make_client(
        [spec_payload(tmp_path), spec_payload(tmp_path, team_name="Docs Squad")],
        execution_engine=FakeExecutionEngine(),
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
        [spec_payload(tmp_path), spec_payload(tmp_path, team_name="Docs Squad")],
        execution_engine=FakeExecutionEngine(),
    )
    authored = {
        path
        for path in harness.client.get("/openapi.json").json()["paths"]
        if path.startswith("/api/")
    }

    responses = _exercise_every_route(harness.client, tmp_path, spec_payload)
    visited = {response.request.url.path for response in responses}

    assert authored <= {_template(path) for path in visited}


def test_the_templating_is_unambiguous():
    """A normaliser that collapses two distinct routes into one template would
    make the assertion above pass while covering less — Story 2.4 adds the
    first two routes in this app that share a segment count (both four
    segments under `/runs`) but are not the same route."""
    assert _template("/api/runs/teams/haiku_team") == "/api/runs/teams/{team_slug}"
    assert _template("/api/runs/some-run-id/transcript") == "/api/runs/{run_id}/transcript"
    assert _template("/api/runs/teams/haiku_team") != _template("/api/runs/some-run-id/transcript")
    assert _template("/api/runs/some-run-id") == "/api/runs/{run_id}"


def test_the_key_config_the_app_loaded_holds_only_sentinels(make_client):
    """Guards the guard: if isolation ever broke, every assertion above would
    be comparing against a real credential."""
    harness = make_client()

    key_config = harness.client.app.state.team_maker_api.key_config

    assert set(key_config.keys) == {"anthropic", "openai", "openrouter"}
    for provider, secret in key_config.keys.items():
        assert secret.get_secret_value() in SENTINEL_VALUES, provider
