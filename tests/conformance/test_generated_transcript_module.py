"""The generated package's transcript recorder, proven against the runtime's
(Story 4.4 AC 3).

AC 3 requires the generated `run_example.py` to capture a transcript "matching
in-process Runtime behavior". A generated package runs *without* `team_maker`
installed, so `codegen/templates/_transcript_module.py.j2` is a standalone port
of `adapters/runtime_crewai/transcript_capture.py` rather than a shared import
— two copies that can drift. This file is what makes the drift fail loudly.

**Why parity and not a separate expectation.** Both recorders subscribe to
crewai's process-global event bus, so both can observe *the same* real run at
once: the generated one is entered around `run_team_package`, whose engine
subscribes its own recorder inside. Any difference in the output is then
attributable to the recorders alone, not to two runs diverging.

This is the only place the generated recorder is ever *executed*.
`tests/unit/test_codegen.py` compiles the rendered template, which proves it
parses and nothing more — the defect this file was written for (attribution
read straight off the event instead of walked up `parent_event_id`, so every
agent turn came back as `"unknown"`) compiles perfectly.

Offline like its sibling: every `BaseLLM.call` is replaced and all HTTP egress
is blocked by `tests/support/crewai_interception.py`. No network, no key, no
real model.
"""
from __future__ import annotations

import importlib.util
import sys

import pytest

# AD-7 conformance gate: crewai is required for these tests.
# If crewai is not installed, the tests must fail explicitly, not skip.
try:
    import crewai  # noqa: F401
except ImportError:
    pytest.fail(
        "crewai is required for generated transcript module tests. "
        "Install with: pip install -e \".[runtime]\""
    )

from team_maker.runtime.executor import run_team_package  # noqa: E402
from team_maker.runtime.loader import load_team_package  # noqa: E402
from team_maker.runtime.ordering import topological_sort  # noqa: E402
from tests.conformance.test_transcript_conformance import (  # noqa: E402
    _KEYS,
    _assert_topology,
    _delegating_responder,
    _package,
)
from tests.support.crewai_interception import (  # noqa: E402
    block_all_network,
    install_call_recorder,
    warm_up_models,
)


def _load_generated_transcript_module(package, name: str, monkeypatch):
    """Import the `transcript.py` the Factory just wrote into *package*.

    Loaded by path under a per-test module name: this is generated output, not
    an installed module, and two tests must not share one cached instance.

    It must be in `sys.modules` *before* it executes. The generated module uses
    `from __future__ import annotations`, so `@dataclass` resolves its fields
    from string annotations by looking the defining module up in `sys.modules`
    — absent, that is an `AttributeError` at class-creation time. `monkeypatch`
    removes the entry again at teardown.
    """
    path = package / "transcript.py"
    assert path.exists(), (
        "the generated package has no transcript.py — CrewAIAdapter.extra_modules "
        "is not reaching the manifest"
    )
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    spec.loader.exec_module(module)
    return module


def _shape(entry):
    """Everything about an entry that either recorder decides."""
    return (
        entry.sequence,
        entry.kind,
        entry.agent_role,
        entry.task_name,
        entry.target_role,
        entry.content,
    )


def _run_both(monkeypatch, package, module, *, responder=None, force_react=False):
    """One real run, observed by both recorders. Returns (generated, runtime)."""
    team = load_team_package(package)
    # The same mapping the engine builds, so a task-boundary entry is attributed
    # to the declaring role rather than to a hierarchical crew's manager.
    task_owners = {
        spec.name: spec.agent_role for spec in topological_sort(team.tasks)
    }

    block_all_network(monkeypatch)
    # Warm up *before* subscribing, so model setup cannot put events into the
    # generated recorder that the engine's (subscribed later) never sees.
    install_call_recorder(
        monkeypatch,
        warm_up_models(package, _KEYS),
        responder=responder,
        force_react=force_react,
    )

    with module.TranscriptRecorder(task_owners) as generated:
        result = run_team_package(package, "ship the thing", _KEYS)
    return generated.entries(), result.transcript


def test_generated_recorder_attributes_a_sequential_run_like_the_runtime(
    tmp_path, monkeypatch
):
    package = _package(tmp_path, orchestrator=False, two_tasks=True)
    _assert_topology(package, hierarchical=False)
    module = _load_generated_transcript_module(
        package, "generated_transcript_sequential", monkeypatch
    )

    generated, runtime = _run_both(monkeypatch, package, module)

    assert generated, "the generated recorder captured nothing"
    for entry in generated:
        # `!= "unknown"`, not truthiness: the sentinel is a non-empty string, so
        # a recorder whose attribution collapsed entirely still passes `assert
        # entry.agent_role`. This is the exact assertion the pre-fix generated
        # recorder failed, on every agent turn.
        assert entry.agent_role != "unknown", f"entry {entry.sequence} lost its agent"
        assert entry.task_name != "unknown", f"entry {entry.sequence} lost its task"
    assert [_shape(e) for e in generated] == [_shape(e) for e in runtime]


def test_generated_recorder_records_a_delegation_like_the_runtime(tmp_path, monkeypatch):
    """The delegation path is where the two ports differ most: identifying a
    delegation means normalizing a tool name that crewai spells differently on
    the Started and Finished events."""
    package = _package(tmp_path, orchestrator=True)
    _assert_topology(package, hierarchical=True)
    module = _load_generated_transcript_module(
        package, "generated_transcript_delegation", monkeypatch
    )

    generated, runtime = _run_both(
        monkeypatch, package, module, responder=_delegating_responder, force_react=True
    )

    assert [_shape(e) for e in generated] == [_shape(e) for e in runtime]
    # Guard the fixture: a run that never delegated would make the comparison
    # above pass while proving nothing about the delegation branch.
    assert any(e.target_role for e in runtime), "fixture produced no delegation"


def test_generated_recorder_leaves_no_handlers_on_the_global_bus(tmp_path, monkeypatch):
    """The bus is a process-global singleton: a recorder that fails to
    unsubscribe silently accumulates every later run's events."""
    from crewai.events import crewai_event_bus

    package = _package(tmp_path, orchestrator=False)
    module = _load_generated_transcript_module(
        package, "generated_transcript_handlers", monkeypatch
    )

    def handler_count() -> int:
        return sum(len(v) for v in getattr(crewai_event_bus, "_sync_handlers", {}).values())

    before = handler_count()
    with module.TranscriptRecorder({}):
        during = handler_count()
    after = handler_count()

    assert during > before, "the recorder never subscribed"
    assert after == before, "the recorder left handlers on the global bus"
