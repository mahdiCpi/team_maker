"""Tests for path security utilities.

These tests verify that path traversal attacks are prevented by the
secure_resolve_path function.
"""
from __future__ import annotations

import os
import pytest
from pathlib import Path

from team_maker.utils.text_sanitizer import secure_resolve_path


class TestSecureResolvePath:
    """Test suite for secure_resolve_path function."""

    def test_valid_relative_path(self, tmp_path: Path) -> None:
        """Valid relative paths should resolve successfully."""
        base = tmp_path / "examples"
        base.mkdir()
        (base / "file.txt").write_text("test")

        result = secure_resolve_path(base, "file.txt")
        assert result == base / "file.txt"

    def test_valid_nested_path(self, tmp_path: Path) -> None:
        """Valid nested paths should resolve successfully."""
        base = tmp_path / "examples"
        base.mkdir()
        (base / "subdir").mkdir()
        (base / "subdir" / "file.txt").write_text("test")

        result = secure_resolve_path(base, "subdir/file.txt")
        assert result == base / "subdir" / "file.txt"

    def test_rejects_parent_traversal(self, tmp_path: Path) -> None:
        """Path with .. should be rejected."""
        base = tmp_path / "examples"
        base.mkdir()

        with pytest.raises(ValueError, match="traversal components"):
            secure_resolve_path(base, "../escape")

    def test_rejects_parent_traversal_with_file(self, tmp_path: Path) -> None:
        """Path with .. and filename should be rejected."""
        base = tmp_path / "examples"
        base.mkdir()

        with pytest.raises(ValueError, match="traversal components"):
            secure_resolve_path(base, "../etc/passwd")

    def test_rejects_absolute_path_unix(self, tmp_path: Path) -> None:
        """Absolute Unix paths should be rejected."""
        base = tmp_path / "examples"
        base.mkdir()

        # On Windows, this might not be an absolute path, so we check differently
        # The key is that it should not resolve within base
        with pytest.raises(ValueError):
            secure_resolve_path(base, "/etc/passwd")

    def test_rejects_windows_drive_letter(self, tmp_path: Path) -> None:
        """Windows drive letters should be rejected."""
        base = tmp_path / "examples"
        base.mkdir()

        with pytest.raises(ValueError):
            secure_resolve_path(base, "C:\\Windows\\System32")

    def test_rejects_mixed_traversal(self, tmp_path: Path) -> None:
        """Paths with multiple traversal components should be rejected."""
        base = tmp_path / "examples"
        base.mkdir()

        with pytest.raises(ValueError, match="traversal components"):
            secure_resolve_path(base, "../../../escape")

    def test_rejects_symlink_escape(self, tmp_path: Path) -> None:
        """Symlinks that escape the base directory should be rejected."""
        base = tmp_path / "examples"
        base.mkdir()

        # Create a symlink outside the base directory
        escape_dir = tmp_path / "escape"
        escape_dir.mkdir()
        symlink_path = base / "link"
        try:
            symlink_path.symlink_to(escape_dir)
        except (OSError, NotImplementedError):
            # Symlinks might not be supported on all systems (e.g., Windows without admin)
            pytest.skip("Symlinks not supported on this system")

        # Try to resolve through the symlink
        with pytest.raises(ValueError, match="escapes base directory"):
            secure_resolve_path(base, "link/file.txt")

    def test_rejects_dot_dot_in_middle(self, tmp_path: Path) -> None:
        """Paths with .. in the middle should be rejected."""
        base = tmp_path / "examples"
        base.mkdir()
        (base / "subdir").mkdir()

        with pytest.raises(ValueError, match="traversal components"):
            secure_resolve_path(base, "subdir/../../../etc/passwd")

    def test_accepts_path_object(self, tmp_path: Path) -> None:
        """Should accept Path objects as relative_path."""
        base = tmp_path / "examples"
        base.mkdir()
        (base / "file.txt").write_text("test")

        result = secure_resolve_path(base, Path("file.txt"))
        assert result == base / "file.txt"

    def test_accepts_empty_path(self, tmp_path: Path) -> None:
        """Empty path should resolve to base directory."""
        base = tmp_path / "examples"
        base.mkdir()

        result = secure_resolve_path(base, "")
        assert result == base

    def test_accepts_dot_only(self, tmp_path: Path) -> None:
        """Path with just . should resolve to base directory."""
        base = tmp_path / "examples"
        base.mkdir()

        # Note: . doesn't contain .. so it should be accepted
        # But we should check if it resolves correctly
        result = secure_resolve_path(base, ".")
        assert result == base

    # =========================================================================
    # Regressions from the Story 4.1 code review
    # =========================================================================

    def test_accepts_filename_containing_dot_dot_substring(self, tmp_path: Path) -> None:
        """Regression for code review P10: the previous check was a bare
        `".." in relative_path` substring test, which rejected legitimate
        filenames like this one even though no path traversal occurs."""
        base = tmp_path / "examples"
        base.mkdir()
        (base / "report..final.yaml").write_text("data")

        result = secure_resolve_path(base, "report..final.yaml")
        assert result == base / "report..final.yaml"

    def test_rejects_traversal_component_with_windows_separators(self, tmp_path: Path) -> None:
        """The component-wise check (split on both `/` and `\\`) still catches
        a genuine `..` segment when the path uses only backslash separators."""
        base = tmp_path / "examples"
        base.mkdir()

        with pytest.raises(ValueError, match="traversal components"):
            secure_resolve_path(base, "subdir\\..\\..\\etc\\passwd")

    def test_rejects_unc_path_regardless_of_host_os(self, tmp_path: Path) -> None:
        """Regression for code review P7: `os.path.isabs` alone only
        recognizes a UNC path when the process itself runs on Windows."""
        base = tmp_path / "examples"
        base.mkdir()

        with pytest.raises(ValueError, match="absolute"):
            secure_resolve_path(base, "\\\\server\\share\\file.txt")

    def test_does_not_force_lowercase_identity(self, tmp_path: Path) -> None:
        """Regression for code review P9/P12: the previous version lower-cased
        both sides of the containment check unconditionally, which is wrong on
        case-sensitive filesystems. A base directory with a mixed-case real
        name must still resolve a same-case request by identity, not by an
        incidental case fold applied to both sides."""
        base = tmp_path / "MixedCaseDir"
        base.mkdir()
        (base / "File.txt").write_text("data")

        result = secure_resolve_path(base, "File.txt")
        assert result == base / "File.txt"
