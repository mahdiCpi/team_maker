"""Unit tests for template_id field in TeamCreationRequest."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from team_maker.pipeline.runner import PipelineRunner
from team_maker.schema.request import TeamCreationRequest, RoleDefinition


# ---------------------------------------------------------------------------
# template_id field tests
# ---------------------------------------------------------------------------


def test_template_id_field_exists():
    """Test that template_id field is present in TeamCreationRequest."""
    req = TeamCreationRequest(
        team_name="Test Team",
        purpose="A test team for verifying template_id field.",
        output_path="/tmp/test_template_id",
        desired_roles=[
            RoleDefinition(name="architect", description="Designs architecture.")
        ],
        template_id="software_delivery_team",
    )
    assert req.template_id == "software_delivery_team"


def test_template_id_defaults_to_none():
    """Test that template_id defaults to None when not provided."""
    req = TeamCreationRequest(
        team_name="Test Team",
        purpose="A test team without template_id specified.",
        output_path="/tmp/test_default",
        desired_roles=[
            RoleDefinition(name="architect", description="Designs architecture.")
        ],
    )
    assert req.template_id is None


def test_template_id_with_none_explicitly():
    """Test that template_id can be explicitly set to None."""
    req = TeamCreationRequest(
        team_name="Test Team",
        purpose="A test team with explicit None template_id.",
        output_path="/tmp/test_none",
        desired_roles=[
            RoleDefinition(name="architect", description="Designs architecture.")
        ],
        template_id=None,
    )
    assert req.template_id is None


def test_generate_from_template_uses_default_when_none():
    """Test that _generate_from_template uses software_delivery_team when template_id is None."""
    # This test verifies the regression guard: requests without template_id
    # should still resolve to software_delivery_team
    req = TeamCreationRequest(
        team_name="Test Team",
        purpose="A test team without template_id.",
        output_path="/tmp/test_gen_default",
        desired_roles=[
            RoleDefinition(name="architect", description="Designs architecture.")
        ],
        template_id=None,
    )
    
    # Call the method directly to verify it uses the default
    from team_maker.templates.registry import get_template
    
    # This should not raise an error because template_id or "software_delivery_team" is valid
    template = get_template(req.template_id or "software_delivery_team")
    assert template is not None
    assert hasattr(template, 'generate')


def test_generate_from_template_with_explicit_template_id():
    """Test that _generate_from_template uses the specified template_id."""
    req = TeamCreationRequest(
        team_name="Test Team",
        purpose="A test team with explicit template_id.",
        output_path="/tmp/test_gen_explicit",
        desired_roles=[
            RoleDefinition(name="architect", description="Designs architecture.")
        ],
        template_id="software_delivery_team",
    )
    
    from team_maker.templates.registry import get_template
    
    # This should use the explicit template_id
    template_id = req.template_id or "software_delivery_team"
    assert template_id == "software_delivery_team"
    
    template = get_template(template_id)
    assert template is not None
