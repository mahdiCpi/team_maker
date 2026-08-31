"""Permanent regression: mandatory sandbox, fail-closed (spec FR-012, FR-013,
FR-082; contract execution-policy.md Parts C, E; Constitution V).

**MUST NOT be skipped when no container runtime is present** — it is
meaningful precisely then, and a skipped fail-closed test is the weakening
Constitution V prohibits. Every scenario here monkeypatches the rendered
module's own `shutil`/`subprocess`, so the outcome never depends on whether
Docker actually happens to be installed on the machine running the suite.
"""
from __future__ import annotations

import subprocess

import pytest

from .conftest import load_tools_module


@pytest.fixture
def module():
    return load_tools_module()


def test_no_environment_variable_or_config_can_disable_sandboxing():
    """D-7: the toggle is deleted, not defaulted to true. No name in the
    rendered source reads an opt-out."""
    from .conftest import render_tools_source

    source = render_tools_source()
    assert "USE_SANDBOX" not in source
    assert 'os.environ.get("SANDBOX_ENABLED"' not in source


def test_runtime_absent_refuses(module, monkeypatch):
    monkeypatch.setattr(module.shutil, "which", lambda name: None)
    with pytest.raises(module.ToolPolicyRefusal, match="not installed"):
        module._check_sandbox_available()


def test_runtime_present_but_unreachable_refuses_on_timeout(module, monkeypatch):
    monkeypatch.setattr(module.shutil, "which", lambda name: "/usr/bin/docker")

    def _raise_timeout(*a, **k):
        raise subprocess.TimeoutExpired(cmd="docker info", timeout=10)

    monkeypatch.setattr(module.subprocess, "run", _raise_timeout)
    with pytest.raises(module.ToolPolicyRefusal, match="did not respond"):
        module._check_sandbox_available()


def test_runtime_present_but_unreachable_refuses_on_oserror(module, monkeypatch):
    monkeypatch.setattr(module.shutil, "which", lambda name: "/usr/bin/docker")

    def _raise_oserror(*a, **k):
        raise OSError("no such file")

    monkeypatch.setattr(module.subprocess, "run", _raise_oserror)
    with pytest.raises(module.ToolPolicyRefusal, match="unreachable"):
        module._check_sandbox_available()


def test_daemon_unreachable_nonzero_returncode_refuses(module, monkeypatch):
    monkeypatch.setattr(module.shutil, "which", lambda name: "/usr/bin/docker")

    class _Result:
        returncode = 1

    monkeypatch.setattr(module.subprocess, "run", lambda *a, **k: _Result())
    with pytest.raises(module.ToolPolicyRefusal, match="unreachable"):
        module._check_sandbox_available()


def test_sandbox_image_unavailable_refuses_distinctly(module):
    with pytest.raises(module.ToolPolicyRefusal, match="image is unavailable"):
        module._raise_on_docker_cli_failure(125, "Unable to find image 'bogus:latest' locally\nno such image")


def test_declared_control_unenforceable_refuses_distinctly(module):
    with pytest.raises(module.ToolPolicyRefusal, match="resource control could not be enforced"):
        module._raise_on_docker_cli_failure(125, "docker: Error response: unknown flag: --pids-limit")


def test_generic_container_creation_failure_refuses_distinctly(module):
    with pytest.raises(module.ToolPolicyRefusal, match="container creation failed"):
        module._raise_on_docker_cli_failure(125, "docker: Error response from daemon: some other failure")


def test_containerized_command_failure_is_not_a_sandbox_refusal(module):
    """A non-125 exit code is the CONTAINERIZED COMMAND's own status (e.g. a
    failing shell command or test run) — ordinary tool output, never
    conflated with a sandbox-establishment failure."""
    module._raise_on_docker_cli_failure(1, "some command printed to stderr and exited 1")  # must not raise


def test_sandbox_unavailable_mid_run_refuses_on_next_call(module, monkeypatch):
    """FR-082: re-checked on every call, not just once — a sandbox available
    at the start of a run but gone later is still caught."""
    calls = {"n": 0}

    def _which(name):
        calls["n"] += 1
        return "/usr/bin/docker" if calls["n"] == 1 else None

    monkeypatch.setattr(module.shutil, "which", _which)

    class _Result:
        returncode = 0

    monkeypatch.setattr(module.subprocess, "run", lambda *a, **k: _Result())
    module._check_sandbox_available()  # first call: available
    with pytest.raises(module.ToolPolicyRefusal, match="not installed"):
        module._check_sandbox_available()  # second call: gone


def test_sandbox_unavailable_never_falls_back_to_host_execution(module, monkeypatch):
    """No else-branch exists (D-7): refusing to establish the sandbox must
    prevent `_run_sandboxed` from reaching `subprocess.run` at all."""
    monkeypatch.setattr(module.shutil, "which", lambda name: None)

    called = {"ran": False}

    def _spy(*a, **k):
        called["ran"] = True
        raise AssertionError("subprocess.run must not be reached when the sandbox is unavailable")

    monkeypatch.setattr(module.subprocess, "run", _spy)
    with pytest.raises(module.ToolPolicyRefusal):
        module._run_sandboxed("echo hi")
    assert called["ran"] is False
