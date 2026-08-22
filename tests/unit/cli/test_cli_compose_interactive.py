"""CLI tests for `team-maker compose --interactive` (Story 1.3). Fully offline, no real key."""
from __future__ import annotations

import os

from click.testing import CliRunner

import team_maker.cli as cli_module
from team_maker.cli import main
from tests.unit.cli.test_cli_compose import _FakeProvider, _isolate_keys, _valid_payload


def test_interactive_run_now_builds_after_a_refinement(tmp_path, monkeypatch):
    first = _valid_payload(tmp_path)
    second = _valid_payload(
        tmp_path,
        desired_roles=[
            {
                "name": "writer",
                "description": "Writes documentation.",
                "llm": {"provider": "google", "model": "gemini-1.5-pro"},
            }
        ],
    )
    _isolate_keys(monkeypatch, tmp_path)
    monkeypatch.setattr(
        # Story 2.10: `start()` classifies before composing, so the first
        # queued response answers that call.
        "team_maker.cli.create_provider",
        lambda cfg: _FakeProvider([{"is_team": True}, first, second]),
    )

    result = CliRunner().invoke(
        main,
        ["compose", "a team to write docs", "--interactive"],
        input="put the writer on Gemini\nrun now\n",
    )

    assert result.exit_code == 0, result.output
    assert "Docs Team" in result.output
    assert "Team generated" in result.output  # _print_result only fires on a real build
    assert (tmp_path / "docs_team").exists()


def test_interactive_done_ends_loop_without_building(tmp_path, monkeypatch):
    _isolate_keys(monkeypatch, tmp_path)
    monkeypatch.setattr(
        # Story 2.10: `start()` classifies before composing.
        "team_maker.cli.create_provider",
        lambda cfg: _FakeProvider([{"is_team": True}, _valid_payload(tmp_path)]),
    )

    result = CliRunner().invoke(
        main, ["compose", "a team to write docs", "--interactive"], input="done\n"
    )

    assert result.exit_code == 0, result.output
    assert "Docs Team" in result.output
    assert "Team generated" not in result.output
    assert not (tmp_path / "docs_team").exists()


def test_interactive_blank_line_ends_loop_without_building(tmp_path, monkeypatch):
    _isolate_keys(monkeypatch, tmp_path)
    monkeypatch.setattr(
        # Story 2.10: `start()` classifies before composing.
        "team_maker.cli.create_provider",
        lambda cfg: _FakeProvider([{"is_team": True}, _valid_payload(tmp_path)]),
    )

    result = CliRunner().invoke(
        main, ["compose", "a team to write docs", "--interactive"], input="\n"
    )

    assert result.exit_code == 0, result.output
    assert "Team generated" not in result.output


def test_interactive_recovers_from_a_failed_refinement_then_runs_now(tmp_path, monkeypatch):
    first = _valid_payload(tmp_path)
    duplicate_roles_payload = _valid_payload(
        tmp_path,
        desired_roles=[
            {"name": "writer", "description": "Writes content."},
            {"name": "writer", "description": "Writes more content."},
        ],
    )
    responses = [
        {"is_team": True},  # Story 2.10: start()'s classification call
        first,
    ] + [duplicate_roles_payload] * 4  # exhausts the default repair budget
    _isolate_keys(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "team_maker.cli.create_provider", lambda cfg: _FakeProvider(responses)
    )

    result = CliRunner().invoke(
        main,
        ["compose", "a team to write docs", "--interactive"],
        input="add a reviewer role\nrun now\n",
    )

    assert result.exit_code == 0, result.output
    assert "Could not apply that change" in result.output
    assert "Team generated" in result.output
    assert (tmp_path / "docs_team").exists()


