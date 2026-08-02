"""CLI test for `team-maker compose` (Story 1.2, AC7). Fully offline, no real key."""
from __future__ import annotations

import os
from typing import Any

from click.testing import CliRunner

from team_maker.cli import main

PROVIDER_ENVS = [
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "GOOGLE_API_KEY",
    "GOOGLE_AI_API_KEY",
    "GROQ_API_KEY",
    "XAI_API_KEY",
    "OPENROUTER_API_KEY",
]


def _isolate_keys(monkeypatch, tmp_path) -> None:
    for var in PROVIDER_ENVS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("TEAM_MAKER_KEYS", str(tmp_path / "unused.keys"))


class _FakeProvider:
    def __init__(self, responses: list[Any]) -> None:
        self._responses = list(responses)

    def complete_structured(self, system: str, user: str, response_model: type) -> Any:
        return response_model.model_validate(self._responses.pop(0))


class _BoomProvider:
    def complete_structured(self, system: str, user: str, response_model: type) -> Any:
        raise EnvironmentError("ANTHROPIC_API_KEY is not set")


def _valid_payload(tmp_path, **overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "team_name": "Docs Team",
        "purpose": "Write and maintain product documentation.",
        "output_path": str(tmp_path / "docs_team"),
        "desired_roles": [{"name": "writer", "description": "Writes documentation."}],
    }
    payload.update(overrides)
    return payload


def test_compose_writes_spec_and_never_prints_secret(tmp_path, monkeypatch):
    _isolate_keys(monkeypatch, tmp_path)
    secret = "sk-CLI-SECRET-DONOTPRINT"
    keyfile = tmp_path / "team_maker.keys"
    keyfile.write_text(f"ANTHROPIC_API_KEY={secret}\n", encoding="utf-8")

    monkeypatch.setattr(
        "team_maker.cli.create_provider",
        lambda cfg: _FakeProvider([_valid_payload(tmp_path)]),
    )

    out_file = tmp_path / "spec.yaml"
    result = CliRunner().invoke(
        main,
        [
            "compose",
            "a team to write docs",
            "--key-file",
            str(keyfile),
            "--out",
            str(out_file),
        ],
    )

    assert result.exit_code == 0, result.output
    assert secret not in result.output
    assert out_file.exists()
    assert secret not in out_file.read_text(encoding="utf-8")
    assert "Docs Team" in out_file.read_text(encoding="utf-8")


def test_compose_prints_spec_to_stdout_without_out_option(tmp_path, monkeypatch):
    _isolate_keys(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "team_maker.cli.create_provider",
        lambda cfg: _FakeProvider([_valid_payload(tmp_path)]),
    )

    result = CliRunner().invoke(main, ["compose", "a team to write docs"])

    assert result.exit_code == 0, result.output
    assert "Docs Team" in result.output


def test_compose_exits_2_when_repair_budget_exhausted(tmp_path, monkeypatch):
    _isolate_keys(monkeypatch, tmp_path)
    bad_payload = _valid_payload(
        tmp_path,
        desired_roles=[
            {"name": "writer", "description": "Writes content."},
            {"name": "writer", "description": "Writes more content."},
        ],
    )
    monkeypatch.setattr(
        "team_maker.cli.create_provider",
        lambda cfg: _FakeProvider([bad_payload] * 4),
    )

    result = CliRunner().invoke(main, ["compose", "a team"])

    assert result.exit_code == 2, result.output


def test_compose_exits_1_on_provider_error(tmp_path, monkeypatch):
    _isolate_keys(monkeypatch, tmp_path)
    monkeypatch.setattr("team_maker.cli.create_provider", lambda cfg: _BoomProvider())

    result = CliRunner().invoke(main, ["compose", "a team"])

    assert result.exit_code == 1, result.output


def test_compose_still_emits_spec_under_quiet_with_no_out_and_no_build(tmp_path, monkeypatch):
    """Regression: --quiet + no --out + no --build must not silently discard the spec."""
    _isolate_keys(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "team_maker.cli.create_provider",
        lambda cfg: _FakeProvider([_valid_payload(tmp_path)]),
    )

    result = CliRunner().invoke(main, ["compose", "a team to write docs", "--quiet"])

    assert result.exit_code == 0, result.output
    assert "Docs Team" in result.output


def test_resolve_authoring_provider_and_bridged_credential_roundtrip(tmp_path, monkeypatch):
    """Direct test of the key-resolution/env-bridging path (Task 2, AD-9) — not
    bypassed by mocking create_provider, unlike the higher-level CLI tests above."""
    from team_maker.cli import _bridged_credential, _resolve_authoring_provider
    from team_maker.keyconfig import KeyConfig

    _isolate_keys(monkeypatch, tmp_path)
    secret = "sk-DIRECT-RESOLUTION-TEST"
    keyfile = tmp_path / "team_maker.keys"
    keyfile.write_text(f"ANTHROPIC_API_KEY={secret}\n", encoding="utf-8")
    key_config = KeyConfig.from_file(keyfile)

    authoring_config = _resolve_authoring_provider(key_config, None)
    assert authoring_config.provider == "anthropic"
    assert authoring_config.api_key_env == "ANTHROPIC_API_KEY"

    assert "ANTHROPIC_API_KEY" not in os.environ
    with _bridged_credential(key_config, "anthropic", authoring_config.api_key_env):
        assert os.environ["ANTHROPIC_API_KEY"] == secret
    # Restored (removed, since it wasn't set beforehand) after the block exits —
    # the secret must not persist in the process environment past this call.
    assert "ANTHROPIC_API_KEY" not in os.environ


def test_bridged_credential_restores_prior_value_after_block(monkeypatch):
    from pydantic import SecretStr

    from team_maker.cli import _bridged_credential
    from team_maker.keyconfig import KeyConfig

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ORIGINAL-ENV-VALUE")
    key_config = KeyConfig(keys={"anthropic": SecretStr("sk-FROM-KEY-CONFIG-FILE")})

    with _bridged_credential(key_config, "anthropic", "ANTHROPIC_API_KEY"):
        assert os.environ["ANTHROPIC_API_KEY"] == "sk-FROM-KEY-CONFIG-FILE"

    assert os.environ["ANTHROPIC_API_KEY"] == "sk-ORIGINAL-ENV-VALUE"


def test_compose_honors_stated_preference_through_the_cli(tmp_path, monkeypatch):
    """AC5 end-to-end through the actual CLI surface (not just the library call)."""
    _isolate_keys(monkeypatch, tmp_path)
    payload = _valid_payload(tmp_path, default_llm={"provider": "ollama", "model": "llama3.2"})
    captured_calls = []

    class _RecordingProvider:
        def complete_structured(self, system, user, response_model):
            captured_calls.append(user)
            return response_model.model_validate(payload)

    monkeypatch.setattr("team_maker.cli.create_provider", lambda cfg: _RecordingProvider())

    result = CliRunner().invoke(
        main, ["compose", "build a team, use local/cheap models"]
    )

    assert result.exit_code == 0, result.output
    assert "use local/cheap models" in captured_calls[0]
    assert "ollama" in result.output
