"""Unit tests for the crewai -> TranscriptEntry mapping (Story 1.7).

These drive `TranscriptRecorder`'s handlers **directly with synthetic event
objects** rather than running a crew. That is deliberate and it is a mock: it
makes the mapping rules (attribution via the parent chain, the two delegation
tool-name spellings, secret projection) testable one at a time. It proves the
*translation*, not that CrewAI emits these events — the real end-to-end proof,
with a genuine `Crew.kickoff`, lives in
`tests/conformance/test_transcript_conformance.py`.
"""
from __future__ import annotations

import pytest

pytest.importorskip("crewai")

from crewai.events import crewai_event_bus  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from team_maker.adapters.runtime_crewai.transcript_capture import (  # noqa: E402
    TranscriptRecorder,
    _answer_text,
    _as_args_dict,
)
from team_maker.runtime.results import (  # noqa: E402
    ENTRY_AGENT_ACTION,
    ENTRY_AGENT_MESSAGE,
    ENTRY_DELEGATION,
    ENTRY_DELEGATION_RESULT,
    ENTRY_TASK_COMPLETED,
    ENTRY_TASK_STARTED,
)

_SECRET = "sk-SENTINEL-DO-NOT-LEAK"


class _Stub:
    """A stand-in for a crewai event/object: attributes only, no behaviour."""

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


def _llm(api_key=_SECRET):
    return _Stub(api_key=api_key, model="anthropic/claude-sonnet-4-6")


def _agent(role):
    """An agent whose `.llm.api_key` is live — mirroring the real event shape."""
    return _Stub(role=role, llm=_llm())


def _task(name, agent_role="architect"):
    return _Stub(name=name, description=f"do {name}", agent=_agent(agent_role))


def _recorder():
    """A recorder with no bus subscription — handlers are invoked directly."""
    return TranscriptRecorder()


def test_task_started_and_completed_become_attributed_entries():
    recorder = _recorder()
    task = _task("design")

    recorder._on_task_started(None, _Stub(
        event_id="e1", parent_event_id=None, emission_sequence=1,
        task_name="design", task=task,
    ))
    recorder._on_task_completed(None, _Stub(
        event_id="e2", parent_event_id=None, emission_sequence=9,
        task_name="design", task=task, output=_Stub(raw="the plan"),
    ))

    entries = recorder.entries()
    assert [e.kind for e in entries] == [ENTRY_TASK_STARTED, ENTRY_TASK_COMPLETED]
    assert all(e.task_name == "design" for e in entries)
    assert all(e.agent_role == "architect" for e in entries)
    assert entries[1].content == "the plan"


def test_a_turn_inherits_its_task_from_the_parent_chain():
    """`AgentLogsExecutionEvent` has no task attribute and `task_name` is None,
    so attribution has to come from its ancestors or AC 2 cannot be met."""
    recorder = _recorder()

    recorder._on_task_started(None, _Stub(
        event_id="task-1", parent_event_id=None, emission_sequence=1,
        task_name="design", task=_task("design"),
    ))
    recorder._on_agent_started(None, _Stub(
        event_id="exec-1", parent_event_id="task-1", emission_sequence=2,
        agent=_agent("architect"), task=_task("design"),
    ))
    # The real event carries neither `task` nor a populated `task_name`.
    recorder._on_agent_turn(None, _Stub(
        event_id="log-1", parent_event_id="exec-1", emission_sequence=3,
        agent_role="architect", task_name=None,
        formatted_answer=_Stub(text="Final Answer: done", output="done"),
    ))

    turn = next(e for e in recorder.entries() if e.kind == ENTRY_AGENT_MESSAGE)
    assert turn.task_name == "design"
    assert turn.agent_role == "architect"
    assert turn.content == "Final Answer: done"


def test_a_turn_resolves_even_when_its_parent_is_handled_after_it():
    """Handlers run on a worker pool, so a child's handler can run first.

    The natural margin on the delegation link was measured at ~2.7 ms, so this
    is a real interleaving, not a theoretical one. Attribution is resolved in
    `entries()` — after every handler has run — precisely so a late parent
    still counts.
    """
    recorder = _recorder()

    # Child first, parent second — the reverse of the emission order.
    recorder._on_agent_turn(None, _Stub(
        event_id="log-1", parent_event_id="exec-1", emission_sequence=5,
        agent_role="architect", task_name=None,
        formatted_answer=_Stub(text="Final Answer: done", output="done"),
    ))
    recorder._on_agent_started(None, _Stub(
        event_id="exec-1", parent_event_id="task-1", emission_sequence=3,
        agent=_agent("architect"), task=_task("design"),
    ))
    recorder._on_task_started(None, _Stub(
        event_id="task-1", parent_event_id=None, emission_sequence=2,
        task_name="design", task=_task("design"),
    ))

    turn = next(e for e in recorder.entries() if e.kind == ENTRY_AGENT_MESSAGE)
    assert turn.task_name == "design"
    assert turn.agent_role == "architect"


