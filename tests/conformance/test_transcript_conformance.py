"""Run-transcript conformance (Story 1.7, FR-27, AD-13, NFR3).

The only place the transcript is proven end to end: a **real** `crewai.Crew`
executes a **real** Team Package built by the Factory, and the resulting
`RunResult.transcript` is asserted. Everything is offline — every `BaseLLM`
implementation's `call` is replaced and all HTTP egress is blocked by the shared
harness in `tests/support/crewai_interception.py`.

**Why this file exists separately from the adapter unit tests:** those
monkeypatch `Crew.kickoff` wholesale, so no crewai events are ever emitted and
the transcript is empty *by construction*. Any assertion about transcript
content there would pass vacuously. Content is only observable with a real
kickoff, which is here.

If this fails after a CrewAI upgrade, do not loosen the assertions — they
describe the product invariant (FR-27), not CrewAI's current internals.
"""
from __future__ import annotations

import pytest

# AD-7 conformance gate: crewai is required for these tests.
# If crewai is not installed, the tests must fail explicitly, not skip.
try:
    import crewai  # noqa: F401
except ImportError:
    pytest.fail(
        "crewai is required for transcript conformance tests. "
        "Install with: pip install -e \".[runtime]\""
    )

from crewai.events import crewai_event_bus  # noqa: E402
from pydantic import SecretStr  # noqa: E402

from team_maker.cli import _format_transcript  # noqa: E402
from team_maker.keyconfig import KeyConfig  # noqa: E402
from team_maker.pipeline.runner import PipelineRunner  # noqa: E402
from team_maker.runtime.executor import run_team_package  # noqa: E402
from team_maker.runtime.loader import load_team_package  # noqa: E402
from team_maker.runtime.results import (  # noqa: E402
    ENTRY_AGENT_ACTION,
    ENTRY_AGENT_MESSAGE,
    ENTRY_DELEGATION,
    ENTRY_DELEGATION_RESULT,
    ENTRY_TASK_COMPLETED,
    ENTRY_TASK_STARTED,
)
from team_maker.schema.request import (  # noqa: E402
    RoleDefinition,
    TaskHint,
    TeamCreationRequest,
)
from tests.support.crewai_interception import (
    block_all_network,
    install_call_recorder,
    warm_up_models,
)

# A value that must never surface in a transcript, an entry repr, or a file.
_SENTINEL = "sk-ant-SENTINEL-DO-NOT-LEAK"

_KEYS = KeyConfig(keys={"anthropic": SecretStr(_SENTINEL)})


def _package(tmp_path, *, orchestrator: bool, two_tasks: bool = False):
    """A real Team Package on disk, built by the Factory.

    `orchestrator=True` uses the role name `coordinator`, which the
    software_delivery template forces to `is_orchestrator=True`
    (`templates/software_delivery/template.py:129,269` — it discards the
    request's own flag). `orchestrator=False` therefore has to use role names
    the template does *not* override, or the "sequential" fixture is silently
    hierarchical. An earlier version of this file passed the flag through and
    got a hierarchical crew in both branches, leaving `Process.sequential`
    completely uncovered.
    """
    lead = "coordinator" if orchestrator else "architect"
    # In a hierarchical crew the lead becomes the manager and is excluded from
    # `agents=`, so the task must belong to a worker for the manager to have
    # someone to delegate to.
    design_owner = "developer" if orchestrator else lead
    roles = [
        RoleDefinition(
            name=lead,
            description="Leads the work and makes the technical decisions.",
        ),
        RoleDefinition(
            name="developer",
            description="Implements what the lead specifies, in code.",
        ),
    ]
    tasks = [
        TaskHint(
            name="design",
            description="Design the thing end to end.",
            agent_role=design_owner,
        )
    ]
    if two_tasks:
        tasks.append(
            TaskHint(
                name="build",
                description="Build the thing that was designed.",
                agent_role="developer",
                dependencies=["design"],
            )
        )
    request = TeamCreationRequest(
        team_name="Transcript Team",
        purpose="A team used to prove the run transcript is captured correctly.",
        output_path=str(tmp_path / "transcript_team"),
        desired_roles=roles,
        desired_tasks=tasks,
    )
    return PipelineRunner().run(request).output_path


def _assert_topology(package, *, hierarchical: bool):
    """Guard the fixture itself: the template can override is_orchestrator."""
    team = load_team_package(package)
    actual = any(agent.is_orchestrator for agent in team.agents)
    assert actual is hierarchical, (
        f"fixture is {'hierarchical' if actual else 'sequential'} but the test "
        f"needs {'hierarchical' if hierarchical else 'sequential'} — the "
        "template may be overriding is_orchestrator"
    )


