"""Authentication guards for the teams API (Story 4.1 AC 6, code review D1/D2).

Every assertion here was written against the pre-review behaviour first: the
teams routes previously authenticated everyone when `TEAM_MAKER_API_KEY` was
unset, and additionally accepted the key via an `api_key` query parameter
that routinely lands in access/proxy logs. Both are closed here.

`make_client()` sets a valid `X-API-Key` header by default (`tests/api/conftest.py`)
so every other teams test keeps authenticating without changes; the tests
below override or remove that header to exercise the unauthenticated paths.
"""
from __future__ import annotations

from tests.api.conftest import TEST_API_KEY


def test_missing_credentials_are_rejected(make_client):
    """No key at all -> 401, not a silent pass."""
    harness = make_client()

    response = harness.client.get("/api/teams", headers={"X-API-Key": ""})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_required"


def test_wrong_api_key_is_rejected(make_client):
    harness = make_client()

    response = harness.client.get("/api/teams", headers={"X-API-Key": "not-the-right-key"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_required"


def test_valid_api_key_via_bearer_header_authenticates(make_client):
    """The header-only fallback: `Authorization: Bearer <key>` works even
    though the default test header is `X-API-Key`."""
    harness = make_client()

    response = harness.client.get(
        "/api/teams",
        headers={"X-API-Key": "", "Authorization": f"Bearer {TEST_API_KEY}"},
    )

    assert response.status_code == 200


def test_empty_bearer_token_does_not_authenticate(make_client):
    """Regression for code review P: an empty `Authorization: Bearer` header
    must not be treated as "no attempt made" and silently pass, nor crash."""
    harness = make_client()

    response = harness.client.get(
        "/api/teams",
        headers={"X-API-Key": "", "Authorization": "Bearer "},
    )

    assert response.status_code == 401


def test_query_string_api_key_no_longer_authenticates(make_client):
    """Regression for code review D2: the query-string `api_key` path was
    removed entirely because query strings land in access/proxy logs,
    contradicting AD-9's "keys must never be logged"."""
    harness = make_client()

    response = harness.client.get(
        "/api/teams", params={"api_key": TEST_API_KEY}, headers={"X-API-Key": ""}
    )

    assert response.status_code == 401


def test_missing_server_configuration_fails_closed(make_client, monkeypatch):
    """Regression for code review D1: with `TEAM_MAKER_API_KEY` unset on the
    server, every request must be rejected -- not silently authenticated
    because "no key configured" used to mean "auth disabled"."""
    monkeypatch.delenv("TEAM_MAKER_API_KEY", raising=False)
    harness = make_client()

    # Sent anyway, to prove a client-supplied key cannot satisfy a check that
    # has nothing configured to compare it against.
    response = harness.client.get("/api/teams", headers={"X-API-Key": TEST_API_KEY})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_required"


def test_every_teams_route_requires_authentication(make_client):
    """Sweep: every route in the teams router rejects an unauthenticated
    request, not just the ones exercised individually above. Bodies are
    schema-valid so a 401 can only come from the auth dependency, never from
    body validation running first."""
    harness = make_client()
    no_auth = {"X-API-Key": ""}

    calls = [
        ("GET", "/api/teams", None),
        ("GET", "/api/teams/browse", None),
        ("GET", "/api/teams/recent", None),
        ("POST", "/api/teams/recent", {"team_name": "Some Team"}),
        ("GET", "/api/teams/SomeTeam", None),
        ("POST", "/api/teams/save", {"team_name": "Some Team", "team_package_path": "/nonexistent"}),
        ("PUT", "/api/teams/rename", {"old_name": "Old Name", "new_name": "New Name"}),
        ("DELETE", "/api/teams/delete?team_name=SomeTeam", None),
        ("DELETE", "/api/teams/SomeTeam", None),
        ("POST", "/api/teams/SomeTeam/record-run", {}),
    ]
    for method, path, body in calls:
        response = harness.client.request(method, path, headers=no_auth, json=body)
        assert response.status_code == 401, f"{method} {path} did not require authentication"
