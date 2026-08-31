"""Operator tool-policy config source tests (spec FR-085; closes CHK001,
CHK005; tasks T054)."""
from __future__ import annotations

from pathlib import Path

from team_maker.tools.config import load_tool_policy


def test_absent_file_denies_all_risky_and_carries_a_diagnostic(tmp_path: Path):
    config = load_tool_policy(tmp_path / "nonexistent.yaml")
    assert config.authorization.enabled_tools == frozenset()
    assert config.network_allowed is False
    assert config.diagnostic is not None
    assert "not found" in config.diagnostic


def test_malformed_yaml_denies_all_risky_and_carries_a_diagnostic(tmp_path: Path):
    bad = tmp_path / "policy.yaml"
    bad.write_text(":::not: valid: yaml: at: all:::", encoding="utf-8")
    config = load_tool_policy(bad)
    assert config.authorization.enabled_tools == frozenset()
    assert config.diagnostic is not None


def test_non_mapping_yaml_denies_all_risky(tmp_path: Path):
    not_a_map = tmp_path / "policy.yaml"
    not_a_map.write_text("- just\n- a\n- list\n", encoding="utf-8")
    config = load_tool_policy(not_a_map)
    assert config.authorization.enabled_tools == frozenset()
    assert config.diagnostic is not None


def test_well_formed_policy_is_parsed_correctly(tmp_path: Path):
    policy_file = tmp_path / "policy.yaml"
    policy_file.write_text(
        """
enabled_tools:
  - docker_runner
network_allowed: true
mount_allowlist:
  - alias: workspace
    host_path: /tmp/workspace
    writable: true
controls:
  cpu_limit: "2.0"
""",
        encoding="utf-8",
    )
    config = load_tool_policy(policy_file)
    assert config.authorization.enabled_tools == frozenset({"docker_runner"})
    assert config.network_allowed is True
    assert len(config.mount_allowlist.entries) == 1
    assert config.mount_allowlist.entries[0].alias == "workspace"
    assert config.mount_allowlist.entries[0].writable is True
    assert config.controls.cpu_limit == "2.0"
    assert config.diagnostic is None


def test_unspecified_controls_use_defaults(tmp_path: Path):
    policy_file = tmp_path / "policy.yaml"
    policy_file.write_text("enabled_tools: []\n", encoding="utf-8")
    config = load_tool_policy(policy_file)
    from team_maker.tools.limits import DEFAULT_CONTROLS

    assert config.controls == DEFAULT_CONTROLS
