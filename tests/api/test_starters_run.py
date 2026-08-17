"""Tests for the starter run endpoint (Story 3-2: Run and adapt a starter team).

Tests for POST /api/starters/{starter_id}/run endpoint.

`_load_and_build_starter` (`api/routers/starters.py`) builds each starter into
its YAML's own literal, relative `output_path` (e.g.
`./generated_teams/baseline_education_team`) — unlike the Composer's build
path, it never calls `derive_output_path`/`output_root()`, so
`TEAM_MAKER_OUTPUT_ROOT` (which `tests/api/conftest.py`'s autouse
`isolated_key_config` fixture already points at a `tmp_path`) has no effect on
where these tests actually write. `monkeypatch.chdir(tmp_path)` is what
isolates them instead — the relative path then resolves under `tmp_path`, not
the repo's real `generated_teams/`. A prior version of this file used its own
bare `TestClient` plus an autouse fixture that unconditionally
`shutil.rmtree`d the real, repo-relative `generated_teams/` directory before
and after every test — a real data-loss risk for any developer with local
build output sitting there, and it existed only because chdir isolation was
missing.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from team_maker.pipeline.runner import PipelineRunner
from team_maker.schema.request import TeamCreationRequest
from team_maker.utils.yaml_utils import load_yaml


@pytest.fixture
def repo_root() -> Path:
    """Return the repository root path (read-only use — locating `examples/`)."""
    return Path(__file__).resolve().parent.parent.parent


@pytest.fixture
def client(make_client, monkeypatch, tmp_path: Path) -> TestClient:
    """The shared `make_client` harness, chdir'd to `tmp_path` first.

    Order matters: `chdir` must happen before the app boots so every build
    this test triggers resolves its starter YAML's relative `output_path`
    under `tmp_path`, never the real repo root.
    """
    monkeypatch.chdir(tmp_path)
    return make_client().client


class TestStarterRun:
    """Tests for POST /api/starters/{starter_id}/run endpoint."""

    def test_run_starter_baseline_education(self, client: TestClient):
        """Test running the baseline education starter team."""
        response = client.post("/api/starters/baseline_education_team/run")

        # Should succeed
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "complete"
        assert "team_slug" in data
        assert data["team_slug"] == "baseline_education_team"
        assert data["team_name"] == "Baseline Education Team"

    def test_run_starter_research_content(self, client: TestClient):
        """Test running the research content starter team."""
        response = client.post("/api/starters/research_content_team/run")

        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "complete"
        assert data["team_slug"] == "research_content_team"
        assert data["team_name"] == "Research Content Team"

    def test_run_starter_not_found(self, client: TestClient):
        """Test that requesting a non-existent starter returns 404."""
        response = client.post("/api/starters/nonexistent/run")

        assert response.status_code == 404

        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "not_found"
        assert "nonexistent" in data["error"]["message"]

    def test_run_starter_idempotent(self, client: TestClient, tmp_path: Path):
        """Test that running the same starter twice produces byte-identical output (AC 1).

        This is the idempotency test explicitly assigned to Story 3.2 by
        deferred-work.md:333.
        """
        starter_id = "baseline_education_team"

        # First run
        response1 = client.post(f"/api/starters/{starter_id}/run")
        assert response1.status_code == 200
        data1 = response1.json()

        # Get the output path — under tmp_path (the `client` fixture chdir'd here).
        output_path = tmp_path / "generated_teams" / data1["team_slug"]
        assert output_path.exists()

        # Capture file contents from first run
        files1 = {}
        for path in sorted(output_path.rglob("*")):
            if path.is_file():
                # Skip timestamp-dependent files
                if path.name in ("generation_report.md", "team_config.yaml"):
                    continue
                relative = path.relative_to(output_path)
                files1[str(relative)] = path.read_bytes()

        # Second run (should be idempotent with overwrite=True)
        response2 = client.post(f"/api/starters/{starter_id}/run")
        assert response2.status_code == 200

        # Capture file contents from second run
        files2 = {}
        for path in sorted(output_path.rglob("*")):
            if path.is_file():
                if path.name in ("generation_report.md", "team_config.yaml"):
                    continue
                relative = path.relative_to(output_path)
                files2[str(relative)] = path.read_bytes()

        # Assert all non-timestamp files are byte-identical
        assert set(files1.keys()) == set(files2.keys()), \
            f"File sets differ: {set(files1.keys())} vs {set(files2.keys())}"

        for key in files1:
            assert files1[key] == files2[key], \
                f"File {key} differs between runs"

    def test_run_starter_produces_actual_files(self, client: TestClient, tmp_path: Path):
        """Test that running a starter actually produces files on disk."""
        response = client.post("/api/starters/baseline_education_team/run")
        assert response.status_code == 200

        data = response.json()
        output_path = tmp_path / "generated_teams" / data["team_slug"]

        assert output_path.exists()
        assert output_path.is_dir()

        # Check for expected files
        expected_files = [
            "README.md",
            "team_config.yaml",
            "run_example.py",
            "agents",
            "docs",
        ]
        for expected in expected_files:
            assert (output_path / expected).exists(), \
                f"Expected file/directory {expected} not found in {output_path}"


class TestStarterBuildDirect:
    """Tests that verify the starter YAMLs can be loaded and built directly."""

    def test_load_baseline_education_yaml(self, repo_root: Path):
        """Test that we can load the baseline education starter YAML."""
        yaml_path = repo_root / "examples" / "baseline_education_team_request.yaml"
        assert yaml_path.exists()

        raw = load_yaml(yaml_path)
        request = TeamCreationRequest(**raw)

        assert request.team_name == "Baseline Education Team"
        assert request.template_id == "baseline_education_team"
        assert len(request.desired_roles) > 0

    def test_load_research_content_yaml(self, repo_root: Path):
        """Test that we can load the research content starter YAML."""
        yaml_path = repo_root / "examples" / "research_content_team_request.yaml"
        assert yaml_path.exists()

        raw = load_yaml(yaml_path)
        request = TeamCreationRequest(**raw)

        assert request.team_name == "Research Content Team"
        assert request.template_id == "research_content_team"
        assert len(request.desired_roles) > 0

    def test_both_starters_build_with_overwrite(self, repo_root: Path, tmp_path):
        """Test that both starters can be built with overwrite=True (the Story 3-2 path)."""
        starters = [
            ("baseline_education_team_request.yaml", "baseline_education_team"),
            ("research_content_team_request.yaml", "research_content_team"),
        ]

        for yaml_file, expected_id in starters:
            yaml_path = repo_root / "examples" / yaml_file
            raw = load_yaml(yaml_path)
            request = TeamCreationRequest(**raw)

            # Force overwrite for idempotency (Story 3-2)
            request = request.model_copy(update={"overwrite": True})
            request.output_path = str(tmp_path / expected_id)

            result = PipelineRunner().run(request)

            # Should succeed
            assert result.output_path.exists()
            assert len(result.written_files) > 0
