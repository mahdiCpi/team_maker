"""Unit tests for provider availability reporting (Story 1.1)."""
from __future__ import annotations

from pydantic import SecretStr

from team_maker.adapters.providers.registry import (
    STATUS_AVAILABLE,
    STATUS_KEYLESS_LOCAL,
    STATUS_MISSING,
    STATUS_VIA_OPENROUTER,
    is_usable,
    report_availability,
)
from team_maker.keyconfig import KeyConfig


def _status_map(config):
    return {s.name: s.status for s in report_availability(config)}


def test_empty_config_cloud_missing_local_available():
    statuses = _status_map(KeyConfig())
    assert statuses["anthropic"] == STATUS_MISSING
    assert statuses["openai"] == STATUS_MISSING
    # keyless local provider is available even with an empty config (FR-13)
    assert statuses["ollama"] == STATUS_KEYLESS_LOCAL


def test_specific_key_marks_that_provider_available():
    cfg = KeyConfig(keys={"anthropic": SecretStr("sk-a")})
    statuses = _status_map(cfg)
    assert statuses["anthropic"] == STATUS_AVAILABLE
    assert statuses["openai"] == STATUS_MISSING


def test_openrouter_key_marks_reachable_models_via_openrouter():
    cfg = KeyConfig(keys={"openrouter": SecretStr("sk-or")})
    statuses = _status_map(cfg)
    # OpenRouter itself is available...
    assert statuses["openrouter"] == STATUS_AVAILABLE
    # ...and reachable providers are marked via-OpenRouter (FR-22)
    assert statuses["anthropic"] == STATUS_VIA_OPENROUTER
    assert statuses["openai"] == STATUS_VIA_OPENROUTER
    # a keyless-local provider is still reported as local, not via-OpenRouter
    assert statuses["ollama"] == STATUS_KEYLESS_LOCAL


def test_direct_key_takes_precedence_over_openrouter():
    cfg = KeyConfig(keys={"anthropic": SecretStr("sk-a"), "openrouter": SecretStr("sk-or")})
    statuses = _status_map(cfg)
    assert statuses["anthropic"] == STATUS_AVAILABLE  # not via-openrouter
    assert statuses["openai"] == STATUS_VIA_OPENROUTER


def test_report_contains_no_secret_values():
    secret = "sk-should-not-appear"
    cfg = KeyConfig(keys={"anthropic": SecretStr(secret)})
    for status in report_availability(cfg):
        assert secret not in status.status
        assert secret not in status.detail
        assert secret not in status.name


def test_is_usable_only_missing_blocks():
    """Decision 2a: available / keyless-local / via-openrouter are runnable; missing is not."""
    assert is_usable(STATUS_AVAILABLE) is True
    assert is_usable(STATUS_KEYLESS_LOCAL) is True
    assert is_usable(STATUS_VIA_OPENROUTER) is True
    assert is_usable(STATUS_MISSING) is False


def test_google_api_key_alone_no_longer_recognized(tmp_path):
    """Story 0.4: the catalog's google entry was fixed from GOOGLE_API_KEY (wrong) to
    GOOGLE_AI_API_KEY (matches the real adapter default) — locks in that the old name
    no longer marks google as available, and the new name does."""
    path = tmp_path / "team_maker.keys"
    path.write_text("GOOGLE_API_KEY=old-wrong-name\n", encoding="utf-8")
    cfg = KeyConfig.from_file(path, include_env=False)
    assert _status_map(cfg)["google"] == STATUS_MISSING

    path.write_text("GOOGLE_AI_API_KEY=correct-name\n", encoding="utf-8")
    cfg = KeyConfig.from_file(path, include_env=False)
    assert _status_map(cfg)["google"] == STATUS_AVAILABLE
