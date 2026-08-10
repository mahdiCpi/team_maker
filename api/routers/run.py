"""The four `run` routes (Story 2.4, `epics.md:335`).

Every handler is `def`, not `async def` (`compose.py`'s rationale applies
identically: nothing in the Runtime is async), and every handler's first
statement is `state = app_state(request)`.

`api/` reaches the runtime only through `team_maker.runtime.executor` and its
siblings (`loader`, `preflight`, `ordering`, `run_context`) — never through
`team_maker/adapters/runtime_crewai/` (AD-6 / AD-8). Every one of those
modules' own module-scope imports is crewai-free (verified, not trusted, in
this story's Debug Log), so importing them here at module scope cannot make
`/api/health` fail to start on a machine without crewai installed.
"""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Request

from api.deps import safe_label
from api.errors import RUN_BLOCKED, TEAM_NOT_FOUND, ApiError
from api.keystatus import STATUS_UNRECOGNIZED, provider_reports
from api.output import output_root, slugify_team_name
from api.runs import RunRecord, TaskPlanEntry
from api.schemas import (
    AgentKeyView,
    RunCreateRequest,
    RunResultView,
    RunView,
    TaskOutputView,
    TaskPlanView,
    TeamPlanView,
    TranscriptEntryView,
    TranscriptView,
)
from api.state import AppState, app_state
from team_maker.domain.models import AgentSpec, GeneratedTeam
from team_maker.keyconfig import KeyConfig
from team_maker.runtime.executor import (
    UnsupportedFrameworkError,
    check_runnable,
    run_team_package,
)
from team_maker.runtime.loader import TeamPackageError, load_team_package
from team_maker.runtime.ordering import topological_sort
from team_maker.runtime.preflight import (
    InvalidPackageError,
    MissingCredentialsError,
    check_credentials,
    describe_unresolved_provider,
)
from team_maker.runtime.run_context import RunDocument

# Named the same as `api/runs.py`'s registry logger, deliberately: the two
# modules together are one feature (the `run` group), the way `api/sessions.py`
# and `api/routers/compose.py` are two — but unlike that pair, this story's
# Dev Notes name this exact logger for this exact file, so the run group's
# route-level and registry-level log lines share one name rather than
# following the compose/keys precedent of one logger per file.
logger = logging.getLogger("api.runs")

router = APIRouter(prefix="/runs", tags=["runs"])


# ---------------------------------------------------------------------------
# GET /api/runs/teams/{team_slug} — declared before GET /{run_id}: both are
# two segments under /runs, so FastAPI resolves them by declaration order.
# ---------------------------------------------------------------------------


@router.get("/teams/{team_slug}", response_model=TeamPlanView)
def get_team_plan(team_slug: str, request: Request) -> TeamPlanView:
    state = app_state(request)
    team, _path, _slug = _load_team_or_404(team_slug)
    return _team_plan_view(team, state)


# ---------------------------------------------------------------------------
# POST /api/runs
# ---------------------------------------------------------------------------


@router.post("", response_model=RunView)
def create_run(payload: RunCreateRequest, request: Request) -> RunView:
    state = app_state(request)
    team, path, slug = _load_team_or_404(payload.team_slug)

    # AD-9 / AC 7: the same public functions `run_team_package` itself calls,
    # run here synchronously, before the thread is spawned — so no client can
    # reach the engine through a path this gate does not cover. `run_team_package`
    # re-runs the identical checks on the background thread; that redundancy
    # is deliberate and cheap, not a second, drifting copy of the rule.
    _synchronous_run_gate(team, state.key_config)

    ordered_tasks = topological_sort(team.tasks)
    plan = tuple(
        TaskPlanEntry(name=task.name, agent_role=task.agent_role, dependencies=tuple(task.dependencies))
        for task in ordered_tasks
    )
    documents = tuple(
        RunDocument(name=document.name, text=document.text) for document in payload.documents
    )

    def work():
        return run_team_package(
            path, payload.goal, state.key_config, state.execution_engine, documents=documents
        )

    record = state.run_registry.start(
        team_slug=slug, team_name=team.team_name, tasks=plan, work=work
    )
    return _run_view(record)


# ---------------------------------------------------------------------------
# GET /api/runs/{run_id}
# ---------------------------------------------------------------------------


@router.get("/{run_id}", response_model=RunView)
def get_run(run_id: str, request: Request) -> RunView:
    state = app_state(request)
    record = state.run_registry.get(run_id)
    return _run_view(record)


# ---------------------------------------------------------------------------
# GET /api/runs/{run_id}/transcript
# ---------------------------------------------------------------------------


