"""Tests for the starters routes (Story 3-1: Ship baseline starter teams).

AC 4: GET /api/starters endpoint lists both starter teams.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import create_app


@pytest.fixture
def client() -> TestClient:
    """Create a test client for the API."""
    return TestClient(create_app())


class TestStartersListing:
    """Tests for GET /api/starters endpoint."""

    def test_list_starters_returns_both_teams(self, client: TestClient):
        """Test that GET /api/starters returns all discovered starter teams.

        Starters are dynamically discovered from examples/starters/ (a
        directory dedicated to curated starter YAMLs, separate from general
        example configs elsewhere under examples/), so this asserts on the
        two starter YAMLs actually checked into that directory.
        """
        response = client.get("/api/starters")
        assert response.status_code == 200

        data = response.json()
        assert "starters" in data
        starters = data["starters"]

        assert len(starters) == 2

        starter_ids = {s["id"] for s in starters}
        assert starter_ids == {"baseline_education_team", "research_content_team"}

    def test_list_starters_returns_expected_fields(self, client: TestClient):
        """Test that each starter has the expected fields."""
        response = client.get("/api/starters")
        assert response.status_code == 200
        
        data = response.json()
        starters = data["starters"]
        
        for starter in starters:
            # Check all required fields are present
            assert "id" in starter
            assert "name" in starter
            assert "purpose" in starter
            assert "template_id" in starter
            assert "agent_count" in starter
            
            # Check types
            assert isinstance(starter["id"], str)
            assert isinstance(starter["name"], str)
            assert isinstance(starter["purpose"], str)
            assert isinstance(starter["template_id"], str)
            assert isinstance(starter["agent_count"], int)
            
            # Check non-empty
            assert starter["id"]
            assert starter["name"]
            assert starter["purpose"]
            assert starter["template_id"]
            assert starter["agent_count"] > 0

    def test_list_starters_education_team_details(self, client: TestClient):
        """Test that the education team starter has correct details."""
        response = client.get("/api/starters")
        assert response.status_code == 200
        
        data = response.json()
        starters = data["starters"]
        
        edu_team = next(
            (s for s in starters if s["id"] == "baseline_education_team"),
            None
        )
        
        assert edu_team is not None
        assert edu_team["name"] == "Baseline Education Team"
        assert "education" in edu_team["purpose"].lower()
        assert edu_team["template_id"] == "baseline_education_team"
        assert edu_team["agent_count"] == 3  # researcher, tutor, clarity_reviewer

    def test_list_starters_research_team_details(self, client: TestClient):
        """Test that the research team starter has correct details."""
        response = client.get("/api/starters")
        assert response.status_code == 200
        
        data = response.json()
        starters = data["starters"]
        
        research_team = next(
            (s for s in starters if s["id"] == "research_content_team"),
            None
        )
        
        assert research_team is not None
        assert research_team["name"] == "Research Content Team"
        assert "research" in research_team["purpose"].lower()
        assert research_team["template_id"] == "research_content_team"
        assert research_team["agent_count"] == 4  # researcher, writer, fact_checker, editor


class TestStarterDetail:
    """Tests for GET /api/starters/{starter_id} endpoint."""

    def test_get_starter_by_id_education(self, client: TestClient):
        """Test getting a specific starter by ID."""
        response = client.get("/api/starters/baseline_education_team")
        assert response.status_code == 200
        
        data = response.json()
        assert data["id"] == "baseline_education_team"
        assert data["name"] == "Baseline Education Team"
        assert data["template_id"] == "baseline_education_team"

    def test_get_starter_by_id_research(self, client: TestClient):
        """Test getting the research starter by ID."""
        response = client.get("/api/starters/research_content_team")
        assert response.status_code == 200
        
        data = response.json()
        assert data["id"] == "research_content_team"
        assert data["name"] == "Research Content Team"

    def test_get_starter_not_found(self, client: TestClient):
        """Test that requesting a non-existent starter returns 404 with proper error envelope."""
        response = client.get("/api/starters/nonexistent_team")
        assert response.status_code == 404
        
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "not_found"
        assert "nonexistent_team" in data["error"]["message"]
        assert "baseline_education_team" in data["error"]["message"]
        assert "research_content_team" in data["error"]["message"]


# ---------------------------------------------------------------------------
# Path traversal security (Story 4.6 Task 4)
# ---------------------------------------------------------------------------


class TestStarterPathTraversal:
    """Tests for path traversal prevention in starter router (Story 4.6 Task 4)."""

    def test_secure_resolve_path_prevents_traversal(self, tmp_path):
        """Test that secure_resolve_path prevents directory traversal attempts.
        
        This verifies the underlying security function used by the starter router.
        """
        from team_maker.utils.text_sanitizer import secure_resolve_path
        from pathlib import Path
        import pytest
        
        base_dir = tmp_path / "examples"
        base_dir.mkdir()
        
        # Valid path should work
        result = secure_resolve_path(base_dir, "valid.yaml")
        assert result == base_dir / "valid.yaml"
        
        # Traversal attempts should be rejected
        with pytest.raises(ValueError, match="traversal components"):
            secure_resolve_path(base_dir, "../etc/passwd")
        
        with pytest.raises(ValueError, match="traversal components"):
            secure_resolve_path(base_dir, "../../../etc/passwd")
        
        # Absolute paths should be rejected. `os.path.isabs("/etc/passwd")` is
        # True on POSIX (raises "Path is absolute") but False on Windows,
        # where it falls through to the "escapes base directory" check
        # instead — so the expected message differs by platform.
        import os
        if os.name == "nt":  # Windows
            with pytest.raises(ValueError, match="escapes base directory"):
                secure_resolve_path(base_dir, "/etc/passwd")
        else:  # POSIX
            with pytest.raises(ValueError, match="absolute"):
                secure_resolve_path(base_dir, "/etc/passwd")

        # UNC paths are caught by the Windows-path regex, which matches on the
        # literal leading "\\\\" regardless of host OS (not by os.path.isabs,
        # which is OS-dependent) — same message on every platform.
        with pytest.raises(ValueError, match="absolute"):
            secure_resolve_path(base_dir, "\\\\server\\share")

    def test_starter_yaml_path_stays_within_examples(self, tmp_path, monkeypatch):
        """Test that starter YAML loading stays within the examples directory.
        
        This verifies that the starter router cannot be tricked into reading
        files outside the examples directory via path traversal.
        """
        from api.routers.starters import _load_starter_yaml
        from pathlib import Path
        import pytest
        
        # Create a test examples directory
        examples_dir = tmp_path / "examples"
        examples_dir.mkdir()
        
        # Create a valid starter YAML in examples
        valid_yaml = examples_dir / "test.yaml"
        valid_yaml.write_text("""template_id: baseline_education_team
