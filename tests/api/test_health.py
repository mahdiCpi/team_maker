"""Task 1 proof of life: the app exists, serves, and exposes only what AC 2 authorises."""
from __future__ import annotations


def test_health_returns_200(make_client):
    client = make_client().client

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_authored_routes_are_exactly_the_ac2_set(make_client):
    """AC 2: "exposes exactly these authored routes and no more".

    FastAPI's generated `/docs`, `/redoc` and `/openapi.json` stay enabled on
    purpose — that generated schema is what Epic 4 will version — so they are
    excluded here rather than asserted absent.
    """
    client = make_client().client

    paths = client.get("/openapi.json").json()["paths"]
    authored = {
        (path, method.upper())
        for path, operations in paths.items()
        for method in operations
    }

    assert authored == {
        ("/api/health", "GET"),
        ("/api/compose/sessions", "POST"),
        ("/api/compose/sessions/{session_id}/messages", "POST"),
        ("/api/compose/sessions/{session_id}/spec", "PUT"),
        ("/api/compose/sessions/{session_id}/build", "POST"),
        # The key-status group, added by Story 2.3 as `epics.md:334`'s designated
        # first consumer. Both are GET: AD-9 means no endpoint here accepts a key.
        ("/api/keys/status", "GET"),
        ("/api/keys/check/{session_id}", "GET"),
    }


def test_unknown_path_still_uses_the_error_envelope(make_client):
    """AC 2: every non-2xx body is the envelope — including framework-level 404s."""
    client = make_client().client

    response = client.get("/api/does-not-exist")

    assert response.status_code == 404
    body = response.json()
    assert set(body) == {"error"}
    assert set(body["error"]) >= {"code", "message"}
