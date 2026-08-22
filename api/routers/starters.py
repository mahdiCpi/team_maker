"""Starter teams routes (Story 3-1: Ship baseline starter teams, Story 3-2: Run and adapt).

This router provides endpoints for listing and running starter teams shipped
with team_maker. Starter teams are static, checked-in content (curated
TeamCreationRequest YAMLs under examples/starters/), not user data. That
directory is dedicated to starters so discovery never mistakes an unrelated
CLI example config (e.g. examples/software_delivery_request.yaml) for one.

This is deliberately separate from api/routers/teams.py which handles
*saved* (user, DB-backed) teams, to avoid conflating the two models.

Story 3.2 additions: POST /starters/{starter_id}/run builds a starter on demand
and returns the team_slug needed to navigate to its Workspace.
"""
from __future__ import annotations

import logging
from functools import cache
from pathlib import Path
from typing import List

import yaml
from fastapi import APIRouter, Request
from pydantic import ValidationError

from api.build import run_build
from api.errors import NOT_FOUND, SPEC_INVALID, ApiError, log_and_wrap
from api.output import slugify_team_name
from api.schemas import StarterRunView, StarterTeamListView, StarterTeamView
from team_maker.schema.request import TeamCreationRequest
from team_maker.utils.text_sanitizer import secure_resolve_path

logger = logging.getLogger("api.starters")

router = APIRouter(prefix="/starters", tags=["starters"])

# Path to the dedicated starters directory, relative to the repo root. Kept
# separate from examples/ at large so discovery never sweeps in a general
# CLI usage example (which may coincidentally have team_name/purpose/
# output_path/template fields) and surfaces it as a starter team.
_STARTERS_DIR = Path(__file__).parent.parent.parent / "examples" / "starters"
# YAML file extensions to look for
_STARTER_YAML_EXTENSIONS = (".yaml", ".yml")


def _get_starters_dir() -> Path:
    """Get the starters directory with path traversal protection.

    This ensures that the starters directory path is resolved securely,
    preventing path traversal attacks via symlinks or manipulation.
    """
    return _STARTERS_DIR.resolve()