def test_run_now_build_happens_with_credential_still_bridged(tmp_path, monkeypatch):
    """Regression for the code-review finding: the credential bridge must cover
    the run-now build, not just the compose turns — verified by actually
    checking os.environ *at build time*, not just that the build succeeded
    (which can pass for unrelated reasons, as the original bug demonstrated)."""
    _isolate_keys(monkeypatch, tmp_path)
    secret = "sk-BUILD-TIME-CREDENTIAL-CHECK"
    keyfile = tmp_path / "team_maker.keys"
    keyfile.write_text(f"ANTHROPIC_API_KEY={secret}\n", encoding="utf-8")
    monkeypatch.setattr(
        # Story 2.10: `start()` classifies before composing.
        "team_maker.cli.create_provider",
        lambda cfg: _FakeProvider([{"is_team": True}, _valid_payload(tmp_path)]),
    )

    observed = {}

    class _RecordingRunner:
        def run(self, request):
            observed["ANTHROPIC_API_KEY"] = os.environ.get("ANTHROPIC_API_KEY")
            from team_maker.pipeline.runner import PipelineRunner

            return PipelineRunner().run(request)

    monkeypatch.setattr(cli_module, "PipelineRunner", _RecordingRunner)

    result = CliRunner().invoke(
        main,
        ["compose", "a team to write docs", "--interactive", "--key-file", str(keyfile)],
        input="run now\n",
    )

    assert result.exit_code == 0, result.output
    assert observed.get("ANTHROPIC_API_KEY") == secret


def test_interactive_eof_on_first_prompt_ends_loop_without_building(tmp_path, monkeypatch):
    """Exercises the `except EOFError` branch specifically (closed stdin, not just a blank line)."""
    _isolate_keys(monkeypatch, tmp_path)
    monkeypatch.setattr(
        # Story 2.10: `start()` classifies before composing.
        "team_maker.cli.create_provider",
        lambda cfg: _FakeProvider([{"is_team": True}, _valid_payload(tmp_path)]),
    )

    result = CliRunner().invoke(
        main, ["compose", "a team to write docs", "--interactive"], input=""
    )

    assert result.exit_code == 0, result.output
    assert "Team generated" not in result.output


def test_interactive_refine_error_sanitizes_message_and_errors_list(tmp_path, monkeypatch):
    """Regression for the Story 4.1 code review (P5/P6): this loop's
    `ComposerError` handler printed `str(exc)` raw (no `sanitize_exception_for_display`
    call at all) and its `.errors` loop was never sanitized either, unlike the
    equivalent top-level handlers elsewhere in `compose()`."""
    from team_maker.composer.composer import ComposerError
    from team_maker.composer.session import ComposerSession

    _isolate_keys(monkeypatch, tmp_path)
    monkeypatch.setattr(
        # Story 2.10: `start()` classifies before composing.
        "team_maker.cli.create_provider",
        lambda cfg: _FakeProvider([{"is_team": True}, _valid_payload(tmp_path)]),
    )
    secret = "sk-ant-SUPER-SECRET-REFINE-KEY-1234567890"

    def _boom(self, message):
        raise ComposerError(
            f"the provider rejected the request: {secret}",
            errors=[f"role.llm.api_key_env: leaked {secret}"],
        )

    monkeypatch.setattr(ComposerSession, "refine", _boom)

    result = CliRunner().invoke(
        main,
        ["compose", "a team to write docs", "--interactive"],
        input="do something\ndone\n",
    )

    assert result.exit_code == 0, result.output
    assert "Could not apply that change" in result.output
    assert secret not in result.output
    assert "[REDACTED]" in result.output


def test_compose_without_interactive_flag_is_unchanged(tmp_path, monkeypatch):
    """AC7 regression guard: no --interactive means the exact Story 1.2 one-shot path."""
    _isolate_keys(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "team_maker.cli.create_provider",
        lambda cfg: _FakeProvider([_valid_payload(tmp_path)]),
    )

    result = CliRunner().invoke(main, ["compose", "a team to write docs"])

    assert result.exit_code == 0, result.output
    assert "Docs Team" in result.output
    assert "Team generated" not in result.output
