"""Starter teams routes (Story 3-1: Ship baseline starter teams).

This router provides a read-only endpoint that lists the starter teams shipped
with team_maker. Starter teams are static, checked-in content (the two curated
TeamCreationRequest YAMLs under examples/), not user data.

This is deliberately separate from api/routers/teams.py which handles
*saved* (user, DB-backed) teams, to avoid conflating the two models.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import List

from fastapi import APIRouter, Request

from api.errors import ApiError, NOT_FOUND
from api.schemas import StarterTeamListView, StarterTeamView
from team_maker.schema.request import TeamCreationRequest

logger = logging.getLogger("api.starters")

router = APIRouter(prefix="/starters", tags=["starters"])

# Path to the examples directory relative to the repo root
_EXAMPLES_DIR = Path(__file__).parent.parent.parent / "examples"

# Starter team YAML filenames
_STARTER_YAMLS = [
    "baseline_education_team_request.yaml",
    "research_content_team_request.yaml",
]


def _load_starter_yaml(filename: str) -> TeamCreationRequest:
    """Load and validate a starter team YAML file."""
    filepath = _EXAMPLES_DIR / filename
    if not filepath.exists():
        raise FileNotFoundError(
            f"Starter team YAML not found: {filepath}"
        )
    
    import yaml
    with open(filepath, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    
    # Validate against the TeamCreationRequest schema
    return TeamCreationRequest.model_validate(data)


def _get_starter_teams() -> List[StarterTeamView]:
    """Load all starter teams from their YAML files and return view models.
    
    This endpoint never builds a package and never touches the filesystem beyond
    reading the two source YAMLs — building is Story 3.2's job.
    """
    starters = []
    for yaml_file in _STARTER_YAMLS:
        try:
            request = _load_starter_yaml(yaml_file)
            # Extract the template_id from the YAML
            # The filename is like "baseline_education_team_request.yaml"
            # The template_id in the YAML is "baseline_education_team"
            template_id = request.template_id
            
            starters.append(
                StarterTeamView(
                    id=template_id,
                    name=request.team_name,
                    purpose=request.purpose,
                    template_id=template_id,
                    agent_count=len(request.desired_roles),
                )
            )
        except FileNotFoundError:
            logger.warning("Starter team YAML not found: %s", yaml_file)
            continue
        except Exception as e:
            logger.error("Failed to load starter team %s: %s", yaml_file, e)
            continue
    
    return starters


@router.get("", response_model=StarterTeamListView)
def list_starters() -> StarterTeamListView:
    """List all available starter teams.
    
    Returns metadata for all starter teams shipped with team_maker.
    Starter teams are concrete curated TeamCreationRequest YAMLs checked
    into the repo, validated against the factory Pydantic schema.
    
    This is a read-only endpoint — it never builds packages or modifies
    any state. Building a starter into a package is Story 3.2's job.
    """
    starters = _get_starter_teams()
    return StarterTeamListView(starters=starters)


@router.get("/{starter_id}", response_model=StarterTeamView)
def get_starter(request: Request, starter_id: str) -> StarterTeamView:
    """Get metadata for a specific starter team by ID."""
    starters = _get_starter_teams()
    starter_dict = {s.id: s for s in starters}
    
    if starter_id not in starter_dict:
        available = ", ".join(sorted(starter_dict.keys()))
        raise ApiError(
            NOT_FOUND,
            f"Starter team '{starter_id}' not found. Available starters: {available}",
        )
    
    return starter_dict[starter_id]