@cache
def _discover_starter_yamls() -> dict[str, str]:
    """Discover all starter YAML files from the starters directory.

    Returns a dictionary mapping template_id (extracted from YAML content) to filename.
    Results are cached for performance.
    """
    try:
        starters_dir = _get_starters_dir()

        if not starters_dir.exists():
            logger.warning("Starters directory not found: %s", starters_dir)
            return {}

        yaml_files = sorted(starters_dir.glob("*"))
    except OSError as e:
        logger.error("Could not scan starters directory: %s", e)
        return {}

    starter_map: dict[str, str] = {}

    # Find all YAML files in the starters directory
    for yaml_file in yaml_files:
        if yaml_file.suffix.lower() not in _STARTER_YAML_EXTENSIONS:
            continue
        
        # Skip non-files (directories, etc.)
        if not yaml_file.is_file():
            continue
        
        try:
            # Read the YAML to extract template_id
            with open(yaml_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            
            if not isinstance(data, dict):
                logger.warning("Skipping %s: not a valid YAML mapping", yaml_file.name)
                continue
            
            # Validate required fields for starter teams (Task 5 & 7)
            # All starter YAMLs must have team_name, purpose, and output_path
            missing_fields = []
            for field in ["team_name", "purpose", "output_path"]:
                if field not in data:
                    missing_fields.append(field)
            
            if missing_fields:
                logger.warning(
                    "Skipping %s: missing required fields: %s",
                    yaml_file.name, ", ".join(missing_fields)
                )
                continue
            
            # Try both template_id and template fields (for backwards compatibility)
            template_id = data.get("template_id") or data.get("template")
            
            if not template_id or not isinstance(template_id, str):
                logger.warning(
                    "Skipping %s: missing or invalid template_id/template field",
                    yaml_file.name
                )
                continue
            
            # Check for duplicate template_ids (Task 6)
            if template_id in starter_map:
                logger.error(
                    "Duplicate template_id '%s' found in %s and %s. "
                    "Each starter must have a unique template_id.",
                    template_id, starter_map[template_id], yaml_file.name
                )
                # Don't add the duplicate, keep the first one
                continue
            
            # Map template_id to filename
            starter_map[template_id] = yaml_file.name
            logger.debug("Discovered starter: %s -> %s", template_id, yaml_file.name)
            
        except yaml.YAMLError as e:
            # Task 8: Handle corrupt/empty YAMLs gracefully
            logger.error("Skipping %s: corrupt or invalid YAML: %s", yaml_file.name, e)
            continue
        except Exception as e:
            logger.error("Skipping %s: unexpected error: %s", yaml_file.name, e)
            continue
    
    if not starter_map:
        logger.warning("No valid starter YAML files found in %s", starters_dir)
    else:
        logger.info("Discovered %d starter YAML files", len(starter_map))

    return starter_map


# The single source of truth mapping a starter_id to its YAML filename.
# `api/schemas.py` and `api/routers/compose.py` read this directly rather than
# keeping a second copy — no circular import: this module imports only
# `api.build`/`api.errors`/`api.output`/`api.schemas`/`team_maker.schema.request`,
# none of which import back from here at module scope.
_STARTER_ID_TO_FILE: dict[str, str] = _discover_starter_yamls()


# Starter team YAML filenames, derived from the discovered map
_STARTER_YAMLS: List[str] = list(_STARTER_ID_TO_FILE.values())


def _load_starter_yaml(filename: str) -> TeamCreationRequest:
    """Load and validate a starter team YAML file."""
    # Use secure path resolution to prevent path traversal
    base_dir = _get_starters_dir()
    filepath = secure_resolve_path(base_dir, filename)
    
    if not filepath.exists():
        raise FileNotFoundError(
            f"Starter team YAML not found: {filepath}"
        )

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


# ---------------------------------------------------------------------------
# Starter Run (Story 3-2: Run and adapt a starter team)
# ---------------------------------------------------------------------------


def _get_starter_filename(starter_id: str) -> str:
    """Map a starter_id to its YAML filename.

    The starter_id matches the template_id in the YAML, which is derived from
    the filename (e.g., baseline_education_team_request.yaml -> baseline_education_team).
    """
    filename = _STARTER_ID_TO_FILE.get(starter_id)
    if filename is None:
        raise FileNotFoundError(f"Unknown starter_id: {starter_id}")
    return filename


def _load_and_build_starter(starter_id: str) -> tuple[str, str]:
    """Load a starter's TeamCreationRequest, build it, and return (team_slug, team_name).

    Reuses _load_starter_yaml and api/build.py::run_build. Forces overwrite=True
    to ensure idempotent rebuilds succeed (Story 3-2 Task 1).

    Returns:
        A tuple of (team_slug, team_name) for navigation.

    Raises:
        FileNotFoundError: if the starter_id is unknown or YAML is missing.
        ApiError: with BUILD_FAILED or OUTPUT_EXISTS codes from run_build.
    """
    filename = _get_starter_filename(starter_id)
    request = _load_starter_yaml(filename)

    # Force overwrite=True for idempotent builds (Story 3-2)
    request = request.model_copy(update={"overwrite": True})

    # Build the starter - this may raise ApiError from run_build
    run_build(request)

    team_slug = slugify_team_name(request.team_name)
    return team_slug, request.team_name


@router.post("/{starter_id}/run", response_model=StarterRunView)
def run_starter(request: Request, starter_id: str) -> StarterRunView:
    """Build a starter team's package and return its slug for navigation.

    This endpoint builds the starter if not already built (idempotently —
    rebuilds produce byte-identical content), and returns the team_slug
    needed to navigate to the Workspace (/teams/{slug}).

    The starter must exist in the curated YAML list; unknown starter_id
    returns 404. A discovered starter YAML that fails schema validation
    returns 422 rather than an unhandled 500. Build failures map to the
    same error codes run_build already uses (OUTPUT_EXISTS, BUILD_FAILED).

    Story 3-2, Task 1.
    """
    try:
        team_slug, team_name = _load_and_build_starter(starter_id)
    except FileNotFoundError as exc:
        available = ", ".join(sorted(_STARTER_ID_TO_FILE))
        raise ApiError(
            NOT_FOUND,
            f"Starter team '{starter_id}' not found. Available starters: {available}",
        ) from exc
    except (ValidationError, yaml.YAMLError) as exc:
        raise log_and_wrap(
            SPEC_INVALID,
            f"Starter team '{starter_id}' has an invalid definition and cannot be run.",
            exc,
        ) from exc

    return StarterRunView(
        team_slug=team_slug,
        team_name=team_name,
    )
