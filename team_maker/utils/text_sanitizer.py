"""Text sanitization utilities for security-sensitive content.

This module provides functions to sanitize text content before display,
removing or neutralizing control characters that could be used for terminal
manipulation attacks (ANSI escape sequences, OSC sequences, etc.).

The sanitization is designed to:
- Strip ANSI escape sequences (ESC [ ... m, etc.)
- Strip OSC sequences (ESC ] ... ST)
- Preserve printable characters and legitimate content
- Be applied at display time, not at storage time (raw content preserved)

Additionally, this module provides:
- Path security utilities to prevent path traversal attacks
- Exception sanitization to prevent sensitive data leakage in logs

Per AD-9: keys and sensitive data (including document text) must never be logged.
"""
from __future__ import annotations

import logging
import os
import re
import traceback
from pathlib import Path
from typing import Final

# ANSI escape sequence pattern: ESC followed by [ and various parameters, or
# the single-byte 8-bit CSI equivalent (\x9b). Matches: ESC [ ... m, ESC [ ...
# H, ESC [ ... J, \x9b ... m, etc.
_ANSI_ESCAPE_PATTERN: Final = re.compile(r"(?:\x1b\[|\x9b)[0-9;:*]*[a-zA-Z]")

# OSC (Operating System Command) sequence pattern: ESC ] ... ST, or the
# single-byte 8-bit OSC equivalent (\x9d) terminated by BEL (\x07), ESC \
# (\x1b\x5c), or the 8-bit ST equivalent (\x9c).
_OSC_PATTERN: Final = re.compile(r"(?:\x1b\]|\x9d)[^\x07\x1b\x9c]*(?:\x07|\x1b\x5c|\x9c)")

# General control character pattern: C0 controls (0x00-0x1F) except \t, \n,
# \r, DEL (0x7F), and the C1 control block (0x80-0x9F) -- the 8-bit
# equivalents of ESC-prefixed sequences (e.g. \x9b/\x9d/\x9c as CSI/OSC/ST)
# that would otherwise bypass the ANSI/OSC patterns above (code review P8).
# We preserve tabs, newlines, and carriage returns as they are legitimate whitespace.
_CONTROL_CHAR_PATTERN: Final = re.compile(
    r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]"
)

# Windows-style absolute paths (drive letter or UNC) that `os.path.isabs`
# only recognizes when the process itself runs on Windows (code review P7) --
# checked in addition to `os.path.isabs` so a Windows-shaped path is rejected
# regardless of the host OS running this check.
_WINDOWS_ABS_PATTERN: Final = re.compile(r"^(?:[A-Za-z]:[\\/]|[\\/]{2})")

# Values following one of these labels (api_key=..., "token": "...", etc.)
# are treated as secrets regardless of shape or length.
_LABELED_SECRET_PATTERN: Final = re.compile(
    r"(?i)\b(api[_-]?key|access[_-]?token|secret|password|credential)\b"
    r"\s*[:=]\s*[\"']?([^\s\"',;]+)"
)
# `Authorization: Bearer <token>` (or a bare `Bearer <token>` fragment).
_BEARER_TOKEN_PATTERN: Final = re.compile(r"(?i)\bBearer\s+([A-Za-z0-9\-._~+/]+=*)")
# Known provider API key prefixes.
_PROVIDER_KEY_PATTERNS: Final = (
    re.compile(r"sk-[A-Za-z0-9-]{20,}"),  # OpenAI / Anthropic (sk-ant-...)
    re.compile(r"xai-[A-Za-z0-9-]{20,}"),  # XAI
    re.compile(r"gsk_[A-Za-z0-9]{20,}"),  # Groq
)
# Conservative high-entropy fallback for secret shapes with no known label or
# prefix -- deliberately favors over-redaction (code review D4). Each match is
# additionally required to contain at least one digit (see `_redact_secrets`)
# so a long, purely-alphabetic identifier -- a test function name, a module
# path segment -- is not mistaken for a secret; real key/token material is
# essentially always a mix of letters and digits.
_HIGH_ENTROPY_PATTERNS: Final = (
    re.compile(r"[A-Za-z0-9+/]{30,}={0,2}"),  # base64-like
    re.compile(r"[A-Za-z0-9_-]{20,}"),  # generic long alphanumeric token
)


