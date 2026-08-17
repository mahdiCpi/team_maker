"""The compose routes (Story 2.0, AC 2 / AC 3 / AC 7 / AC 8, Story 3-2: from-starter).

Every path operation here is declared `def`, not `async def`, and that is
load-bearing. `Composer.compose()` performs up to four *sequential blocking*
LLM round-trips (`composer.py:106-126`) and nothing in the core is async — the
port is sync, the Anthropic adapter uses the blocking client. Declaring these
`async def` would block the event loop for the whole turn and the API would
stop serving everything, including `/api/health`. Declared `def`, FastAPI runs
them in its threadpool. `tests/api/test_concurrency.py` proves it, and that
test goes red if any handler here is flipped to `async def`.

Story 3.2 addition: POST /compose/sessions/from-starter seeds a session from
a starter team spec without invoking the LLM.

Provider-resolution architecture (Story 3-2 resolved decision)
----------------------------------------------------------------
`create_session` (an ordinary, intent-driven session) still resolves and
credential-gates its authoring provider eagerly, before anything else — that
first turn is going to call the LLM immediately, so there is nothing to defer.

`create_session_from_starter` is different: seeding a session from a starter
spec never calls the LLM (`ComposerSession.seed()` only assigns fields), so it
must not require a usable credential either — "Adapt with Composer" and
direct spec-editing (`PUT .../spec`) have to work with zero configured
provider credentials. It therefore calls `build_authoring_provider(...,
require_credential=False)`: the adapter object is still constructed (every
concrete adapter's `__init__` is credential-free — see `api/deps.py`), but the
"is there a usable credential" gate is skipped.

The gate itself is not skipped forever — it moves to `send_message`, the one
route that turns into a *real* LLM call (`ComposerSession.refine()`). Before
spending a turn, `send_message` now checks `has_usable_credential` itself and
raises the same `AUTHORING_UNAVAILABLE` a normal session would have raised at
creation, just at the point a credential is actually needed. This applies
uniformly to every session, not only starter-seeded ones — for a normal
session the check is a no-op (its credential was already validated at
creation and nothing changes it mid-conversation), so this adds no new failure
mode there, only a clearer one for a session that skipped the eager gate.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Request, status
from pydantic import ValidationError

from api.build import run_build
from api.deps import (
    authoring_unavailable,
    build_authoring_provider,
    has_usable_credential,
    resolve_authoring_choice,
)
from api.errors import (
    AUTHORING_UNAVAILABLE,
    COMPOSE_FAILED,
    NOT_FOUND,
    SPEC_INVALID,
    ApiError,
    FieldError,
    fields_from_composer_errors,
    fields_from_validation_error,
    log_and_wrap,
)
from api.output import derive_output_path, with_output_path
from api.routers.starters import (
    _STARTER_ID_TO_FILE,
    _get_starter_filename,
    _load_starter_yaml,
)
from api.schemas import (
    BuildView,
    CreateSessionFromStarterRequest,
    CreateSessionRequest,
    MessageRequest,
    SessionView,
    SpecEditRequest,
)
from api.sessions import ComposeSession
from api.state import AppState, app_state
from team_maker.composer.composer import Composer, ComposerError
from team_maker.composer.session import ComposerSession
from team_maker.schema.request import TeamCreationRequest

logger = logging.getLogger("api.compose")

router = APIRouter(prefix="/compose", tags=["compose"])


@router.post("/sessions", status_code=status.HTTP_201_CREATED, response_model=SessionView)
def create_session(payload: CreateSessionRequest, request: Request) -> SessionView:
    """Open a conversation and perform its first authoring turn."""
    state = app_state(request)
    selection = payload.authoring
    choice = resolve_authoring_choice(
        selection.provider if selection else None,
        selection.model if selection else None,
    )
    provider = build_authoring_provider(choice, state.key_config, state.provider_factory)
    conversation = ComposerSession(Composer(provider, key_config=state.key_config))

    entry = state.registry.create(conversation, choice)
    state.registry.begin_turn(entry)
    try:
        with state.registry.hold(entry):
            # Story 2.10: start() can return None for non-team input instead of
            # raising — `ComposerSession.start()` already leaves `current` as
            # `None` in that case, so only the clarification text is our job.
            result = _guarded(entry, lambda: conversation.start(payload.intent))
            if result is None:
                entry.clarification = _generate_clarification()
            _adopt_server_output_path(entry)
    except ApiError:
        # The first turn produced no spec, so there is nothing to refine and a
        # follow-up message would hit `refine() before start()`. Drop the
        # session rather than leave a half-born one that only 500s.
        state.registry.discard(entry.session_id)
        raise
    return _session_view(state, entry)


@router.post("/sessions/{session_id}/messages", response_model=SessionView)
def send_message(session_id: str, payload: MessageRequest, request: Request) -> SessionView:
    """Refine the current spec. On failure `session.current` is left intact."""
    state = app_state(request)
    entry = state.registry.get(session_id)
    # The deferred half of the "Provider resolution architecture" note above:
    # a session created via `create_session_from_starter` never had this
    # checked, since seeding spends no LLM call. This turn is the first one
    # that actually does, so the gate belongs here — for every session, not
    # only a starter-seeded one, since nothing else re-checks it later either.
    if not has_usable_credential(entry.choice, state.key_config):
        raise authoring_unavailable(entry.choice)
    # Reserved before the call, not after: a failed turn still spent 1–4 LLM
    # round-trips, and the cap exists to bound spend, not successes.
    state.registry.begin_turn(entry)
    with state.registry.hold(entry):
        # Story 2.10: refine() can return None — still no spec yet, or the
        # message didn't describe one either — instead of raising.
        result = _guarded(entry, lambda: entry.conversation.refine(payload.message))
        if result is None:
            entry.clarification = _generate_clarification()
        # A refine re-authors the whole spec, including `output_path`, which is
        # how a free-text message used to steer where the build writes.
        _adopt_server_output_path(entry)
    return _session_view(state, entry)


@router.put("/sessions/{session_id}/spec", response_model=SessionView)
def replace_spec(session_id: str, payload: SpecEditRequest, request: Request) -> SessionView:
    """Apply a direct edit to the three client-owned dimensions of the spec.

    No LLM call happens here, so this does not consume a turn.

    Story 2.10: If the session is in needs_clarification state (current is None),
    spec edits are not allowed.
    """
    state = app_state(request)
    entry = state.registry.get(session_id)
    with state.registry.hold(entry):
        # Story 2.10: cannot edit spec if we don't have one yet
        if entry.conversation.current is None:
            raise ApiError(
                SPEC_INVALID,
                "This conversation has no team specification yet. "
                "Describe a team first, then you can edit it.",
            )
        current = _current_spec(entry)
        merged = _merge_spec(current, payload)
        try:
            updated = TeamCreationRequest(**merged)
        except ValidationError as exc:
            # `session.current` is untouched — `merged` was a throwaway dict.
            raise ApiError(
                SPEC_INVALID,
                "Those changes do not produce a valid team specification.",
                fields=fields_from_validation_error(exc),
            ) from exc
        entry.conversation.current = updated
        _adopt_server_output_path(entry)
    return _session_view(state, entry)


@router.post("/sessions/{session_id}/build", response_model=BuildView)
def build_session(session_id: str, request: Request) -> BuildView:
    """Generate the team package from the session's current spec."""
    state = app_state(request)
    entry = state.registry.get(session_id)
    with state.registry.hold(entry):
        # Story 2.10: cannot build if we don't have a spec
        if entry.conversation.current is None:
            raise ApiError(
                SPEC_INVALID,
                "This conversation has no team specification yet. "
                "Describe a team first, then you can build it.",
            )
        return run_build(_current_spec(entry))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _session_view(state: AppState, entry: ComposeSession) -> SessionView:
    current = entry.conversation.current
    if current is None:
        # needs_clarification path: no spec yet
        return SessionView(
            session_id=entry.session_id,
            status="needs_clarification",
            spec=None,
            clarification=entry.clarification,
            turn=entry.turn,
            turns_remaining=state.registry.turns_remaining(entry),
        )
    spec = current
    return SessionView(
        session_id=entry.session_id,
        status="complete",
        # The re-serialised server spec is authoritative: `_pre_process`
        # (`request.py:271-354`) silently rewrites input in five ways, so
        # "edited JSON in" is not "JSON out" and a client must re-render from
        # this rather than from its own local edit.
        spec=spec.model_dump(mode="json", exclude_none=True),
        clarification=None,
        turn=entry.turn,
        turns_remaining=state.registry.turns_remaining(entry),
    )


