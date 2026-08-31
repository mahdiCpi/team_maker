"""Unit tests for the CrewAI execution adapter (Story 1.5 AC 2/3/4/5,
Story 1.6 AC 4/6).

Requires CrewAI installed (this repo's `.venv` has 1.14.6) — `Crew.kickoff` is
monkeypatched in every test so no real LLM/network call ever happens.

Since Story 1.6 the engine no longer sees a `KeyConfig`: it receives a
pre-resolved `{role: ResolvedCredential}` map and only translates it into
crewai `LLM` objects. Tests build that map through the real gate
(`check_credentials`) rather than by hand, so the two halves stay in step.
"""
from __future__ import annotations

import pytest

pytest.importorskip("crewai")

from crewai import Crew, Process  # noqa: E402
from pydantic import SecretStr  # noqa: E402

from team_maker.adapters.providers.resolution import ResolvedCredential  # noqa: E402
from team_maker.adapters.runtime_crewai.crewai_execution_engine import (  # noqa: E402
    CrewAIExecutionEngine,
)
from team_maker.domain.models import GeneratedTeam  # noqa: E402
from team_maker.keyconfig import KeyConfig  # noqa: E402
from team_maker.runtime.preflight import check_credentials  # noqa: E402
from team_maker.runtime.results import TaskResult  # noqa: E402
from team_maker.runtime.run_context import (  # noqa: E402
    GoalNotInjectedError,
    augment_team_for_run,
)
from tests.support.team_factories import agent_spec as _agent  # noqa: E402
from tests.support.team_factories import generated_team as _team  # noqa: E402
from tests.support.team_factories import task_spec as _task  # noqa: E402

_ANTHROPIC_KEYS = KeyConfig(keys={"anthropic": SecretStr("sk-test-key")})


def _creds(team: GeneratedTeam, key_config: KeyConfig) -> dict[str, ResolvedCredential]:
    """Resolve through the real pre-run gate, exactly as production does."""
    return check_credentials(team, key_config)


def _runnable(team: GeneratedTeam, goal: str) -> GeneratedTeam:
    """The team in the shape the engine actually receives it in production.

    `run_team_package` weaves the run's goal into every task description
    (`run_context.augment_team_for_run`) before any engine is reached, and the
    engine refuses a team where that has not happened (Story 2.4 review,
    decision 2 - a goal an engine cannot honour is refused, never silently
    discarded). These tests previously called `run()` with a team straight from
    the factories, which is a shape the Runtime never produces; they now build
    the production shape, so what they exercise is what ships.
    """
    return augment_team_for_run(team, goal)


class _FakeTaskOutput:
    def __init__(self, raw: str) -> None:
        self.raw = raw


class _FakeCrewOutput:
    def __init__(self, raw: str, tasks_output: list[_FakeTaskOutput]) -> None:
        self.raw = raw
        self.tasks_output = tasks_output


def _install_fake_kickoff(monkeypatch, captured_crews: list, output: _FakeCrewOutput) -> None:
    def _fake_kickoff(self, inputs=None):
        captured_crews.append(self)
        return output

    monkeypatch.setattr(Crew, "kickoff", _fake_kickoff)


def test_builds_agent_with_explicit_per_agent_credentials(monkeypatch):
    team = _team([_agent("architect")], [_task("design", "architect")])
    captured: list = []
    _install_fake_kickoff(
        monkeypatch, captured, _FakeCrewOutput(raw="final", tasks_output=[_FakeTaskOutput("design output")])
    )

    result = CrewAIExecutionEngine().run(_runnable(team, "ship it"), _creds(team, _ANTHROPIC_KEYS), "ship it")

    crew = captured[0]
    assert crew.process == Process.sequential
    [agent_obj] = crew.agents
    assert agent_obj.role == "architect"
    # CrewAI's LLM parses "provider/model" into separate attributes internally.
    assert agent_obj.llm.provider == "anthropic"
    assert agent_obj.llm.model == "claude-sonnet-4-6"
    assert agent_obj.llm.api_key == "sk-test-key"
    assert result.final_output == "final"
    assert result.task_results == [TaskResult(name="design", agent_role="architect", output="design output")]


