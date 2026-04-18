"""Unit tests for input schema validation."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from team_maker.schema.request import (
    DocumentationLevel,
    ProviderConfig,
    RoleDefinition,
    TeamCreationRequest,
    TeamTemplateId,
)


# ---------------------------------------------------------------------------
# TeamCreationRequest — happy paths
# ---------------------------------------------------------------------------


def test_minimal_valid_request():
    req = TeamCreationRequest(
        team_name="My Team",
        purpose="A team that does useful things across the platform.",
        output_path="/tmp/out",
        desired_roles=[
            RoleDefinition(name="architect", description="Designs architecture.")
        ],
    )
    assert req.team_name == "My Team"
    assert req.template == TeamTemplateId.SOFTWARE_DELIVERY
    assert req.documentation_level == DocumentationLevel.STANDARD
    assert req.overwrite is False


def test_full_valid_request():
    req = TeamCreationRequest(
        team_name="Full Team",
        purpose="A complete engineering team for building production software products.",
        output_path="/tmp/full_team",
        stack="Python, React",
        desired_roles=[
            RoleDefinition(name="architect", description="Designs architecture."),
            RoleDefinition(name="backend_engineer", description="Builds APIs."),
        ],
        default_llm=ProviderConfig(
            provider="anthropic",
            model="claude-sonnet-4-6",
            api_key_env="ANTHROPIC_API_KEY",
        ),
        overwrite=True,
        tags=["startup", "mvp"],
    )
    assert len(req.desired_roles) == 2
    assert req.default_llm is not None
    assert req.default_llm.provider == "anthropic"


def test_provider_name_normalised_to_lowercase():
    cfg = ProviderConfig(provider="Anthropic", model="claude-sonnet-4-6")
    assert cfg.provider == "anthropic"


def test_team_name_with_spaces_and_hyphens():
    req = TeamCreationRequest(
        team_name="Acme-Dev Team",
        purpose="Builds software products for Acme Corporation's platform.",
        output_path="/tmp/x",
        desired_roles=[RoleDefinition(name="architect", description="Designs things.")],
    )
    assert req.team_name == "Acme-Dev Team"


# ---------------------------------------------------------------------------
# TeamCreationRequest — validation failures
# ---------------------------------------------------------------------------


def test_missing_team_name_fails():
    with pytest.raises(ValidationError) as exc_info:
        TeamCreationRequest(
            purpose="Some purpose here that is long enough.",
            output_path="/tmp/x",
            desired_roles=[RoleDefinition(name="architect", description="Designs.")],
        )
    assert "team_name" in str(exc_info.value)


def test_too_short_purpose_fails():
    with pytest.raises(ValidationError):
        TeamCreationRequest(
            team_name="My Team",
            purpose="Too short",
            output_path="/tmp/x",
            desired_roles=[RoleDefinition(name="architect", description="Designs.")],
        )


def test_empty_desired_roles_fails():
    with pytest.raises(ValidationError):
        TeamCreationRequest(
            team_name="My Team",
            purpose="A long enough purpose statement for validation.",
            output_path="/tmp/x",
            desired_roles=[],
        )


def test_duplicate_role_names_fails():
    with pytest.raises(ValidationError) as exc_info:
        TeamCreationRequest(
            team_name="My Team",
            purpose="A long enough purpose statement for validation.",
            output_path="/tmp/x",
            desired_roles=[
                RoleDefinition(name="architect", description="First architect."),
                RoleDefinition(name="architect", description="Duplicate architect."),
            ],
        )
    assert "Duplicate role names" in str(exc_info.value)


def test_invalid_role_name_format_fails():
    with pytest.raises(ValidationError) as exc_info:
        RoleDefinition(name="My Role", description="A role with spaces in the name.")
    assert "snake_case" in str(exc_info.value)


def test_role_name_starting_with_digit_fails():
    with pytest.raises(ValidationError):
        RoleDefinition(name="1role", description="Starts with digit.")


def test_team_name_starting_with_digit_fails():
    with pytest.raises(ValidationError):
        TeamCreationRequest(
            team_name="123team",
            purpose="A long enough purpose for this validation check.",
            output_path="/tmp/x",
            desired_roles=[RoleDefinition(name="architect", description="Designs.")],
        )


def test_empty_output_path_fails():
    with pytest.raises(ValidationError):
        TeamCreationRequest(
            team_name="My Team",
            purpose="A long enough purpose for this validation check.",
            output_path="   ",
            desired_roles=[RoleDefinition(name="architect", description="Designs.")],
        )


# ---------------------------------------------------------------------------
# RoleDefinition
# ---------------------------------------------------------------------------


def test_role_display_name_defaults_to_title_case():
    role = RoleDefinition(name="backend_engineer", description="Builds APIs.")
    assert role.resolved_display_name == "Backend Engineer"


def test_role_display_name_explicit_override():
    role = RoleDefinition(
        name="backend_engineer",
        description="Builds APIs.",
        display_name="API Developer",
    )
    assert role.resolved_display_name == "API Developer"


def test_role_optional_flag_defaults_false():
    role = RoleDefinition(name="coordinator", description="Coordinates the team.")
    assert role.is_optional is False


def test_role_llm_override():
    role = RoleDefinition(
        name="architect",
        description="Designs architecture.",
        llm=ProviderConfig(provider="openai", model="gpt-4o"),
    )
    assert role.llm is not None
    assert role.llm.provider == "openai"
    assert role.llm.model == "gpt-4o"