team_name: Test
purpose: Test purpose
output_path: /tmp/test
desired_roles: []
""")
        
        # Mock _get_starters_dir to return our test directory
        monkeypatch.setattr("api.routers.starters._get_starters_dir", lambda: examples_dir)
        
        # Valid file should load successfully
        result = _load_starter_yaml("test.yaml")
        assert result.template_id == "baseline_education_team"
        
        # Attempt to load file outside examples directory should fail
        # Path traversal is caught by the traversal components check
        with pytest.raises(ValueError, match="traversal components"):
            _load_starter_yaml("../etc/passwd")
        
        with pytest.raises(ValueError, match="traversal components"):
            _load_starter_yaml("../escape.yaml")

    def test_malicious_filename_rejected(self, tmp_path, monkeypatch):
        """Test that various malicious filename patterns are rejected."""
        from api.routers.starters import _load_starter_yaml
        from pathlib import Path
        import pytest
        
        examples_dir = tmp_path / "examples"
        examples_dir.mkdir()
        
        monkeypatch.setattr("api.routers.starters._get_starters_dir", lambda: examples_dir)
        
        # Test path traversal with ../
        with pytest.raises(ValueError, match="traversal components"):
            _load_starter_yaml("../etc/passwd")
        
        # Test path traversal with subdir/../../
        with pytest.raises(ValueError, match="traversal components"):
            _load_starter_yaml("subdir/../../etc/passwd")
        
        # Test absolute path
        with pytest.raises(ValueError):
            _load_starter_yaml("/etc/passwd")
        
        # Test Windows path traversal
        with pytest.raises(ValueError, match="traversal components"):
            _load_starter_yaml("..\\windows\\system32")


# ---------------------------------------------------------------------------
# Duplicate template ID prevention (Story 4.6 Task 6)
# YAML structure validation (Story 4.6 Task 5)
# YAML error handling (Story 4.6 Task 8)
# ---------------------------------------------------------------------------


class TestYamlValidationAndErrorHandling:
    """Tests for YAML validation, duplicate prevention, and error handling (Tasks 5, 6, 8).

    Each test exercises the real `_discover_starter_yamls()` against a temp
    directory (not a reimplementation of its logic), so a regression in the
    production function actually fails these tests.
    """

    @pytest.fixture(autouse=True)
    def _isolate_discovery_cache(self, tmp_path, monkeypatch):
        """Point discovery at a temp dir and reset its cache before and after.

        `_discover_starter_yamls` is `functools.cache`d with no arguments, so
        without this, whichever directory it saw first (real or a previous
        test's temp dir) would stick for the rest of the process.
        """
        from api.routers.starters import _discover_starter_yamls

        starters_dir = tmp_path / "starters"
        starters_dir.mkdir()
        monkeypatch.setattr("api.routers.starters._get_starters_dir", lambda: starters_dir)
        _discover_starter_yamls.cache_clear()
        yield starters_dir
        _discover_starter_yamls.cache_clear()

    def test_duplicate_template_id_handled_gracefully(self, _isolate_discovery_cache):
        """Test that duplicate template_ids are detected and handled gracefully (Task 6)."""
        from api.routers.starters import _discover_starter_yamls

        starters_dir = _isolate_discovery_cache

        (starters_dir / "first.yaml").write_text(
            "template_id: duplicate_id\n"
            "team_name: First Team\n"
            "purpose: First purpose\n"
            "output_path: /tmp/first\n"
        )
        (starters_dir / "second.yaml").write_text(
            "template_id: duplicate_id\n"
            "team_name: Second Team\n"
            "purpose: Second purpose\n"
            "output_path: /tmp/second\n"
        )
        (starters_dir / "third.yaml").write_text(
            "template_id: unique_id\n"
            "team_name: Third Team\n"
            "purpose: Third purpose\n"
            "output_path: /tmp/third\n"
        )

        starter_map = _discover_starter_yamls()

        # Alphabetically-first file wins for the duplicate id; the unique id
        # is always included.
        assert starter_map == {"duplicate_id": "first.yaml", "unique_id": "third.yaml"}

    def test_missing_required_fields_detected(self, _isolate_discovery_cache):
        """Test that YAMLs missing required fields are excluded (Task 5)."""
        from api.routers.starters import _discover_starter_yamls

        starters_dir = _isolate_discovery_cache

        # Missing team_name, purpose, output_path entirely.
        (starters_dir / "incomplete.yaml").write_text("template_id: test_id\n")
        (starters_dir / "complete.yaml").write_text(
            "template_id: complete_id\n"
            "team_name: Complete Team\n"
            "purpose: Complete purpose\n"
            "output_path: /tmp/complete\n"
        )

        starter_map = _discover_starter_yamls()

        assert starter_map == {"complete_id": "complete.yaml"}

    def test_corrupt_yaml_detected(self, _isolate_discovery_cache):
        """Test that corrupt YAMLs are skipped without failing the other files (Task 8)."""
        from api.routers.starters import _discover_starter_yamls

        starters_dir = _isolate_discovery_cache

        (starters_dir / "corrupt.yaml").write_text("template_id: test\nteam_name: [invalid")
        (starters_dir / "valid.yaml").write_text(
            "template_id: valid_id\n"
            "team_name: Valid Team\n"
            "purpose: Valid purpose\n"
            "output_path: /tmp/valid\n"
        )

        starter_map = _discover_starter_yamls()

        assert starter_map == {"valid_id": "valid.yaml"}

    def test_empty_yaml_detected(self, _isolate_discovery_cache):
        """Test that empty YAMLs are skipped without failing the other files (Task 8)."""
        from api.routers.starters import _discover_starter_yamls

        starters_dir = _isolate_discovery_cache

        (starters_dir / "empty.yaml").write_text("")
        (starters_dir / "valid.yaml").write_text(
            "template_id: valid_id\n"
            "team_name: Valid Team\n"
            "purpose: Valid purpose\n"
            "output_path: /tmp/valid\n"
        )

        starter_map = _discover_starter_yamls()

        assert starter_map == {"valid_id": "valid.yaml"}
