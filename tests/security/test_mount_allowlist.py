"""Permanent regression: mount allowlist evaluation order and dangerous-
location floor (spec FR-014 to FR-017, FR-079; audit RC-10; contract
execution-policy.md Part D; Constitution V).

Exercises both the product-side algorithm (`team_maker/tools/policy.py`,
covered in depth by `tests/unit/tools/test_policy.py`) and its rendered
mirror inside the generated package, since FR-081 requires the two to
enforce identically.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from team_maker.tools.policy import MountAllowlist, MountAllowlistEntry, MountRefused, evaluate_mount

from .conftest import load_tools_module


@pytest.fixture
def non_home_workspace():
    """`tmp_path` sits under the OS user's home tree, which the dangerous-
    location floor deliberately covers (see
    tests/unit/tools/test_policy.py). A workspace outside that tree is
    needed to exercise the ordinary, safe-path case."""
    root = Path.cwd() / "_test_scratch_security_non_home_workspace"
    root.mkdir(exist_ok=True)
    try:
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_non_allowlisted_mount_refused_product_side():
    with pytest.raises(MountRefused, match="not in the operator-configured allowlist"):
        evaluate_mount("/some/unlisted/path", MountAllowlist())


def test_deny_beats_allow_product_side():
    allowlist = MountAllowlist((MountAllowlistEntry(alias="root", host_path="/"),))
    with pytest.raises(MountRefused, match="dangerous-location floor"):
        evaluate_mount("/", allowlist)


def test_mount_without_explicit_writable_defaults_read_only():
    entry = MountAllowlistEntry(alias="ws", host_path="/tmp/ws")
    assert entry.writable is False


def test_refusal_never_degrades_to_running_without_the_mount(tmp_path):
    """`docker_runner_tool` must raise on a non-allowlisted mount rather than
    silently running the container without it."""
    module = load_tools_module()
    with pytest.raises(module.ToolPolicyRefusal, match="not in the operator-configured allowlist"):
        module._evaluate_mount(str(tmp_path / "unlisted"))


def test_generated_package_mirror_refuses_non_allowlisted_mount():
    module = load_tools_module()
    with pytest.raises(module.ToolPolicyRefusal, match="not in the operator-configured allowlist"):
        module._evaluate_mount("/some/unlisted/path")


def test_generated_package_mirror_denies_dangerous_location_even_if_allowlisted():
    entry = {"alias": "dangerous-root", "host_path": "/", "writable": True}
    module = load_tools_module(mount_allowlist=[entry])
    with pytest.raises(module.ToolPolicyRefusal, match="dangerous-location floor"):
        module._evaluate_mount("/")


def test_generated_package_mirror_accepts_allowlisted_safe_path(non_home_workspace):
    workspace = non_home_workspace / "workspace"
    workspace.mkdir(exist_ok=True)
    entry = {"alias": "ws", "host_path": str(workspace), "writable": False}
    module = load_tools_module(mount_allowlist=[entry])
    matched = module._evaluate_mount(str(workspace))
    assert matched["alias"] == "ws"
    assert matched["writable"] is False
