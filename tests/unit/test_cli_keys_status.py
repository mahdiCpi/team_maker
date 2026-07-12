"""CLI test for `team-maker keys status` (Story 1.1, AC6)."""
from __future__ import annotations

from click.testing import CliRunner

from team_maker.cli import main

PROVIDER_ENVS = [
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "GOOGLE_API_KEY",
    "GROQ_API_KEY",
    "OPENROUTER_API_KEY",
]


def _clear_provider_env(monkeypatch):
    for var in PROVIDER_ENVS:
        monkeypatch.delenv(var, raising=False)


def test_keys_status_renders_table_and_never_prints_secret(tmp_path, monkeypatch):
    _clear_provider_env(monkeypatch)
    secret = "sk-CLI-SECRET-DONOTPRINT"
    keyfile = tmp_path / "team_maker.keys"
    keyfile.write_text(f"ANTHROPIC_API_KEY={secret}\n", encoding="utf-8")

    result = CliRunner().invoke(main, ["keys", "status", "--file", str(keyfile)])

    assert result.exit_code == 0, result.output
    assert "anthropic" in result.output
    assert "available" in result.output
    assert "ollama" in result.output  # keyless-local shown
    # AC4/AD-9: the key value must never appear in CLI output
    assert secret not in result.output


def test_keys_status_rejects_missing_file(tmp_path, monkeypatch):
    _clear_provider_env(monkeypatch)
    result = CliRunner().invoke(
        main, ["keys", "status", "--file", str(tmp_path / "nope.keys")]
    )
    # click validates exists=True on an explicit --file → usage error, not a crash
    assert result.exit_code != 0
    assert "does not exist" in result.output.lower() or "invalid value" in result.output.lower()