def test_engine_uses_the_credential_it_is_handed_and_never_resolves_its_own(monkeypatch):
    """AD-7: the adapter is a pure translator. Hand it a credential the Key
    Config could not have produced and it must still be what reaches crewai —
    proving there is no second lookup (and no global-env fallback) inside."""
    team = _team([_agent("architect")], [_task("design", "architect")])
    captured: list = []
    _install_fake_kickoff(
        monkeypatch, captured, _FakeCrewOutput(raw="final", tasks_output=[_FakeTaskOutput("x")])
    )
    handed = {
        "architect": ResolvedCredential(
            model="openai/gpt-4o",
            api_key="sk-handed-in",
            base_url=None,
            via_openrouter=False,
        )
    }

    CrewAIExecutionEngine().run(_runnable(team, "goal"), handed, "goal")

    [agent_obj] = captured[0].agents
    # The AgentSpec says anthropic/claude-sonnet-4-6; the credential says
    # otherwise, and the credential wins.
    assert agent_obj.llm.provider == "openai"
    assert agent_obj.llm.model == "gpt-4o"
    assert agent_obj.llm.api_key == "sk-handed-in"


def test_openrouter_credential_reaches_crewai_in_gateway_form(monkeypatch):
    """Story 1.6 AC 4: an agent admitted `via-openrouter` is actually executed
    through OpenRouter with the OpenRouter key — not with api_key=None."""
    team = _team(
        [_agent("reviewer", provider="openai", model="gpt-4o", api_key_env="OPENAI_API_KEY")],
        [_task("review", "reviewer")],
    )
    captured: list = []
    _install_fake_kickoff(
        monkeypatch, captured, _FakeCrewOutput(raw="final", tasks_output=[_FakeTaskOutput("x")])
    )
    key_config = KeyConfig(keys={"openrouter": SecretStr("sk-or-test")})

    CrewAIExecutionEngine().run(_runnable(team, "goal"), _creds(team, key_config), "goal")

    [agent_obj] = captured[0].agents
    assert agent_obj.llm.provider == "openrouter"
    assert agent_obj.llm.model == "openai/gpt-4o"
    assert agent_obj.llm.api_key == "sk-or-test"


def test_ollama_agent_gets_base_url_not_an_api_key(monkeypatch):
    key_config = KeyConfig(keys={})
    team = _team(
        [_agent("local_agent", provider="ollama", model="llama3.2", api_key_env=None)],
        [_task("design", "local_agent")],
    )
    captured: list = []
    _install_fake_kickoff(
        monkeypatch, captured, _FakeCrewOutput(raw="final", tasks_output=[_FakeTaskOutput("x")])
    )

    CrewAIExecutionEngine().run(_runnable(team, "goal"), _creds(team, key_config), "goal")

    [agent_obj] = captured[0].agents
    assert agent_obj.llm.provider == "ollama"
    assert agent_obj.llm.model == "llama3.2"
    assert "localhost:11434" in agent_obj.llm.base_url


def test_ollama_agent_uses_package_specified_base_url_when_present(monkeypatch):
    """A package built with the Ollama sidecar compose stack rewrites
    base_url to the in-network service hostname — that must be honored, not
    silently overridden by the hardcoded localhost default."""
    key_config = KeyConfig(keys={})
    team = _team(
        [
            _agent(
                "local_agent",
                provider="ollama",
                model="llama3.2",
                api_key_env=None,
                base_url="http://ollama:11434",
            )
        ],
        [_task("design", "local_agent")],
    )
    captured: list = []
    _install_fake_kickoff(
        monkeypatch, captured, _FakeCrewOutput(raw="final", tasks_output=[_FakeTaskOutput("x")])
    )

    CrewAIExecutionEngine().run(_runnable(team, "goal"), _creds(team, key_config), "goal")

    [agent_obj] = captured[0].agents
    assert "ollama:11434" in agent_obj.llm.base_url


def test_downstream_task_receives_upstream_task_as_context(monkeypatch):
    team = _team(
        [_agent("architect"), _agent("backend_engineer")],
        [
            _task("backend_implementation", "backend_engineer", ["architecture_design"]),
            _task("architecture_design", "architect"),
        ],
    )
    captured: list = []
    _install_fake_kickoff(
        monkeypatch,
        captured,
        _FakeCrewOutput(raw="final", tasks_output=[_FakeTaskOutput("a"), _FakeTaskOutput("b")]),
    )

    result = CrewAIExecutionEngine().run(_runnable(team, "goal"), _creds(team, _ANTHROPIC_KEYS), "goal")

    crew = captured[0]
    # topologically sorted: architecture_design (no deps) before backend_implementation
    # `description` now carries the appended run-context block, so compare the
    # authored first line; the claim under test is the ordering, not the text.
    assert [t.description.splitlines()[0] for t in crew.tasks] == [
        "do architecture_design",
        "do backend_implementation",
    ]
    assert crew.tasks[1].context == [crew.tasks[0]]
    assert [tr.name for tr in result.task_results] == ["architecture_design", "backend_implementation"]


