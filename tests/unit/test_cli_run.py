"""CLI tests for `team-maker run` (Story 1.5, AC 6). Fully offline —
`run_team_package` is monkeypatched, so these never need CrewAI installed.
"""
from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from team_maker.cli import main
from team_maker.runtime.executor import UnsupportedFrameworkError
from team_maker.runtime.loader import TeamPackageError
from team_maker.runtime.results import RunResult, TaskResult


def test_run_missing_package_exits_1_with_plain_message(tmp_path, monkeypatch):
    def _fake_run_team_package(package, goal, key_config, engine=None):
        raise TeamPackageError(f"Team Package directory not found: {package}")

    monkeypatch.setattr("team_maker.cli.run_team_package", _fake_run_team_package)

    result = CliRunner().invoke(
        main, ["run", "--package", str(tmp_path / "does_not_exist"), "ship it"]
    )

    assert result.exit_code == 1, result.output
    assert "Cannot run this package" in result.output
    assert "not found" in result.output


def test_run_non_crewai_framework_exits_1_with_plain_message(tmp_path, monkeypatch):
    def _fake_run_team_package(package, goal, key_config, engine=None):
        raise UnsupportedFrameworkError("Only 'crewai' packages can be run in v1.")

    monkeypatch.setattr("team_maker.cli.run_team_package", _fake_run_team_package)

    result = CliRunner().invoke(main, ["run", "--package", str(tmp_path), "ship it"])

    assert result.exit_code == 1, result.output
    assert "Cannot run this package" in result.output
    assert "crewai" in result.output


def test_run_missing_crewai_install_exits_1_with_install_hint(tmp_path, monkeypatch):
    def _fake_run_team_package(package, goal, key_config, engine=None):
        raise ImportError("No module named 'crewai'")

    monkeypatch.setattr("team_maker.cli.run_team_package", _fake_run_team_package)

    result = CliRunner().invoke(main, ["run", "--package", str(tmp_path), "ship it"])

    assert result.exit_code == 1, result.output
    assert "CrewAI is required" in result.output
    assert "team_maker[runtime]" in result.output


def test_run_execution_failure_exits_1_with_plain_message_not_a_traceback(tmp_path, monkeypatch):
    def _fake_run_team_package(package, goal, key_config, engine=None):
        raise RuntimeError("model provider returned 401 Unauthorized")

    monkeypatch.setattr("team_maker.cli.run_team_package", _fake_run_team_package)

    result = CliRunner().invoke(main, ["run", "--package", str(tmp_path), "ship it"])

    assert result.exit_code == 1, result.output
    assert "Run failed" in result.output
    assert "401 Unauthorized" in result.output
    assert "Traceback" not in result.output


def test_run_success_prints_final_output_and_per_task_breakdown(tmp_path, monkeypatch):
    fake_result = RunResult(
        final_output="the app is done",
        task_results=[
            TaskResult(name="architecture_design", agent_role="architect", output="the plan"),
            TaskResult(name="backend_implementation", agent_role="backend_engineer", output="the code"),
        ],
    )
    captured = {}

    def _fake_run_team_package(package, goal, key_config, engine=None):
        captured["package"] = package
        captured["goal"] = goal
        return fake_result

    monkeypatch.setattr("team_maker.cli.run_team_package", _fake_run_team_package)

    result = CliRunner().invoke(main, ["run", "--package", str(tmp_path), "ship the app"])

    assert result.exit_code == 0, result.output
    assert "the app is done" in result.output
    assert "architecture_design" in result.output
    assert "the plan" in result.output
    assert "backend_implementation" in result.output
    assert "the code" in result.output
    assert captured["package"] == Path(tmp_path)
    assert captured["goal"] == "ship the app"


def test_run_success_escapes_rich_markup_in_result_output(tmp_path, monkeypatch):
    """Agent/LLM output is free-form text that can legitimately contain
    bracketed content (markdown links, literal "[TODO]" notes, etc.) — Rich
    must not interpret it as console markup and silently strip/mangle it."""
    fake_result = RunResult(
        final_output="See [not_a_tag] and a [markdown link](http://example.com)",
        task_results=[
            TaskResult(
                name="t1", agent_role="a1", output="output with [red]fake[/red] markup"
            )
        ],
    )
    monkeypatch.setattr(
        "team_maker.cli.run_team_package",
        lambda package, goal, key_config, engine=None: fake_result,
    )

    result = CliRunner().invoke(main, ["run", "--package", str(tmp_path), "ship it"])

    assert result.exit_code == 0, result.output
    assert "[not_a_tag]" in result.output
    assert "[markdown link](http://example.com)" in result.output
    assert "[red]fake[/red]" in result.output


def test_run_quiet_suppresses_both_banner_and_result_output(tmp_path, monkeypatch):
    fake_result = RunResult(final_output="done", task_results=[])
    monkeypatch.setattr(
        "team_maker.cli.run_team_package",
        lambda package, goal, key_config, engine=None: fake_result,
    )

    result = CliRunner().invoke(
        main, ["run", "--package", str(tmp_path), "ship it", "--quiet"]
    )

    assert result.exit_code == 0, result.output
    assert "Running team" not in result.output
    assert "done" not in result.output  # --quiet also suppresses the result panel
