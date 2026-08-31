"""Shared harness for `tests/security/` — the permanent execution-policy
regression suite (spec FR-006 to FR-018, FR-070 to FR-078; Constitution V:
these tests may never be skipped, deleted or weakened).

Renders `codegen/templates/tools.py.j2` and executes it as a real module so
runtime behaviour, not just source text, can be exercised — e.g. that
`_check_sandbox_available` actually raises `ToolPolicyRefusal` when Docker is
unavailable.
"""
from __future__ import annotations

import linecache
import sys
import types

import pytest

from team_maker.codegen import render_template
from team_maker.schema.request import SandboxConfig
from team_maker.tools.limits import DEFAULT_CONTROLS
from team_maker.tools.policy import EMPTY_ALLOWLIST, MountAllowlist, MountAllowlistEntry


def render_tools_source(**overrides) -> str:
    """Default policy context matches an unconfigured operator (FR-054:
    absent policy denies/defaults restrictively)."""
    kwargs = dict(
        sandbox=SandboxConfig(),
        suggested_tools=[],
        context_dir=None,
        effective_network="none",
        network_allowed=False,
        controls=DEFAULT_CONTROLS,
        mount_allowlist=EMPTY_ALLOWLIST.entries,
    )
    kwargs.update(overrides)
    return render_template("tools.py.j2", **kwargs)


def load_tools_module(**overrides) -> types.ModuleType:
    """Render and exec the template into a real module object. Fakes the
    sibling `state_store` module a generated package always ships alongside
    `tools.py`, since that module is not on the test interpreter's path."""
    if "state_store" not in sys.modules:
        fake_state_store = types.ModuleType("state_store")
        fake_state_store.read_state = lambda key: None
        fake_state_store.write_state = lambda key, value: None
        sys.modules["state_store"] = fake_state_store

    source = render_tools_source(**overrides)
    filename = "<tools.py>"
    # Register with linecache so `inspect.getsource` on functions defined in
    # this exec'd module works (tests/security/test_safe_tool_boundary.py
    # inspects tool bodies structurally).
    linecache.cache[filename] = (len(source), None, source.splitlines(keepends=True), filename)
    module = types.ModuleType("generated_tools_under_test")
    exec(compile(source, filename, "exec"), module.__dict__)  # noqa: S102
    return module


@pytest.fixture
def tools_module():
    return load_tools_module()


def make_allowlist(*, alias: str, host_path: str, writable: bool = False) -> tuple:
    return (MountAllowlistEntry(alias=alias, host_path=host_path, writable=writable),)