def test_attribution_climbs_past_an_ancestor_that_knows_nothing():
    """A single parent lookup only works if every intermediate event type is
    subscribed. The walk has to survive a link that resolved to nothing —
    otherwise one unknown node poisons the whole branch below it."""
    recorder = _recorder()

    # exec-1 contributes no task of its own; the grandparent has it.
    recorder._on_task_started(None, _Stub(
        event_id="task-1", parent_event_id=None, emission_sequence=1,
        task_name="design", task=_task("design"),
    ))
    recorder._on_agent_started(None, _Stub(
        event_id="exec-1", parent_event_id="task-1", emission_sequence=2,
        agent=_agent("architect"), task=_Stub(name=None, agent=None),
    ))
    recorder._on_agent_turn(None, _Stub(
        event_id="log-1", parent_event_id="exec-1", emission_sequence=3,
        agent_role="architect", task_name=None,
        formatted_answer=_Stub(text="hi", output="hi"),
    ))

    turn = next(e for e in recorder.entries() if e.kind == ENTRY_AGENT_MESSAGE)
    assert turn.task_name == "design", "the walk stopped at the unknown ancestor"


def test_a_parent_cycle_terminates_instead_of_hanging():
    recorder = _recorder()

    recorder._on_agent_turn(None, _Stub(
        event_id="a", parent_event_id="b", emission_sequence=1,
        agent_role=None, task_name=None,
        formatted_answer=_Stub(text="x", output="x"),
    ))
    # Force a cycle in the parent map.
    recorder._parents["b"] = "a"
    recorder._parents["a"] = "b"

    entry = recorder.entries()[0]
    assert entry.task_name == "unknown"
    assert entry.agent_role == "unknown"


def test_task_boundaries_are_attributed_to_the_declared_owner():
    """CrewAI rebinds `task.agent` to the manager in a hierarchical crew, which
    would make a task-boundary entry disagree with `TaskResult.agent_role`."""
    recorder = TranscriptRecorder({"design": "architect"})

    recorder._on_task_started(None, _Stub(
        event_id="t1", parent_event_id=None, emission_sequence=1,
        task_name="design", task=_task("design", "coordinator"),
    ))

    entry = recorder.entries()[0]
    assert entry.agent_role == "architect"  # the declared owner, not the manager


def test_a_delegated_turn_resolves_to_the_real_task_not_the_synthetic_one():
    """CrewAI invents a throwaway Task for a delegation; attributing entries to
    it would scatter a run across task names no consumer recognizes."""
    recorder = _recorder()

    recorder._on_task_started(None, _Stub(
        event_id="task-1", parent_event_id=None, emission_sequence=1,
        task_name="coordinate", task=_task("coordinate", "coordinator"),
    ))
    recorder._on_agent_started(None, _Stub(
        event_id="exec-mgr", parent_event_id="task-1", emission_sequence=2,
        agent=_agent("coordinator"), task=_task("coordinate", "coordinator"),
    ))
    recorder._on_tool_started(None, _Stub(
        event_id="tool-1", parent_event_id="exec-mgr", emission_sequence=3,
        agent_role="coordinator", task_name="coordinate",
        tool_name="Delegate work to coworker",
        tool_args='{"task": "design it", "coworker": "architect"}',
    ))
    # The delegate's execution hangs off the tool event, and its own `.task` is
    # the synthetic one CrewAI built for the delegation.
    recorder._on_agent_started(None, _Stub(
        event_id="exec-del", parent_event_id="tool-1", emission_sequence=4,
        agent=_agent("architect"), task=_task("design it", "architect"),
    ))
    recorder._on_agent_turn(None, _Stub(
        event_id="log-del", parent_event_id="exec-del", emission_sequence=5,
        agent_role="architect", task_name=None,
        formatted_answer=_Stub(text="Final Answer: done", output="done"),
    ))

    delegated_turn = next(
        e for e in recorder.entries()
        if e.kind == ENTRY_AGENT_MESSAGE and e.agent_role == "architect"
    )
    assert delegated_turn.task_name == "coordinate"