def _delegating_responder(role, call_index):
    """Manager delegates on its first turn, then answers."""
    if role == "coordinator" and call_index == 1:
        return (
            "Thought: the developer should handle this.\n"
            "Action: Delegate work to coworker\n"
            "Action Input: "
            '{"task": "design it", "context": "ctx", "coworker": "developer"}\n'
        )
    return "Final Answer: done"


def _bus_handler_count() -> int:
    handlers = getattr(crewai_event_bus, "_sync_handlers", {})
    return sum(len(v) for v in handlers.values())


def _run(monkeypatch, package, *, responder=None, force_react=False):
    block_all_network(monkeypatch)
    install_call_recorder(
        monkeypatch,
        warm_up_models(package, _KEYS),
        responder=responder,
        force_react=force_react,
    )
    return run_team_package(package, "ship the thing", _KEYS)


def test_a_run_returns_an_ordered_attributed_transcript(tmp_path, monkeypatch):
    """FR-27: not just the final answer. Every entry is ordered and attributed."""
    package = _package(tmp_path, orchestrator=False)
    _assert_topology(package, hierarchical=False)

    result = _run(monkeypatch, package)

    assert result.transcript, "no transcript was captured — the recorder is not wired"
    sequences = [entry.sequence for entry in result.transcript]
    # Sortedness is guaranteed by `entries()`, so asserting it proves nothing.
    # Uniqueness and strict increase do carry information.
    assert len(sequences) == len(set(sequences))
    assert all(b > a for a, b in zip(sequences, sequences[1:]))
    for entry in result.transcript:
        # `!= "unknown"`, not mere truthiness: the sentinel is a non-empty
        # string, so a run whose attribution collapsed entirely would satisfy
        # `assert entry.agent_role` while failing the AC it defends.
        assert entry.agent_role != "unknown", f"entry {entry.sequence} lost its agent"
        assert entry.task_name != "unknown", f"entry {entry.sequence} lost its task"
        assert entry.kind


def test_a_sequential_multi_task_run_records_tasks_in_dag_order(tmp_path, monkeypatch):
    """AC 3's first clause: messages recorded in execution order along the DAG."""
    package = _package(tmp_path, orchestrator=False, two_tasks=True)
    _assert_topology(package, hierarchical=False)

    result = _run(monkeypatch, package)

    assert result.transcript
    design = [e.sequence for e in result.transcript if e.task_name == "design"]
    build = [e.sequence for e in result.transcript if e.task_name == "build"]
    assert design and build, (
        f"expected both tasks, saw {[e.task_name for e in result.transcript]}"
    )
    assert max(design) < min(build)
    owners = {
        e.task_name: e.agent_role
        for e in result.transcript
        if e.kind in (ENTRY_TASK_STARTED, ENTRY_TASK_COMPLETED)
    }
    assert owners == {"design": "architect", "build": "developer"}


def test_the_transcript_extends_rather_than_replaces_the_story_1_5_result(
    tmp_path, monkeypatch
):
    """The existing contract is untouched: same final output, same per-task results."""
    package = _package(tmp_path, orchestrator=False)

    result = _run(monkeypatch, package)

    assert result.final_output
    assert [task.name for task in result.task_results] == ["design"]
    assert result.task_results[0].agent_role == "architect"
    assert result.transcript


def test_transcript_and_task_results_agree_on_who_owns_each_task(tmp_path, monkeypatch):
    """A consumer grouping by task must not see the two halves disagree.

    In a hierarchical crew CrewAI rebinds `task.agent` to the manager, so a
    task-boundary entry would say "coordinator" while `TaskResult` says
    "architect" for the same task — the same correlation defect the `name=`
    fix addressed, one field over.
    """
    package = _package(tmp_path, orchestrator=True)
    _assert_topology(package, hierarchical=True)

    result = _run(monkeypatch, package)

    from_results = {t.name: t.agent_role for t in result.task_results}
    from_transcript = {
        e.task_name: e.agent_role
        for e in result.transcript
        if e.kind in (ENTRY_TASK_STARTED, ENTRY_TASK_COMPLETED)
    }
    assert from_transcript, "no task-boundary entries were captured"
    for task_name, owner in from_transcript.items():
        assert from_results.get(task_name) == owner, (
            f"task {task_name!r}: transcript says {owner!r}, "
            f"task_results says {from_results.get(task_name)!r}"
        )


