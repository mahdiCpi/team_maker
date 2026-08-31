"""`run_team_package` refuses a run with an unauthorized or unresolvable
declared tool before any agent is constructed (spec FR-023, FR-055, FR-058;
contracts/tool-resolver-port.md test obligations: "Unresolvable refuses",
"No partial resolution"; tasks T105-T108)."""
from __future__ import annotations

from pydantic import SecretStr

from team_maker.keyconfig import KeyConfig
from team_maker.pipeline.runner import PipelineRunner
from team_maker.runtime.executor import run_team_package
from team_maker.runtime.preflight import UnauthorizedToolError, UnavailableToolError
from team_maker.schema.request import RoleDefinition, TeamCreationRequest

_KEYS = KeyConfig(keys={"anthropic": SecretStr("sk-ant-test")})


def _build(tmp_path, output_dir: str, *, tools: list[str]):
    request = TeamCreationRequest(
        team_name="Gate Team",
        purpose="A team for verifying the preflight tool-resolution gate.",
        output_path=str(tmp_path / output_dir),
        desired_roles=[
            RoleDefinition(name="operator_role", description="Runs risky tools.", tools=tools),
        ],
    )
    return PipelineRunner().run(request).output_path


def test_unauthorized_risky_tool_refuses_before_the_engine_is_ever_reached(tmp_path, monkeypatch):
    package_path = _build(tmp_path, "unauthorized_team", tools=["shell"])
    monkeypatch.setattr(
        "team_maker.tools.config.default_path", lambda: tmp_path / "does_not_exist.yaml"
    )
    engine_constructed = {"yes": False}
    monkeypatch.setattr(
        "team_maker.adapters.runtime_crewai.crewai_execution_engine.CrewAIExecutionEngine",
        lambda tool_resolver=None: engine_constructed.__setitem__("yes", True),
    )

    try:
        run_team_package(package_path, "ship it", _KEYS)
        raised = False
    except UnauthorizedToolError as exc:
        raised = True
        assert "shell" in str(exc.denied)

    assert raised, "expected UnauthorizedToolError"
    assert engine_constructed["yes"] is False, "engine must never be constructed after a denied tool"


def test_unresolvable_tool_names_it_and_refuses(tmp_path, monkeypatch):
    """Simulates a catalog/registry drift: a canonical, authorized, SAFE
    tool that this particular package's registry does not actually bind —
    the exact three-availability-state gap FR-065 describes. Raises
    `UnavailableToolError` (Phase 7, T107) — distinct from
    `UnauthorizedToolError`, since this has nothing to do with permission."""
    package_path = _build(tmp_path, "drifted_team", tools=["state_reader"])
    tools_py = package_path / "tools.py"
    source = tools_py.read_text(encoding="utf-8")
    tools_py.write_text(source.replace('"state_reader":   state_reader_tool,\n', ""), encoding="utf-8")

    engine_constructed = {"yes": False}
    monkeypatch.setattr(
        "team_maker.adapters.runtime_crewai.crewai_execution_engine.CrewAIExecutionEngine",
        lambda tool_resolver=None: engine_constructed.__setitem__("yes", True),
    )

    try:
        run_team_package(package_path, "ship it", _KEYS)
        raised = False
    except UnavailableToolError as exc:
        raised = True
        assert "state_reader" in str(exc)

    assert raised, "expected UnresolvableToolError"
    assert engine_constructed["yes"] is False
