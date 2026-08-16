"""Shared helpers for the run-route suites (Story 2.4).

Not a test module — no `test_` prefix, so pytest does not collect it. Split
out up front, following the `keyroutes.py` precedent (Story 2.3, extracted
once `test_key_status.py` passed 700 lines): `test_run.py` and
`test_run_documents.py` both need a real Team Package on disk, and building
one inline in every test would duplicate the same five lines everywhere.
"""
from __future__ import annotations

import time
from pathlib import Path

from api.output import slugify_team_name
from team_maker.pipeline.runner import PipelineRunner
from team_maker.schema.request import RoleDefinition, TeamCreationRequest

_DEFAULT_ROLES = [
    RoleDefinition(
        name="architect",
        description="Designs system architecture and makes technical decisions.",
    )
]


def build_team(tmp_path: Path, *, team_name: str = "Test Team", roles=None) -> str:
    """Build a real, on-disk crewai Team Package and return its slug.

    Writes under `tmp_path`, which `isolated_key_config` (autouse,
    `tests/api/conftest.py`) has already pointed `TEAM_MAKER_OUTPUT_ROOT` at —
    so `output_root() / slug` resolves to exactly where this writes.
    """
    slug = slugify_team_name(team_name)
    request = TeamCreationRequest(
        team_name=team_name,
        purpose="A team built for the Story 2.4 run-route test suite.",
        output_path=str(tmp_path / slug),
        desired_roles=roles if roles is not None else _DEFAULT_ROLES,
    )
    PipelineRunner().run(request)
    return slug


def run_body(team_slug: str, goal: str = "ship it", documents: list | None = None) -> dict:
    body: dict = {"team_slug": team_slug, "goal": goal}
    if documents is not None:
        body["documents"] = documents
    return body


def poll_until_terminal(client, run_id: str, *, timeout: float = 5.0) -> dict:
    """Poll `GET /api/runs/{run_id}` until it leaves `running`.

    A run executes on a real background thread (`api/runs.py`), so a test
    that needs its terminal state cannot simply read it back synchronously
    after `POST`. Bounded, so a genuinely stuck run fails the test instead of
    hanging the suite.
    """
    deadline = time.monotonic() + timeout
    body = client.get(f"/api/runs/{run_id}").json()
    while body["status"] == "running" and time.monotonic() < deadline:
        time.sleep(0.01)
        body = client.get(f"/api/runs/{run_id}").json()
    assert body["status"] != "running", "run never reached a terminal status within the test timeout"
    return body
