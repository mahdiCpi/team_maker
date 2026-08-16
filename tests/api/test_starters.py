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
        """Test that GET /api/starters returns both starter teams."""
        response = client.get("/api/starters")
        assert response.status_code == 200
        
        data = response.json()
        assert "starters" in data
        starters = data["starters"]
        
        # Should have both starter teams
        assert len(starters) == 2
        
        # Extract IDs for easier assertion
        starter_ids = {s["id"] for s in starters}
        assert "baseline_education_team" in starter_ids
        assert "research_content_team" in starter_ids

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