def _current_spec(entry: ComposeSession) -> TeamCreationRequest:
    current = entry.conversation.current
    if current is None:  # pragma: no cover — sessions without a spec return needs_clarification
        raise ApiError(
            SPEC_INVALID, "This conversation has no team specification yet."
        )
    return current


def _adopt_server_output_path(entry: ComposeSession) -> None:
    """Replace whatever the composer chose with the server's own path.

    `output_path` is the one required spec field a client can steer without
    sending it: the LLM authors it from free-text intent, so refusing it on the
    edit body (which `SpecEditRequest` does) closed only one of two doors. The
    path is derived once, from the first spec this session produced, and pinned
    for the session's life — see `api/output.py`.
    """
    current = entry.conversation.current
    if current is None:  # pragma: no cover — a spec-less session returns needs_clarification
        return
    if entry.output_path is None:
        entry.output_path = derive_output_path(current.team_name)
    entry.conversation.current = with_output_path(current, entry.output_path)


def _guarded(
    entry: ComposeSession, call: Callable[[], TeamCreationRequest | None]
) -> TeamCreationRequest | None:
    """Run one authoring turn, mapping every failure onto an AC 2 error code.

    The CLI's interactive loop catches only `ComposerError` and any other
    exception kills the conversation (`deferred-work.md:53`); the repair loop
    retries only on `pydantic.ValidationError`, so a network blip propagates
    with zero retries (`deferred-work.md:47`). This catches broadly and never
    lets an exception string reach the client — `str(exc)` on an SDK error can
    echo an embedded secret (`deferred-work.md:45`).

    Returns the call's result (`None` for a Story 2.10 needs_clarification
    turn) so the caller can react to it; every failure raises instead of
    returning.
    """
    try:
        return call()
    except ComposerError as exc:
        raise log_and_wrap(
            SPEC_INVALID,
            "The team specification could not be completed from that description. "
            "Try rephrasing it, or simplifying the requirements.",
            exc,
            fields=fields_from_composer_errors(exc.errors),
        ) from exc
    except Exception as exc:
        if entry.choice.keyless:
            # A keyless local provider cannot fail for a credential — it fails
            # because nothing is listening. Say that, and say where (AC 10).
            endpoint = entry.choice.config.base_url or "its local endpoint"
            raise log_and_wrap(
                AUTHORING_UNAVAILABLE,
                f"Could not reach the local authoring provider "
                f"'{entry.choice.config.provider}' at {endpoint}. Start it, or "
                f"choose a hosted authoring provider.",
                exc,
            ) from exc
        # Causally neutral on purpose. This branch catches *everything* that is
        # not a ComposerError — a network fault, yes, but equally a TypeError
        # from a bug in this repo. The previous copy ("the authoring provider
        # could not be reached") asserted a cause the code has not established,
        # which blamed the upstream for our own defects and invited a retry loop
        # that spends money and can never succeed. Saying only what is known —
        # the spec was not created — costs nothing and misleads no one.
        # Classifying the exception properly would mean recognising SDK-specific
        # types inside api/, which is precisely what AD-8 keeps out of this
        # layer; it is deliberately not attempted in this story.
        raise log_and_wrap(
            COMPOSE_FAILED,
            "The team specification could not be created. Retry once; if the "
            "problem repeats, stop and report it.",
            exc,
        ) from exc


