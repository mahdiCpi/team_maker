"""Permanent regression: no credential value and no raw host path appears
in any tool receipt (spec FR-029, FR-071; SC-010, SC-017; Constitution V;
tasks.md T126). Full coverage lives alongside the broader secret-leakage
suite in `tests/unit/test_secret_leakage_regression.py`; this is the
constitutionally protected permanent copy the contract requires at this
path."""
from __future__ import annotations

import dataclasses

from team_maker.adapters.runtime_crewai.transcript_capture import _sanitize_arguments
from team_maker.runtime.results import ToolReceipt

_SENTINEL_KEY = "sk-ant-DO-NOT-LEAK-0123456789abcdef"


def test_receipt_arguments_never_carry_a_labeled_secret():
    sanitized = _sanitize_arguments({"body": f'{{"api_key": "{_SENTINEL_KEY}"}}'})
    assert _SENTINEL_KEY not in sanitized["body"]


def test_receipt_arguments_never_carry_a_raw_resolved_host_path():
    sanitized = _sanitize_arguments({"mounts": "/Users/real-operator/private-repo"})
    assert "private-repo" not in sanitized["mounts"]


def test_tool_receipt_shape_holds_only_primitives():
    """No credential, no engine object — the same constraint `TranscriptEntry`
    already documents under AD-9/NFR3, verified structurally so a future
    field addition cannot silently reopen the leak path."""
    allowed_types = {int, str, bool, dict}
    for f in dataclasses.fields(ToolReceipt):
        origin = getattr(f.type, "__origin__", f.type)
        assert origin in allowed_types or f.type in ("int", "str", "bool", "dict[str, str]"), (
            f"ToolReceipt.{f.name} has a non-primitive type {f.type!r}"
        )
