"""Unit tests for OutputValidator."""
from __future__ import annotations

import pytest

from team_maker.domain.models import AgentSpec, GeneratedTeam, ProviderRouting, TaskSpec
from team_maker.validation.validator import OutputValidator, ValidationResult


def _minimal_team() -> GeneratedTeam:
    return GeneratedTeam(
        team_name="Test Team",
        purpose="Testing validator behaviour end to end.",
        template_used="software_delivery_team",
        agents=[
            AgentSpec(
                role="architect",
                display_name="Architect",
                description="Designs.",
                goal="Design well.",
                backstory="Experienced.",
                capabilities=[],
                tools=[],
                routing=ProviderRouting(provider="anthropic", model="claude-sonnet-4-6"),
            )
        ],
        tasks=[
            TaskSpec(
                name="architecture_design",
                description="Design it.",
                expected_output="Diagram.",
                agent_role="architect",
            )
        ],
    )


def _write_required_files(root):
    """Write the minimal set of required files for validation to pass."""
    import yaml
    from team_maker.validation.validator import _REQUIRED_FILES

    for rel in _REQUIRED_FILES:
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"# {rel}\n")

    # Write agent and task YAML
    agent_dir = root / "agents"
    agent_dir.mkdir(exist_ok=True)
    (agent_dir / "architect.yaml").write_text(
        yaml.dump({"role": "architect", "goal": "Design."})
    )
    tasks_dir = root / "tasks"
    tasks_dir.mkdir(exist_ok=True)
    (tasks_dir / "architecture_design.yaml").write_text(
        yaml.dump({"name": "architecture_design"})
    )


def test_valid_package_passes(tmp_path):
    _write_required_files(tmp_path)
    validator = OutputValidator()
    result = validator.validate(tmp_path, _minimal_team())
    assert result.passed
    assert result.issues == []


def test_missing_readme_fails(tmp_path):
    _write_required_files(tmp_path)
    (tmp_path / "README.md").unlink()
    validator = OutputValidator()
    result = validator.validate(tmp_path, _minimal_team())
    assert not result.passed
    assert any("README.md" in issue for issue in result.issues)


def test_missing_team_config_fails(tmp_path):
    _write_required_files(tmp_path)
    (tmp_path / "team_config.yaml").unlink()
    validator = OutputValidator()
    result = validator.validate(tmp_path, _minimal_team())
    assert not result.passed


def test_missing_agent_file_fails(tmp_path):
    _write_required_files(tmp_path)
    (tmp_path / "agents" / "architect.yaml").unlink()
    validator = OutputValidator()
    result = validator.validate(tmp_path, _minimal_team())
    assert not result.passed
    assert any("architect.yaml" in issue for issue in result.issues)


def test_missing_task_file_fails(tmp_path):
    _write_required_files(tmp_path)
    (tmp_path / "tasks" / "architecture_design.yaml").unlink()
    validator = OutputValidator()
    result = validator.validate(tmp_path, _minimal_team())
    assert not result.passed


def test_malformed_yaml_fails(tmp_path):
    _write_required_files(tmp_path)
    (tmp_path / "agents" / "architect.yaml").write_text("invalid: yaml: :\n  - bad\n  indented wrong\n: x")
    validator = OutputValidator()
    result = validator.validate(tmp_path, _minimal_team())
    # malformed YAML should cause a failure
    assert not result.passed


def test_no_tasks_produces_warning():
    team = GeneratedTeam(
        team_name="Empty Tasks",
        purpose="A team with no tasks to test warning generation.",
        template_used="custom",
        agents=[
            AgentSpec(
                role="architect",
                display_name="Architect",
                description=".",
                goal=".",
                backstory=".",
                capabilities=[],
                tools=[],
                routing=ProviderRouting(provider="anthropic", model="claude-sonnet-4-6"),
            )
        ],
        tasks=[],
    )
    import tempfile, pathlib
    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        # Write minimal files so other checks pass
        from team_maker.validation.validator import _REQUIRED_FILES
        for rel in _REQUIRED_FILES:
            p = root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(f"# {rel}\n")
        (root / "agents").mkdir(exist_ok=True)
        import yaml
        (root / "agents" / "architect.yaml").write_text(yaml.dump({"role": "architect"}))
        validator = OutputValidator()
        result = validator.validate(root, team)
        assert any("No tasks" in w for w in result.warnings)