def _merge_spec(current: TeamCreationRequest, payload: SpecEditRequest) -> dict[str, Any]:
    """Overlay the permitted dimensions onto a dump of the current spec.

    Server-owned fields are carried across simply by starting from the current
    spec and never letting the body name them (`SpecEditRequest` is
    `extra="forbid"`). `exclude_unset=True` is what distinguishes "the client
    omitted this" from "the client explicitly cleared it".
    """
    merged = current.model_dump(mode="json")
    edit = payload.model_dump(mode="json", exclude_unset=True)

    for key in ("team_name", "purpose"):
        if key in edit:
            merged[key] = edit[key]

    if "desired_roles" in edit:
        merged["desired_roles"] = _merge_roles(merged.get("desired_roles") or [], payload)
    if "desired_tasks" in edit:
        # TaskHint's fields are exactly TaskEdit's, so tasks replace wholesale.
        merged["desired_tasks"] = [
            task.model_dump(mode="json") for task in (payload.desired_tasks or [])
        ]

    if not merged.get("desired_roles"):
        # An empty roles list flips the build into a second LLM call through
        # `planning_llm` — a different provider config, and silent cost
        # (`runner.py:66-69`, `llm/planner.py:24-46`).
        raise ApiError(
            SPEC_INVALID,
            "A team needs at least one role.",
            fields=[FieldError("desired_roles", "Add at least one role.")],
        )
    _check_task_integrity(merged)
    return merged


