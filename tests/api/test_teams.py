"""Tests for the teams routes (Story 2-5: Named teams — save, browse, rename, delete).

AC 1-4: Save, browse, rename, delete teams.
"""
from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_recent_teams():
    """`_recent_teams` is module-level global state, unrelated to the
    DB_PATH/SAVED_TEAMS_ROOT monkeypatching every test below does — without
    this, tests accumulate each other's recent-teams entries within one
    pytest process. Surfaced while adding this review's own `/recent` tests;
    it was latent before that too (any test asserting an exact recent-list
    length was one full-suite run away from failing depending on order)."""
    import api.routers.teams as teams_module

    teams_module._recent_teams = []
    yield
    teams_module._recent_teams = []


@pytest.fixture
def teams_data_dir(tmp_path) -> Path:
    """Create a temporary data directory for the teams database and storage."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    saved_teams_dir = data_dir / "saved_teams"
    saved_teams_dir.mkdir()
    return data_dir


@pytest.fixture
def sample_team_package(tmp_path) -> Path:
    """Create a minimal team package for testing."""
    team_dir = tmp_path / "sample_team"
    team_dir.mkdir()
    (team_dir / "team_config.yaml").write_text("team_name: sample\n")
    agents_dir = team_dir / "agents"
    agents_dir.mkdir()
    (agents_dir / "agent1.py").write_text("# Agent 1\n")
    tasks_dir = team_dir / "tasks"
    tasks_dir.mkdir()
    (tasks_dir / "task1.py").write_text("# Task 1\n")
    return team_dir


# ---------------------------------------------------------------------------
# Test: List teams (GET /api/teams)
# ---------------------------------------------------------------------------


def test_list_teams_empty(make_client, tmp_path, monkeypatch):
    """Empty database returns an empty list of teams.

    Isolated like every other test in this file (code review P9) — the
    original version of this test hit the real `./data/teams.db`, which is
    exactly what left an untracked `data/` directory in the working tree.
    """
    import api.routers.teams as teams_module
    original_db_path = teams_module.DB_PATH
    original_saved_path = teams_module.SAVED_TEAMS_ROOT

    new_db_path = tmp_path / "data" / "teams.db"
    new_saved_path = tmp_path / "data" / "saved_teams"
    new_saved_path.mkdir(parents=True, exist_ok=True)

    teams_module.DB_PATH = new_db_path
    teams_module.SAVED_TEAMS_ROOT = new_saved_path

    try:
        harness = make_client()
        response = harness.client.get("/api/teams")
        assert response.status_code == 200
        data = response.json()
        assert data["teams"] == []
    finally:
        teams_module.DB_PATH = original_db_path
        teams_module.SAVED_TEAMS_ROOT = original_saved_path


# ---------------------------------------------------------------------------
# Test: Save a team (POST /api/teams/save)
# ---------------------------------------------------------------------------


def test_save_team_happy_path(make_client, sample_team_package, tmp_path, monkeypatch):
    """Save a team with valid data."""
    # Point the teams router at the temp directory
    import api.routers.teams as teams_module
    original_db_path = teams_module.DB_PATH
    original_saved_path = teams_module.SAVED_TEAMS_ROOT
    
    new_db_path = tmp_path / "data" / "teams.db"
    new_saved_path = tmp_path / "data" / "saved_teams"
    new_saved_path.mkdir(parents=True, exist_ok=True)
    
    teams_module.DB_PATH = new_db_path
    teams_module.SAVED_TEAMS_ROOT = new_saved_path
    
    try:
        harness = make_client()
        
        payload = {
            "team_name": "My Test Team",
            "team_package_path": str(sample_team_package),
            "run_results": {"output": "test result"},
        }
        
        response = harness.client.post("/api/teams/save", json=payload)
        
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "My Test Team"
        assert data["message"] == "Team saved successfully."
        assert data["storage_path"].endswith("data\\saved_teams\\My Test Team") or data["storage_path"].endswith("data/saved_teams/My Test Team")
        
        # Verify files were copied
        saved_team_dir = new_saved_path / "My Test Team"
        assert saved_team_dir.exists()
        assert (saved_team_dir / "team_config.yaml").exists()
        assert (saved_team_dir / "agents" / "agent1.py").exists()
        
        # Verify run results were saved
        runs_dir = saved_team_dir / "runs"
        assert runs_dir.exists()
        assert len(list(runs_dir.iterdir())) > 0
        
    finally:
        teams_module.DB_PATH = original_db_path
        teams_module.SAVED_TEAMS_ROOT = original_saved_path


def test_save_team_duplicate_name(make_client, sample_team_package, tmp_path, monkeypatch):
    """Reject duplicate team names (case-insensitive)."""
    import api.routers.teams as teams_module
    original_db_path = teams_module.DB_PATH
    original_saved_path = teams_module.SAVED_TEAMS_ROOT
    
    new_db_path = tmp_path / "data" / "teams.db"
    new_saved_path = tmp_path / "data" / "saved_teams"
    new_saved_path.mkdir(parents=True, exist_ok=True)
    
    teams_module.DB_PATH = new_db_path
    teams_module.SAVED_TEAMS_ROOT = new_saved_path
    
    try:
        harness = make_client()
        
        # First save
        payload1 = {
            "team_name": "Test Team",
            "team_package_path": str(sample_team_package),
        }
        response1 = harness.client.post("/api/teams/save", json=payload1)
        assert response1.status_code == 201
        
        # Second save with same name (different case)
        payload2 = {
            "team_name": "test team",
            "team_package_path": str(sample_team_package),
        }
        response2 = harness.client.post("/api/teams/save", json=payload2)
        assert response2.status_code == 409
        assert response2.json()["error"]["code"] == "output_exists"
        
    finally:
        teams_module.DB_PATH = original_db_path
        teams_module.SAVED_TEAMS_ROOT = original_saved_path


def test_save_team_reserved_name(make_client, sample_team_package, tmp_path, monkeypatch):
    """Reject reserved team names."""
    import api.routers.teams as teams_module
    original_db_path = teams_module.DB_PATH
    original_saved_path = teams_module.SAVED_TEAMS_ROOT
    
    new_db_path = tmp_path / "data" / "teams.db"
    new_saved_path = tmp_path / "data" / "saved_teams"
    new_saved_path.mkdir(parents=True, exist_ok=True)
    
    teams_module.DB_PATH = new_db_path
    teams_module.SAVED_TEAMS_ROOT = new_saved_path
    
    try:
        harness = make_client()
        
        for reserved in ["starter", "example", "demo", "template", "sample"]:
            payload = {
                "team_name": reserved,
                "team_package_path": str(sample_team_package),
            }
            response = harness.client.post("/api/teams/save", json=payload)
            assert response.status_code == 400
            assert response.json()["error"]["code"] == "request_rejected"

    finally:
        teams_module.DB_PATH = original_db_path
        teams_module.SAVED_TEAMS_ROOT = original_saved_path


def test_save_team_short_name(make_client, sample_team_package, tmp_path, monkeypatch):
    """Reject team names that are too short (validated by Pydantic)."""
    import api.routers.teams as teams_module
    original_db_path = teams_module.DB_PATH
    original_saved_path = teams_module.SAVED_TEAMS_ROOT
    
    new_db_path = tmp_path / "data" / "teams.db"
    new_saved_path = tmp_path / "data" / "saved_teams"
    new_saved_path.mkdir(parents=True, exist_ok=True)
    
    teams_module.DB_PATH = new_db_path
    teams_module.SAVED_TEAMS_ROOT = new_saved_path
    
    try:
        harness = make_client()
        
        payload = {
            "team_name": "a",
            "team_package_path": str(sample_team_package),
        }
        response = harness.client.post("/api/teams/save", json=payload)
        # Pydantic validation rejects this before reaching our handler
        assert response.status_code == 422
        assert "team_name" in response.json()["error"]["fields"][0]["path"]
        
    finally:
        teams_module.DB_PATH = original_db_path
        teams_module.SAVED_TEAMS_ROOT = original_saved_path


# ---------------------------------------------------------------------------
# Test: Get a team (GET /api/teams/{team_name})
# ---------------------------------------------------------------------------


def test_get_team(make_client, sample_team_package, tmp_path, monkeypatch):
    """Get metadata for a saved team."""
    import api.routers.teams as teams_module
    original_db_path = teams_module.DB_PATH
    original_saved_path = teams_module.SAVED_TEAMS_ROOT
    
    new_db_path = tmp_path / "data" / "teams.db"
    new_saved_path = tmp_path / "data" / "saved_teams"
    new_saved_path.mkdir(parents=True, exist_ok=True)
    
    teams_module.DB_PATH = new_db_path
    teams_module.SAVED_TEAMS_ROOT = new_saved_path
    
    try:
        harness = make_client()
        
        # Save a team first
        payload = {
            "team_name": "Get Test Team",
            "team_package_path": str(sample_team_package),
        }
        harness.client.post("/api/teams/save", json=payload)
        
        # Get the team
        response = harness.client.get("/api/teams/Get Test Team")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Get Test Team"
        assert data["run_count"] == 0
        
    finally:
        teams_module.DB_PATH = original_db_path
        teams_module.SAVED_TEAMS_ROOT = original_saved_path


def test_get_team_not_found(make_client):
    """Return 404 for a non-existent team."""
    harness = make_client()
    response = harness.client.get("/api/teams/NonExistent")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Test: Rename a team (PUT /api/teams/rename)
# ---------------------------------------------------------------------------


def test_rename_team(make_client, sample_team_package, tmp_path, monkeypatch):
    """Rename a team successfully."""
    import api.routers.teams as teams_module
    original_db_path = teams_module.DB_PATH
    original_saved_path = teams_module.SAVED_TEAMS_ROOT
    
    new_db_path = tmp_path / "data" / "teams.db"
    new_saved_path = tmp_path / "data" / "saved_teams"
    new_saved_path.mkdir(parents=True, exist_ok=True)
    
    teams_module.DB_PATH = new_db_path
    teams_module.SAVED_TEAMS_ROOT = new_saved_path
    
    try:
        harness = make_client()
        
        # Save a team first
        payload = {
            "team_name": "Old Name",
            "team_package_path": str(sample_team_package),
        }
        harness.client.post("/api/teams/save", json=payload)
        
        # Rename the team
        rename_payload = {
            "old_name": "Old Name",
            "new_name": "New Name",
        }
        response = harness.client.put("/api/teams/rename", json=rename_payload)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "New Name"
        
        # Verify old name no longer exists
        response_old = harness.client.get("/api/teams/Old Name")
        assert response_old.status_code == 404
        
        # Verify new name exists
        response_new = harness.client.get("/api/teams/New Name")
        assert response_new.status_code == 200
        assert response_new.json()["name"] == "New Name"
        
    finally:
        teams_module.DB_PATH = original_db_path
        teams_module.SAVED_TEAMS_ROOT = original_saved_path


def test_rename_team_duplicate(make_client, sample_team_package, tmp_path, monkeypatch):
    """Reject rename to a duplicate name."""
    import api.routers.teams as teams_module
    original_db_path = teams_module.DB_PATH
    original_saved_path = teams_module.SAVED_TEAMS_ROOT
    
    new_db_path = tmp_path / "data" / "teams.db"
    new_saved_path = tmp_path / "data" / "saved_teams"
    new_saved_path.mkdir(parents=True, exist_ok=True)
    
    teams_module.DB_PATH = new_db_path
    teams_module.SAVED_TEAMS_ROOT = new_saved_path
    
    try:
        harness = make_client()
        
        # Save two teams
        for name in ["Team One", "Team Two"]:
            payload = {
                "team_name": name,
                "team_package_path": str(sample_team_package),
            }
            harness.client.post("/api/teams/save", json=payload)
        
        # Try to rename Team One to Team Two
        rename_payload = {
            "old_name": "Team One",
            "new_name": "Team Two",
        }
        response = harness.client.put("/api/teams/rename", json=rename_payload)
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "output_exists"
        
    finally:
        teams_module.DB_PATH = original_db_path
        teams_module.SAVED_TEAMS_ROOT = original_saved_path


def test_rename_team_reserved(make_client, sample_team_package, tmp_path, monkeypatch):
    """Reject rename to a reserved name."""
    import api.routers.teams as teams_module
    original_db_path = teams_module.DB_PATH
    original_saved_path = teams_module.SAVED_TEAMS_ROOT
    
    new_db_path = tmp_path / "data" / "teams.db"
    new_saved_path = tmp_path / "data" / "saved_teams"
    new_saved_path.mkdir(parents=True, exist_ok=True)
    
    teams_module.DB_PATH = new_db_path
    teams_module.SAVED_TEAMS_ROOT = new_saved_path
    
    try:
        harness = make_client()
        
        # Save a team
        payload = {
            "team_name": "Rename Test Team",
            "team_package_path": str(sample_team_package),
        }
        harness.client.post("/api/teams/save", json=payload)
        
        # Try to rename to reserved name
        rename_payload = {
            "old_name": "Rename Test Team",
            "new_name": "demo",
        }
        response = harness.client.put("/api/teams/rename", json=rename_payload)
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "request_rejected"

    finally:
        teams_module.DB_PATH = original_db_path
        teams_module.SAVED_TEAMS_ROOT = original_saved_path


# ---------------------------------------------------------------------------
# Test: Delete a team (DELETE /api/teams/{team_name})
# ---------------------------------------------------------------------------


def test_delete_team(make_client, sample_team_package, tmp_path, monkeypatch):
    """Delete a team and all its saved runs/results."""
    import api.routers.teams as teams_module
    original_db_path = teams_module.DB_PATH
    original_saved_path = teams_module.SAVED_TEAMS_ROOT
    
    new_db_path = tmp_path / "data" / "teams.db"
    new_saved_path = tmp_path / "data" / "saved_teams"
    new_saved_path.mkdir(parents=True, exist_ok=True)
    
    teams_module.DB_PATH = new_db_path
    teams_module.SAVED_TEAMS_ROOT = new_saved_path
    
    try:
        harness = make_client()
        
        # Save a team
        payload = {
            "team_name": "Delete Me",
            "team_package_path": str(sample_team_package),
            "run_results": {"output": "test"},
        }
        harness.client.post("/api/teams/save", json=payload)
        
        # Verify team exists
        response = harness.client.get("/api/teams/Delete Me")
        assert response.status_code == 200
        
        # Delete the team
        response = harness.client.delete("/api/teams/Delete Me")
        assert response.status_code == 200
        assert "deleted" in response.json()["message"].lower()
        
        # Verify team no longer exists
        response = harness.client.get("/api/teams/Delete Me")
        assert response.status_code == 404
        
        # Verify files were deleted
        saved_team_dir = new_saved_path / "Delete Me"
        assert not saved_team_dir.exists()
        
    finally:
        teams_module.DB_PATH = original_db_path
        teams_module.SAVED_TEAMS_ROOT = original_saved_path


def test_delete_team_not_found(make_client):
    """Return 404 when deleting a non-existent team."""
    harness = make_client()
    response = harness.client.delete("/api/teams/NonExistent")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Test: Recent teams (GET /api/teams/recent)
# ---------------------------------------------------------------------------


def test_recent_teams(make_client, sample_team_package, tmp_path, monkeypatch):
    """List recently accessed teams."""
    import api.routers.teams as teams_module
    original_db_path = teams_module.DB_PATH
    original_saved_path = teams_module.SAVED_TEAMS_ROOT
    
    new_db_path = tmp_path / "data" / "teams.db"
    new_saved_path = tmp_path / "data" / "saved_teams"
    new_saved_path.mkdir(parents=True, exist_ok=True)
    
    teams_module.DB_PATH = new_db_path
    teams_module.SAVED_TEAMS_ROOT = new_saved_path
    
    try:
        harness = make_client()
        
        # Save a team
        payload = {
            "team_name": "Recent Team",
            "team_package_path": str(sample_team_package),
        }
        harness.client.post("/api/teams/save", json=payload)
        
        # Get the team (adds to recent)
        harness.client.get("/api/teams/Recent Team")
        
        # List recent teams
        response = harness.client.get("/api/teams/recent")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Recent Team"

    finally:
        teams_module.DB_PATH = original_db_path
        teams_module.SAVED_TEAMS_ROOT = original_saved_path


# ---------------------------------------------------------------------------
# Test: Delete a team by query param (DELETE /api/teams/delete)
# ---------------------------------------------------------------------------


def test_delete_team_by_query_param(make_client, sample_team_package, tmp_path, monkeypatch):
    """The literal `/api/teams/delete` route (code review D1/P13) performs the
    same deletion as `DELETE /{team_name}`, addressed via a query parameter."""
    import api.routers.teams as teams_module
    original_db_path = teams_module.DB_PATH
    original_saved_path = teams_module.SAVED_TEAMS_ROOT

    new_db_path = tmp_path / "data" / "teams.db"
    new_saved_path = tmp_path / "data" / "saved_teams"
    new_saved_path.mkdir(parents=True, exist_ok=True)

    teams_module.DB_PATH = new_db_path
    teams_module.SAVED_TEAMS_ROOT = new_saved_path

    try:
        harness = make_client()

        payload = {
            "team_name": "Delete By Query",
            "team_package_path": str(sample_team_package),
        }
        harness.client.post("/api/teams/save", json=payload)

        response = harness.client.delete(
            "/api/teams/delete", params={"team_name": "Delete By Query"}
        )
        assert response.status_code == 200
        assert "deleted" in response.json()["message"].lower()

        response = harness.client.get("/api/teams/Delete By Query")
        assert response.status_code == 404

    finally:
        teams_module.DB_PATH = original_db_path
        teams_module.SAVED_TEAMS_ROOT = original_saved_path


def test_delete_team_by_query_param_not_found(make_client):
    """Return 404 when deleting a non-existent team via the query-param route."""
    harness = make_client()
    response = harness.client.delete("/api/teams/delete", params={"team_name": "NonExistent"})
    assert response.status_code == 404


def test_delete_team_by_query_param_missing_returns_422_not_500(make_client):
    """Regression for code review P4: `team_name` was made `str = None` only
    to satisfy Python's param-ordering rule once `Depends(authenticated_request)`
    was added, which silently turned this required query parameter into an
    optional one -- an omitted `team_name` crashed with an unhandled 500
    (`TypeError` in `safe_label`) instead of FastAPI's normal 422."""
    harness = make_client()
    response = harness.client.delete("/api/teams/delete")
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Test: Record a recent team without saving it (POST /api/teams/recent)
# ---------------------------------------------------------------------------


