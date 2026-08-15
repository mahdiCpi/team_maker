"""Unit tests for provider availability reporting (Story 1.1)."""
from __future__ import annotations

from pydantic import SecretStr

from team_maker.adapters.providers.registry import (
    STATUS_AVAILABLE,
    STATUS_KEYLESS_LOCAL,
    STATUS_MISSING,
    STATUS_UNSUPPORTED_BY_RUNTIME,
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
    """available / keyless-local / via-openrouter are runnable; missing is not,
    and neither is a provider the installed engine cannot construct."""
    assert is_usable(STATUS_AVAILABLE) is True
    assert is_usable(STATUS_KEYLESS_LOCAL) is True
    assert is_usable(STATUS_VIA_OPENROUTER) is True
    assert is_usable(STATUS_MISSING) is False
    assert is_usable(STATUS_UNSUPPORTED_BY_RUNTIME) is False


def test_google_status_stays_unsupported_by_runtime_regardless_of_key_name(tmp_path):
    """Story 0.4: the catalog's google entry was fixed from GOOGLE_API_KEY (wrong) to
    GOOGLE_AI_API_KEY (matches the real adapter default).

    Story 1.6 code review narrowed what "recognized" means: the correct key name
    is now *recognized* but still not directly runnable, because the installed
    CrewAI needs the `crewai[google-genai]` extra to call Google natively. The
    wrong name is still simply missing — the distinction the original test was
    written to lock in survives, it just has three states now instead of two.

    Story 2.9: GOOGLE_API_KEY is now recognized as an alias for GOOGLE_AI_API_KEY
    (so `.has("google")` is True — asserted below, renamed from "...no_longer_recognized"
    since that name became inaccurate once the alias made it recognized again), but the
    status is unchanged for the separate, unrelated `runtime_supported=False` reason
    (CrewAI still can't call Google directly).
    """
    path = tmp_path / "team_maker.keys"
    path.write_text("GOOGLE_API_KEY=old-wrong-name\n", encoding="utf-8")
    cfg = KeyConfig.from_file(path, include_env=False)
    # The key is now recognized via alias, so .has("google") is True, with the
    # real value stored under the canonical provider name
    assert cfg.has("google") is True
    assert cfg.keys["google"].get_secret_value() == "old-wrong-name"
    # But status is still UNSUPPORTED_BY_RUNTIME due to runtime_supported=False
    assert _status_map(cfg)["google"] == STATUS_UNSUPPORTED_BY_RUNTIME

    path.write_text("GOOGLE_AI_API_KEY=correct-name\n", encoding="utf-8")
    cfg = KeyConfig.from_file(path, include_env=False)
    assert _status_map(cfg)["google"] == STATUS_UNSUPPORTED_BY_RUNTIME

    # ...and with an OpenRouter key it becomes genuinely runnable via the gateway.
    path.write_text(
        "GOOGLE_AI_API_KEY=correct-name\nOPENROUTER_API_KEY=sk-or\n", encoding="utf-8"
    )
    cfg = KeyConfig.from_file(path, include_env=False)
    assert _status_map(cfg)["google"] == STATUS_VIA_OPENROUTER


def test_a_provider_the_engine_cannot_construct_is_not_reported_runnable(tmp_path):
    """The gate must not admit a provider that would die at LLM construction.

    crewai 1.14.6 has no native groq/xai provider and litellm is not installed,
    so a valid key for either is not enough — and groq, being an inference host
    rather than a model vendor, has no OpenRouter namespace to fall back to.
    """
    path = tmp_path / "team_maker.keys"
    path.write_text(
        "GROQ_API_KEY=sk-groq\nXAI_API_KEY=sk-xai\nOPENROUTER_API_KEY=sk-or\n",
        encoding="utf-8",
    )
    cfg = KeyConfig.from_file(path, include_env=False)
    statuses = _status_map(cfg)

    assert statuses["groq"] == STATUS_UNSUPPORTED_BY_RUNTIME
    assert statuses["xai"] == STATUS_UNSUPPORTED_BY_RUNTIME
    assert is_usable(statuses["groq"]) is False
    assert is_usable(statuses["xai"]) is False
