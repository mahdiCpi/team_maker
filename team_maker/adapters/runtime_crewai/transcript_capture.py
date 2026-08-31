"""Translate crewai run events into engine-neutral transcript entries (Story 1.7).

Lives under ``adapters/runtime_crewai/`` because it is the only place allowed to
know crewai exists (AD-6). It emits ``TranscriptEntry`` — a plain dataclass owned
by ``runtime/results.py`` — so nothing crewai-shaped escapes into the Runtime.

## Why the event bus, and not ``step_callback``

``Crew(step_callback=...)`` / ``Agent(step_callback=...)`` are the obvious hook
and they are the wrong one. Verified against the installed crewai 1.14.6: they
fire inconsistently (once on a native-tool finish, never on a forced-ReAct run),
and — decisive here — the ``AgentAction``/``AgentFinish`` they receive carry **no
agent and no task reference**, so per-entry attribution is impossible. The event
bus is what crewai's own console and tracing listeners are built on.

## Three things about the bus that shape this code

1. **Dispatch is exact-type** (``event_bus.py`` looks up ``type(event)``).
   Subscribing to a base class catches nothing, so ``_subscribe`` enumerates
   concrete event classes one by one.
2. **Handlers run on a worker pool**, so a *child* event's handler can run before
   its parent's — the natural margin on the delegation link was measured at
   ~2.7 ms. Attribution is therefore **resolved lazily in `entries()`**, once
   every handler has run and the bus has been flushed, rather than eagerly
   inside each handler where a parent may not have been seen yet. Handler
   exceptions are also swallowed and printed by the bus, so a broken handler
   fails silently; tests must assert on captured content.
3. **The bus is a process-global singleton.** Handlers must be unregistered or
   they accumulate entries from every later run in the process. Reproduced while
   building this: a spike that skipped ``off()`` recorded every event twice on
   its second run. Hence the context-manager shape, with the registration loop
   unwinding itself if it fails partway.

## Attribution: a real walk, and no sentinels in the map

``AgentLogsExecutionEvent`` is the per-turn event, and it has neither a ``task``
nor an ``agent`` attribute; its ``task_name`` is always ``None``.
``AgentExecutionStartedEvent`` reports ``agent_role``/``task_name`` as ``None``
too, and for a *delegated* execution its own ``.task`` is a synthetic throwaway
task crewai invents. So attribution comes from ancestors::

    normal turn:    AgentLogsExecutionEvent -> AgentExecutionStartedEvent -> TaskStartedEvent
    delegated turn: AgentLogsExecutionEvent -> AgentExecutionStartedEvent -> ToolUsageStartedEvent

Two rules make that walk trustworthy, both learned the hard way in review:

* **Only real values enter the map.** An earlier version stored the literal
  ``"unknown"`` placeholder, which is truthy — so a descendant stopped at the
  placeholder instead of continuing to a grandparent that knew the answer. One
  missed link silently corrupted a whole branch. Unresolved is ``None``.
* **The walk is multi-level**, with a visited-set so a malformed parent cycle
  terminates. A single ``.get`` only works if every intermediate event type is
  subscribed; walking survives an unsubscribed link in the chain.

## Secrets

Several events hold **live** ``Agent``/``Task`` objects whose ``.llm.api_key`` is
a plain string that ``to_json()`` will serialize. Measured leak paths on real
runs: ``TaskStartedEvent``/``TaskCompletedEvent`` at ``.task.agent.llm.api_key``;
``AgentExecutionStartedEvent``/``AgentExecutionCompletedEvent`` at
``.agent.llm.api_key`` and ``.task.agent.llm.api_key``; and
``ToolUsageStartedEvent`` at ``.agent.llm.api_key`` while its ``Finished`` twin
is clean. The safe/unsafe split is per-event *and* per-emit-site, so this module
projects scalars unconditionally, never retains an event object, and never
stringifies an arbitrary object into ``content`` (AD-9, NFR3).
"""
from __future__ import annotations

import json
import re
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from crewai.events import crewai_event_bus
from crewai.events.types.agent_events import AgentExecutionStartedEvent
from crewai.events.types.logging_events import AgentLogsExecutionEvent
from crewai.events.types.task_events import TaskCompletedEvent, TaskStartedEvent
from crewai.events.types.tool_usage_events import (
    ToolUsageErrorEvent,
    ToolUsageFinishedEvent,
    ToolUsageStartedEvent,
)
from crewai.utilities.string_utils import sanitize_tool_name

