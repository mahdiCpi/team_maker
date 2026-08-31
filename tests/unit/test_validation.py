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


# ---------------------------------------------------------------------------
# Tool declaration checks (Phase 7, spec FR-030, FR-037, FR-038; tasks
# T129-T131, T138)
# ---------------------------------------------------------------------------


def _team_with_tools(*, role: str = "architect", tools: list[str]) -> GeneratedTeam:
    return GeneratedTeam(
        team_name="Test Team",
        purpose="Testing tool declaration validation.",
        template_used="software_delivery_team",
        agents=[
            AgentSpec(
                role=role,
                display_name=role.title(),
                description="Does things.",
                goal="Do things well.",
                backstory="Experienced.",
                capabilities=[],
                tools=tools,
                routing=ProviderRouting(provider="anthropic", model="claude-sonnet-4-6"),
            )
        ],
        tasks=[
            TaskSpec(
                name="do_it",
                description="Do it.",
                expected_output="Done.",
                agent_role=role,
            )
        ],
    )


def _write_package_with_tools(root, tools: list[str], *, tools_source: str | None = None) -> None:
    _write_required_files(root)
    import yaml
    (root / "agents").mkdir(exist_ok=True)
    (root / "agents" / "architect.yaml").write_text(yaml.dump({"role": "architect", "tools": tools}))
    (root / "tasks").mkdir(exist_ok=True)
    (root / "tasks" / "do_it.yaml").write_text(yaml.dump({"name": "do_it"}))
    if tools_source is not None:
        (root / "tools.py").write_text(tools_source, encoding="utf-8")
        from team_maker.codegen import render_template
        (root / "state_store.py").write_text(
            render_template("state_store.py.j2", use_vector=False, use_file=True),
            encoding="utf-8",
        )


def _current_tools_source() -> str:
    from team_maker.codegen import render_template
    from team_maker.schema.request import SandboxConfig
    from team_maker.tools.limits import DEFAULT_CONTROLS
    from team_maker.tools.policy import EMPTY_ALLOWLIST

    return render_template(
        "tools.py.j2",
        sandbox=SandboxConfig(),
        suggested_tools=[],
        context_dir=None,
        effective_network="none",
        network_allowed=False,
        controls=DEFAULT_CONTROLS,
        mount_allowlist=EMPTY_ALLOWLIST.entries,
    )


def test_all_canonical_package_is_unaffected(tmp_path):
    """FR-038, SC-011: an all-canonical package's validation is unaffected."""
    _write_package_with_tools(tmp_path, ["state_reader"], tools_source=_current_tools_source())
    result = OutputValidator().validate(tmp_path, _team_with_tools(tools=["state_reader"]))
    assert result.passed
    assert result.issues == []


def test_invented_tool_name_fails_validation_naming_it(tmp_path):
    _write_package_with_tools(tmp_path, ["text_summarizer"], tools_source=_current_tools_source())
    result = OutputValidator().validate(tmp_path, _team_with_tools(tools=["text_summarizer"]))
    assert not result.passed
    assert any("text_summarizer" in issue and "architect" in issue for issue in result.issues)


def test_unauthorized_risky_tool_fails_validation(tmp_path):
    _write_package_with_tools(tmp_path, ["shell"], tools_source=_current_tools_source())
    result = OutputValidator().validate(tmp_path, _team_with_tools(tools=["shell"]))
    assert not result.passed
    assert any("unauthorized" in issue for issue in result.issues)


def test_unresolvable_tool_fails_validation(tmp_path):
    """A canonical, authorized, SAFE name with no binding in this specific
    package's registry (catalog/registry drift)."""
    source = _current_tools_source().replace('"state_reader":   state_reader_tool,\n', "")
    _write_package_with_tools(tmp_path, ["state_reader"], tools_source=source)
    result = OutputValidator().validate(tmp_path, _team_with_tools(tools=["state_reader"]))
    assert not result.passed
    assert any("state_reader" in issue for issue in result.issues)


def test_failure_scoped_to_offending_declaration_only(tmp_path):
    """FR-038: four safe tools plus one invented one names only the
    offending declaration."""
    tools = ["state_reader", "state_writer", "http_client", "ci_tool", "text_summarizer"]
    _write_package_with_tools(tmp_path, tools, tools_source=_current_tools_source())
    result = OutputValidator().validate(tmp_path, _team_with_tools(tools=tools))
    assert not result.passed
    assert len(result.issues) == 1
    assert "text_summarizer" in result.issues[0]


def test_pre_remediation_package_fails_validation(tmp_path):
    """Uses a SAFE tool (`state_reader`) so the pre-remediation-shape check
    is exercised in isolation, not shadowed by the (also correct, but
    distinct) unauthorized-RISKY-tool rejection a name like `shell` would
    also trigger."""
    old_shape = (
        'USE_SANDBOX = os.environ.get("SANDBOX_ENABLED", "false").lower() == "true"\n'
        "def state_reader_tool(key):\n    pass\n"
        "TOOL_REGISTRY = {'state_reader': state_reader_tool}\n"
    )
    _write_package_with_tools(tmp_path, ["state_reader"], tools_source=old_shape)
    result = OutputValidator().validate(tmp_path, _team_with_tools(tools=["state_reader"]))
    assert not result.passed
    assert any("pre-remediation" in issue for issue in result.issues)
