"""Tests for text sanitization utilities.

These tests verify that control characters, ANSI escape sequences, and OSC sequences
are properly removed from text content while preserving legitimate characters.
"""
from __future__ import annotations

import pytest

from team_maker.utils.text_sanitizer import sanitize_control_characters


class TestSanitizeControlCharacters:
    """Test suite for sanitize_control_characters function."""

    # =========================================================================
    # ANSI Escape Sequence Tests
    # =========================================================================

    def test_removes_ansi_color_codes(self) -> None:
        """ANSI color codes (e.g., ESC[31m for red) should be removed."""
        input_text = "\x1b[31mRed Text\x1b[0m"
        expected = "Red Text"
        assert sanitize_control_characters(input_text) == expected

    def test_removes_ansi_color_with_multiple_params(self) -> None:
        """ANSI codes with multiple parameters should be removed."""
        input_text = "\x1b[1;31;40mBold Red on Black\x1b[0m"
        expected = "Bold Red on Black"
        assert sanitize_control_characters(input_text) == expected

    def test_removes_ansi_cursor_movement(self) -> None:
        """ANSI cursor movement codes should be removed."""
        # ESC[H - Move cursor to home position
        input_text = "Start\x1b[HOverwrite"
        expected = "StartOverwrite"
        assert sanitize_control_characters(input_text) == expected

    def test_removes_ansi_clear_screen(self) -> None:
        """ANSI clear screen code (ESC[2J) should be removed."""
        input_text = "Before\x1b[2JAfter"
        expected = "BeforeAfter"
        assert sanitize_control_characters(input_text) == expected

    def test_removes_ansi_clear_line(self) -> None:
        """ANSI clear line code (ESC[K) should be removed."""
        input_text = "Text\x1b[K"
        expected = "Text"
        assert sanitize_control_characters(input_text) == expected

    def test_removes_multiple_ansi_sequences(self) -> None:
        """Multiple ANSI sequences should all be removed."""
        input_text = "\x1b[31mRed\x1b[0m \x1b[1mBold\x1b[0m Text"
        expected = "Red Bold Text"
        assert sanitize_control_characters(input_text) == expected

    # =========================================================================
    # OSC Sequence Tests
    # =========================================================================

    def test_removes_osc_hyperlink(self) -> None:
        """OSC 8 hyperlink sequences should be removed."""
        # OSC 8: ESC]8;;https://example.comESC\Click hereESC]8;;ESC\
        input_text = "\x1b]8;;https://example.com\x07Click here\x1b]8;;\x07"
        expected = "Click here"
        assert sanitize_control_characters(input_text) == expected

    def test_removes_osc_window_title(self) -> None:
        """OSC window title sequences should be removed."""
        # OSC 0: ESC]TitleESC\
        input_text = "\x1b]New Title\x07Rest of text"
        expected = "Rest of text"
        assert sanitize_control_characters(input_text) == expected

    def test_removes_osc_with_bel_terminator(self) -> None:
        """OSC sequences terminated with BEL (0x07) should be removed."""
        input_text = "Text\x1b]test\x07More text"
        expected = "TextMore text"
        assert sanitize_control_characters(input_text) == expected

    def test_removes_osc_with_st_terminator(self) -> None:
        """OSC sequences terminated with ST (ESC\\\\) should be removed."""
        input_text = "Text\x1b]test\x1b\\More text"
        expected = "TextMore text"
        assert sanitize_control_characters(input_text) == expected

    # =========================================================================
    # Control Character Tests
    # =========================================================================

    def test_removes_null_character(self) -> None:
        """Null characters (0x00) should be removed."""
        input_text = "Text\x00More"
        expected = "TextMore"
        assert sanitize_control_characters(input_text) == expected

    def test_removes_bell_character(self) -> None:
        """BEL character (0x07) should be removed when standalone."""
        input_text = "Text\x07More"
        expected = "TextMore"
        assert sanitize_control_characters(input_text) == expected

    def test_removes_backspace(self) -> None:
        """Backspace (0x08) should be removed."""
        input_text = "Text\x08More"
        expected = "TextMore"
        assert sanitize_control_characters(input_text) == expected

    def test_removes_form_feed(self) -> None:
        """Form feed (0x0C) should be removed."""
        input_text = "Text\x0cMore"
        expected = "TextMore"
        assert sanitize_control_characters(input_text) == expected

    def test_removes_del_character(self) -> None:
        """DEL character (0x7F) should be removed."""
        input_text = "Text\x7fMore"
        expected = "TextMore"
        assert sanitize_control_characters(input_text) == expected

    # =========================================================================
    # Preservation Tests
    # =========================================================================

    def test_preserves_printable_ascii(self) -> None:
        """All printable ASCII characters should be preserved."""
        input_text = "Hello, World! 123 @#$%^&*()_+-={}[]|:;<>?,./"
        expected = input_text
        assert sanitize_control_characters(input_text) == expected

    def test_preserves_newlines(self) -> None:
        """Newline characters should be preserved."""
        input_text = "Line 1\nLine 2\nLine 3"
        expected = input_text
        assert sanitize_control_characters(input_text) == expected

    def test_preserves_tabs(self) -> None:
        """Tab characters should be preserved."""
        input_text = "Col1\tCol2\tCol3"
        expected = input_text
        assert sanitize_control_characters(input_text) == expected

    def test_preserves_carriage_returns(self) -> None:
        """Carriage return characters should be preserved."""
        input_text = "Line1\r\nLine2"
        expected = input_text
        assert sanitize_control_characters(input_text) == expected

    def test_preserves_unicode(self) -> None:
        """Unicode characters should be preserved."""
        input_text = "Hello 世界 🌍 Привет"
        expected = input_text
        assert sanitize_control_characters(input_text) == expected

    def test_preserves_empty_string(self) -> None:
        """Empty string should remain empty."""
        assert sanitize_control_characters("") == ""

    def test_preserves_whitespace_only(self) -> None:
        """Whitespace-only strings should be preserved."""
        input_text = "   \t\n\r  "
        expected = input_text
        assert sanitize_control_characters(input_text) == expected

    # =========================================================================
    # Edge Cases and Combined Tests
    # =========================================================================

    def test_handles_mixed_content(self) -> None:
        """Mixed ANSI, OSC, and control characters should all be removed."""
        input_text = "\x1b[31mRed\x1b[0m\x1b]title\x07Normal\x00Text\x07"
        expected = "RedNormalText"
        assert sanitize_control_characters(input_text) == expected

    def test_handles_partial_sequences(self) -> None:
        """Partial/incomplete sequences should be handled gracefully."""
        # Partial ANSI sequence (missing terminating character)
        # Note: The pattern [0-9;:]* can match zero characters, then any letter terminates.
        # So \x1b[P would match and be removed. Use a non-letter terminator.
        input_text = "Text\x1b[31 Partial"
        # Here "31 " has a space which doesn't match [0-9;:], so the pattern won't match
        result = sanitize_control_characters(input_text)
        # The partial sequence stays because it doesn't match the pattern
        assert "Text" in result
        assert "Partial" in result

    def test_handles_consecutive_sequences(self) -> None:
        """Consecutive control sequences should all be removed."""
        input_text = "\x1b[31m\x1b[1m\x1b[4mBold Red Underline\x1b[0m"
        expected = "Bold Red Underline"
        assert sanitize_control_characters(input_text) == expected

    def test_handles_esc_esc(self) -> None:
        """Literal ESC ESC should be handled."""
        # Two consecutive ESC characters
        input_text = "Text\x1b\x1bMore"
        # First ESC might start a sequence, but without proper continuation it stays
        result = sanitize_control_characters(input_text)
        assert "Text" in result
        assert "More" in result

    def test_idempotent_sanitization(self) -> None:
        """Sanitizing already sanitized text should produce the same result."""
        input_text = "\x1b[31mRed\x1b[0m Text"
        first_pass = sanitize_control_characters(input_text)
        second_pass = sanitize_control_characters(first_pass)
        assert first_pass == second_pass == "Red Text"

    # =========================================================================
    # Security-Specific Tests
    # =========================================================================

    def test_prevents_cursor_movement_attack(self) -> None:
        """Cursor movement sequences that could manipulate terminal should be removed."""
        # ESC[H - Move cursor to home
        # ESC[A - Move cursor up
        # ESC[B - Move cursor down
        input_text = "\x1b[H\x1b[A\x1b[BAttack"
        expected = "Attack"
        assert sanitize_control_characters(input_text) == expected

    def test_prevents_screen_clear_attack(self) -> None:
        """Screen clear sequences should be removed."""
        # ESC[2J - Clear entire screen
        input_text = "\x1b[2JCleared!"
        expected = "Cleared!"
        assert sanitize_control_characters(input_text) == expected

    def test_prevents_hyperlink_injection(self) -> None:
        """OSC 8 hyperlink injection should be prevented."""
        # Malicious hyperlink that could be used in terminal
        input_text = "\x1b]8;;javascript:alert('xss')\x07Click me\x1b]8;;\x07"
        expected = "Click me"
        assert sanitize_control_characters(input_text) == expected

    def test_prevents_osc_command_execution(self) -> None:
        """OSC commands that could execute should be removed."""
        input_text = "\x1b]1;Malicious\x07Text"
        expected = "Text"
        assert sanitize_control_characters(input_text) == expected

    # =========================================================================
    # 8-bit (C1) Control Sequence Tests (code review P8)
    #
    # A terminal that honours 8-bit control codes treats \x9b/\x9d/\x9c as the
    # single-byte equivalents of ESC[ / ESC] / ESC\ -- the 7-bit-only patterns
    # above would let these bypass sanitization entirely.
    # =========================================================================

    def test_removes_8bit_csi_sequence(self) -> None:
        """\\x9b is the single-byte CSI equivalent of ESC[."""
        input_text = "Text\x9b31mRed\x9b0mMore"
        assert sanitize_control_characters(input_text) == "TextRedMore"

    def test_removes_8bit_osc_sequence_with_bel_terminator(self) -> None:
        """\\x9d is the single-byte OSC equivalent of ESC]."""
        input_text = "Text\x9dtest\x07More"
        assert sanitize_control_characters(input_text) == "TextMore"

    def test_removes_8bit_osc_sequence_with_8bit_st_terminator(self) -> None:
        """\\x9c is the single-byte ST equivalent of ESC\\."""
        input_text = "Text\x9dtest\x9cMore"
        assert sanitize_control_characters(input_text) == "TextMore"

    def test_removes_bare_c1_control_characters(self) -> None:
        """Any C1 control byte (0x80-0x9F) not consumed as part of a CSI/OSC
        sequence above is still stripped by the general control-char pattern."""
        input_text = "Text\x85More"  # NEL
        assert sanitize_control_characters(input_text) == "TextMore"
