"""Permanent regression: mandatory sandbox controls (spec FR-073 to FR-078;
contract execution-policy.md Part E; Constitution V).

A breach here means `ToolPolicyRefusal` is raised (never a downgraded string
return) — Phase 6 (T116-T118) wires that raise to a **failed** receipt via
crewai's `ToolUsageErrorEvent`; recording the receipt itself is verified in
`tests/security/test_sandbox_controls.py`'s Phase 6 counterpart, not here.
"""
from __future__ import annotations

import subprocess

import pytest

from team_maker.tools.limits import DEFAULT_CONTROLS

from .conftest import load_tools_module, render_tools_source


def test_network_denied_by_default():
    source = render_tools_source()
    assert 'SANDBOX_NETWORK = "none"' in source


def test_network_permitted_only_when_operator_policy_allows():
    from team_maker.schema.request import SandboxConfig

    source = render_tools_source(
        sandbox=SandboxConfig(network="bridge"),
        effective_network="bridge",
        network_allowed=True,
    )
    assert 'SANDBOX_NETWORK = "bridge"' in source


def test_every_docker_invocation_carries_the_resource_flags():
    module = load_tools_module()
    flags = module._docker_resource_flags()
    assert "--network" in flags
    assert "--cpus" in flags
    assert "--memory" in flags
    assert "--pids-limit" in flags
    assert "--storage-opt" in flags


def test_per_class_timeouts_preserved_and_distinct():
    assert DEFAULT_CONTROLS.timeout_process_seconds == 120
    assert DEFAULT_CONTROLS.timeout_container_seconds == 300
    assert DEFAULT_CONTROLS.timeout_http_seconds == 30


def test_process_timeout_breach_terminates(monkeypatch):
    module = load_tools_module()
    monkeypatch.setattr(module.shutil, "which", lambda name: "/usr/bin/docker")

    def _fake_run(cmd, **kwargs):
        if cmd[:2] == ["docker", "info"]:
            class _R:
                returncode = 0
            return _R()
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=kwargs.get("timeout"))

    monkeypatch.setattr(module.subprocess, "run", _fake_run)
    with pytest.raises(module.ToolPolicyRefusal, match="timeout limit and was terminated"):
        module._run_sandboxed("sleep 1000")


def test_output_size_breach_terminates_rather_than_truncating(monkeypatch):
    """FR-077: exceeding the output cap is a limit breach, not a silent
    truncate-and-succeed."""
    module = load_tools_module()
    oversized = "x" * (module.MAX_OUTPUT_BYTES + 1)
    with pytest.raises(module.ToolPolicyRefusal, match="output exceeded"):
        module._capped_output(oversized)


def test_output_at_exactly_the_cap_is_not_a_breach():
    module = load_tools_module()
    exact = "x" * module.MAX_OUTPUT_BYTES
    assert module._capped_output(exact) == exact


def test_agent_supplied_control_values_are_ignored_not_merged():
    """FR-076: no tool parameter exists anywhere in the generated module
    through which a control value could be supplied — the controls are
    build-time module constants, not per-call arguments."""
    import inspect

    module = load_tools_module()
    for fn in (module.shell_tool.func, module.docker_runner_tool.func, module.test_runner_tool.func):
        params = set(inspect.signature(fn).parameters)
        assert not params & {
            "timeout", "cpu_limit", "memory_limit", "max_processes", "storage_limit", "network",
        }
