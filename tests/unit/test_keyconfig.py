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
    path = _write(tmp_path, f"# comment\n\nanthropic={SECRET}\n  \nGOOGLE_AI_API_KEY=g\n")
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


def test_env_var_alias_used_as_fallback_when_no_file(tmp_path, monkeypatch):
    """Story 2.9 follow-up: an alias env var (not just the canonical one) is a valid fallback."""
    monkeypatch.delenv("GOOGLE_AI_API_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "sk-google-alias-env")
    cfg = KeyConfig.from_file(tmp_path / "none.keys", include_env=True)
    assert cfg.has("google") is True
    assert cfg.keys["google"].get_secret_value() == "sk-google-alias-env"


def test_env_var_canonical_takes_priority_over_alias(tmp_path, monkeypatch):
    monkeypatch.setenv("GOOGLE_AI_API_KEY", "sk-canonical-env")
    monkeypatch.setenv("GOOGLE_API_KEY", "sk-alias-env")
    cfg = KeyConfig.from_file(tmp_path / "none.keys", include_env=True)
    assert cfg.keys["google"].get_secret_value() == "sk-canonical-env"


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


def test_google_api_key_alias_is_recognized(tmp_path):
    """Story 2.9: GOOGLE_API_KEY should be recognized as an alias for GOOGLE_AI_API_KEY."""
    path = _write(tmp_path, f"GOOGLE_API_KEY={SECRET}\n")
    cfg = KeyConfig.from_file(path, include_env=False)
    # The alias should resolve to the google provider, with the real value stored
    assert cfg.has("google") is True
    assert cfg.keys["google"].get_secret_value() == SECRET
    # No "Unrecognized key name" warning should be produced
    assert not any("Unrecognized key name" in w for w in cfg.load_warnings)


def test_later_line_wins_between_alias_and_canonical_google_key(tmp_path):
    """AC2: the alias invents no new precedence rule — same last-line-wins as any
    other duplicate provider definition (see the story-1.1 deferred-work entry)."""
    path = _write(tmp_path, f"GOOGLE_API_KEY=old-alias-value\nGOOGLE_AI_API_KEY={SECRET}\n")
    cfg = KeyConfig.from_file(path, include_env=False)
    assert cfg.keys["google"].get_secret_value() == SECRET

    path = _write(tmp_path, f"GOOGLE_AI_API_KEY={SECRET}\nGOOGLE_API_KEY=later-alias-value\n")
    cfg = KeyConfig.from_file(path, include_env=False)
    assert cfg.keys["google"].get_secret_value() == "later-alias-value"


# --- duplicate key handling (Story 4.2) ---


def test_duplicate_canonical_and_alias_entries_produce_warning(tmp_path):
    """AC2: duplicate entries for the same provider produce a warning."""
    # Use unique sentinel values to verify they never appear in warnings
    SENTINEL_ANTHROPIC = "ANTHROPIC_SENTINEL_VALUE_123"
    SENTINEL_ALIAS = "ANTHROPIC_SENTINEL_VALUE_456"
    
    path = _write(tmp_path, f"ANTHROPIC_API_KEY={SENTINEL_ANTHROPIC}\nanthropic={SENTINEL_ALIAS}\n")
    cfg = KeyConfig.from_file(path, include_env=False)
    
    # Must have exactly one warning for the duplicate
    duplicate_warnings = [w for w in cfg.load_warnings if "Duplicate key entries" in w]
    assert len(duplicate_warnings) == 1, f"Expected 1 duplicate warning, got {len(duplicate_warnings)}"
    
    # Warning must identify the provider
    assert "anthropic" in duplicate_warnings[0]
    
    # Warning must identify the conflicting key names
    assert "ANTHROPIC_API_KEY" in duplicate_warnings[0]
    assert "anthropic" in duplicate_warnings[0]
    
    # Warning must NOT contain secret values (security check)
    assert SENTINEL_ANTHROPIC not in duplicate_warnings[0]
    assert SENTINEL_ALIAS not in duplicate_warnings[0]


def test_duplicate_bare_provider_names_produce_warning(tmp_path):
    """Duplicate bare provider names produce a warning."""
    SENTINEL_1 = "OPENAI_SENTINEL_1"
    SENTINEL_2 = "OPENAI_SENTINEL_2"
    
    path = _write(tmp_path, f"openai={SENTINEL_1}\nopenai={SENTINEL_2}\n")
    cfg = KeyConfig.from_file(path, include_env=False)
    
    duplicate_warnings = [w for w in cfg.load_warnings if "Duplicate key entries" in w]
    assert len(duplicate_warnings) == 1
    assert "openai" in duplicate_warnings[0]
    assert SENTINEL_1 not in duplicate_warnings[0]
    assert SENTINEL_2 not in duplicate_warnings[0]


def test_duplicate_warning_includes_line_numbers(tmp_path):
    """Duplicate warning includes line numbers for better debugging."""
    path = _write(tmp_path, f"anthropic=value1\nANTHROPIC_API_KEY=value2\n")
    cfg = KeyConfig.from_file(path, include_env=False)
    
    duplicate_warnings = [w for w in cfg.load_warnings if "Duplicate key entries" in w]
    assert len(duplicate_warnings) == 1
    assert "lines [1, 2]" in duplicate_warnings[0]


def test_last_recognized_entry_wins_for_duplicates(tmp_path):
    """Last-recognized entry wins for backward compatibility."""
    SENTINEL_FIRST = "FIRST_VALUE"
    SENTINEL_LAST = "LAST_VALUE"
    
    path = _write(tmp_path, f"ANTHROPIC_API_KEY={SENTINEL_FIRST}\nanthropic={SENTINEL_LAST}\n")
    cfg = KeyConfig.from_file(path, include_env=False)
    
    # Last entry should win
    assert cfg.keys["anthropic"].get_secret_value() == SENTINEL_LAST


def test_no_warning_for_non_duplicate_entries(tmp_path):
    """Non-duplicate entries do not produce duplicate warnings."""
    path = _write(tmp_path, f"ANTHROPIC_API_KEY=value1\nOPENAI_API_KEY=value2\n")
    cfg = KeyConfig.from_file(path, include_env=False)
    
    duplicate_warnings = [w for w in cfg.load_warnings if "Duplicate key entries" in w]
    assert len(duplicate_warnings) == 0


def test_duplicate_warning_with_sentinel_secrets_never_leaks(tmp_path):
    """Security check: sentinel secret values never appear in duplicate warnings."""
    # Use the specific sentinel from the story requirements
    SENTINEL = "SK-1234567890ABCDEF"
    
    path = _write(tmp_path, f"ANTHROPIC_API_KEY={SENTINEL}\nanthropic={SENTINEL}\n")
    cfg = KeyConfig.from_file(path, include_env=False)
    
    # Check that sentinel never appears in any warning
    for warning in cfg.load_warnings:
        assert SENTINEL not in warning, f"Sentinel secret leaked in warning: {warning}"


# --- keyless provider handling (Story 4.2, AC 3) ---


def test_keyless_provider_without_key_classified_correctly(tmp_path):
    """Ollama (keyless_local=True) without key should be classified as keyless-local."""
    # Empty config - no keys at all
    path = _write(tmp_path, "# just a comment\n")
    cfg = KeyConfig.from_file(path, include_env=False)
    
    # No warning should be issued for missing keys on keyless providers
    keyless_warnings = [w for w in cfg.load_warnings if "keyless-local provider" in w]
    assert len(keyless_warnings) == 0


def test_keyless_provider_with_supplied_key_issues_warning(tmp_path):
    """Ollama with supplied key issues warning identifying provider and key name only."""
    SENTINEL_OLLAMA = "OLLAMA_SENTINEL_SECRET"
    
    path = _write(tmp_path, f"ollama={SENTINEL_OLLAMA}\n")
    cfg = KeyConfig.from_file(path, include_env=False)
    
    # Must have exactly one warning for the keyless provider key
    keyless_warnings = [w for w in cfg.load_warnings if "keyless-local provider" in w]
    assert len(keyless_warnings) == 1, f"Expected 1 keyless warning, got {len(keyless_warnings)}"
    
    # Warning must identify the provider
    assert "ollama" in keyless_warnings[0]
    
    # Warning must identify the key name
    assert "ollama" in keyless_warnings[0]
    
    # Warning must NOT contain secret value (security check)
    assert SENTINEL_OLLAMA not in keyless_warnings[0]


def test_keyless_provider_warning_identifies_provider_and_key_only(tmp_path):
    """Warning for keyless provider identifies provider name and key name, not value."""
    SENTINEL = "KEYLESS_SENTINEL_ABC123"
    
    path = _write(tmp_path, f"ollama={SENTINEL}\n")
    cfg = KeyConfig.from_file(path, include_env=False)
    
    keyless_warnings = [w for w in cfg.load_warnings if "keyless-local provider" in w]
    assert len(keyless_warnings) == 1
    
    warning = keyless_warnings[0]
    assert "ollama" in warning  # provider name
    assert "'ollama'" in warning  # key name in quotes
    assert SENTINEL not in warning  # never the value
