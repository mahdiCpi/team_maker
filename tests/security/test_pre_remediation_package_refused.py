"""Permanent regression: a pre-remediation-shape package is detected and
refused, never partially loaded (spec FR-084; closes CHK040; SC-020;
Constitution V; tasks.md T112)."""
from __future__ import annotations

import pytest

from team_maker.adapters.tools.package_tool_resolver import (
    PackageToolResolver,
    PreRemediationPackageError,
)

_PRE_REMEDIATION_TOOLS_PY = '''
import subprocess

USE_SANDBOX = os.environ.get("SANDBOX_ENABLED", "false").lower() == "true"


def shell_command_tool(command):
    if USE_SANDBOX:
        return _run_sandboxed(command)
    return subprocess.run(command, shell=True, capture_output=True, text=True)


TOOL_REGISTRY = {"shell_command": shell_command_tool}
'''


def test_pre_remediation_package_refused_with_actionable_message(tmp_path):
    package_dir = tmp_path / "old_devops_team"
    package_dir.mkdir()
    (package_dir / "tools.py").write_text(_PRE_REMEDIATION_TOOLS_PY, encoding="utf-8")

    resolver = PackageToolResolver(package_dir)
    with pytest.raises(PreRemediationPackageError) as exc_info:
        resolver.resolve("shell")

    message = str(exc_info.value)
    assert "old_devops_team" in message
    assert "rebuild" in message.lower()


def test_pre_remediation_package_is_never_partially_loaded(tmp_path):
    """The module must not be imported/executed at all on refusal — proven
    by a side-effecting statement in the fixture module that would leave
    evidence (a file write) if the module ever ran."""
    package_dir = tmp_path / "old_team_with_side_effect"
    package_dir.mkdir()
    sentinel = package_dir / "side_effect_sentinel.txt"
    (package_dir / "tools.py").write_text(
        _PRE_REMEDIATION_TOOLS_PY
        + f'\nopen(r"{sentinel}", "w").write("module was executed")\n',
        encoding="utf-8",
    )

    resolver = PackageToolResolver(package_dir)
    with pytest.raises(PreRemediationPackageError):
        resolver.resolve("shell")

    assert not sentinel.exists(), "pre-remediation module must never be executed, only inspected as text"
