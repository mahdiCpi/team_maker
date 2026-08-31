"""Mount evaluation order and dangerous-location floor tests (spec FR-014 to
FR-017, FR-079; audit RC-10; D-8; tasks T063-T067)."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from team_maker.tools.policy import (
    MountAllowlist,
    MountAllowlistEntry,
    MountRefused,
    evaluate_mount,
    is_dangerous,
)


@pytest.fixture
def non_home_workspace(tmp_path_factory: pytest.TempPathFactory):
    """`tmp_path` sits under the current OS user's home tree (e.g.
    `C:\\Users\\...\\AppData\\Local\\Temp` on Windows), which the
    dangerous-location floor's own home-directory pattern (data-model.md §4
    -- `C:\\Users\\*`, mirroring `/Users/*` and `/home/*`) deliberately
    covers. A workspace outside that tree is needed to test the *ordinary,
    safe* path case without the floor's own broad home-tree rule firing.
    This repository's own working tree lives outside the home tree, so a
    scratch directory is created there and removed after the test."""
    root = Path.cwd() / "_test_scratch_non_home_workspace"
    root.mkdir(exist_ok=True)
    try:
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


class TestDangerousLocationFloor:
    def test_host_root_is_dangerous(self):
        assert is_dangerous(Path("/").resolve())

    def test_etc_is_dangerous(self):
        # Compare against the *normalized string* form to avoid the Windows
        # resolve()-reinterprets-unix-paths issue this module works around.
        from team_maker.tools.policy import _normalize

        assert is_dangerous(Path("/etc"))  # constructed, not resolved — exercises normalize path
        # exercise with an explicit posix-shaped Path that resolve() would mis-map on Windows
        assert _normalize("/etc/foo") == "/etc/foo"

    def test_ordinary_workspace_path_is_not_dangerous(self, non_home_workspace: Path):
        workspace = non_home_workspace / "workspace"
        workspace.mkdir()
        assert not is_dangerous(workspace.resolve())

    def test_home_directory_is_dangerous(self):
        home = Path("~").expanduser().resolve()
        assert is_dangerous(home)


class TestEvaluateMountOrder:
    def test_non_allowlisted_mount_refused(self, non_home_workspace: Path):
        with pytest.raises(MountRefused, match="not in the operator-configured allowlist"):
            evaluate_mount(str(non_home_workspace / "unlisted"), MountAllowlist())

    def test_allowlisted_safe_path_accepted(self, non_home_workspace: Path):
        workspace = non_home_workspace / "workspace"
        workspace.mkdir()
        allowlist = MountAllowlist((MountAllowlistEntry(alias="ws", host_path=str(workspace)),))

        entry = evaluate_mount(str(workspace), allowlist)
        assert entry.alias == "ws"

    def test_allowlisted_path_resolving_to_dangerous_location_refused(self):
        """Deny beats allow: an operator entry pointing at a dangerous
        location is refused regardless of being on the allowlist (FR-016)."""
        allowlist = MountAllowlist((MountAllowlistEntry(alias="dangerous-root", host_path="/"),))
        with pytest.raises(MountRefused, match="dangerous-location floor"):
            evaluate_mount("/", allowlist)

    def test_subpath_of_allowlisted_entry_is_accepted(self, non_home_workspace: Path):
        workspace = non_home_workspace / "workspace"
        (workspace / "sub").mkdir(parents=True)
        allowlist = MountAllowlist((MountAllowlistEntry(alias="ws", host_path=str(workspace)),))

        entry = evaluate_mount(str(workspace / "sub"), allowlist)
        assert entry.alias == "ws"

    def test_symlink_to_dangerous_location_is_refused_after_resolution(self, non_home_workspace: Path):
        """FR-016: resolution happens before the deny-check so a symlinked
        allowlist entry cannot launder a dangerous path (D-8)."""
        target_home = Path("~").expanduser().resolve()
        symlink_path = non_home_workspace / "sneaky_link"
        try:
            symlink_path.symlink_to(target_home, target_is_directory=True)
        except (OSError, NotImplementedError):
            pytest.skip("symlink creation not permitted in this environment")

        allowlist = MountAllowlist((MountAllowlistEntry(alias="sneaky", host_path=str(symlink_path)),))
        with pytest.raises(MountRefused, match="dangerous-location floor"):
            evaluate_mount(str(symlink_path), allowlist)
