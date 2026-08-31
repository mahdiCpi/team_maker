"""Permanent regression: no raw resolved host path in any user-facing
surface; a rejected mount is named by alias or sanitized identifier (spec
FR-070 to FR-072; contract execution-policy.md Part F; Constitution V)."""
from __future__ import annotations

import pytest

from team_maker.tools.identifiers import sanitized_id
from team_maker.tools.policy import MountAllowlist, MountAllowlistEntry, MountRefused, evaluate_mount

from .conftest import load_tools_module

_SECRET_PATH = "/very/secret/host/path/that/must/never/leak"


def test_non_allowlisted_refusal_names_a_sanitized_identifier_not_the_raw_path():
    with pytest.raises(MountRefused) as exc_info:
        evaluate_mount(_SECRET_PATH, MountAllowlist())
    assert _SECRET_PATH not in str(exc_info.value)
    assert sanitized_id(_SECRET_PATH) in str(exc_info.value)


def test_dangerous_location_refusal_names_the_operator_alias_not_the_raw_path():
    allowlist = MountAllowlist((MountAllowlistEntry(alias="totally-dangerous", host_path="/"),))
    with pytest.raises(MountRefused) as exc_info:
        evaluate_mount("/", allowlist)
    assert "totally-dangerous" in str(exc_info.value)


def test_sanitized_identifier_is_stable_and_non_reversible():
    first = sanitized_id(_SECRET_PATH)
    second = sanitized_id(_SECRET_PATH)
    assert first == second
    assert _SECRET_PATH not in first
    assert first.startswith("mount-")


def test_generated_package_mirror_never_leaks_the_raw_path_on_refusal(tmp_path):
    secret = str(tmp_path / "secret_workspace")
    module = load_tools_module()
    with pytest.raises(module.ToolPolicyRefusal) as exc_info:
        module._evaluate_mount(secret)
    assert secret not in str(exc_info.value)
