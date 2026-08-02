"""CLI tests for the opt-in run transcript (Story 1.7, AC 5/6).

Fully offline — `run_team_package` is monkeypatched, so these never need CrewAI
installed. They cover the CLI's *presentation* of a transcript, not its capture;
capture is proven against a real crew in `tests/conformance/`.
"""
from __future__ import annotations

import pytest
from click.testing import CliRunner

from team_maker.cli import main
from team_maker.runtime.preflight import InvalidTaskNamesError
from team_maker.runtime.results import (
    ENTRY_AGENT_MESSAGE,
    ENTRY_DELEGATION,
    RunResult,
    TaskResult,
    TranscriptEntry,
)


def _result_with_transcript() -> RunResult:
    return RunResult(
        final_output="the final answer",
        task_results=[
            TaskResult(name="design", agent_role="architect", output="the plan")
        ],
        transcript=[
            TranscriptEntry(
                sequence=1,
                kind=ENTRY_AGENT_MESSAGE,
                agent_role="architect",
                task_name="design",
                # Brackets on purpose: Rich eats `[...]` as markup unless the
                # text is escaped, so this is the input that actually exercises
                # escape(). Bracket-free content would pass with escaping removed.
                content="I considered [option A] and [bold]option B[/bold]",
            ),
            TranscriptEntry(
                sequence=4,
                kind=ENTRY_DELEGATION,
                agent_role="coordinator",
                task_name="design",
                content="design it",
                target_role="architect",
            ),
        ],
    )


def _install(monkeypatch, result: RunResult) -> None:
    def _fake_run_team_package(package, goal, key_config, engine=None):
        return result

    monkeypatch.setattr("team_maker.cli.run_team_package", _fake_run_team_package)


def test_default_run_output_is_byte_identical_with_and_without_a_transcript(
    tmp_path, monkeypatch
):
    """AC 5: the transcript is strictly opt-in; Story 1.5's output is unchanged.

    Compared byte for byte against the same run carrying an empty transcript,
    rather than by substring — a substring check would still pass if the
    presence of a transcript changed spacing, ordering, or added a line.
    """
    with_transcript = _result_with_transcript()
    without = RunResult(
        final_output=with_transcript.final_output,
        task_results=with_transcript.task_results,
    )

    _install(monkeypatch, with_transcript)
    a = CliRunner().invoke(main, ["run", "--package", str(tmp_path), "ship it"])
    _install(monkeypatch, without)
    b = CliRunner().invoke(main, ["run", "--package", str(tmp_path), "ship it"])

    assert a.exit_code == 0 and b.exit_code == 0
    assert a.output == b.output, "carrying a transcript changed the default output"
    # And the Story 1.5 surface is intact, with nothing transcript-shaped in it.
    assert "the final answer" in a.output
    assert "Per-task results" in a.output
    assert "Run transcript" not in a.output
    assert "option A" not in a.output


def test_transcript_flag_prints_ordered_attributed_entries(tmp_path, monkeypatch):
    _install(monkeypatch, _result_with_transcript())

    result = CliRunner().invoke(
        main, ["run", "--package", str(tmp_path), "ship it", "--transcript"]
    )

    assert result.exit_code == 0, result.output
    assert "Run transcript" in result.output
    assert "architect" in result.output
    assert "design" in result.output
    # The delegation names who it went to.
    assert "-> architect" in result.output


def test_transcript_content_survives_rich_markup(tmp_path, monkeypatch):
    """The content is raw LLM text. Rich must render it verbatim, not consume
    the brackets as markup (this repo has shipped that bug three times)."""
    _install(monkeypatch, _result_with_transcript())

    result = CliRunner().invoke(
        main, ["run", "--package", str(tmp_path), "ship it", "--transcript"]
    )

    assert result.exit_code == 0, result.output
    assert "[option A]" in result.output
    assert "[bold]option B[/bold]" in result.output


def test_transcript_can_be_written_to_a_file(tmp_path, monkeypatch):
    _install(monkeypatch, _result_with_transcript())
    out = tmp_path / "out" / "transcript.txt"

    result = CliRunner().invoke(
        main,
        ["run", "--package", str(tmp_path), "ship it", "--transcript-out", str(out)],
    )

    assert result.exit_code == 0, result.output
    written = out.read_text(encoding="utf-8")
    assert "[option A]" in written  # verbatim, not Rich-processed
    assert "architect" in written
    assert "-> architect" in written


