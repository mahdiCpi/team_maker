"""End-to-end: a task requiring a capability it never actually invokes is
NOT reported successfully complete (spec FR-027, FR-061 to FR-064; audit
RC-11, P0-4; contracts/receipts-and-completion.md; tasks.md T127).

Attaching real tools (Phase 5) does not make the product truthful by
itself — a model handed a working `test_runner` may still decline to call
it and assert the tests passed. This is the scenario recorded in
`evidence/p4_transcript_fusion_policy_research_team.txt`; this test proves
it is now caught.
"""
from __future__ import annotations

import pytest

pytest.importorskip("crewai")

from pydantic import SecretStr  # noqa: E402

from team_maker.keyconfig import KeyConfig  # noqa: E402
from team_maker.pipeline.runner import PipelineRunner  # noqa: E402
from team_maker.runtime.completion import run_is_successfully_complete  # noqa: E402
from team_maker.runtime.executor import run_team_package  # noqa: E402
from team_maker.schema.request import RoleDefinition, TaskHint, TeamCreationRequest  # noqa: E402
from team_maker.utils.yaml_utils import dump_yaml, load_yaml  # noqa: E402
from tests.support.crewai_interception import (  # noqa: E402
    block_all_network,
    install_call_recorder,
    warm_up_models,
)

_KEYS = KeyConfig(keys={"anthropic": SecretStr("sk-ant-SENTINEL")})


def _build_package_requiring_test_runner(tmp_path):
    request = TeamCreationRequest(
        team_name="Truthfulness Team",
        purpose="A team used to prove an unevidenced capability is caught.",
        output_path=str(tmp_path / "truthfulness_team"),
        desired_roles=[
            RoleDefinition(name="engineer", description="Builds and tests the thing.", tools=["test_runner"]),
        ],
        desired_tasks=[
            TaskHint(name="build", description="Build the thing and run its tests.", agent_role="engineer"),
        ],
    )
    package_path = PipelineRunner().run(request).output_path

    # TaskHint has no authoring-schema field for required_capabilities yet
    # (out of this remediation's scope — only TaskSpec, the domain model,
    # was widened per T120). Set it directly on the built package's own
    # task file, exactly as an operator hand-authoring `required_capabilities`
    # would.
    task_file = package_path / "tasks" / "build.yaml"
    task_cfg = load_yaml(task_file)
    task_cfg["required_capabilities"] = ["test_runner"]
    task_file.write_text(dump_yaml(task_cfg), encoding="utf-8")
    return package_path


def test_declined_required_tool_is_not_reported_successfully_complete(tmp_path, monkeypatch):
    package_path = _build_package_requiring_test_runner(tmp_path)

    # `test_runner` is RISKY (spec FR-052) — authorize it via a temporary
    # operator policy file so this test exercises the completion rule, not
    # the (already-covered, Phase 4/5) authorization gate.
    policy_file = tmp_path / "team_maker.tools.yaml"
    policy_file.write_text("enabled_tools:\n  - test_runner\n", encoding="utf-8")
    monkeypatch.setenv("TEAM_MAKER_TOOL_POLICY", str(policy_file))

    # The model asserts success without ever invoking test_runner — the
    # default responder ("Final Answer: done") already models exactly this;
    # no tool-call is ever scripted.
    install_call_recorder(monkeypatch, warm_up_models(package_path, _KEYS))
    block_all_network(monkeypatch)

    result = run_team_package(package_path, "build and test it", _KEYS)

    assert result.error is None
    assert "test_runner" in result.unevidenced_capabilities
    assert not run_is_successfully_complete(result.error, result.unevidenced_capabilities)
    # The tool-execution record is inspectable — empty here, since the tool
    # was never invoked, but present and readable on the result (FR-028).
    assert result.tool_receipts == []


def _test_runner_responder(role, call_index):
    """Invokes `test_runner` on the first turn, then answers — the honest
    counterpart to the module-level scenario above."""
    if call_index == 1:
        return (
            "Thought: I should run the tests.\n"
            "Action: test_runner\n"
            'Action Input: {"path": "."}\n'
        )
    return "Final Answer: 42 passed"


def test_an_actually_invoked_required_tool_produces_an_inspectable_receipt(tmp_path, monkeypatch):
    package_path = _build_package_requiring_test_runner(tmp_path)

    policy_file = tmp_path / "team_maker.tools.yaml"
    policy_file.write_text("enabled_tools:\n  - test_runner\n", encoding="utf-8")
    monkeypatch.setenv("TEAM_MAKER_TOOL_POLICY", str(policy_file))

    install_call_recorder(
        monkeypatch,
        warm_up_models(package_path, _KEYS),
        responder=_test_runner_responder,
        force_react=True,
    )
    block_all_network(monkeypatch)

    result = run_team_package(package_path, "build and test it", _KEYS)

    assert result.error is None
    assert result.unevidenced_capabilities == []
    assert run_is_successfully_complete(result.error, result.unevidenced_capabilities)
    assert result.tool_receipts, "expected at least one receipt to be recorded"
    assert all(r.tool_name == "test_runner" and r.task_name == "build" for r in result.tool_receipts)