def secure_resolve_path(base_dir: Path, relative_path: str | Path) -> Path:
    """Securely resolve a relative path within a base directory.

    This function prevents path traversal attacks by ensuring the resolved path
    stays within the specified base directory. It validates that the path doesn't
    contain traversal components (..) and resolves symlinks safely.

    Args:
        base_dir: The base directory that the resolved path must be within.
        relative_path: The relative path to resolve (string or Path object).

    Returns:
        The resolved absolute path within base_dir.

    Raises:
        ValueError: If the resolved path would escape the base directory or
                   if the relative path contains traversal components.

    Example:
        >>> secure_resolve_path(Path("/safe/dir"), "file.txt")
        PosixPath('/safe/dir/file.txt')
        >>> secure_resolve_path(Path("/safe/dir"), "../escape")  # doctest: +IGNORE_EXCEPTION_DETAIL
        Traceback (most recent call last):
            ...
        ValueError: Path contains traversal components: ../escape
    """
    # Convert to string if Path object
    if isinstance(relative_path, Path):
        relative_path = str(relative_path)

    # Check for path traversal *components* -- not a bare substring check, so
    # a legitimate filename that merely contains ".." (e.g. "report..final.yaml")
    # is not rejected (code review P10). Covers both Unix (../) and Windows
    # (..\) separators.
    segments = relative_path.replace("\\", "/").split("/")
    if any(segment == ".." for segment in segments):
        raise ValueError(f"Path contains traversal components: {relative_path}")

    # Check for absolute paths (Unix, Windows drive letter, or UNC) regardless
    # of the host OS running this check (code review P7).
    if os.path.isabs(relative_path) or _WINDOWS_ABS_PATTERN.match(relative_path):
        raise ValueError(f"Path is absolute: {relative_path}")

    # Get absolute base directory
    base_abs = base_dir.resolve()

    # Build target path and resolve it (this follows symlinks)
    target_path = (base_abs / relative_path).resolve()

    # Normalize paths for comparison. `os.path.normcase` folds case only on
    # platforms where the filesystem is actually case-insensitive (Windows) --
    # a blanket `.lower()` was incorrect on case-sensitive POSIX filesystems
    # (code review P9/P12).
    base_abs_str = os.path.normcase(str(base_abs)).replace("\\", "/")
    target_str = os.path.normcase(str(target_path)).replace("\\", "/")

    # Ensure target is within base directory
    # Check both exact match and path with trailing slash
    if not (target_str == base_abs_str or target_str.startswith(base_abs_str + "/")):
        raise ValueError(
            f"Path '{relative_path}' escapes base directory '{base_dir}'. "
            f"Resolved to '{target_path}' which is outside '{base_abs}'"
        )

    return target_path


def _redact_known_secret_values(text: str) -> str:
    """Redact any substring that exactly matches a currently configured
    secret value (e.g. a bridged provider credential or the API's own auth
    key), regardless of shape. Only environment values of a plausible secret
    length are considered, so short/common configuration values (flags,
    single characters) are never treated as secrets.
    """
    for value in os.environ.values():
        if len(value) >= 12 and value in text:
            text = text.replace(value, "[REDACTED]")
    return text


def _redact_if_digit_present(match: re.Match[str]) -> str:
    """Redact a high-entropy match only if it contains a digit.

    A long run of pure letters and underscores is far more likely to be a
    Python identifier or a filename/module-path segment (e.g. inside a
    traceback frame) than an actual secret -- real key/token material is
    essentially always a mix of letters and digits. Without this guard, the
    generic fallback in `_HIGH_ENTROPY_PATTERNS` redacted ordinary function
    and test names, making a sanitized traceback useless for debugging.
    """
    value = match.group(0)
    return "[REDACTED]" if any(ch.isdigit() for ch in value) else value


def _redact_secrets(text: str) -> str:
    """Redact likely secrets from *text* using a combined approach.

    Shared by both the logging path (`sanitize_exception_message`) and the
    display path (`sanitize_exception_for_display`) so there is exactly one
    place that decides what "looks like a secret" (code review D3/D4) --
    exact configured secret values, labeled values (api_key=..., Bearer ...),
    known provider-key prefixes, and a conservative high-entropy fallback for
    everything else. Deliberately prefers over-redaction to under-redaction.
    """
    text = _redact_known_secret_values(text)
    text = _BEARER_TOKEN_PATTERN.sub("Bearer [REDACTED]", text)
    text = _LABELED_SECRET_PATTERN.sub(lambda m: f"{m.group(1)}=[REDACTED]", text)
    for pattern in _PROVIDER_KEY_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    for pattern in _HIGH_ENTROPY_PATTERNS:
        text = pattern.sub(_redact_if_digit_present, text)
    return text


