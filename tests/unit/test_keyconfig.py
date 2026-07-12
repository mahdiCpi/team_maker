"""Unit tests for the Key Config loader (Story 1.1)."""
from __future__ import annotations

import json
import logging

from pydantic import SecretStr

from team_maker.keyconfig import KeyConfig

SECRET = "sk-super-secret-value-123"


def _write(tmp_path, text, encoding="utf-8"):
    p = tmp_path / "team_maker.keys"
    p.write_text(text, encoding=encoding)
    return p


# --- basic loading (file-only; env fallback disabled for determinism) ---


def test_missing_file_returns_empty_config(tmp_path):
    cfg = KeyConfig.from_file(tmp_path / "does_not_exist.keys", include_env=False)
    assert cfg.keys == {}
    assert cfg.has("anthropic") is False


def test_existing_but_empty_file_returns_empty_config(tmp_path):
    """AC5: an existing-but-empty file must not crash and yields no keys."""
    path = _write(tmp_path, "")
    cfg = KeyConfig.from_file(path, include_env=False)
    assert cfg.keys == {}
    assert cfg.has("anthropic") is False


def test_loads_keys_by_env_var_name(tmp_path):
    path = _write(tmp_path, f"ANTHROPIC_API_KEY={SECRET}\nOPENAI_API_KEY=sk-openai\n")
    cfg = KeyConfig.from_file(path, include_env=False)
    assert cfg.has("anthropic") is True
    assert cfg.has("openai") is True
    assert cfg.has("groq") is False


def test_loads_keys_by_provider_name_and_ignores_comments_blanks(tmp_path):
    path = _write(tmp_path, f"# comment\n\nanthropic={SECRET}\n  \nGOOGLE_API_KEY=g\n")
    cfg = KeyConfig.from_file(path, include_env=False)
    assert cfg.has("anthropic") is True
    assert cfg.has("google") is True


def test_empty_value_is_not_present(tmp_path):
    path = _write(tmp_path, "ANTHROPIC_API_KEY=\n")
    cfg = KeyConfig.from_file(path, include_env=False)
    assert cfg.has("anthropic") is False


# --- parsing edge cases (from code review) ---


def test_utf8_bom_does_not_drop_first_key(tmp_path):
    """A BOM-prefixed file (common on Windows editors) must still load the first key."""
    path = _write(tmp_path, f"﻿ANTHROPIC_API_KEY={SECRET}\n", encoding="utf-8")
    cfg = KeyConfig.from_file(path, include_env=False)
    assert cfg.has("anthropic") is True


def test_unreadable_or_non_utf8_file_warns_and_does_not_raise(tmp_path):
    """from_file must never raise; a bad file becomes a warning and an empty config."""
    p = tmp_path / "team_maker.keys"
    p.write_bytes(b"\xff\xfeANTHROPIC_API_KEY=x")  # invalid UTF-8
    cfg = KeyConfig.from_file(p, include_env=False)
    assert cfg.has("anthropic") is False
    assert any("Could not read" in w for w in cfg.load_warnings)


def test_inline_comment_is_stripped_from_value(tmp_path):
    path = _write(tmp_path, f"ANTHROPIC_API_KEY={SECRET} # prod key\n")
    cfg = KeyConfig.from_file(path, include_env=False)
    assert cfg.keys["anthropic"].get_secret_value() == SECRET


def test_matched_quote_pair_is_unwrapped_once(tmp_path):
    path = _write(tmp_path, f'ANTHROPIC_API_KEY="{SECRET}"\n')
    cfg = KeyConfig.from_file(path, include_env=False)
    assert cfg.keys["anthropic"].get_secret_value() == SECRET


def test_unmatched_leading_quote_is_preserved(tmp_path):
    path = _write(tmp_path, 'ANTHROPIC_API_KEY="abc\n')  # only a leading quote
    cfg = KeyConfig.from_file(path, include_env=False)
    assert cfg.keys["anthropic"].get_secret_value() == '"abc'


def test_unknown_key_name_is_warned_not_silently_dropped(tmp_path):
    path = _write(tmp_path, "ANTRHOPIC_API_KEY=typo\n")  # misspelled
    cfg = KeyConfig.from_file(path, include_env=False)
    assert cfg.has("anthropic") is False
    assert any("Unrecognized key name" in w for w in cfg.load_warnings)


# --- env-var fallback (decision 1a: file priority, env fallback) ---


def test_env_var_used_as_fallback_when_no_file(tmp_path, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "sk-groq-env")
    cfg = KeyConfig.from_file(tmp_path / "none.keys", include_env=True)
    assert cfg.has("groq") is True


def test_file_takes_priority_over_env(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-from-env")
    path = _write(tmp_path, "ANTHROPIC_API_KEY=sk-from-file\n")
    cfg = KeyConfig.from_file(path, include_env=True)
    assert cfg.keys["anthropic"].get_secret_value() == "sk-from-file"


# --- security (AD-9) ---


def test_key_value_never_leaks_in_repr_or_serialization(tmp_path, caplog):
    """AD-9: key values must never appear in repr, str, logs, or serialized output."""
    path = _write(tmp_path, f"ANTHROPIC_API_KEY={SECRET}\n")
    cfg = KeyConfig.from_file(path, include_env=False)

    assert SECRET not in repr(cfg)
    assert SECRET not in str(cfg)
    assert SECRET not in str(cfg.keys["anthropic"])
    assert SECRET not in json.dumps(cfg.model_dump(mode="json"))

    with caplog.at_level(logging.DEBUG):
        logging.getLogger("test").debug("config=%r keys=%s", cfg, cfg.keys)
    assert SECRET not in caplog.text

    assert cfg.keys["anthropic"].get_secret_value() == SECRET


def test_default_path_honours_env_override(tmp_path, monkeypatch):
    target = tmp_path / "custom.keys"
    monkeypatch.setenv("TEAM_MAKER_KEYS", str(target))
    assert KeyConfig.default_path() == target


def test_secretstr_used_for_stored_keys(tmp_path):
    path = _write(tmp_path, f"OPENAI_API_KEY={SECRET}\n")
    cfg = KeyConfig.from_file(path, include_env=False)
    assert isinstance(cfg.keys["openai"], SecretStr)