def _check_task_integrity(merged: dict[str, Any]) -> None:
    """Reject task edits the core would silently discard at build time.

    Neither of these is caught by `TeamCreationRequest`: it validates unique
    *role* names (`request.py`'s `check_unique_role_names`) but has no
    equivalent for tasks and no referential check between the two lists. The
    template does the discarding instead, and does it quietly —

    * two tasks with the same name collapse onto one manifest key, so one file
      is written while `task_count` reports two;
    * a task whose `agent_role` no longer names a role is dropped, and if
      *every* declared task drops the template substitutes its own defaults —
      so renaming a role to `architect` can put tasks in the built package that
      the user never authored.

    Both are reachable from an ordinary edit: renaming a role without touching
    `desired_tasks` orphans them. Better a 422 naming the problem than a 200
    describing a package that was not built.
    """
    tasks = merged.get("desired_tasks") or []
    role_names = {role.get("name") for role in merged.get("desired_roles") or []}

    seen: set[str] = set()
    duplicates: list[str] = []
    orphans: list[tuple[int, str, str]] = []
    for index, task in enumerate(tasks):
        name = task.get("name")
        if name in seen and name not in duplicates:
            duplicates.append(name)
        seen.add(name)
        owner = task.get("agent_role")
        if owner not in role_names:
            orphans.append((index, str(name), str(owner)))

    fields: list[FieldError] = []
    for name in duplicates:
        fields.append(
            FieldError("desired_tasks", f"Two tasks are both named '{name}'; names must be unique.")
        )
    for index, name, owner in orphans:
        fields.append(
            FieldError(
                f"desired_tasks.{index}.agent_role",
                f"Task '{name}' is assigned to '{owner}', which is not one of the team's roles.",
            )
        )
    if fields:
        raise ApiError(
            SPEC_INVALID,
            "Those changes leave the task list inconsistent with the team's roles.",
            fields=fields,
        )


