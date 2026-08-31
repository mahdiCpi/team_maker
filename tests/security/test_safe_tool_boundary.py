"""Permanent regression: no SAFE-classified tool executes host commands,
writes outside the sandbox workspace, or controls the container runtime
(spec FR-083; closes CHK025; Constitution V).

Reproduces and closes a defect found while writing this suite:
`git_account_tool`'s `clone` action ran `subprocess.run(["git", "clone", ...])`
directly on the host — a SAFE-classified tool executing an unsandboxed host
command, the exact thing FR-083 forbids. Fixed to return the clone URL for
the (RISKY, sandboxed) `shell` tool to use instead of executing anything.

Network access is deliberately excluded from this boundary check: FR-083's
"open network connections on its own authority" targets a RISKY tool
reaching the network as a side effect of unrestricted command/container
execution, not `http_client`'s own catalog-declared purpose (bounded,
timeout-limited HTTP requests) — `http_client` was SAFE before this
remediation and remains so; the four RISKY names are unchanged (T013).
"""
from __future__ import annotations

import inspect

from team_maker.tools.catalog import RiskClass, TOOL_CATALOG

from .conftest import load_tools_module

_LOCAL_SAFE_TOOL_NAMES = (
    "http_client", "git_account", "state_reader", "state_writer", "ci_tool", "context_reader",
)


def test_catalog_agrees_these_names_are_safe():
    for name in _LOCAL_SAFE_TOOL_NAMES:
        assert TOOL_CATALOG[name].risk is RiskClass.SAFE


def test_no_safe_tool_calls_subprocess_directly():
    module = load_tools_module(context_dir="/tmp/ctx")
    for name in _LOCAL_SAFE_TOOL_NAMES:
        fn = getattr(module, f"{name}_tool").func
        source = inspect.getsource(fn)
        assert "subprocess." not in source, f"{name}_tool calls subprocess directly"
        assert "_run_sandboxed(" not in source, f"{name}_tool routes through the sandboxed execution path"
        assert "docker" not in source.lower(), f"{name}_tool references the container runtime"


def test_no_safe_tool_writes_outside_the_sandbox_workspace():
    """The only local-filesystem-writing SAFE tool is `state_writer`, and it
    writes through `write_state` (the shared state store), never a raw
    `open(..., "w")` to an arbitrary path."""
    module = load_tools_module()
    source = inspect.getsource(module.state_writer_tool.func)
    assert "open(" not in source
    assert "write_state(" in source


def test_context_reader_only_reads_within_its_declared_directory():
    module = load_tools_module(context_dir="/tmp/ctx")
    source = inspect.getsource(module.context_reader_tool.func)
    assert "CONTEXT_DIR" in source
    assert "open(" not in source  # uses Path.read_text scoped to CONTEXT_DIR, not a raw open()
