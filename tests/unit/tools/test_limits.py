"""Sandbox control defaults (spec FR-078, FR-086; tasks T074, T090)."""
from __future__ import annotations

from team_maker.tools.config import load_tool_policy
from team_maker.tools.limits import DEFAULT_CONTROLS


def test_silent_operator_policy_yields_the_documented_default(tmp_path):
    cfg = load_tool_policy(tmp_path / "absent.yaml")
    assert cfg.controls == DEFAULT_CONTROLS


def test_preserved_pre_existing_timeout_values():
    """These three preserve tools.py.j2's pre-remediation hardcoded values —
    collapsing to one value would itself be a behaviour change (data-model.md
    §10)."""
    assert DEFAULT_CONTROLS.timeout_process_seconds == 120
    assert DEFAULT_CONTROLS.timeout_container_seconds == 300
    assert DEFAULT_CONTROLS.timeout_http_seconds == 30


def test_new_mandatory_limits_are_restrictive_not_unbounded():
    assert DEFAULT_CONTROLS.cpu_limit == "1.0"
    assert DEFAULT_CONTROLS.memory_limit == "512m"
    assert DEFAULT_CONTROLS.max_processes == 128
    assert DEFAULT_CONTROLS.storage_limit == "1g"
    assert DEFAULT_CONTROLS.max_output_bytes == 1_048_576


def test_operator_override_replaces_only_the_specified_fields(tmp_path):
    policy_file = tmp_path / "team_maker.tools.yaml"
    policy_file.write_text("controls:\n  cpu_limit: '2.0'\n")
    cfg = load_tool_policy(policy_file)
    assert cfg.controls.cpu_limit == "2.0"
    assert cfg.controls.memory_limit == DEFAULT_CONTROLS.memory_limit  # untouched fields fall back
