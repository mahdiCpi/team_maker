"""Permanent regression: RISKY-tool authorization (spec FR-050 to FR-054;
SC-014; Constitution V — this test may never be skipped, deleted or
weakened). Full unit-level coverage lives in
`tests/unit/tools/test_authorization.py`; this file is the constitutionally
protected permanent copy the contract requires at this path."""
from __future__ import annotations

import inspect

from team_maker.tools.authorization import (
    AuthorizationPolicy,
    check_authorization,
    is_authorized,
)
from team_maker.tools.catalog import RiskClass, TOOL_CATALOG
from team_maker.tools.config import load_tool_policy


def test_risky_tool_declared_without_operator_enablement_is_denied():
    assert check_authorization(["shell"], AuthorizationPolicy()) == ["shell"]


def test_every_risky_tool_is_denied_under_empty_policy():
    risky = [name for name, d in TOOL_CATALOG.items() if d.risk is RiskClass.RISKY]
    denied = check_authorization(risky, AuthorizationPolicy())
    assert set(denied) == set(risky)


def test_absent_policy_file_denies_every_risky_tool(tmp_path):
    cfg = load_tool_policy(tmp_path / "does_not_exist.yaml")
    assert check_authorization(["shell", "docker_runner"], cfg.authorization) == ["shell", "docker_runner"]


def test_malformed_policy_file_denies_rather_than_raising(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("not: [valid, yaml: structure")
    cfg = load_tool_policy(bad)  # must not raise
    assert cfg.authorization.enabled_tools == frozenset()


def test_no_agent_supplied_input_reaches_the_policy_decision():
    """FR-053: there is no escalation-request parameter — the authorization
    functions' signatures are the proof no per-call override path exists."""
    assert set(inspect.signature(is_authorized).parameters) == {
        "tool_name", "assigned_tools", "policy",
    }
    assert set(inspect.signature(check_authorization).parameters) == {
        "tool_names", "policy",
    }