@router.get("/{run_id}/transcript", response_model=TranscriptView)
def get_run_transcript(run_id: str, request: Request) -> TranscriptView:
    state = app_state(request)
    record = state.run_registry.get(run_id)
    if record.result is None:
        # Covers both "still running" and "failed" (`deferred-work.md:101`:
        # a failed run's partial transcript is discarded along with the
        # exception, so there is genuinely nothing to return). A `200` with
        # an explicit `available=False`, never a 404 (that would mean "no
        # such run") and never a bare empty list (that would mean "the
        # agents said nothing").
        return TranscriptView(available=False, entries=[])
    entries = sorted(record.result.transcript, key=lambda entry: entry.sequence)
    return TranscriptView(
        available=True,
        entries=[
            TranscriptEntryView(
                sequence=entry.sequence,
                kind=entry.kind,
                agent_role=entry.agent_role,
                task_name=entry.task_name,
                content=entry.content,
                target_role=entry.target_role,
            )
            for entry in entries
        ],
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_team_path(slug: str) -> Path:
    """*slug* must already be the re-slugified value — see `_load_team_or_404`.

    The containment check below can never actually fire against a value that
    already went through `slugify_team_name` ("a single safe path segment.
    Never empty, never a traversal", by construction) — it exists anyway,
    deliberately, as defence in depth: Story 2.0's review found a *verified*
    path traversal in this exact codebase, and a second, independent check is
    the response to having shipped that once.
    """
    root = output_root()
    resolved = (root / slug).resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        raise ApiError(TEAM_NOT_FOUND, "No such team.") from None
    return resolved


def _load_team_or_404(team_slug: str) -> tuple[GeneratedTeam, Path, str]:
    """The client's value names a slug, never a path (Story 2.4 AC 2) — it is
    re-slugged here, once, and the *resolved* slug (never the client's raw
    value) is what every caller stores and echoes back."""
    slug = slugify_team_name(team_slug)
    path = _resolve_team_path(slug)
    try:
        team = load_team_package(path)
    except TeamPackageError:
        # Never a message that echoes a filesystem path, and the slug itself
        # is not echoed either (AC 2) — the client already knows what it sent.
        raise ApiError(TEAM_NOT_FOUND, "No such team, or its package could not be read.") from None
    return team, path, slug


def _team_plan_view(team: GeneratedTeam, state: AppState) -> TeamPlanView:
    reports_by_provider = {
        report.name: report
        for report in provider_reports(state.key_config, state.key_config, state.file_providers)
    }
    return TeamPlanView(
        team_name=team.team_name,
        agents=[_agent_key_view(agent, reports_by_provider) for agent in team.agents],
        tasks=[_task_plan_view(task) for task in topological_sort(team.tasks)],
    )


def _agent_key_view(agent: AgentSpec, reports_by_provider: dict) -> AgentKeyView:
    report = reports_by_provider.get(agent.routing.provider)
    if report is None:
        # Mirrors `keystatus.role_reports`'s handling of the identical case
        # for the Composer's surface: an unrecognised provider is not
        # "missing a key" — no key exists to add.
        return AgentKeyView(
            role=agent.role,
            provider=agent.routing.provider,
            model=agent.routing.model,
            status=STATUS_UNRECOGNIZED,
            detail="not a known provider",
            usable=False,
            fix_hint=describe_unresolved_provider(agent.routing.provider).reason,
        )
    return AgentKeyView(
        role=agent.role,
        provider=agent.routing.provider,
        model=agent.routing.model,
        status=report.status,
        detail=report.detail,
        usable=report.usable,
        fix_hint=report.fix_hint,
    )


def _task_plan_view(task) -> TaskPlanView:
    return TaskPlanView(name=task.name, agent_role=task.agent_role, dependencies=list(task.dependencies))


def _run_view(record: RunRecord) -> RunView:
    result_view = None
    if record.result is not None:
        result_view = RunResultView(
            final_output=record.result.final_output,
            task_results=[
                TaskOutputView(name=item.name, agent_role=item.agent_role, output=item.output)
                for item in record.result.task_results
            ],
        )
    return RunView(
        status=record.status,
        run_id=record.run_id,
        team_slug=record.team_slug,
        team_name=record.team_name,
        tasks=[
            TaskPlanView(name=entry.name, agent_role=entry.agent_role, dependencies=list(entry.dependencies))
            for entry in record.tasks
        ],
        result=result_view,
        transcript_available=record.result is not None,
        failure_reason=record.failure_reason,
    )


def _synchronous_run_gate(team: GeneratedTeam, key_config: KeyConfig) -> None:
    """AD-9 / AC 7: fail fast, before the thread is spawned.

    `run_blocked` covers three distinct causes with three distinct sentences
    (the client's handling is identical — refuse, state why — but the
    remedies differ, and telling someone to add a key that would not help is
    worse than telling them the truth).
    """
    try:
        check_runnable(team)
    except UnsupportedFrameworkError as exc:
        # Authored entirely by `executor.check_runnable` from a static
        # template plus the package's own (safe-charset) framework name —
        # not an opaque exception, so `str(exc)` here is that authored
        # sentence, not a leak.
        raise ApiError(RUN_BLOCKED, str(exc)) from exc

    try:
        check_credentials(team, key_config)
    except InvalidPackageError as exc:
        # Same reasoning: `DuplicateAgentRoleError` / `InvalidTaskNamesError`
        # messages are authored entirely by `preflight.py` from a static
        # template plus role/task names already constrained to a safe
        # charset by the compose pipeline. No key would fix either; the
        # message says so.
        raise ApiError(RUN_BLOCKED, str(exc)) from exc
    except MissingCredentialsError as exc:
        raise _run_blocked_from_missing_credentials(exc) from exc


def _run_blocked_from_missing_credentials(exc: MissingCredentialsError) -> ApiError:
    """Author the sentence from `exc.unresolved`'s structured fields.

    Never `str(exc)` / `MissingCredentialsError.__str__` — that is
    `preflight._render_message`, a multi-line, hanging-indent format authored
    for a terminal, not this envelope's single `message` string.
    """
    clauses = []
    for item in exc.unresolved:
        roles = ", ".join(safe_label(role) for role in item.roles) if item.roles else "no roles recorded"
        clauses.append(f"'{safe_label(item.provider)}' ({roles}): {item.reason}")
    message = "This team cannot run yet: " + "; ".join(clauses)
    return ApiError(RUN_BLOCKED, message)
