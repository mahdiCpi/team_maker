"""Permanent regression: exactly one definition per tool name, registry
resolves to the real implementation, no duplicate keys (spec FR-006, FR-007;
audit RC-4, P0-2; contract execution-policy.md Part A; Constitution V — this
test may never be skipped, deleted or weakened).

Reproduces the exact defect recorded in `evidence/baseline-stub-shadowing.txt`:
`devops_team`'s `suggested_tools` carried `shell_command`, `test_runner` and
`docker_runner`, each rebinding the real tool at module scope.
"""
from __future__ import annotations

import re

from .conftest import render_tools_source, load_tools_module

_RISKY_NAMES = ("shell", "code_writer", "test_runner", "docker_runner")


def test_each_risky_tool_defined_exactly_once():
    source = render_tools_source()
    for name in _RISKY_NAMES:
        assert len(re.findall(rf'@tool\("{name}"\)', source)) == 1, f"{name} decorated more than once"


def test_registry_has_no_duplicate_keys():
    source = render_tools_source()
    registry_body = source.split("TOOL_REGISTRY: dict[str, Any] = {", 1)[1].split("\n}", 1)[0]
    keys = re.findall(r'"([a-z_]+)":', registry_body)
    assert len(keys) == len(set(keys)), f"duplicate registry keys: {keys}"


def test_registry_resolves_to_the_real_implementation():
    module = load_tools_module()
    assert module.TOOL_REGISTRY["shell"].func is module.shell_tool.func
    assert module.TOOL_REGISTRY["test_runner"].func is module.test_runner_tool.func
    assert module.TOOL_REGISTRY["docker_runner"].func is module.docker_runner_tool.func


def test_suggested_tool_matching_a_real_name_does_not_shadow_it():
    """RC-4's exact reproduction: an alias-shaped `suggested_tools` entry
    used to render a second, later definition that won Python's rebinding
    and made the real tool dead code. The stub-emission block is deleted
    entirely (T044, T045) — this is not "no longer wins", it "no longer
    exists"."""
    from team_maker.schema.request import ToolSuggestion

    suggested = [
        ToolSuggestion(name="shell_command", description="Run shell commands."),
        ToolSuggestion(name="test_runner", description="Run tests."),
        ToolSuggestion(name="docker_runner", description="Run containers."),
    ]
    source = render_tools_source(suggested_tools=suggested)
    for name in _RISKY_NAMES:
        assert len(re.findall(rf'@tool\("{name}"\)', source)) == 1
    assert source.count('"shell":') == 1
    assert source.count('"test_runner":') == 1
    assert source.count('"docker_runner":') == 1