def test_add_recent_team_without_saving(make_client, tmp_path, monkeypatch):
    """Declining the save prompt still leaves a recent-teams entry (code
    review D2/P14) — the entry carries no DB-backed metadata."""
    import api.routers.teams as teams_module
    original_db_path = teams_module.DB_PATH
    original_saved_path = teams_module.SAVED_TEAMS_ROOT

    new_db_path = tmp_path / "data" / "teams.db"
    new_saved_path = tmp_path / "data" / "saved_teams"
    new_saved_path.mkdir(parents=True, exist_ok=True)

    teams_module.DB_PATH = new_db_path
    teams_module.SAVED_TEAMS_ROOT = new_saved_path

    try:
        harness = make_client()

        response = harness.client.post("/api/teams/recent", json={"team_name": "Never Saved"})
        assert response.status_code == 200

        response = harness.client.get("/api/teams/recent")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Never Saved"
        assert data[0]["run_count"] == 0
        assert data[0]["last_run_at"] is None

    finally:
        teams_module.DB_PATH = original_db_path
        teams_module.SAVED_TEAMS_ROOT = original_saved_path


def test_add_recent_team_rejects_reserved_name(make_client):
    """A reserved name cannot be smuggled into the recent list either."""
    harness = make_client()
    response = harness.client.post("/api/teams/recent", json={"team_name": "starter"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "request_rejected"


# ---------------------------------------------------------------------------
# Test: Record a re-run (POST /api/teams/{team_name}/record-run)
# ---------------------------------------------------------------------------


def test_record_team_run_updates_metadata(make_client, sample_team_package, tmp_path, monkeypatch):
    """Re-running a saved team updates `last_run_at`/`run_count` (code review
    D3/P15) — previously these were only ever set once, at save time."""
    import api.routers.teams as teams_module
    original_db_path = teams_module.DB_PATH
    original_saved_path = teams_module.SAVED_TEAMS_ROOT

    new_db_path = tmp_path / "data" / "teams.db"
    new_saved_path = tmp_path / "data" / "saved_teams"
    new_saved_path.mkdir(parents=True, exist_ok=True)

    teams_module.DB_PATH = new_db_path
    teams_module.SAVED_TEAMS_ROOT = new_saved_path

    try:
        harness = make_client()

        payload = {
            "team_name": "Rerun Team",
            "team_package_path": str(sample_team_package),
        }
        harness.client.post("/api/teams/save", json=payload)

        response = harness.client.post(
            "/api/teams/Rerun Team/record-run", json={"run_results": {"output": "second run"}}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["run_count"] == 1
        assert data["last_run_at"] is not None

        # A saved team with no prior run_results starts at run_count 0, so one
        # record-run call takes it to 1 — not 2.
        browse = harness.client.get("/api/teams/browse")
        browsed = next(t for t in browse.json()["teams"] if t["name"] == "Rerun Team")
        assert browsed["run_count"] == 1

    finally:
        teams_module.DB_PATH = original_db_path
        teams_module.SAVED_TEAMS_ROOT = original_saved_path


def test_record_team_run_not_found(make_client):
    """Return 404 when recording a run for a team that was never saved."""
    harness = make_client()
    response = harness.client.post("/api/teams/NonExistent/record-run", json={})
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Test: Security — team_name path traversal and team_package_path containment
# ---------------------------------------------------------------------------


def test_save_team_name_path_traversal_rejected(make_client, sample_team_package, tmp_path, monkeypatch):
    """A `team_name` containing path-traversal segments is rejected outright,
    never used as a filesystem path (code review P1)."""
    import api.routers.teams as teams_module
    original_db_path = teams_module.DB_PATH
    original_saved_path = teams_module.SAVED_TEAMS_ROOT

    new_db_path = tmp_path / "data" / "teams.db"
    new_saved_path = tmp_path / "data" / "saved_teams"
    new_saved_path.mkdir(parents=True, exist_ok=True)

    teams_module.DB_PATH = new_db_path
    teams_module.SAVED_TEAMS_ROOT = new_saved_path

    try:
        harness = make_client()
        payload = {
            "team_name": "../escaped",
            "team_package_path": str(sample_team_package),
        }
        response = harness.client.post("/api/teams/save", json=payload)
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "request_rejected"
        # Nothing escaped the sandboxed storage root.
        assert not (new_saved_path.parent / "escaped").exists()

    finally:
        teams_module.DB_PATH = original_db_path
        teams_module.SAVED_TEAMS_ROOT = original_saved_path


def test_save_team_package_path_outside_output_root_rejected(make_client, tmp_path, monkeypatch):
    """A `team_package_path` outside the generated-teams output root is
    rejected rather than copied and served back (code review P2)."""
    import api.routers.teams as teams_module
    original_db_path = teams_module.DB_PATH
    original_saved_path = teams_module.SAVED_TEAMS_ROOT

    new_db_path = tmp_path / "data" / "teams.db"
    new_saved_path = tmp_path / "data" / "saved_teams"
    new_saved_path.mkdir(parents=True, exist_ok=True)

    teams_module.DB_PATH = new_db_path
    teams_module.SAVED_TEAMS_ROOT = new_saved_path

    # A real directory that exists but sits entirely outside output_root()
    # (which the autouse `isolated_key_config` fixture points at `tmp_path`).
    outside_dir = Path(tempfile.mkdtemp())
    (outside_dir / "secret.txt").write_text("do not copy me")

    try:
        harness = make_client()
        payload = {
            "team_name": "Outside Team",
            "team_package_path": str(outside_dir),
        }
        response = harness.client.post("/api/teams/save", json=payload)
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "request_rejected"

    finally:
        teams_module.DB_PATH = original_db_path
        teams_module.SAVED_TEAMS_ROOT = original_saved_path
        shutil.rmtree(outside_dir, ignore_errors=True)
