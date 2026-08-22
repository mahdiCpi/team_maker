"""Tests for secret redaction and safe exception logging (Story 4.1 code
review D3/D4/P3/P11).

Distinct from `test_text_sanitizer.py` (control characters / ANSI-OSC
stripping): this file covers what the module does with likely *secrets* and
how it logs exceptions safely, per AD-9.
"""
from __future__ import annotations

import logging

import pytest

from team_maker.utils.text_sanitizer import (
    log_exception_safely,
    sanitize_exception_for_display,
    sanitize_exception_message,
    sanitize_text_for_display,
)


class TestSecretRedaction:
    def test_labeled_api_key_value_is_redacted(self) -> None:
        text = sanitize_text_for_display("failed: api_key=super-secret-value-123")
        assert "super-secret-value-123" not in text
        assert "[REDACTED]" in text

    def test_bearer_token_is_redacted(self) -> None:
        text = sanitize_text_for_display("Authorization: Bearer abc.def-token-value-xyz")
        assert "abc.def-token-value-xyz" not in text
        assert "Bearer [REDACTED]" in text

    def test_anthropic_style_key_prefix_is_redacted(self) -> None:
        text = sanitize_text_for_display("error from sk-ant-abcdefghijklmnopqrstuvwxyz")
        assert "sk-ant-abcdefghijklmnopqrstuvwxyz" not in text

    def test_groq_style_key_prefix_is_redacted(self) -> None:
        text = sanitize_text_for_display("error from gsk_abcdefghijklmnopqrstuvwxyz")
        assert "gsk_abcdefghijklmnopqrstuvwxyz" not in text

    def test_high_entropy_token_with_no_label_is_redacted(self) -> None:
        """Regression for code review D4: the old 32/40-char thresholds let a
        31-char (or shorter) secret through completely unredacted."""
        text = sanitize_text_for_display("token value: aB3dE7gH9jK1mN3pQ5rS")  # 20 chars
        assert "aB3dE7gH9jK1mN3pQ5rS" not in text

    def test_short_common_words_are_not_redacted(self) -> None:
        """Over-redaction should not eat ordinary short words/sentences."""
        text = sanitize_text_for_display("connection timed out after 30 seconds")
        assert text == "connection timed out after 30 seconds"

    def test_a_currently_configured_env_secret_is_redacted_even_when_shape_alone_would_not_match(
        self, monkeypatch
    ) -> None:
        """"Exact configured secret values" (code review D4) -- a value with
        spaces (so it matches none of the label/prefix/entropy patterns, which
        all require an unbroken run of token characters) must still be caught
        purely because it is currently published in the environment."""
        secret = "my configured secret value"
        monkeypatch.setenv("SOME_PROVIDER_TOKEN", secret)
        text = sanitize_text_for_display(f"upstream said: {secret}")
        assert secret not in text


class TestSanitizeExceptionMessageRedactsNotJustTruncates:
    def test_short_message_with_embedded_secret_is_redacted(self) -> None:
        """Regression for code review D3: a message under the truncation
        length previously passed through completely unredacted -- only
        control characters were stripped, nothing else."""
        exc = ValueError("provider key sk-ant-abcdefghijklmnopqrstuvwxyz rejected")
        sanitized = sanitize_exception_message(exc)
        assert "sk-ant-abcdefghijklmnopqrstuvwxyz" not in sanitized

    def test_display_and_logging_paths_share_the_same_redaction(self) -> None:
        exc = ValueError("api_key=totally-a-real-secret-value")
        assert "totally-a-real-secret-value" not in sanitize_exception_message(exc)
        assert "totally-a-real-secret-value" not in sanitize_exception_for_display(exc)


class TestLogExceptionSafely:
    def test_accepts_a_logger_adapter(self, caplog) -> None:
        """Regression for code review P11: a strict `isinstance(logger,
        logging.Logger)` check rejected valid duck-typed loggers that
        implement the same `.error()`/`.debug()` interface."""
        base_logger = logging.getLogger("test.adapter.logger")
        adapter = logging.LoggerAdapter(base_logger, {})

        with caplog.at_level(logging.DEBUG, logger="test.adapter.logger"):
            log_exception_safely(adapter, "context", ValueError("boom"))

        assert "context" in caplog.text

    def test_rejects_a_non_logger(self) -> None:
        with pytest.raises(TypeError):
            log_exception_safely("not a logger", "context", ValueError("boom"))

    def test_traceback_debug_log_does_not_repeat_the_raw_message(self, caplog) -> None:
        """Regression for code review P3: `traceback.format_exc()` re-embedded
        `str(exc)` verbatim as its last line, bypassing the sanitization
        already applied to the ERROR-level message logged just above it."""
        logger = logging.getLogger("test.traceback.logger")
        secret = "sk-ant-DEBUG-LEAK-CHECK-abcdefghij"

        try:
            raise ValueError(f"provider failed: {secret}")
        except ValueError as exc:
            with caplog.at_level(logging.DEBUG, logger="test.traceback.logger"):
                log_exception_safely(logger, "context", exc)

        assert secret not in caplog.text

    def test_traceback_debug_log_still_carries_stack_frame_info(self, caplog) -> None:
        """The fix must not throw away the actual debugging value -- file/line
        frame info should still reach the debug log, only the final
        "ExceptionType: message" line is omitted."""
        logger = logging.getLogger("test.traceback.frames")

        try:
            raise ValueError("boom")
        except ValueError as exc:
            with caplog.at_level(logging.DEBUG, logger="test.traceback.frames"):
                log_exception_safely(logger, "context", exc)

        assert "test_exception_sanitizer.py" in caplog.text