def test_task_with_no_dependencies_has_no_context(monkeypatch):
    team = _team([_agent("architect")], [_task("design", "architect")])
    captured: list = []
    _install_fake_kickoff(
        monkeypatch, captured, _FakeCrewOutput(raw="final", tasks_output=[_FakeTaskOutput("x")])
    )

    CrewAIExecutionEngine().run(_runnable(team, "goal"), _creds(team, _ANTHROPIC_KEYS), "goal")

    assert captured[0].tasks[0].context is None


def test_orchestrator_agent_selects_hierarchical_process_with_manager(monkeypatch):
    team = _team(
        [_agent("coordinator", is_orchestrator=True), _agent("engineer")],
        [_task("build", "engineer")],
    )
    captured: list = []
    _install_fake_kickoff(
        monkeypatch, captured, _FakeCrewOutput(raw="final", tasks_output=[_FakeTaskOutput("x")])
    )

    CrewAIExecutionEngine().run(_runnable(team, "goal"), _creds(team, _ANTHROPIC_KEYS), "goal")

    crew = captured[0]
    assert crew.process == Process.hierarchical
    assert crew.manager_agent.role == "coordinator"
    # CrewAI>=1.x rejects a manager also present in `agents` — only workers here.
    assert [a.role for a in crew.agents] == ["engineer"]


def test_hierarchical_manager_carries_no_tools_even_when_its_role_declares_them(monkeypatch):
    """CrewAI 1.14.6 raises "Manager agent should not have tools" if a
    hierarchical crew's `manager_agent` carries any `tools` — it only ever
    delegates, never executes directly. Found while adding Phase 5's
    resolver: a coordinator role declaring tools (e.g. `state_reader`,
    `state_writer` — the software_delivery template's own default) used to
    be silently safe only because RC-5 dropped every agent's tools
    entirely; fixing RC-5 exposed this crewai constraint, which
    `_build_crew` must respect by stripping the manager's tools specifically.
    There is no "sequential orchestrator" case to contrast with: any
    `is_orchestrator=True` agent always selects the hierarchical branch in
    `_build_crew` (`next(... if a.is_orchestrator)`), regardless of
    `topology_pattern`."""
    team = _team(
        [_agent("coordinator", is_orchestrator=True, tools=["shell"]), _agent("engineer")],
        [_task("build", "engineer")],
    )
    captured: list = []
    _install_fake_kickoff(
        monkeypatch, captured, _FakeCrewOutput(raw="final", tasks_output=[_FakeTaskOutput("x")])
    )

    CrewAIExecutionEngine().run(_runnable(team, "goal"), _creds(team, _ANTHROPIC_KEYS), "goal")

    assert captured[0].manager_agent.tools == []


def test_kickoff_receives_no_interpolation_inputs(monkeypatch):
    """Story 2.4 AC 5 superseded this test's original claim (that the goal
    reached the run via `kickoff(inputs={"goal": ...})`). Measured against the
    installed crewai: that mechanism raises `ValueError` the moment a pasted
    goal or document contains an unmatched brace, since crewai runs its own
    `{token}` template interpolation over every task description whenever
    `inputs=` is passed at all. The goal now reaches the run by being woven
    directly into each task's description before the engine is ever called
    (`team_maker/runtime/run_context.py`), so this test's remaining job is to
    prove the engine performs no interpolation of its own — `kickoff()` is
    called with no `inputs=` kwarg, of any shape, ever."""
    team = _team([_agent("architect")], [_task("design", "architect")])
    received: list = []

    def _fake_kickoff(self, inputs=None):
        received.append(inputs)
        return _FakeCrewOutput(raw="final", tasks_output=[_FakeTaskOutput("x")])

    monkeypatch.setattr(Crew, "kickoff", _fake_kickoff)

    CrewAIExecutionEngine().run(_runnable(team, "a very specific goal"), _creds(team, _ANTHROPIC_KEYS), "a very specific goal")

    assert received == [None]


def test_a_direct_unaugmented_engine_call_is_refused_before_crewai_starts(monkeypatch):
    """Story 2.4 review, decision 2.

    `ExecutionEngine.run`'s signature is pinned by Story 1.7 AC 7, so `goal`
    cannot be removed even though this adapter never reads it — the goal
    reaches the model through the task descriptions instead. That made `goal` a
    load-bearing argument an engine would accept and silently discard if a
    caller bypassed `run_team_package`. The engine now refuses instead.

    Two things are asserted, not one: that it raises, and that `Crew.kickoff`
    was never reached — a guard that fires *after* execution starts would have
    already spent money and is not the guard this test claims to prove.
    """
    team = _team([_agent("architect")], [_task("design", "architect")])
    kickoffs: list = []

    def _fake_kickoff(self, inputs=None):
        kickoffs.append(inputs)
        return _FakeCrewOutput(raw="final", tasks_output=[_FakeTaskOutput("x")])

    monkeypatch.setattr(Crew, "kickoff", _fake_kickoff)

    with pytest.raises(GoalNotInjectedError, match="augment_team_for_run"):
        # `team` straight from the factories — never through the run-context
        # path. This is exactly the call shape every test in this file used
        # before the guard existed.
        CrewAIExecutionEngine().run(team, _creds(team, _ANTHROPIC_KEYS), "a goal nobody wove in")

    assert kickoffs == [], "the guard must fire before any crewai execution, not after"