def test_delegation_is_recognized_under_both_tool_name_spellings():
    """The two emit sites disagree: the Started event carries the raw
    "Delegate work to coworker" and the Finished event the sanitized form.
    Matching only one produces a branch no real run can reach."""
    recorder = _recorder()

    recorder._on_tool_started(None, _Stub(
        event_id="t1", parent_event_id=None, emission_sequence=1,
        agent_role="coordinator", task_name="coordinate",
        tool_name="Delegate work to coworker",
        tool_args='{"task": "design it", "coworker": "architect"}',
    ))
    recorder._on_tool_finished(None, _Stub(
        event_id="t2", parent_event_id=None, emission_sequence=2,
        agent_role="coordinator", task_name="coordinate",
        tool_name="delegate_work_to_coworker",
        tool_args={"task": "design it", "coworker": "architect"},
        output="done by architect",
    ))

    entries = recorder.entries()
    assert [e.kind for e in entries] == [ENTRY_DELEGATION, ENTRY_DELEGATION_RESULT]
    assert entries[0].target_role == "architect"
    assert entries[0].content == "design it"
    assert entries[1].content == "done by architect"


def test_a_non_delegation_tool_does_not_become_a_handoff_entry():
    recorder = _recorder()

    recorder._on_tool_started(None, _Stub(
        event_id="t1", parent_event_id=None, emission_sequence=1,
        agent_role="architect", task_name="design",
        tool_name="search_the_web", tool_args='{"q": "x"}',
    ))

    assert recorder.entries() == []


def test_an_intermediate_step_is_distinguished_from_an_answer():
    """A UI renders a tool-using step differently from a reply, so it must not
    have to parse `content` to tell them apart."""
    recorder = _recorder()

    recorder._on_agent_turn(None, _Stub(
        event_id="a1", parent_event_id=None, emission_sequence=1,
        agent_role="architect", task_name="design",
        formatted_answer=_Stub(text="Thought: ...", tool="Delegate work to coworker"),
    ))
    recorder._on_agent_turn(None, _Stub(
        event_id="a2", parent_event_id=None, emission_sequence=2,
        agent_role="architect", task_name="design",
        formatted_answer=_Stub(text="Final Answer: done", output="done"),
    ))

    assert [e.kind for e in recorder.entries()] == [
        ENTRY_AGENT_ACTION,
        ENTRY_AGENT_MESSAGE,
    ]


def test_entries_are_returned_in_emission_order_not_arrival_order():
    """Bus handlers run on a worker pool, so arrival order is not emission
    order — observed [..., 9, 11, 10, 12, ...] on a real run."""
    recorder = _recorder()

    for sequence in (5, 2, 9, 1):
        recorder._on_agent_turn(None, _Stub(
            event_id=f"e{sequence}", parent_event_id=None, emission_sequence=sequence,
            agent_role="architect", task_name="design",
            formatted_answer=_Stub(text=f"turn {sequence}", output=""),
        ))

    assert [e.sequence for e in recorder.entries()] == [1, 2, 5, 9]


def test_an_event_without_a_sequence_is_not_admitted():
    """An unorderable entry cannot belong to an ordered transcript, and would
    break a streaming consumer that sorts on sequence."""
    recorder = _recorder()

    recorder._on_agent_turn(None, _Stub(
        event_id="e1", parent_event_id=None, emission_sequence=None,
        agent_role="architect", task_name="design",
        formatted_answer=_Stub(text="orphan", output=""),
    ))

    assert recorder.entries() == []


def test_no_credential_reaches_an_entry_even_though_events_carry_live_objects():
    """The events below hold live Agent/Task objects whose `.llm.api_key` is a
    plain string — the measured leak surface. Projection is the defence."""
    recorder = _recorder()
    task = _task("design")

    recorder._on_task_started(None, _Stub(
        event_id="e1", parent_event_id=None, emission_sequence=1,
        task_name="design", task=task,
    ))
    recorder._on_agent_started(None, _Stub(
        event_id="e2", parent_event_id="e1", emission_sequence=2,
        agent=_agent("architect"), task=task,
    ))
    recorder._on_tool_started(None, _Stub(
        event_id="e3", parent_event_id="e2", emission_sequence=3,
        agent_role="coordinator", task_name="design", agent=_agent("coordinator"),
        tool_name="Delegate work to coworker",
        tool_args='{"task": "t", "coworker": "architect"}',
    ))

    entries = recorder.entries()
    assert entries, "empty transcript would make this assertion vacuous"
    assert _SECRET not in repr(entries)
    for entry in entries:
        assert _SECRET not in entry.content
        assert _SECRET not in repr(entry)


