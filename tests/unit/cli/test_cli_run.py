"""CLI tests for `team-maker run` (Story 1.5 AC 6, Story 1.6 AC 2/9). Fully
offline — `run_team_package` is monkeypatched, so these never need CrewAI
installed.
"""
from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from team_maker.cli import main
from team_maker.runtime.executor import UnsupportedFrameworkError
from team_maker.runtime.loader import TeamPackageError
from team_maker.runtime.preflight import (
    DuplicateAgentRoleError,
    MissingCredentialsError,
    UnresolvedProvider,
)
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


def test_run_missing_credentials_exits_1_naming_provider_key_and_roles(tmp_path, monkeypatch):
    """Story 1.6 AC 2/9: a missing key is a *configuration* problem, reported
    before anything runs — distinct from a malformed package."""

    def _fake_run_team_package(package, goal, key_config, engine=None):
        raise MissingCredentialsError(
            [
                UnresolvedProvider(
                    provider="openai",
                    roles=("reviewer", "editor"),
                    expected_key="OPENAI_API_KEY",
                    reason=(
                        "add OPENAI_API_KEY to your Key Config, or add "
                        "OPENROUTER_API_KEY to reach it via OpenRouter."
                    ),
                )
            ]
        )

    monkeypatch.setattr("team_maker.cli.run_team_package", _fake_run_team_package)

    result = CliRunner().invoke(main, ["run", "--package", str(tmp_path), "ship it"])

    assert result.exit_code == 1, result.output
    assert "Missing credentials" in result.output
    assert "openai" in result.output
    assert "OPENAI_API_KEY" in result.output
    assert "reviewer" in result.output
    # Not conflated with the malformed-package category.
    assert "Cannot run this package" not in result.output
    assert "Traceback" not in result.output


def test_run_missing_credentials_echoes_the_resolved_key_config_path(tmp_path, monkeypatch):
    """"Add the key to your Key Config" is only actionable if the user knows
    which file that is — `keys status` already prints it, so `run` does too."""
    key_file = tmp_path / "custom.keys"
    key_file.write_text("ANTHROPIC_API_KEY=sk-x\n", encoding="utf-8")

    def _fake_run_team_package(package, goal, key_config, engine=None):
        raise MissingCredentialsError(
            [
                UnresolvedProvider(
                    provider="openai",
                    roles=("reviewer",),
                    expected_key="OPENAI_API_KEY",
                    reason="add OPENAI_API_KEY to your Key Config.",
                )
            ]
        )

    monkeypatch.setattr("team_maker.cli.run_team_package", _fake_run_team_package)

    result = CliRunner().invoke(
        main, ["run", "--package", str(tmp_path), "ship it", "--key-file", str(key_file)]
    )

    assert result.exit_code == 1, result.output
    assert "custom.keys" in result.output


def test_run_missing_credentials_message_survives_rich_markup(tmp_path, monkeypatch):
    """The message must reach the user verbatim (Story 1.5 shipped this bug
    class twice).

    The reason deliberately contains square brackets. Rich treats `[...]` as
    markup and silently swallows it unless the text is escaped, so this is the
    input that actually exercises `escape()` — an earlier version of this test
    used bracket-free text and passed even with the escaping removed.
    """

    def _fake_run_team_package(package, goal, key_config, engine=None):
        raise MissingCredentialsError(
            [
                UnresolvedProvider(
                    provider="antropic",
                    roles=("helper",),
                    expected_key=None,
                    reason=(
                        "unrecognized provider; expected one of: "
                        "[anthropic, openai]. See [bold]the docs[/bold]."
                    ),
                )
            ]
        )

    monkeypatch.setattr("team_maker.cli.run_team_package", _fake_run_team_package)

    result = CliRunner().invoke(main, ["run", "--package", str(tmp_path), "ship it"])

    assert result.exit_code == 1, result.output
    assert "unrecognized provider" in result.output
    assert "antropic" in result.output
    # The brackets survive rather than being eaten as markup.
    assert "[anthropic, openai]" in result.output
    assert "[bold]the docs[/bold]" in result.output