def _merge_roles(existing: list[dict[str, Any]], payload: SpecEditRequest) -> list[dict[str, Any]]:
    """Replace the roles list, preserving fields the edit shape cannot express.

    `RoleEdit` carries three of `RoleDefinition`'s nine fields. A role whose
    name still matches keeps its `goal`, `backstory`, `capabilities`, `tools`,
    `display_name` and `is_optional`; a renamed or new role starts clean.
    """
    by_name = {role.get("name"): role for role in existing}
    merged: list[dict[str, Any]] = []
    for role in payload.desired_roles or []:
        base = dict(by_name.get(role.name) or {})
        base.update(role.model_dump(mode="json", exclude_unset=True))
        base["name"] = role.name
        merged.append(base)
    return merged


def _generate_clarification() -> str:
    """A short, direct invitation to describe a team to build (Story 2.10)."""
    return "Please describe the team you want to build and what they should do."


# ---------------------------------------------------------------------------
# Starter-seeded sessions (Story 3-2: Run and adapt a starter team)
# ---------------------------------------------------------------------------


@router.post("/sessions/from-starter", status_code=status.HTTP_201_CREATED, response_model=SessionView)
def create_session_from_starter(
    payload: CreateSessionFromStarterRequest, request: Request
) -> SessionView:
    """Create a Composer session pre-loaded with a starter team's spec.

    This endpoint seeds a session from an existing starter team's
    TeamCreationRequest without invoking the LLM (no authoring turn is
    spent). The seeded spec's team_name is automatically suffixed with
    "-adapted" to ensure the build directory is distinct from the original
    starter's, preventing accidental overwrites (Story 3-2 resolved decision).

    No authoring credential is required to create this session — see this
    module's "Provider resolution architecture" note above. The returned
    session can be driven through the existing /messages, /spec, and /build
    routes exactly like a normally-composed session.

    Story 3-2, Task 3.
    """
    state = app_state(request)
    # Always the default authoring provider — a starter-seeded session has no
    # `authoring` selection of its own (`CreateSessionFromStarterRequest`
    # carries only `starter_id`).
    choice = resolve_authoring_choice(None, None)
    # `require_credential=False`: seeding spends no LLM call, so no credential
    # is required to create this session. The adapter is still constructed
    # (safe and credential-free — see `build_authoring_provider`'s docstring)
    # so a later chat message has a real provider to call; `send_message`
    # is where a missing credential is actually gated.
    provider = build_authoring_provider(
        choice, state.key_config, state.provider_factory, require_credential=False
    )
    conversation = ComposerSession(Composer(provider, key_config=state.key_config))

    entry = state.registry.create(conversation, choice)
    # No begin_turn: seeding from a starter does not consume an authoring turn
    try:
        with state.registry.hold(entry):
            # Load the starter spec — the same helpers `api/routers/starters.py`
            # itself uses, not a second copy of them.
            filename = _get_starter_filename(payload.starter_id)
            starter_spec = _load_starter_yaml(filename)

            # Auto-rename to prevent overwriting the original starter's build
            # (Story 3-2 resolved decision: suffix with "-adapted")
            adapted_spec = starter_spec.model_copy(
                update={"team_name": f"{starter_spec.team_name}-adapted"}
            )

            # Seed the session with the adapted spec
            conversation.seed(adapted_spec)

            # Adopt the server output path (same as create_session)
            _adopt_server_output_path(entry)
    except FileNotFoundError as exc:
        # Discarded here too, not just in the `ApiError` branch below — a
        # half-born session that never got a spec is exactly as useless to
        # leave behind as one whose seeding raised an `ApiError`.
        state.registry.discard(entry.session_id)
        available = ", ".join(sorted(_STARTER_ID_TO_FILE))
        raise ApiError(
            NOT_FOUND,
            f"Starter team '{payload.starter_id}' not found. Available starters: {available}",
        ) from exc
    except ApiError:
        # Clean up the session if seeding fails
        state.registry.discard(entry.session_id)
        raise

    return _session_view(state, entry)
