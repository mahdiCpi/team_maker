"""Integration tests: full pipeline runs producing real files on disk."""
from __future__ import annotations

import yaml
import pytest
from pathlib import Path

from team_maker.pipeline.runner import PipelineRunner, PipelineResult
from team_maker.schema.request import (
    DocumentationLevel,
    ProviderConfig,
    RoleDefinition,
    TeamCreationRequest,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run(request: TeamCreationRequest) -> PipelineResult:
    return PipelineRunner().run(request)


def _required_files():
    return [
        "README.md",
        "team_config.yaml",
        "run_example.py",
        "tools.py",
        "requirements.txt",
        "generation_report.md",
        "docs/how_to_run.md",
        "docs/how_to_extend.md",
        "docs/model_routing.md",
        "routing_config.yaml",
    ]


# ---------------------------------------------------------------------------
# End-to-end: full software delivery team
# ---------------------------------------------------------------------------


def test_full_pipeline_produces_all_required_files(full_request):
    result = _run(full_request)
    for rel in _required_files():
        assert (result.output_path / rel).exists(), f"Missing: {rel}"


def test_full_pipeline_produces_agent_files(full_request):
    result = _run(full_request)
    for agent in result.team.agents:
        path = result.output_path / "agents" / f"{agent.role}.yaml"
        assert path.exists(), f"Missing agent file: agents/{agent.role}.yaml"


def test_full_pipeline_produces_task_files(full_request):
    result = _run(full_request)
    for task in result.team.tasks:
        path = result.output_path / "tasks" / f"{task.name}.yaml"
        assert path.exists(), f"Missing task file: tasks/{task.name}.yaml"


def test_full_pipeline_validation_passes(full_request):
    result = _run(full_request)
    assert result.validation.passed, f"Validation issues: {result.validation.issues}"


def test_agent_yaml_files_are_valid(full_request):
    result = _run(full_request)
    for agent_file in (result.output_path / "agents").glob("*.yaml"):
        data = yaml.safe_load(agent_file.read_text())
        assert "role" in data
        assert "goal" in data
        # LLM config lives in routing_config.yaml, not agent files
        assert "llm" not in data


def test_task_yaml_files_are_valid(full_request):
    result = _run(full_request)
    for task_file in (result.output_path / "tasks").glob("*.yaml"):
        data = yaml.safe_load(task_file.read_text())
        assert "name" in data
        assert "agent_role" in data


def test_team_config_contains_team_name(full_request):
    result = _run(full_request)
    data = yaml.safe_load((result.output_path / "team_config.yaml").read_text())
    assert data["team_name"] == full_request.team_name


def test_generation_report_contains_validation_status(full_request):
    result = _run(full_request)
    report = (result.output_path / "generation_report.md").read_text()
    assert "PASSED" in report or "FAILED" in report


def test_routing_config_lists_all_agents(full_request):
    result = _run(full_request)
    data = yaml.safe_load((result.output_path / "routing_config.yaml").read_text())
    for agent in result.team.agents:
        assert agent.role in data["routing"]


def test_readme_contains_team_name(full_request):
    result = _run(full_request)
    readme = (result.output_path / "README.md").read_text()
    assert full_request.team_name in readme


# ---------------------------------------------------------------------------
# Minimal request
# ---------------------------------------------------------------------------


def test_minimal_request_pipeline_completes(minimal_request):
    result = _run(minimal_request)
    assert result.output_path.exists()
    assert len(result.written_files) > 0


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


def test_pipeline_raises_on_non_empty_dir_without_overwrite(tmp_path):
    out = tmp_path / "existing"
    out.mkdir()
    (out / "sentinel.txt").write_text("existing")

    request = TeamCreationRequest(
        team_name="Conflict Team",
        purpose="Testing conflict detection when output directory exists.",
        output_path=str(out),
        desired_roles=[RoleDefinition(name="architect", description="Designs.")],
        overwrite=False,
    )
    with pytest.raises(FileExistsError):
        _run(request)


def test_pipeline_overwrites_when_flag_set(tmp_path):
    out = tmp_path / "existing"
    out.mkdir()
    (out / "old_file.txt").write_text("stale")

    request = TeamCreationRequest(
        team_name="Overwrite Team",
        purpose="Testing overwrite flag behaviour in the generation pipeline.",
        output_path=str(out),
        desired_roles=[RoleDefinition(name="architect", description="Designs.")],
        overwrite=True,
    )
    result = _run(request)
    assert (out / "README.md").exists()


# ---------------------------------------------------------------------------
# Per-agent LLM routing round-trip
# ---------------------------------------------------------------------------


def test_per_agent_llm_routing_in_routing_config(tmp_path):
    request = TeamCreationRequest(
        team_name="Routing Test Team",
        purpose="Validating per-agent LLM routing in the generated YAML artifacts.",
        output_path=str(tmp_path / "out"),
        desired_roles=[
            RoleDefinition(
                name="architect",
                description="Designs architecture.",
                llm=ProviderConfig(
                    provider="openai", model="gpt-4o", api_key_env="OPENAI_API_KEY"
                ),
            ),
            RoleDefinition(
                name="backend_engineer",
                description="Builds APIs.",
                llm=ProviderConfig(provider="anthropic", model="claude-opus-4-7"),
            ),
        ],
        overwrite=True,
    )
    result = _run(request)
    routing = yaml.safe_load((result.output_path / "routing_config.yaml").read_text())["routing"]

    assert routing["architect"]["provider"] == "openai"
    assert routing["architect"]["model"] == "gpt-4o"
    assert routing["backend_engineer"]["provider"] == "anthropic"
    assert routing["backend_engineer"]["model"] == "claude-opus-4-7"


# ---------------------------------------------------------------------------
# Idempotency: running twice with overwrite=True produces same output
# ---------------------------------------------------------------------------


def test_pipeline_is_idempotent(full_request):
    full_request.overwrite = True
    result1 = _run(full_request)
    files1 = sorted(result1.written_files)

    result2 = _run(full_request)
    files2 = sorted(result2.written_files)

    assert files1 == files2

    # Agent YAML content should be identical
    for agent in result1.team.agents:
        path = result1.output_path / "agents" / f"{agent.role}.yaml"
        content1 = path.read_text()
        content2 = (result2.output_path / "agents" / f"{agent.role}.yaml").read_text()
        # Timestamps in reports differ; compare agent configs specifically
        assert content1 == content2


# ---------------------------------------------------------------------------
# documentation_level: full
# ---------------------------------------------------------------------------


def test_full_documentation_level_completes(tmp_path):
    request = TeamCreationRequest(
        team_name="Well-Documented Team",
        purpose="Testing full documentation level setting in the pipeline runner.",
        output_path=str(tmp_path / "out"),
        desired_roles=[
            RoleDefinition(name="architect", description="Designs architecture."),
        ],
        documentation_level=DocumentationLevel.FULL,
        overwrite=True,
    )
    result = _run(request)
    assert result.output_path.exists()