def test_task_boundaries_and_agent_messages_are_both_recorded(tmp_path, monkeypatch):
    """AC 2's kind discriminator: a consumer must not have to parse `content`."""
    package = _package(tmp_path, orchestrator=False)

    result = _run(monkeypatch, package)

    kinds = {entry.kind for entry in result.transcript}
    assert ENTRY_TASK_STARTED in kinds
    assert ENTRY_TASK_COMPLETED in kinds
    assert ENTRY_AGENT_MESSAGE in kinds

    started = next(e for e in result.transcript if e.kind == ENTRY_TASK_STARTED)
    completed = next(e for e in result.transcript if e.kind == ENTRY_TASK_COMPLETED)
    assert started.task_name == "design"
    assert completed.task_name == "design"
    assert started.sequence < completed.sequence


def test_a_delegation_is_recorded_naming_both_agents(tmp_path, monkeypatch):
    """FR-27's handoffs and delegations, proven on a real hierarchical crew.

    `force_react=True` is required, not incidental: the default executor takes
    the native function-calling branch, which never reaches the ReAct parser, so
    a stubbed delegation is swallowed as a final answer and CrewAI emits no
    `ToolUsage*` event at all. Verified against crewai 1.14.6.
    """
    package = _package(tmp_path, orchestrator=True)
    _assert_topology(package, hierarchical=True)

    result = _run(
        monkeypatch, package, responder=_delegating_responder, force_react=True
    )

    delegations = [e for e in result.transcript if e.kind == ENTRY_DELEGATION]
    assert delegations, (
        "no delegation entry captured — a hierarchical run must record the handoff"
    )
    handoff = delegations[0]
    assert handoff.agent_role == "coordinator"  # who delegated
    assert handoff.target_role == "developer"  # to whom

    results_back = [e for e in result.transcript if e.kind == ENTRY_DELEGATION_RESULT]
    assert results_back, "the delegate's answer coming back was not recorded"
    assert results_back[0].sequence > handoff.sequence

    # An intermediate step is captured and distinguished from an answer.
    assert ENTRY_AGENT_ACTION in {e.kind for e in result.transcript}

    # Both agents appear, each attributed to the real crew task rather than the
    # synthetic task CrewAI invents for a delegation.
    assert {"coordinator", "developer"} <= {e.agent_role for e in result.transcript}
    assert {e.task_name for e in result.transcript} == {"design"}


def test_no_key_or_secret_ever_appears_in_the_transcript(tmp_path, monkeypatch):
    """NFR3/AD-9, on the paths that actually render.

    Runs the **hierarchical** fixture so `ToolUsageStartedEvent` is emitted —
    that event holds a live `Agent` whose `.llm.api_key` is a plain string, and
    it is the one measured leak site an `orchestrator=False` run never reaches.
    Also checks the rendered CLI text and the written file, which is what a
    user actually sees.
    """
    package = _package(tmp_path, orchestrator=True)

    result = _run(
        monkeypatch, package, responder=_delegating_responder, force_react=True
    )

    assert result.transcript, "empty transcript would make this assertion vacuous"
    assert any(e.kind == ENTRY_DELEGATION for e in result.transcript), (
        "the ToolUsage emit site — a measured leak path — was not exercised"
    )
    for entry in result.transcript:
        assert _SENTINEL not in entry.content
        assert _SENTINEL not in repr(entry)
    assert _SENTINEL not in repr(result.transcript)
    assert _SENTINEL not in repr(result)

    # The two surfaces a user actually sees.
    rendered = _format_transcript(result)
    assert _SENTINEL not in rendered
    assert "sk-" not in rendered
    out = tmp_path / "t.txt"
    out.write_text(rendered, encoding="utf-8")
    assert _SENTINEL not in out.read_text(encoding="utf-8")


def test_handlers_are_actually_removed_from_the_global_bus(tmp_path, monkeypatch):
    """The bus is a process-global singleton.

    Asserted against the **bus**, not the recorder's own bookkeeping:
    `_unsubscribe` empties `_registered` with its own `pop()` loop, so checking
    that list passes even if `off()` were a no-op. Counting the bus's handlers
    before and after is the only thing that proves removal.
    """
    package = _package(tmp_path, orchestrator=False)

    before = _bus_handler_count()
    _run(monkeypatch, package)
    after = _bus_handler_count()

    assert after == before, (
        f"{after - before} handler(s) left on the global bus after the run"
    )