from team_maker.runtime.results import (
    ENTRY_AGENT_ACTION,
    ENTRY_AGENT_MESSAGE,
    ENTRY_DELEGATION,
    ENTRY_DELEGATION_RESULT,
    ENTRY_TASK_COMPLETED,
    ENTRY_TASK_STARTED,
    ToolReceipt,
    TranscriptEntry,
)
from team_maker.utils.text_sanitizer import sanitize_text_for_display

# crewai's delegation tools, by their sanitized names. The raw `name` differs
# between emit sites ("Delegate work to coworker" on Started, the snake_case
# form on Finished), so both sides are normalized before comparison — matching
# the snake_case name alone yields a branch no real run can reach.
_DELEGATION_TOOLS = frozenset({"delegate_work_to_coworker", "ask_question_to_coworker"})

# Shown only when the walk genuinely cannot attribute an entry. Never stored in
# the attribution map — see the module docstring.
_UNKNOWN_AGENT = "unknown"
_UNKNOWN_TASK = "unknown"

# Depth cap on the parent walk; far beyond any real crewai nesting, and a
# backstop against a malformed chain that the visited-set somehow misses.
_MAX_PARENT_DEPTH = 32


def _role_of(obj: Any) -> Optional[str]:
    role = getattr(obj, "role", None)
    return str(role) if role else None


def _name_of(obj: Any) -> Optional[str]:
    name = getattr(obj, "name", None)
    return str(name) if name else None


def _as_args_dict(raw: Any) -> dict[str, Any]:
    """`tool_args` arrives as a JSON string on Started and a dict on Finished."""
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
        except ValueError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


# An absolute filesystem path — Windows drive-letter or POSIX-rooted. A raw
# resolved host path must never appear in a receipt (spec FR-071); rather
# than only recognizing the operator's own dangerous-location prefixes (a
# list that could drift from `tools/policy.py`), any absolute path is
# redacted outright — over-redaction here costs a little receipt fidelity
# for something like a harmless in-sandbox `/workspace/...` argument, never
# a leaked secret location. Mirrors `_redact_secrets`' own stated preference
# for over- over under-redaction (utils/text_sanitizer.py).
_ABS_PATH_PATTERN = re.compile(r"^(?:[A-Za-z]:[\\/]|/)\S*$")


def _sanitize_argument_value(value: Any) -> str:
    """One tool-call argument value, safe to store in a `ToolReceipt` (spec
    FR-029, FR-071). Routes through the same secret-redaction guard used
    for exception messages and CLI/API-facing text
    (`utils/text_sanitizer.sanitize_text_for_display`), then additionally
    redacts anything shaped like an absolute host path."""
    text = str(value)
    text = sanitize_text_for_display(text)
    if _ABS_PATH_PATTERN.match(text.strip()):
        return "[REDACTED_PATH]"
    return text


def _sanitize_arguments(args: dict[str, Any]) -> dict[str, str]:
    return {key: _sanitize_argument_value(value) for key, value in args.items()}


def _text_of(value: Any) -> Optional[str]:
    """A string, or None. Deliberately refuses to stringify anything else.

    `AgentFinish.output` may be a pydantic model, and `str(model)` renders every
    field — which is how a structured output holding a credential would land in
    `content`. Only genuine strings are accepted; anything else is not content.
    """
    return value if isinstance(value, str) and value.strip() else None


def _answer_text(formatted_answer: Any) -> str:
    """Pull a string out of an AgentAction/AgentFinish without retaining it.

    Both carry ``.text``; ``.output`` is a fallback and is only used when it is
    already a string.
    """
    return (
        _text_of(getattr(formatted_answer, "text", None))
        or _text_of(getattr(formatted_answer, "output", None))
        or ""
    )


@dataclass
class _Pending:
    """An entry captured but not yet attributed.

    Attribution is deferred until `entries()` because a parent event's handler
    may not have run when this one did.
    """

    sequence: int
    kind: str
    content: str
    event_id: Optional[str]
    parent_event_id: Optional[str]
    agent_role: Optional[str]
    task_name: Optional[str]
    target_role: Optional[str] = None