def test_the_same_call_succeeds_once_the_run_context_path_has_run(monkeypatch):
    """The passing half of the guard, on the identical inputs — so the test
    above cannot be satisfied by an engine that refuses everything."""
    team = _team([_agent("architect")], [_task("design", "architect")])
    kickoffs: list = []

    def _fake_kickoff(self, inputs=None):
        kickoffs.append(inputs)
        return _FakeCrewOutput(raw="final", tasks_output=[_FakeTaskOutput("x")])

    monkeypatch.setattr(Crew, "kickoff", _fake_kickoff)

    goal = "a goal nobody wove in"
    result = CrewAIExecutionEngine().run(
        _runnable(team, goal), _creds(team, _ANTHROPIC_KEYS), goal
    )

    assert kickoffs == [None]
    assert result.final_output == "final"


def test_task_output_count_mismatch_raises_clear_error_instead_of_silent_truncation(monkeypatch):
    """CrewAI returning fewer task outputs than tasks submitted must not
    silently drop results via zip()'s truncation — it must fail loudly."""
    team = _team(
        [_agent("architect")],
        [_task("design", "architect"), _task("review", "architect")],
    )
    captured: list = []
    _install_fake_kickoff(
        monkeypatch, captured, _FakeCrewOutput(raw="final", tasks_output=[_FakeTaskOutput("only one")])
    )

    with pytest.raises(RuntimeError, match="task output"):
        CrewAIExecutionEngine().run(_runnable(team, "goal"), _creds(team, _ANTHROPIC_KEYS), "goal")


def test_agent_declaring_tools_is_constructed_with_them(monkeypatch):
    """RC-12 / audit §9 Step 0 regression oracle (spec FR-034, FR-036).

    `AgentSpec.tools` is read off disk by `loader.py` and then discarded:
    `_build_agent` never passes a `tools=` argument to `Agent(...)`. Every
    pre-existing test here uses the shared `tools=[]` factory default, so an
    engine that honours declared tools and one that silently drops them are
    behaviourally identical under test — that is RC-12 exactly, and it is why
    P0-1 shipped undetected.

    This test is the fix for that blind spot: it declares a non-empty tool
    list and asserts the constructed `Agent` actually carries a matching
    tool. It MUST fail against the current engine (no `tools=` wiring exists
    yet) and MUST start passing only once the Phase 5 resolver boundary
    attaches resolved instances in `_build_agent`.
    """
    team = _team([_agent("architect", tools=["shell"])], [_task("design", "architect")])
    captured: list = []
    _install_fake_kickoff(
        monkeypatch, captured, _FakeCrewOutput(raw="final", tasks_output=[_FakeTaskOutput("design output")])
    )

    CrewAIExecutionEngine().run(_runnable(team, "ship it"), _creds(team, _ANTHROPIC_KEYS), "ship it")

    [agent_obj] = captured[0].agents
    tool_names = {getattr(t, "name", None) for t in (agent_obj.tools or [])}
    assert "shell" in tool_names, (
        f"agent declared tools=['shell'] but the constructed Agent carries no "
        f"matching tool (got {tool_names!r}) - RC-5: _build_agent drops "
        f"AgentSpec.tools entirely"
    )


def test_kickoff_failure_returns_a_run_result_with_error_set_instead_of_raising(monkeypatch):
    """Story 4.4 AC 1 / review fix: a run that fails partway through must still
    tell its caller it failed (`result.error`), not go quiet behind an
    empty-but-successful-shaped `RunResult` — swallowing the exception
    entirely was the bug this guards against (both the CLI's exit code and
    the API's run status depend on this field)."""
    team = _team([_agent("architect")], [_task("design", "architect")])

    def _raising_kickoff(self, inputs=None):
        raise RuntimeError("kaboom: provider rejected the request")

    monkeypatch.setattr(Crew, "kickoff", _raising_kickoff)

    result = CrewAIExecutionEngine().run(_runnable(team, "goal"), _creds(team, _ANTHROPIC_KEYS), "goal")

    assert result.error == "kaboom: provider rejected the request"
    assert result.final_output == ""
    assert result.task_results == []
    assert result.transcript == []