def test_run_surfaces_key_config_load_warnings_with_the_credential_error(
    tmp_path, monkeypatch
):
    """A typo'd key name is ignored at load time, so the user sees "add
    OPENAI_API_KEY" while staring at a file that looks like it has one. The
    warning naming the typo is the actual answer — print it."""
    key_file = tmp_path / "typo.keys"
    key_file.write_text("OPENAI_KEY=sk-oops\n", encoding="utf-8")

    def _fake_run_team_package(package, goal, key_config, engine=None):
        raise MissingCredentialsError(
            [
                UnresolvedProvider(
                    provider="openai",
                    roles=("reviewer",),
                    expected_key="OPENAI_API_KEY",
                    reason="add OPENAI_API_KEY to your Key Config.",
                )
            ]
        )

    monkeypatch.setattr("team_maker.cli.run_team_package", _fake_run_team_package)

    result = CliRunner().invoke(
        main, ["run", "--package", str(tmp_path), "ship it", "--key-file", str(key_file)]
    )

    assert result.exit_code == 1, result.output
    assert "OPENAI_KEY" in result.output  # the typo'd name is called out
    assert "sk-oops" not in result.output  # but never its value


def test_run_duplicate_agent_roles_exits_1_as_an_invalid_package(tmp_path, monkeypatch):
    """A duplicate role is a malformed package, not a credential problem — it
    must not be reported as "Missing credentials"."""

    def _fake_run_team_package(package, goal, key_config, engine=None):
        raise DuplicateAgentRoleError(
            "Cannot start this run - these agent roles are declared more than once: worker."
        )

    monkeypatch.setattr("team_maker.cli.run_team_package", _fake_run_team_package)

    result = CliRunner().invoke(main, ["run", "--package", str(tmp_path), "ship it"])

    assert result.exit_code == 1, result.output
    assert "Invalid package" in result.output
    assert "worker" in result.output
    assert "Missing credentials" not in result.output
    assert "Traceback" not in result.output


def test_run_provider_import_error_does_not_tell_the_user_to_install_crewai(
    tmp_path, monkeypatch
):
    """crewai raises ImportError both when it is absent and when a provider
    module it lacks is requested. Only the first deserves the install hint;
    telling the second to `pip install team_maker[runtime]` is a dead end."""

    def _fake_run_team_package(package, goal, key_config, engine=None):
        raise ImportError(
            "Unable to initialize LLM with model 'groq/llama-3.3-70b': the "
            "LiteLLM fallback package is not installed"
        )

    monkeypatch.setattr("team_maker.cli.run_team_package", _fake_run_team_package)

    result = CliRunner().invoke(main, ["run", "--package", str(tmp_path), "ship it"])

    assert result.exit_code == 1, result.output
    assert "not available in the installed runtime" in result.output
    assert "pip install" not in result.output


def test_run_execution_failure_exits_1_with_plain_message_not_a_traceback(tmp_path, monkeypatch):
    def _fake_run_team_package(package, goal, key_config, engine=None):
        raise RuntimeError("model provider returned 401 Unauthorized")

    monkeypatch.setattr("team_maker.cli.run_team_package", _fake_run_team_package)

    result = CliRunner().invoke(main, ["run", "--package", str(tmp_path), "ship it"])

    assert result.exit_code == 1, result.output
    assert "Run failed" in result.output
    assert "401 Unauthorized" in result.output
    assert "Traceback" not in result.output


def test_run_result_with_error_set_exits_1_instead_of_reporting_success(tmp_path, monkeypatch):
    """Story 4.4 AC 1 / review fix: `run_team_package` can now return normally
    with `result.error` set (a partial-transcript failure) instead of
    raising — the CLI must still treat this as a failed run, not silently
    print an empty "success" panel and exit 0."""
    fake_result = RunResult(
        final_output="",
        task_results=[],
        error="model provider returned 401 Unauthorized",
    )
    monkeypatch.setattr("team_maker.cli.run_team_package", lambda package, goal, key_config, engine=None: fake_result)

    result = CliRunner().invoke(main, ["run", "--package", str(tmp_path), "ship it"])

    assert result.exit_code == 1, result.output
    assert "Run failed" in result.output
    assert "401 Unauthorized" in result.output


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