def test_transcript_file_is_written_even_when_quiet(tmp_path, monkeypatch):
    """`--quiet` suppresses console output, but an explicitly requested file is
    a deliverable — matching how `compose` still writes its spec when quiet."""
    _install(monkeypatch, _result_with_transcript())
    out = tmp_path / "transcript.txt"

    result = CliRunner().invoke(
        main,
        [
            "run", "--package", str(tmp_path), "ship it",
            "--transcript-out", str(out), "--quiet",
        ],
    )

    assert result.exit_code == 0, result.output
    assert out.exists()
    assert result.output.strip() == ""


def test_quiet_suppresses_the_printed_transcript(tmp_path, monkeypatch):
    _install(monkeypatch, _result_with_transcript())

    result = CliRunner().invoke(
        main, ["run", "--package", str(tmp_path), "ship it", "--transcript", "--quiet"]
    )

    assert result.exit_code == 0, result.output
    assert "Run transcript" not in result.output


@pytest.mark.parametrize(
    "error, fragment",
    [
        (OSError("disk is full"), "disk is full"),
        # Raw model output can contain lone surrogates, which utf-8 refuses.
        # UnicodeEncodeError is a ValueError, not an OSError — a handler that
        # catches only OSError produces the traceback the AC forbids.
        (UnicodeEncodeError("utf-8", "\ud800", 0, 1, "surrogates not allowed"), "surrogate"),
    ],
)
def test_a_failed_transcript_write_exits_1_with_a_plain_message(
    tmp_path, monkeypatch, error, fragment
):
    """The exception *type* is the real check.

    `CliRunner` turns an *unhandled* exception into `exit_code == 1` with no
    traceback in `output`, so asserting those two alone passes whether or not
    the handler exists. What distinguishes handled from unhandled is that a
    handled failure surfaces as `SystemExit` (our `sys.exit(1)`), while an
    unhandled one surfaces as the original error.
    """
    _install(monkeypatch, _result_with_transcript())

    def _boom(self, *args, **kwargs):
        raise error

    monkeypatch.setattr("pathlib.Path.write_text", _boom)

    result = CliRunner().invoke(
        main,
        [
            "run", "--package", str(tmp_path), "ship it",
            "--transcript-out", str(tmp_path / "t.txt"),
        ],
    )

    assert isinstance(result.exception, SystemExit), (
        f"error escaped the handler: {result.exception!r}"
    )
    assert result.exit_code == 1, result.output
    assert "Could not write the transcript" in result.output
    assert fragment in result.output


def test_an_empty_transcript_says_so_rather_than_printing_nothing(
    tmp_path, monkeypatch
):
    """Silence would read as a broken flag. EXPERIENCE.md: always say why."""
    _install(
        monkeypatch,
        RunResult(final_output="done", task_results=[], transcript=[]),
    )

    result = CliRunner().invoke(
        main, ["run", "--package", str(tmp_path), "ship it", "--transcript"]
    )

    assert result.exit_code == 0, result.output
    assert "No transcript was captured" in result.output


def test_an_empty_transcript_is_not_written_as_a_zero_byte_file(tmp_path, monkeypatch):
    """Writing 0 bytes and reporting "Transcript written to ..." is an
    affirmative success claim for no content — and the console path already
    says the opposite for the same state."""
    _install(
        monkeypatch,
        RunResult(final_output="done", task_results=[], transcript=[]),
    )
    out = tmp_path / "t.txt"

    result = CliRunner().invoke(
        main,
        ["run", "--package", str(tmp_path), "ship it", "--transcript-out", str(out)],
    )

    assert result.exit_code == 1, result.output
    assert not out.exists(), "a zero-byte transcript file was written"
    assert "No transcript was captured" in result.output


def test_a_none_transcript_does_not_raise(tmp_path, monkeypatch):
    """`RunResult` has no validation and any ExecutionEngine may return None.
    `_print_transcript` guards this; the file path must too."""
    _install(
        monkeypatch,
        RunResult(final_output="done", task_results=[], transcript=None),
    )

    result = CliRunner().invoke(
        main, ["run", "--package", str(tmp_path), "ship it", "--transcript"]
    )

    assert result.exception is None, f"unhandled: {result.exception!r}"
    assert result.exit_code == 0, result.output


def test_an_invalid_package_is_reported_separately_from_missing_credentials(
    tmp_path, monkeypatch
):
    """A blank or duplicated task name is a malformed package, not a key
    problem — no credential would fix it."""

    def _fake_run_team_package(package, goal, key_config, engine=None):
        raise InvalidTaskNamesError(
            "Cannot start this run - these task names are declared more than "
            "once: design."
        )

    monkeypatch.setattr("team_maker.cli.run_team_package", _fake_run_team_package)

    result = CliRunner().invoke(main, ["run", "--package", str(tmp_path), "ship it"])

    assert result.exit_code == 1, result.output
    assert "Invalid package" in result.output
    assert "design" in result.output
    assert "Missing credentials" not in result.output
