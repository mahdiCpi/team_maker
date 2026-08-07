"""Pre-run credential gate (Story 1.6, FR-10, AD-7, AD-9).

AD-9: "Key-aware resolution runs **before** any run and fails fast with a
plain-language reason." This module is that gate. It resolves every agent's
credential up front and either hands the caller a complete role → credential
map or refuses the run, naming *every* provider that cannot be satisfied.

Two rules shape the implementation:

* **Collect, don't short-circuit.** A user missing two keys should learn both
  in one attempt rather than discovering the second after fixing the first.
* **Name the variable, never the value.** The message says
  ``ANTHROPIC_API_KEY``; it never prints what that key contains (AD-9).

Engine-agnostic by construction — no crewai import, enforced by
``tests/.../test_runtime_engine_port.py``.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

from team_maker.adapters.providers.registry import (
    OPENROUTER,
    get_provider,
    provider_names,
)
from team_maker.adapters.providers.resolution import resolve_credential
from team_maker.domain.models import GeneratedTeam, ResolvedCredential
from team_maker.keyconfig import KeyConfig


@dataclass(frozen=True)
class UnresolvedProvider:
    """One provider that no agent using it can authenticate against.

    ``roles`` is a tuple, not a list: this dataclass is frozen and is handed to
    API callers, so it must actually be hashable and actually be immutable.
    """

    provider: str
    roles: tuple[str, ...] = ()
    expected_key: Optional[str] = None  # None when the provider is unrecognized
    reason: str = ""


class InvalidPackageError(Exception):
    """The package's own data is internally inconsistent, keys aside.

    Distinct from ``MissingCredentialsError``: no key would fix these. The
    Factory cannot produce them (``schema/request.py`` validates the request);
    a hand-edited or third-party package can.
    """


class DuplicateAgentRoleError(InvalidPackageError):
    """Two agents in one package claim the same role.

    Role is the key for both the credential map and the engine's agent map, so
    duplicates silently collapse — the second agent's credential wins and tasks
    belonging to the first execute on it. That is precisely AD-7's "agent A on
    agent B's credential" failure, so it is refused rather than resolved. The
    Factory cannot produce this (``schema/request.py`` enforces role uniqueness);
    a hand-edited or third-party package can.
    """


class InvalidTaskNamesError(InvalidPackageError):
    """A task has no name, or two tasks share one.

    Task name is the join key between `TaskResult`, the transcript, and the
    engine's own task map, so neither case can be resolved silently.
    """


class MissingCredentialsError(Exception):
    """A run cannot start: one or more providers have no usable credentials.

    Carries the structured ``unresolved`` list alongside the rendered message so
    non-CLI callers (the Epic 4 API) can surface it their own way.
    """

    def __init__(self, unresolved: Sequence[UnresolvedProvider]) -> None:
        self.unresolved = tuple(unresolved)
        # `args` must hold what `__init__` accepts, so `type(e)(*e.args)` — how
        # Python reconstructs exceptions when pickling across processes — round
        # trips instead of re-entering `_render_message` with a string.
        super().__init__(self.unresolved)

    def __str__(self) -> str:
        return _render_message(self.unresolved)


def check_credentials(
    team: GeneratedTeam, key_config: KeyConfig
) -> dict[str, ResolvedCredential]:
    """Resolve every agent's credential, or refuse the run.

    Returns a ``{role: ResolvedCredential}`` map covering every agent. Raises
    ``MissingCredentialsError`` if any agent cannot be resolved, or an
    ``InvalidPackageError`` subclass if the package's own data is inconsistent.
    """
    _reject_duplicate_roles(team)
    _reject_invalid_task_names(team)

    resolved: dict[str, ResolvedCredential] = {}
    failed_roles: dict[str, list[str]] = {}

    for agent in team.agents:
        credential = resolve_credential(agent.routing, key_config)
        if credential is None:
            failed_roles.setdefault(agent.routing.provider, []).append(agent.role)
        else:
            resolved[agent.role] = credential

    if failed_roles:
        raise MissingCredentialsError(
            [
                describe_unresolved_provider(provider_name, roles)
                for provider_name, roles in failed_roles.items()
            ]
        )

    return resolved


def _reject_duplicate_roles(team: GeneratedTeam) -> None:
    seen: set[str] = set()
    duplicates: list[str] = []
    for agent in team.agents:
        if agent.role in seen and agent.role not in duplicates:
            duplicates.append(agent.role)
        seen.add(agent.role)
    if duplicates:
        raise DuplicateAgentRoleError(
            "Cannot start this run - these agent roles are declared more than once: "
            + ", ".join(duplicates)
            + ". Role must be unique within a package: it keys each agent's "
            "credential, so duplicates would run one agent on another's key."
        )


def _reject_invalid_task_names(team: GeneratedTeam) -> None:
    """Task name is a join key, so it must be present and unique.

    It identifies a task in `TaskResult`, in every transcript entry, and in the
    crewai `Task` the engine builds. An empty name makes crewai fall back to the
    task *description*, so the transcript and `task_results` stop agreeing;
    duplicates collapse the engine's `crewai_tasks_by_name` map, silently
    breaking `context=` wiring for anything that depends on them. Same reasoning
    as the duplicate-role check above.
    """
    blank = [task.agent_role for task in team.tasks if not (task.name or "").strip()]
    if blank:
        raise InvalidTaskNamesError(
            "Cannot start this run - "
            f"{len(blank)} task(s) have no name (owned by: {', '.join(blank)}). "
            "Task name identifies a task in the results and the transcript, so "
            "it cannot be blank."
        )

    seen: set[str] = set()
    duplicates: list[str] = []
    for task in team.tasks:
        if task.name in seen and task.name not in duplicates:
            duplicates.append(task.name)
        seen.add(task.name)
    if duplicates:
        raise InvalidTaskNamesError(
            "Cannot start this run - these task names are declared more than "
            "once: " + ", ".join(duplicates) + ". Task name must be unique "
            "within a package: it keys the run's results and transcript, and "
            "duplicates would collapse dependent tasks onto one another."
        )


def describe_unresolved_provider(
    provider_name: str, roles: Sequence[str] = ()
) -> UnresolvedProvider:
    """What the user should actually do about a provider that cannot be used.

    Public because it is the *only* fix-hint generator in the system: Story 2.3's
    key-status routes surface the same advice over HTTP, and a second copy would
    be free to drift into the two false statements this function exists to avoid
    — telling someone to add a key that cannot help, and offering OpenRouter to a
    provider it cannot reach.

    ``roles`` is optional: a provider-level caller (the key check) has no role to
    attach and must not have to invent one.

    Names the variable, never the value (AD-9). Every string here is built from
    catalog data, so no credential can enter it.
    """
    provider = get_provider(provider_name)
    if provider is None:
        return UnresolvedProvider(
            provider=provider_name,
            roles=tuple(roles),
            expected_key=None,
            reason=(
                "unrecognized provider; expected one of: "
                + ", ".join(provider_names())
            ),
        )

    if not provider.runtime_supported:
        # A key would not help, so do not ask for one.
        detail = provider.unsupported_reason or "not supported by the installed runtime engine"
        reason = f"{detail}."
        if provider.openrouter_reachable:
            openrouter = get_provider(OPENROUTER)
            if openrouter is not None and openrouter.env_var:
                reason += f" Add {openrouter.env_var} to route it via OpenRouter."
        return UnresolvedProvider(
            provider=provider.name,
            roles=tuple(roles),
            expected_key=None,
            reason=reason,
        )

    if provider.env_var:
        reason = f"add {provider.env_var} to your Key Config"
    else:
        reason = "no API key is configured for it"
    if provider.openrouter_reachable:
        openrouter = get_provider(OPENROUTER)
        if openrouter is not None and openrouter.env_var:
            reason += f", or add {openrouter.env_var} to reach it via OpenRouter"
    return UnresolvedProvider(
        provider=provider.name,
        roles=tuple(roles),
        expected_key=provider.env_var,
        reason=reason + ".",
    )


def _render_message(unresolved: Sequence[UnresolvedProvider]) -> str:
    lines = [
        f"Cannot start this run - {len(unresolved)} provider(s) have no usable credentials:"
    ]
    for item in unresolved:
        agents = ", ".join(item.roles) if item.roles else "none recorded"
        lines.append(f"  - {item.provider} (agents: {agents}) - {item.reason}")
    return "\n".join(lines)
