"""Integration tests for starter teams (Story 3.1, Task 8, AC 3).

Proves both example YAMLs build to passing PipelineResult.validation.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from team_maker.pipeline.runner import PipelineRunner, PipelineResult
from team_maker.schema.request import TeamCreationRequest
from team_maker.utils.yaml_utils import load_yaml


# ---------------------------------------------------------------------------
# Fixture: repo root path
# ---------------------------------------------------------------------------


@pytest.fixture
def repo_root() -> Path:
    """Return the repository root path."""
    return Path(__file__).resolve().parent.parent.parent


def _authorize_risky_tools(monkeypatch, tmp_path, *tool_names: str) -> None:
    """Phase 7's validator checks RISKY-tool authorization (FR-037), denied
    by default (FR-052) absent an operator policy. These tests are about
    starter-team build mechanics, not authorization semantics, so they
    authorize what the fixture's roles declare — `research_content_team`'s
    `writer` role declares `code_writer` — exactly as a real operator
    enabling their starter template would."""
    policy_file = tmp_path / "team_maker.tools.yaml"
    enabled = "\n".join(f"  - {name}" for name in tool_names)
    policy_file.write_text(f"enabled_tools:\n{enabled}\n", encoding="utf-8")
    monkeypatch.setenv("TEAM_MAKER_TOOL_POLICY", str(policy_file))


# ---------------------------------------------------------------------------
# Fixture: load example YAMLs
# ---------------------------------------------------------------------------


@pytest.fixture
def baseline_education_request(repo_root: Path) -> TeamCreationRequest:
    """Load the baseline education team request from examples/."""
    yaml_path = repo_root / "examples" / "starters" / "baseline_education_team_request.yaml"
    raw = load_yaml(yaml_path)
    return TeamCreationRequest(**raw)


@pytest.fixture
def research_content_request(repo_root: Path) -> TeamCreationRequest:
    """Load the research content team request from examples/."""
    yaml_path = repo_root / "examples" / "starters" / "research_content_team_request.yaml"
    raw = load_yaml(yaml_path)
    return TeamCreationRequest(**raw)


# ---------------------------------------------------------------------------
# Tests: Pipeline validation passes for both starter teams
# ---------------------------------------------------------------------------


def test_baseline_education_team_builds_and_validates(
    baseline_education_request: TeamCreationRequest, tmp_path
) -> None:
    """AC 3: baseline_education_team_request.yaml builds to a valid package.
    
    Given the curated baseline education team YAML,
    when loaded, validated against TeamCreationRequest, and run through
    PipelineRunner().run(),
    then it produces a PipelineResult whose validation.passed is True.
    """
    # Point output to temp directory to avoid filesystem conflicts
    baseline_education_request.output_path = str(tmp_path / "baseline_education_team")
    baseline_education_request.overwrite = True
    
    runner = PipelineRunner()
    result: PipelineResult = runner.run(baseline_education_request)
    
    # AC 3: validation.passed must be True
    assert result.validation.passed, (
        f"Baseline education team validation failed with issues: {result.validation.issues}"
    )
    
    # Sanity checks: the pipeline ran and produced output
    assert result.output_path.exists()
    assert len(result.written_files) > 0
    
    # Confirm it used the correct template
    assert result.team.template_used == "baseline_education_team"


def test_research_content_team_builds_and_validates(
    research_content_request: TeamCreationRequest, tmp_path, monkeypatch
) -> None:
    """AC 3: research_content_team_request.yaml builds to a valid package.

    Given the curated research/content team YAML,
    when loaded, validated against TeamCreationRequest, and run through
    PipelineRunner().run(),
    then it produces a PipelineResult whose validation.passed is True.
    """
    _authorize_risky_tools(monkeypatch, tmp_path, "code_writer")
    # Point output to temp directory to avoid filesystem conflicts
    research_content_request.output_path = str(tmp_path / "research_content_team")
    research_content_request.overwrite = True
    
    runner = PipelineRunner()
    result: PipelineResult = runner.run(research_content_request)
    
    # AC 3: validation.passed must be True
    assert result.validation.passed, (
        f"Research content team validation failed with issues: {result.validation.issues}"
    )
    
    # Sanity checks: the pipeline ran and produced output
    assert result.output_path.exists()
    assert len(result.written_files) > 0
    
    # Confirm it used the correct template
    assert result.team.template_used == "research_content_team"


# ---------------------------------------------------------------------------
# Tests: Both starter teams together (parameterized)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "yaml_filename,expected_template",
    [
        ("baseline_education_team_request.yaml", "baseline_education_team"),
        ("research_content_team_request.yaml", "research_content_team"),
    ],
)
def test_all_starter_teams_validate(
    repo_root: Path,
    yaml_filename: str,
    expected_template: str,
    tmp_path,
    monkeypatch,
) -> None:
    """Parameterized test: both starter team YAMLs build and validate successfully."""
    _authorize_risky_tools(monkeypatch, tmp_path, "code_writer")
    yaml_path = repo_root / "examples" / "starters" / yaml_filename
    raw = load_yaml(yaml_path)
    request = TeamCreationRequest(**raw)
    
    # Point output to temp directory
    request.output_path = str(tmp_path / Path(yaml_filename).stem)
    request.overwrite = True
    
    runner = PipelineRunner()
    result: PipelineResult = runner.run(request)
    
    # AC 3: validation must pass
    assert result.validation.passed, (
        f"{yaml_filename} validation failed with issues: {result.validation.issues}"
    )
    
    # Structure checks
    assert result.team.template_used == expected_template
    # Verify the pipeline produced agents and tasks (counts determined by template)
    assert len(result.team.agents) > 0
    assert len(result.team.tasks) > 0
    assert result.output_path.exists()
