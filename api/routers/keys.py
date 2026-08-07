"""The key-status group (Story 2.3, AC 1 / AC 2 / AC 3).

`epics.md:334` assigns this group to Story 2.3 as the first consumer, because AD-9
forbids the browser touching keys: the four UX-DR5 states have to come from a
read-only server endpoint. **Status only — never a key value.**

Both handlers are `def`, not `async def`. They re-read the Key Config from disk
(see below), which is blocking I/O, so FastAPI runs them in its threadpool —
`api/main.py:44-53` documents why `health()` is the one exemption to that rule.

Why the Key Config is re-read per request
-----------------------------------------
`api/main.py`'s lifespan loads it once into a frozen `AppState`. Reporting from
that snapshot would mean a user who follows a fix hint, adds the key, and
re-checks is told the pre-edit truth forever — the feature broken in exactly the
flow it exists for. `KeyConfig.from_file()` never raises, so a fresh read is safe.

Nothing here writes the fresh config back into `AppState`, and nothing re-runs
`bridge_credentials`: `api/deps.py:12-24` documents the race that makes a
per-request `os.environ` mutation unsafe. The cost of that is real and reported
rather than hidden — see `needs_restart_to_author`.

Why the config is read *twice*
------------------------------
The documented credential priority is the Key Config file, then the provider's
environment variable (`keyconfig.py:8-10`), and both are legitimate. But
`bridge_credentials` copies every file value into `os.environ` at startup, so
after a user *deletes* a key the env fallback keeps returning the value this
process bridged — and a single read cannot tell that apart from a key the file
still defines. Reading once with the fallback and once without gives the honest
answer: the credential is real (so it is not hidden) *and* the report says which
source supplied it. See `api/keystatus.credential_source`.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Request

from api.keystatus import (
    any_key_present,
    blocking_reason,
    check_overall,
    needs_restart_to_author,
    provider_overall,
    provider_reports,
    role_reports,
)
from api.routings import requested_routings
from api.schemas import (
    KeyCheckView,
    KeyStatusView,
    ProviderKeyView,
    RoleKeyView,
)
from api.state import AppState, app_state
from team_maker.domain.models import ProviderRouting
from team_maker.keyconfig import KeyConfig
from team_maker.schema.request import TeamCreationRequest

logger = logging.getLogger("api.keys")

router = APIRouter(prefix="/keys", tags=["keys"])

#: The synthetic role standing in for the LLM that *invents* the team when the
#: client supplies no roles. Not a spec role — deliberately not snake_case, so it
#: can never collide with one (`request.py` requires `^[a-z][a-z0-9_]*$`).
PLANNER_ROLE = "(the planner)"


@router.get("/status", response_model=KeyStatusView)
def key_status(request: Request) -> KeyStatusView:
    """Per-provider key status. Reads the Key Config; returns no key value."""
    state = app_state(request)
    config = _fresh_config()
    file_config = _file_only_config()
    return KeyStatusView(
        overall=provider_overall(config),
        providers=_provider_views(config, file_config, state.file_providers),
        **_common_fields(state, config),
    )


@router.get("/check/{session_id}", response_model=KeyCheckView)
def key_check(session_id: str, request: Request) -> KeyCheckView:
    """Whether this conversation's team can actually run, role by role."""
    state = app_state(request)
    # Raises the existing `session_not_found` (404) for an unknown or evicted id,
    # rather than inventing a second not-found path.
    entry = state.registry.get(session_id)
    spec = entry.conversation.current
    config = _fresh_config()
    file_config = _file_only_config()

    if spec is None:  # pragma: no cover — a spec-less session is discarded
        roles = []
    else:
        routings, inherited = _required_routings(spec)
        roles = role_reports(
            routings,
            inherited,
            config,
            file_config,
            state.file_providers,
            required=frozenset({PLANNER_ROLE}),
        )

    reason = blocking_reason(roles)
    return KeyCheckView(
        overall=check_overall(roles),
        blocked=reason is not None,
        blocking_reason=reason,
        roles=[RoleKeyView(**vars(report)) for report in roles],
        providers=_provider_views(config, file_config, state.file_providers),
        **_common_fields(state, config),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fresh_config() -> KeyConfig:
    """Re-read the Key Config so a post-startup edit is visible. Never raises."""
    return KeyConfig.from_file()


def _file_only_config() -> KeyConfig:
    """The same read without the environment fallback, for source attribution."""
    return KeyConfig.from_file(include_env=False)


def _provider_views(
    config: KeyConfig, file_config: KeyConfig, file_providers: tuple[str, ...]
) -> list[ProviderKeyView]:
    return [
        ProviderKeyView(**vars(report))
        for report in provider_reports(config, file_config, file_providers)
    ]


def _common_fields(state: AppState, config: KeyConfig) -> dict:
    return {
        "key_config_path": str(KeyConfig.default_path()),
        "load_warnings": list(config.load_warnings),
        "any_key_present": any_key_present(config),
        "needs_restart_to_author": needs_restart_to_author(
            config, state.bridged_providers
        ),
    }


def _required_routings(
    spec: TeamCreationRequest,
) -> tuple[dict[str, ProviderRouting], dict[str, bool]]:
    """Which providers this spec's build actually needs, and which were inherited.

    Two build strategies, and they need different credentials
    (`pipeline/runner.py:66-69`):

    * **With roles** — the template resolves each role's routing in memory and the
      build needs no credential of its own, so the required set is the roles.
    * **Without roles (the planner path)** — the team is *invented* at build time by
      `TeamPlanner.from_request`, which calls `create_provider(request.planning_llm)`
      (`llm/planner.py:26`). That is the one build that genuinely cannot start
      without a working credential, and reporting it as "nothing to check" left the
      only path needing a key as the only path ungated.

    `planning_llm` is a real, defaulted field on the request, so its provider is as
    classifiable as any role's — "unknown" was a choice, not a limit.
    """
    routings = requested_routings(spec)
    if routings:
        return routings, {role.name: role.llm is None for role in spec.desired_roles}
    planning = spec.planning_llm
    return (
        {
            PLANNER_ROLE: ProviderRouting(
                provider=planning.provider,
                model=planning.model,
                api_key_env=planning.api_key_env,
            )
        },
        # The client never names `planning_llm` through this API, so it is always
        # the server-supplied default.
        {PLANNER_ROLE: True},
    )
