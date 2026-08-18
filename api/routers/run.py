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

from api.deps import current_key_config, file_only_key_config, safe_label
from api.errors import RUN_BLOCKED, TEAM_NOT_FOUND, ApiError
from api.keystatus import STATUS_UNRECOGNIZED, provider_reports
from api.output import output_root, slugify_team_name
from api.routers.teams import resolve_saved_team_path
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
from team_maker.utils.text_sanitizer import sanitize_control_characters
from team_maker.runtime.executor import (
    UnsupportedFrameworkError,
    check_runnable,
    run_team_package,
)
from team_maker.runtime.loader import TeamPackageError, load_team_package
from team_maker.runtime.ordering import TaskDependencyCycleError, topological_sort
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
# GET /api/runs/teams/{team_slug} — declared first, deliberately.
#
# The pair that actually collides is this route and `GET /{run_id}/transcript`:
# both are two segments under `/runs`, so a team literally named "Transcript"
# makes `/api/runs/teams/transcript` ambiguous between "the plan for team
# `transcript`" and "the transcript of run `teams`". Starlette resolves by
# declaration order, and declaring this one first resolves it correctly.
#
# It does *not* collide with `GET /{run_id}`, which is one segment under
# `/runs` — the story's Dev Notes said otherwise and its Completion Notes
# corrected the claim, but the disproven reason was left standing in this
# comment and in `api/main.py`. Both now say what is true, because the next
# person to reorder these routes will preserve whatever the comment claims.
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

    # Read once, here, and used for both the gate and the run itself, so the
    # two cannot disagree. Re-read rather than `state.key_config`'s startup
    # snapshot: `deps.providers_needing_restart` exists precisely because
    # *authoring* needs a restart to see a new key and *running* does not, and
    # a gate that refused a key the key panel reports as present would be the
    # same availability rule answering twice (Story 2.4 review).
    key_config = current_key_config()

    # AD-9 / AC 7: the same public functions `run_team_package` itself calls,
    # run here synchronously, before the thread is spawned — so no client can
    # reach the engine through a path this gate does not cover. `run_team_package`
    # re-runs the identical checks on the background thread; that redundancy
    # is deliberate and cheap, not a second, drifting copy of the rule.
    _synchronous_run_gate(team, key_config)

    ordered_tasks = _ordered_tasks(team)
    plan = tuple(
        TaskPlanEntry(name=task.name, agent_role=task.agent_role, dependencies=tuple(task.dependencies))
        for task in ordered_tasks
    )
    documents = tuple(
        RunDocument(name=document.name, text=document.text) for document in payload.documents
    )

    def work():
        return run_team_package(
            path, payload.goal, key_config, state.execution_engine, documents=documents
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
                # Sanitize control characters to prevent terminal manipulation attacks
                # via ANSI/OSC sequences in transcript content
                content=sanitize_control_characters(entry.content) if entry.content else "",
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
    value) is what every caller stores and echoes back.

    Story 2.8: a saved team (Story 2.5's `SAVED_TEAMS_ROOT/<team_name>`, keyed
    on the verbatim team name, not a slug) is tried as a fallback when nothing
    exists under the build-output root — this is what lets My Teams reopen a
    team whose original build output no longer exists. The fallback resolves
    against `team_slug` as given (not the re-slugged value), since that is how
    `SAVED_TEAMS_ROOT` keys its directories; the resolved identifier returned
    in that case is `team_slug` itself, so a later lookup by the same value
    (e.g. `record-run`) resolves the same way again.
    """
    slug = slugify_team_name(team_slug)
    path = _resolve_team_path(slug)
    try:
        team = load_team_package(path)
    except TeamPackageError:
        saved_path = resolve_saved_team_path(team_slug)
        if saved_path is not None:
            try:
                return load_team_package(saved_path), saved_path, team_slug
            except TeamPackageError:
                pass
        # Never a message that echoes a filesystem path, and the slug itself
        # is not echoed either (AC 2) — the client already knows what it sent.
        raise ApiError(TEAM_NOT_FOUND, "No such team, or its package could not be read.") from None
    return team, path, slug


def _ordered_tasks(team: GeneratedTeam) -> list:
    """Topological order, with the one failure `topological_sort` can raise
    turned into an authored refusal rather than a 500.

    A package whose tasks depend on each other in a cycle loads cleanly and
    passes both `check_runnable` and `check_credentials` — neither looks at the
    graph — so before this the cycle surfaced as an unhandled
    `TaskDependencyCycleError` on two routes, i.e. `internal_error` for a
    perfectly diagnosable package problem. It is the same category as AC 7's
    second `run_blocked` cause (an internally inconsistent package): no key
    fixes it, and the copy must not suggest one.
    """
    try:
        return topological_sort(team.tasks)
    except TaskDependencyCycleError as exc:
        raise ApiError(
            RUN_BLOCKED,
            "This team cannot run: its tasks depend on one another in a cycle, "
            "so there is no order that satisfies them. No API key will change "
            "that — the package itself needs to be rebuilt.",
        ) from exc


def _team_plan_view(team: GeneratedTeam, state: AppState) -> TeamPlanView:
    # Two *different* configs, exactly as `api/routers/keys.py` passes them:
    # the second is the file-only read, and `keystatus.credential_source` uses
    # the difference between them to tell "the Key Config file supplies this"
    # apart from "only the environment does" and from "the file used to and no
    # longer does". Passing the same object twice — as this did — collapses all
    # three into `key-config`, so the Workspace badge silently dropped the
    # source note the Composer's badge shows for the same provider.
    config = current_key_config()
    reports_by_provider = {
        report.name: report
        for report in provider_reports(config, file_only_key_config(), state.file_providers)
    }
    return TeamPlanView(
        team_name=team.team_name,
        agents=[_agent_key_view(agent, reports_by_provider) for agent in team.agents],
        tasks=[_task_plan_view(task) for task in _ordered_tasks(team)],
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
        # Authored here from the exception's structured field rather than from
        # `str(exc)`. The earlier version's justification — that the framework
        # name is "safe-charset, produced by the compose pipeline" — is not
        # true of a package on disk: `loader.py` reads `primary_framework`
        # straight out of `team_config.yaml` with no validation at all, and
        # nothing stops a hand-edited or corrupt package from putting arbitrary
        # text there. `safe_label` is the sanitiser this codebase already has
        # for exactly this ("a provider id containing a newline forges a log
        # record").
        raise ApiError(
            RUN_BLOCKED,
            f"This team cannot run here: its package targets "
            f"'{safe_label(exc.framework)}', and this server can only run "
            f"'crewai' packages.",
        ) from exc

    try:
        check_credentials(team, key_config)
    except InvalidPackageError as exc:
        # `DuplicateAgentRoleError` / `InvalidTaskNamesError` are single-line
        # sentences authored by `preflight.py`, but they interpolate role and
        # task names read off disk — same exposure as the framework name above,
        # for the same reason. Sanitised with the same helper, at a length that
        # fits a sentence rather than a label. No key would fix either of these
        # and the message does not suggest one.
        raise ApiError(RUN_BLOCKED, safe_label(str(exc), limit=300)) from exc
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
