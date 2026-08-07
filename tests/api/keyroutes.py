"""Shared readers for the two key-route suites (Story 2.3).

Not a test module — no `test_` prefix, so pytest does not collect it. Split out when
`test_key_status.py` passed 700 lines, which is well past CLAUDE.md's ~200-400
guideline; the two suites answer different questions (what the machine has, versus
whether one team can run) and now live apart.
"""
from __future__ import annotations

STATUS_PATH = "/api/keys/status"


def statuses(body) -> dict[str, str]:
    return {p["name"]: p["status"] for p in body["providers"]}


def by_name(body, name: str) -> dict:
    return next(p for p in body["providers"] if p["name"] == name)


def start_session(harness, **authoring) -> str:
    payload: dict = {"intent": "docs team"}
    if authoring:
        payload["authoring"] = authoring
    response = harness.client.post("/api/compose/sessions", json=payload)
    assert response.status_code == 201, response.text
    return response.json()["session_id"]
