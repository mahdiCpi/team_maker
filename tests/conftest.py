"""Shared pytest fixtures."""
from __future__ import annotations

import pytest
from team_maker.schema.request import (
    ProviderConfig,
    RoleDefinition,
    TeamCreationRequest,
    DocumentationLevel,
)


@pytest.fixture()
def minimal_request(tmp_path) -> TeamCreationRequest:
    """A minimal valid request with one role."""
    return TeamCreationRequest(
        team_name="Test Team",
        purpose="A team for running automated tests in CI/CD pipelines.",
        output_path=str(tmp_path / "output"),
        desired_roles=[
            RoleDefinition(
                name="architect",
                description="Designs system architecture and makes technical decisions.",
            )
        ],
    )


@pytest.fixture()
def full_request(tmp_path) -> TeamCreationRequest:
    """A full software delivery request with all standard roles."""
    return TeamCreationRequest(
        team_name="Acme Software Team",
        purpose=(
            "Build a software product end-to-end including architecture, coding, "
            "testing, and deployment guidance."
        ),
        output_path=str(tmp_path / "acme_team"),
        stack="Python, React, PostgreSQL",
        desired_roles=[
            RoleDefinition(
                name="architect",
                description="Designs system architecture.",
            ),
            RoleDefinition(
                name="backend_engineer",
                description="Implements backend services.",
            ),
            RoleDefinition(
                name="frontend_engineer",
                description="Implements user interfaces.",
            ),
            RoleDefinition(
                name="reviewer_qa",
                description="Reviews code and runs QA.",
            ),
            RoleDefinition(
                name="devops",
                description="Manages CI/CD and deployment.",
            ),
        ],
        default_llm=ProviderConfig(
            provider="anthropic",
            model="claude-sonnet-4-6",
            api_key_env="ANTHROPIC_API_KEY",
        ),
        documentation_level=DocumentationLevel.STANDARD,
        overwrite=True,
    )
