"""CLI tests for `team-maker create` (Story 1.4, AC 1-2-5). Fully offline — no
network, no LLM; `create` never touches the Composer.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from click.testing import CliRunner

from team_maker.cli import main
from team_maker.domain.models import GeneratedTeam
from team_maker.pipeline.runner import PipelineResult
from team_maker.validation.validator import ValidationResult


def _valid_payload(tmp_path: Path, **overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "team_name": "Docs Team",
        "purpose": "Write and maintain product documentation.",
        "output_path": str(tmp_path / "docs_team"),
        "desired_roles": [{"name": "writer", "description": "Writes documentation."}],
    }
    payload.update(overrides)
    return payload


def _write_config(tmp_path: Path, filename: str = "request.yaml", **overrides: Any) -> Path:
    config_path = tmp_path / filename
    config_path.write_text(
        yaml.safe_dump(_valid_payload(tmp_path, **overrides)), encoding="utf-8"
    )
    return config_path


def test_create_clean_build_passes_and_prints_passed(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path)

    result = CliRunner().invoke(main, ["create", "--config", str(config_path)])

    assert result.exit_code == 0, result.output
    assert "PASSED" in result.output
    assert "Validation issues:" not in result.output
    assert (tmp_path / "docs_team" / "README.md").exists()
    assert (tmp_path / "docs_team" / "agents" / "writer.yaml").exists()


def test_create_invalid_schema_config_exits_1(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path, team_name="")

    result = CliRunner().invoke(main, ["create", "--config", str(config_path)])

    assert result.exit_code == 1, result.output
    assert "Invalid request config" in result.output
    assert "team_name" in result.output  # names the actual offending field


def test_create_conflict_without_overwrite_exits_1(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path)
    first = CliRunner().invoke(main, ["create", "--config", str(config_path)])
    assert first.exit_code == 0, first.output

    second = CliRunner().invoke(main, ["create", "--config", str(config_path)])

    assert second.exit_code == 1, second.output
    assert "Output conflict" in second.output


def test_create_overwrite_succeeds_after_conflict(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path)
    first = CliRunner().invoke(main, ["create", "--config", str(config_path)])
    assert first.exit_code == 0, first.output

    result = CliRunner().invoke(
        main, ["create", "--config", str(config_path), "--overwrite"]
    )

    assert result.exit_code == 0, result.output


def test_create_renders_specific_issues_and_warnings_and_exits_2_on_validation_failure(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """A fabricated failing PipelineResult proves the CLI's issue/warning rendering
    contract (AC5). The real factory always passes for a schema-valid request (every
    required/agent/task file is unconditionally part of the manifest it just wrote),
    so this failure path can only be exercised by injecting a rigged result, not by
    trying to organically break a clean build.
    """
    config_path = _write_config(tmp_path)

    class _FakeRunner:
        def run(self, request: Any) -> PipelineResult:
            output_path = Path(request.output_path)
            output_path.mkdir(parents=True, exist_ok=True)
            (output_path / "README.md").write_text("stub", encoding="utf-8")
            validation = ValidationResult(passed=True)
            validation.add_issue("Missing required file: team_config.yaml")
            validation.add_warning("No tasks were generated for this team.")
            team = GeneratedTeam(
                team_name=request.team_name,
                purpose=request.purpose,
                template_used="software_delivery_team",
                agents=[],
                tasks=[],
            )
            return PipelineResult(
                output_path=output_path,
                team=team,
                written_files=["README.md"],
                validation=validation,
            )

    monkeypatch.setattr("team_maker.cli.PipelineRunner", _FakeRunner)

    result = CliRunner().invoke(main, ["create", "--config", str(config_path)])

    assert result.exit_code == 2, result.output
    assert "FAILED" in result.output
    assert "Missing required file: team_config.yaml" in result.output
    assert "No tasks were generated for this team." in result.output

    # The written-file tree renders after the issues/warnings block even on
    # failure. Assert README.md appears there (not merely somewhere in the
    # output) by checking it comes after the issues section.
    issues_index = result.output.index("Validation issues:")
    tree_readme_index = result.output.rindex("README.md")
    assert tree_readme_index > issues_index, result.output