def test_tool_args_parse_from_either_a_json_string_or_a_dict():
    assert _as_args_dict('{"coworker": "architect"}') == {"coworker": "architect"}
    assert _as_args_dict({"coworker": "architect"}) == {"coworker": "architect"}
    # Malformed or absent args must degrade, not raise, inside a bus handler
    # whose exceptions the bus swallows.
    assert _as_args_dict("not json") == {}
    assert _as_args_dict(None) == {}
    assert _as_args_dict("[1, 2]") == {}


def test_answer_text_prefers_text_and_never_stringifies_an_object():
    assert _answer_text(_Stub(text="hello", output="ignored")) == "hello"
    assert _answer_text(_Stub(text="", output="fallback")) == "fallback"
    assert _answer_text(_Stub(text=None, output=None)) == ""
    assert _answer_text(None) == ""


def test_a_structured_output_object_is_never_stringified_into_content():
    """`AgentFinish.output` may be a pydantic model, and `str(model)` renders
    every field — which is how a structured output holding a credential would
    end up in the transcript. Only genuine strings are accepted."""

    class _Structured(BaseModel):
        summary: str = "ok"
        api_key: str = "sk-LEAK-VIA-STR"

    assert str(_Structured()), "precondition: str(model) renders its fields"
    assert "sk-LEAK-VIA-STR" not in _answer_text(
        _Stub(text=None, output=_Structured())
    )
    assert _answer_text(_Stub(text=None, output=_Structured())) == ""


def test_a_delegation_whose_args_do_not_parse_is_skipped_rather_than_named_nobody():
    """FR-27's point is that a delegation names both agents. A handoff to
    nobody is a plausible-but-wrong entry, which is worse than omitting it."""
    recorder = _recorder()

    for bad_args in ("not json", "", None, '{"task": "t"}', '{"coworker": ["a"]}'):
        recorder._on_tool_started(None, _Stub(
            event_id="t1", parent_event_id=None, emission_sequence=1,
            agent_role="coordinator", task_name="design",
            tool_name="Delegate work to coworker", tool_args=bad_args,
        ))

    assert recorder.entries() == []


def _bus_handler_count() -> int:
    """Handlers actually attached to the process-global bus."""
    handlers = getattr(crewai_event_bus, "_sync_handlers", {})
    return sum(len(v) for v in handlers.values())


def test_the_recorder_removes_its_handlers_from_the_bus_on_exit():
    """Asserted against the bus, not the recorder's own bookkeeping.

    `_unsubscribe` empties `_registered` with its own `pop()` loop, so a test
    that only checks that list passes even if `off()` were a no-op — which is
    exactly what an earlier version of this test did.
    """
    before = _bus_handler_count()

    with TranscriptRecorder():
        during = _bus_handler_count()

    assert during > before, "handlers were not attached to the bus on entry"
    assert _bus_handler_count() == before, "handlers were left on the global bus"


def test_handlers_are_removed_from_the_bus_even_when_the_run_raises():
    before = _bus_handler_count()

    with pytest.raises(RuntimeError):
        with TranscriptRecorder():
            raise RuntimeError("kickoff blew up")

    assert _bus_handler_count() == before


def test_a_failed_registration_does_not_strand_handlers_on_the_bus(monkeypatch):
    """`__exit__` never runs if `__enter__` raises, so `_subscribe` has to
    unwind itself — otherwise a partial registration leaks for the life of the
    process, which is the exact failure the context manager exists to prevent."""
    before = _bus_handler_count()
    real_on = crewai_event_bus.on
    calls = {"n": 0}

    def _flaky_on(event_type):
        calls["n"] += 1
        if calls["n"] == 4:  # fail partway through the seven registrations
            raise RuntimeError("bus refused the registration")
        return real_on(event_type)

    monkeypatch.setattr(crewai_event_bus, "on", _flaky_on)

    with pytest.raises(RuntimeError, match="refused"):
        with TranscriptRecorder():
            pass

    assert _bus_handler_count() == before, "partial registration was not unwound"


def test_a_flush_failure_does_not_mask_the_real_exception(monkeypatch):
    """If kickoff failed, that is the error the user needs — not a bus error
    raised while draining handlers on the way out."""

    def _boom():
        raise RuntimeError("flush exploded")

    monkeypatch.setattr(crewai_event_bus, "flush", _boom)

    with pytest.raises(RuntimeError, match="the real failure"):
        with TranscriptRecorder():
            raise RuntimeError("the real failure")