def sanitize_exception_message(exc: BaseException, max_length: int = 500) -> str:
    """Sanitize an exception message to prevent sensitive data leakage.

    This function removes control characters, redacts likely secrets, and
    truncates very long messages (which might contain document text or other
    sensitive data) before they are logged.

    Per AD-9: keys and sensitive data (including document text) must never be
    logged.

    Args:
        exc: The exception whose message to sanitize.
        max_length: Maximum length of the sanitized message.

    Returns:
        A sanitized version of the exception message, truncated if necessary.
    """
    msg = str(exc)
    msg = sanitize_control_characters(msg)
    msg = _redact_secrets(msg)
    # Truncate to max_length to prevent large data dumps (e.g., document text)
    if len(msg) > max_length:
        msg = msg[:max_length] + "... [truncated]"
    return msg


def sanitize_text_for_display(text: str, max_length: int = 1000) -> str:
    """Sanitize an arbitrary string for safe display to users.

    Removes control characters, redacts likely secrets (`_redact_secrets`,
    shared with the logging path), and truncates very long text. Used both
    for a formatted exception message and for standalone error strings like
    `ComposerError.errors` entries, which carry the same leak risk but are
    not exceptions themselves (code review P6).

    Per AD-9: keys and sensitive data must never be exposed to users.
    """
    text = sanitize_control_characters(text)
    text = _redact_secrets(text)
    if len(text) > max_length:
        text = text[:max_length] + "... [truncated]"
    return text


def sanitize_exception_for_display(exc: BaseException, max_length: int = 1000) -> str:
    """Sanitize an exception message for safe display to users.

    Per AD-9: keys and sensitive data must never be exposed to users.

    Args:
        exc: The exception whose message to sanitize.
        max_length: Maximum length of the sanitized message for display.

    Returns:
        A sanitized version of the exception message safe for display.
    """
    return sanitize_text_for_display(str(exc), max_length)


_MAX_TRACEBACK_LENGTH: Final = 4000


def log_exception_safely(logger, message: str, exc: BaseException) -> None:
    """Log an exception safely, sanitizing the message to prevent data leakage.

    This function logs an exception with a sanitized message to prevent
    sensitive data (like document text, API keys, etc.) from appearing in logs.

    Per AD-9: keys and sensitive data must never be logged.

    Args:
        logger: The logger instance to use. Accepts `logging.Logger` or
            `logging.LoggerAdapter` -- anything implementing the same
            `.error()`/`.debug()` interface (code review P11).
        message: The message to log.
        exc: The exception to log.
    """
    if not isinstance(logger, (logging.Logger, logging.LoggerAdapter)):
        raise TypeError(f"Expected a logging.Logger or LoggerAdapter, got {type(logger)}")

    # Get the sanitized exception message
    sanitized_msg = sanitize_exception_message(exc)

    # Log the message with exception type
    logger.error("%s: %s (%s)", message, sanitized_msg, type(exc).__name__)

    # Log the stack frames only, at debug level -- never the final
    # "ExceptionType: message" line, which repeats `str(exc)` verbatim and
    # would bypass the sanitization above entirely (code review P3). Built
    # from `exc.__traceback__` explicitly rather than the ambient
    # `sys.exc_info()`, which is only valid inside the exact active `except`
    # block for *this* exception.
    frames = traceback.format_exception(type(exc), exc, exc.__traceback__)
    frames = frames[:-1] if frames else frames
    sanitized_tb = sanitize_control_characters("".join(frames))
    sanitized_tb = _redact_secrets(sanitized_tb)
    if len(sanitized_tb) > _MAX_TRACEBACK_LENGTH:
        sanitized_tb = sanitized_tb[:_MAX_TRACEBACK_LENGTH] + "... [truncated]"
    logger.debug("Exception traceback (message omitted, logged above):\n%s", sanitized_tb)


def sanitize_control_characters(text: str) -> str:
    """Remove ANSI escape sequences, OSC sequences, and control characters from text.

    This function sanitizes text content by removing:
    - ANSI escape sequences (e.g., ESC[31m for red color)
    - OSC sequences (e.g., ESC]8;;https://example.com ESC\\ for hyperlinks)
    - Other control characters (except tab, newline, carriage return)

    The function preserves:
    - All printable characters
    - Tab (\\t), newline (\\n), and carriage return (\\r) characters
    - The original content structure and meaning

    Args:
        text: The input text that may contain control sequences.

    Returns:
        The sanitized text with all control sequences removed.

    Example:
        >>> sanitize_control_characters("Normal text\\x1b[31mRed\\x1b[0m")
        'Normal textRed'
        >>> sanitize_control_characters("Line1\\nLine2")
        'Line1\\nLine2'
    """
    # Apply all sanitization patterns
    result = _ANSI_ESCAPE_PATTERN.sub("", text)
    result = _OSC_PATTERN.sub("", result)
    result = _CONTROL_CHAR_PATTERN.sub("", result)
    return result