class TranscriptRecorder:
    """Collects an ordered, attributed transcript from one crew run.

    Use as a context manager around ``kickoff`` so handlers are always removed::

        with TranscriptRecorder(task_owners) as recorder:
            output = crew.kickoff(inputs=...)
        transcript = recorder.entries()

    ``task_owners`` maps task name -> the role that *declares* ownership of it.
    It exists because crewai rebinds ``task.agent`` to the manager in a
    hierarchical crew, which would otherwise make a task-boundary entry say
    "coordinator" while ``TaskResult.agent_role`` says "architect" for the same
    task — a disagreement a consumer grouping by task cannot reconcile.
    """

    def __init__(self, task_owners: Optional[dict[str, str]] = None) -> None:
        self._task_owners = dict(task_owners or {})
        self._pending: list[_Pending] = []
        self._receipts: list[ToolReceipt] = []
        # event_id -> (task_name | None, agent_role | None). Only real values.
        self._attribution: dict[str, tuple[Optional[str], Optional[str]]] = {}
        # event_id -> parent_event_id, so the walk can climb past a link whose
        # own attribution is unknown.
        self._parents: dict[str, str] = {}
        self._registered: list[tuple[type, Callable[..., None]]] = []
        self._lock = threading.Lock()

    # -- lifecycle ---------------------------------------------------------

    def __enter__(self) -> TranscriptRecorder:
        self._subscribe()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        # Flush before unsubscribing: kickoff flushes internally *before* its
        # final event, so the tail can still be in flight when it returns.
        # Both steps are best-effort — a failure here must never replace the
        # exception the caller actually needs to see (a kickoff auth error is
        # far more useful than "the bus failed to drain").
        try:
            crewai_event_bus.flush()
        except Exception:  # noqa: BLE001 - deliberately swallowed, see above
            pass
        finally:
            self._unsubscribe()

    def entries(self) -> list[TranscriptEntry]:
        """The transcript: attributed, then ordered by emission sequence.

        Attribution happens here rather than in the handlers because handlers
        run out of order on a worker pool; by now every parent has been seen.
        """
        with self._lock:
            pending = list(self._pending)
        resolved = [self._attribute(item) for item in pending]
        return sorted(resolved, key=lambda entry: entry.sequence)

    def receipts(self) -> list[ToolReceipt]:
        """Every tool execution recorded during this run (spec FR-026,
        FR-028), ordered by emission sequence — the sole admissible
        evidence for `runtime/completion.py`'s completion rule."""
        with self._lock:
            return sorted(self._receipts, key=lambda receipt: receipt.sequence)

    # -- subscription ------------------------------------------------------

    def _subscribe(self) -> None:
        handlers: list[tuple[type, Callable[..., None]]] = [
            (TaskStartedEvent, self._on_task_started),
            (TaskCompletedEvent, self._on_task_completed),
            (AgentExecutionStartedEvent, self._on_agent_started),
            (AgentLogsExecutionEvent, self._on_agent_turn),
            (ToolUsageStartedEvent, self._on_tool_started),
            (ToolUsageFinishedEvent, self._on_tool_finished),
            (ToolUsageErrorEvent, self._on_tool_error),
        ]
        try:
            for event_type, handler in handlers:
                crewai_event_bus.on(event_type)(handler)
                self._registered.append((event_type, handler))
        except Exception:
            # __exit__ never runs if __enter__ raises, so a partial
            # registration would strand handlers on the process-global bus for
            # the life of the process. Unwind what we managed to attach.
            self._unsubscribe()
            raise

    def _unsubscribe(self) -> None:
        while self._registered:
            event_type, handler = self._registered.pop()
            try:
                crewai_event_bus.off(event_type, handler)
            except Exception:  # noqa: BLE001 - one failure must not strand the rest
                pass

    # -- attribution -------------------------------------------------------

    def _remember(
        self, event: Any, task_name: Optional[str], agent_role: Optional[str]
    ) -> None:
        """Record what this event knows. Never records a placeholder."""
        event_id = getattr(event, "event_id", None)
        if not event_id:
            return
        parent_id = getattr(event, "parent_event_id", None)
        with self._lock:
            self._attribution[str(event_id)] = (task_name, agent_role)
            if parent_id:
                self._parents[str(event_id)] = str(parent_id)

    def _walk(
        self, event_id: Optional[str], parent_id: Optional[str]
    ) -> tuple[Optional[str], Optional[str]]:
        """Climb the parent chain until both task and agent are known."""
        with self._lock:
            task, agent = self._attribution.get(str(event_id), (None, None)) if event_id else (
                None,
                None,
            )
            seen: set[str] = {str(event_id)} if event_id else set()
            current = str(parent_id) if parent_id else None
            depth = 0
            while current and current not in seen and depth < _MAX_PARENT_DEPTH:
                seen.add(current)
                depth += 1
                parent_task, parent_agent = self._attribution.get(current, (None, None))
                task = task or parent_task
                agent = agent or parent_agent
                if task and agent:
                    break
                current = self._parents.get(current)
        return task, agent

    def _attribute(self, item: _Pending) -> TranscriptEntry:
        task, agent = self._walk(item.event_id, item.parent_event_id)
        task_name = item.task_name or task or _UNKNOWN_TASK
        agent_role = item.agent_role or agent or _UNKNOWN_AGENT
        # Task boundaries belong to the role that declares the task, not to the
        # manager crewai rebinds onto it in a hierarchical crew.
        if item.kind in (ENTRY_TASK_STARTED, ENTRY_TASK_COMPLETED):
            agent_role = self._task_owners.get(task_name, agent_role)
        return TranscriptEntry(
            sequence=item.sequence,
            kind=item.kind,
            agent_role=agent_role,
            task_name=task_name,
            content=item.content,
            target_role=item.target_role,
        )

    def _add(
        self,
        event: Any,
        kind: str,
        content: str,
        *,
        task_name: Optional[str] = None,
        agent_role: Optional[str] = None,
        target_role: Optional[str] = None,
    ) -> None:
        sequence = getattr(event, "emission_sequence", None)
        if not isinstance(sequence, int):
            return  # not orderable, so not admissible to an ordered transcript
        event_id = getattr(event, "event_id", None)
        parent_id = getattr(event, "parent_event_id", None)
        item = _Pending(
            sequence=sequence,
            kind=kind,
            content=content,
            event_id=str(event_id) if event_id else None,
            parent_event_id=str(parent_id) if parent_id else None,
            agent_role=agent_role,
            task_name=task_name,
            target_role=target_role,
        )
        with self._lock:
            self._pending.append(item)

    # -- handlers ----------------------------------------------------------
    # Each reads scalars off the event and retains nothing else.

    def _on_task_started(self, source: Any, event: Any) -> None:
        task = getattr(event, "task", None)
        task_name = getattr(event, "task_name", None) or _name_of(task)
        agent_role = _role_of(getattr(task, "agent", None))
        self._remember(event, task_name, agent_role)
        description = _text_of(getattr(task, "description", None))
        self._add(
            event,
            ENTRY_TASK_STARTED,
            description or task_name or "",
            task_name=task_name,
            agent_role=agent_role,
        )

    def _on_task_completed(self, source: Any, event: Any) -> None:
        task = getattr(event, "task", None)
        task_name = getattr(event, "task_name", None) or _name_of(task)
        agent_role = _role_of(getattr(task, "agent", None))
        self._remember(event, task_name, agent_role)
        raw = _text_of(getattr(getattr(event, "output", None), "raw", None))
        self._add(
            event,
            ENTRY_TASK_COMPLETED,
            raw or "",
            task_name=task_name,
            agent_role=agent_role,
        )

    def _on_agent_started(self, source: Any, event: Any) -> None:
        # Emits no entry: it exists to put this execution's agent into the map
        # so the turns hanging off it can be attributed. Its own `.task` is a
        # synthetic throwaway for a delegated execution, so no task is recorded
        # here — the walk picks the real one up from an ancestor.
        self._remember(event, None, _role_of(getattr(event, "agent", None)))

    def _on_agent_turn(self, source: Any, event: Any) -> None:
        agent_role = getattr(event, "agent_role", None)
        self._remember(event, getattr(event, "task_name", None), agent_role)
        formatted = getattr(event, "formatted_answer", None)
        # AgentAction is an intermediate step (it names a tool); AgentFinish is
        # the turn's answer. Distinguishing them is what lets a UI render a
        # "thinking" step differently from a reply.
        kind = (
            ENTRY_AGENT_ACTION
            if getattr(formatted, "tool", None)
            else ENTRY_AGENT_MESSAGE
        )
        self._add(
            event,
            kind,
            _answer_text(formatted),
            task_name=getattr(event, "task_name", None),
            agent_role=agent_role,
        )

    def _on_tool_started(self, source: Any, event: Any) -> None:
        task_name = getattr(event, "task_name", None)
        agent_role = getattr(event, "agent_role", None)
        self._remember(event, task_name, agent_role)
        target = self._delegate_of(event)
        if target is None:
            return
        args = _as_args_dict(getattr(event, "tool_args", None))
        self._add(
            event,
            ENTRY_DELEGATION,
            _text_of(args.get("task")) or "",
            task_name=task_name,
            agent_role=agent_role,
            target_role=target,
        )

    def _on_tool_finished(self, source: Any, event: Any) -> None:
        task_name = getattr(event, "task_name", None)
        agent_role = getattr(event, "agent_role", None)
        self._remember(event, task_name, agent_role)
        self._record_receipt(event, succeeded=True)
        target = self._delegate_of(event)
        if target is None:
            return
        self._add(
            event,
            ENTRY_DELEGATION_RESULT,
            _text_of(getattr(event, "output", None)) or "",
            task_name=task_name,
            agent_role=agent_role,
            target_role=target,
        )

    def _on_tool_error(self, source: Any, event: Any) -> None:
        """`ToolUsageErrorEvent` is a distinct event from `Finished` (D-3,
        D-IMPL-003 Decision A) — this is how a `ToolPolicyRefusal` (Phase 4:
        a refused sandbox, mount or resource-limit breach) and any other
        tool exception surface as a **failed** receipt (FR-077) rather than
        producing no receipt at all."""
        task_name = getattr(event, "task_name", None)
        agent_role = getattr(event, "agent_role", None)
        self._remember(event, task_name, agent_role)
        self._record_receipt(event, succeeded=False)

    def _record_receipt(self, event: Any, *, succeeded: bool) -> None:
        """One receipt per execution (data-model.md §5), built entirely
        from the outcome event (`Finished`/`Error`) — both inherit every
        field a receipt needs (`tool_name`, `tool_args`, `agent_role`,
        `task_name`) from `ToolUsageEvent`, so no correlation with the
        earlier `Started` event is required."""
        sequence = getattr(event, "emission_sequence", None)
        if not isinstance(sequence, int):
            return  # not orderable — not admissible, matching `_add`'s rule
        tool_name = getattr(event, "tool_name", None)
        if not tool_name:
            return
        args = _sanitize_arguments(_as_args_dict(getattr(event, "tool_args", None)))
        event_id = getattr(event, "event_id", None)
        receipt = ToolReceipt(
            sequence=sequence,
            tool_name=str(tool_name),
            agent_role=str(getattr(event, "agent_role", None) or _UNKNOWN_AGENT),
            task_name=str(getattr(event, "task_name", None) or _UNKNOWN_TASK),
            arguments=args,
            succeeded=succeeded,
            timestamp=datetime.now(timezone.utc).isoformat(),
            output_ref=str(event_id) if event_id else f"tool-receipt-{sequence}",
        )
        with self._lock:
            self._receipts.append(receipt)

    @classmethod
    def _delegate_of(cls, event: Any) -> Optional[str]:
        """The coworker a delegation names, or None if this isn't one.

        Returns None rather than emitting a nameless entry when the args cannot
        be parsed or the coworker is not a plain string: FR-27's point is that a
        delegation names both agents, and a "handoff to nobody" is a
        plausible-but-wrong entry, which is worse than omitting it.
        """
        tool_name = getattr(event, "tool_name", None)
        if not tool_name:
            return None
        if sanitize_tool_name(str(tool_name)) not in _DELEGATION_TOOLS:
            return None
        args = _as_args_dict(getattr(event, "tool_args", None))
        return _text_of(args.get("coworker")) or _text_of(args.get("agent"))
