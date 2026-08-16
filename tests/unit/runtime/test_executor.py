"""Unit tests for the Runtime's single public entry point (Story 1.5 AC 1/2/6,
Story 1.6 AC 1/9).

Fully offline — uses a fake ExecutionEngine, no CrewAI needed for these tests.

Story 1.6 changed the `ExecutionEngine` port: engines now receive a resolved
`{role: ResolvedCredential}` map instead of the raw `KeyConfig`. The entry point
resolves credentials once, up front, and refuses the run if any agent cannot be
satisfied — so an engine can neither re-resolve differently nor see key material
for agents it isn't running (AD-7).
"""
from __future__ import annotations

import pytest
from pydantic import SecretStr

from team_maker.keyconfig import KeyConfig
from team_maker.pipeline.runner import PipelineRunner
from team_maker.ports.execution_engine import ExecutionEngine
from team_maker.runtime.executor import UnsupportedFrameworkError, run_team_package
from team_maker.runtime.loader import load_team_package
from team_maker.runtime.preflight import MissingCredentialsError
from team_maker.runtime.results import RunResult
from team_maker.runtime.run_context import (
    GoalNotInjectedError,
    RunDocument,
    goal_is_injected,
    require_goal_injected,
)
from team_maker.schema.request import RoleDefinition, TeamCreationRequest

# The default routing for a request that names no models (project-context:
# role.llm -> request.default_llm -> anthropic/claude-sonnet-4-6).
_DEFAULT_KEYS = KeyConfig(keys={"anthropic": SecretStr("sk-ant-test")})


class _FakeEngine(ExecutionEngine):
    def __init__(self):
        self.calls = []

    def run(self, team, credentials, goal):
        self.calls.append((team, credentials, goal))
        return RunResult(final_output="fake result", task_results=[])


def test_run_team_package_loads_and_delegates_to_the_engine(minimal_request):
    build = PipelineRunner().run(minimal_request)
    engine = _FakeEngine()

    result = run_team_package(build.output_path, "ship it", _DEFAULT_KEYS, engine=engine)

    assert result.final_output == "fake result"
    assert len(engine.calls) == 1
    called_team, called_credentials, called_goal = engine.calls[0]
    assert called_team.team_name == minimal_request.team_name
    assert called_goal == "ship it"
    # The engine receives resolved credentials, not the KeyConfig.
    assert set(called_credentials) == {agent.role for agent in called_team.agents}
    assert all(c.api_key == "sk-ant-test" for c in called_credentials.values())


def test_run_team_package_rejects_non_crewai_framework(tmp_path):
    request = TeamCreationRequest(
        team_name="LangGraph Team",
        purpose="A team targeting a non-crewai framework for this test.",
        output_path=str(tmp_path / "lg_team"),
        framework="langgraph",
        desired_roles=[
            RoleDefinition(
                name="architect",
                description="Designs system architecture and makes technical decisions.",
            )
        ],
    )
    build = PipelineRunner().run(request)
    engine = _FakeEngine()

    with pytest.raises(UnsupportedFrameworkError, match="crewai"):
        run_team_package(build.output_path, "ship it", _DEFAULT_KEYS, engine=engine)

    assert engine.calls == []


def test_run_team_package_defaults_to_the_crewai_execution_engine(minimal_request, monkeypatch):
    """When no engine is passed, run_team_package must default to
    CrewAIExecutionEngine — patch the class at its *source* module (where the
    lazy import in executor.py reads it from), not on executor.py itself
    (which has no such module-level attribute, by design)."""
    build = PipelineRunner().run(minimal_request)
    fake = _FakeEngine()
    monkeypatch.setattr(
        "team_maker.adapters.runtime_crewai.crewai_execution_engine.CrewAIExecutionEngine",
        lambda: fake,
    )

    result = run_team_package(build.output_path, "ship it", _DEFAULT_KEYS)

    assert result.final_output == "fake result"
    assert len(fake.calls) == 1


def test_missing_credentials_abort_before_the_engine_is_ever_called(minimal_request):
    """Story 1.6 AC 1: fail fast means *before work begins* — not merely before
    the first LLM call. The engine must never be entered."""
    build = PipelineRunner().run(minimal_request)
    engine = _FakeEngine()

    with pytest.raises(MissingCredentialsError) as exc_info:
        run_team_package(build.output_path, "ship it", KeyConfig(keys={}), engine=engine)

    assert engine.calls == []
    assert "anthropic" in str(exc_info.value)
    assert "ANTHROPIC_API_KEY" in str(exc_info.value)


