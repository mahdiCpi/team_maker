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
        # The run group, added by Story 2.4 (`epics.md:335`). Declaration order
        # matters: `/teams/{team_slug}` is registered before `/{run_id}` so the
        # parameterised route cannot swallow it.
        ("/api/runs/teams/{team_slug}", "GET"),
        ("/api/runs", "POST"),
        ("/api/runs/{run_id}", "GET"),
        ("/api/runs/{run_id}/transcript", "GET"),
        # The teams group, added by Story 2.5 (Named teams — save, browse, rename, delete).
        ("/api/teams", "GET"),
        ("/api/teams/browse", "GET"),
        ("/api/teams/save", "POST"),
        ("/api/teams/rename", "PUT"),
        ("/api/teams/recent", "GET"),
        ("/api/teams/recent", "POST"),
        # `/delete` is the literal path the story's Technical Requirements
        # table documents; `/{team_name}` DELETE does the same thing
        # RESTfully (code review D1).
        ("/api/teams/delete", "DELETE"),
        ("/api/teams/{team_name}", "GET"),
        ("/api/teams/{team_name}", "DELETE"),
        # Lets Story 2-4's re-run flow keep last_run_at/run_count honest
        # (code review D3).
        ("/api/teams/{team_name}/record-run", "POST"),
    }


def test_unknown_path_still_uses_the_error_envelope(make_client):
    """AC 2: every non-2xx body is the envelope — including framework-level 404s."""
    client = make_client().client

    response = client.get("/api/does-not-exist")

    assert response.status_code == 404
    body = response.json()
    assert set(body) == {"error"}
    assert set(body["error"]) >= {"code", "message"}