def test_documents_reach_the_engine_via_the_augmented_team(minimal_request):
    """Story 2.4 AC 5/6: `documents` is plumbed through to the team the engine
    receives, by way of `run_context.augment_team_for_run` — not passed to
    the engine as a separate argument, since `ExecutionEngine.run`'s
    signature does not change (Story 1.7 AC 7)."""
    build = PipelineRunner().run(minimal_request)
    engine = _FakeEngine()

    run_team_package(
        build.output_path,
        "ship it",
        _DEFAULT_KEYS,
        engine=engine,
        documents=[RunDocument(name="brief.txt", text="Ship a v1 by Friday.")],
    )

    called_team, _, _ = engine.calls[0]
    assert all("brief.txt" in task.description for task in called_team.tasks)
    assert all("Ship a v1 by Friday." in task.description for task in called_team.tasks)


def test_documents_default_to_empty_for_every_existing_caller(minimal_request):
    """Every pre-2.4 caller omits `documents` entirely; the augmented team's
    task descriptions must still gain no document section."""
    build = PipelineRunner().run(minimal_request)
    engine = _FakeEngine()

    run_team_package(build.output_path, "ship it", _DEFAULT_KEYS, engine=engine)

    called_team, _, _ = engine.calls[0]
    assert all("Attached document" not in task.description for task in called_team.tasks)


def test_framework_check_runs_before_the_credential_gate(tmp_path):
    """A non-crewai package is unrunnable regardless of keys; reporting the
    framework problem is more useful than a missing-key message the user would
    fix pointlessly."""
    request = TeamCreationRequest(
        team_name="LangGraph Team",
        purpose="A team targeting a non-crewai framework for this test.",
        output_path=str(tmp_path / "lg_team2"),
        framework="langgraph",
        desired_roles=[
            RoleDefinition(
                name="architect",
                description="Designs system architecture and makes technical decisions.",
            )
        ],
    )
    build = PipelineRunner().run(request)

    with pytest.raises(UnsupportedFrameworkError):
        run_team_package(build.output_path, "ship it", KeyConfig(keys={}))


def test_the_team_run_team_package_hands_the_engine_satisfies_the_goal_guard(minimal_request):
    """Story 2.4 review, decision 2 — the *passing* half of the guard.

    An engine refuses a goal that never reached the task descriptions
    (`require_goal_injected`). This proves the normal entry point always
    satisfies that contract, so the guard can never fire on the supported
    path — the half a guard test usually omits, and the half that would catch
    someone reordering `augment_team_for_run` after `check_credentials`.
    """
    build = PipelineRunner().run(minimal_request)
    engine = _FakeEngine()

    run_team_package(build.output_path, "ship a v1", _DEFAULT_KEYS, engine=engine)

    called_team, _, called_goal = engine.calls[0]
    assert called_team.tasks, "a vacuous pass: the team handed over has no tasks to check"
    assert goal_is_injected(called_team, called_goal)
    require_goal_injected(called_team, called_goal)  # must not raise


def test_the_goal_guard_would_fire_on_the_package_as_loaded(minimal_request):
    """The falsification for the test above: the same package, *before*
    augmentation, must fail the guard. Without this, the assertion above could
    pass because `goal_is_injected` returns `True` for everything."""
    build = PipelineRunner().run(minimal_request)
    engine = _FakeEngine()

    run_team_package(build.output_path, "ship a v1", _DEFAULT_KEYS, engine=engine)
    _augmented, _, goal = engine.calls[0]

    # The loader's own output — precisely what a caller bypassing the Runtime
    # would hand an engine. Read from disk rather than reconstructed by string
    # surgery, so this cannot quietly stop being the shape it claims to be.
    as_loaded = load_team_package(build.output_path)

    assert as_loaded.tasks, "a vacuous pass: the loaded team has no tasks to check"
    assert not goal_is_injected(as_loaded, goal)
    with pytest.raises(GoalNotInjectedError):
        require_goal_injected(as_loaded, goal)
