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

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

from team_maker.adapters.providers.registry import (
    OPENROUTER,
    get_provider,
    provider_names,
)
from team_maker.adapters.providers.resolution import UnqualifiedModelError, resolve_credential
from team_maker.domain.models import GeneratedTeam, ResolvedCredential
from team_maker.keyconfig import KeyConfig
from team_maker.tools.authorization import AuthorizationPolicy
from team_maker.tools.config import ToolPolicyConfig


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
    unqualified: list[UnresolvedProvider] = []

    for agent in team.agents:
        try:
            credential = resolve_credential(agent.routing, key_config)
        except UnqualifiedModelError as exc:
            # A usable credential exists, but the model string itself could not
            # be safely qualified (AC8) -- distinct from a missing key, so it
            # gets its own reason rather than being folded into "add a key".
            unqualified.append(
                UnresolvedProvider(
                    provider=agent.routing.provider,
                    roles=(agent.role,),
                    expected_key=None,
                    reason=str(exc),
                )
            )
            continue
        if credential is None:
            failed_roles.setdefault(agent.routing.provider, []).append(agent.role)
        else:
            resolved[agent.role] = credential

    if failed_roles or unqualified:
        raise MissingCredentialsError(
            [
                describe_unresolved_provider(provider_name, roles)
                for provider_name, roles in failed_roles.items()
            ]
            + unqualified
        )

    return resolved


class UnauthorizedToolError(Exception):
    """One or more declared RISKY tools are not authorized by operator
    policy (spec FR-050 to FR-055, FR-058).

    Distinct from an unresolvable tool (`UnresolvableToolError`) — this
    tool exists and could run, but the operator has not permitted it. FR-051:
    a team declaring a tool is not authorization, so this check runs at
    preflight, before any agent is constructed, exactly like
    `check_credentials`.
    """

    def __init__(self, denied: Sequence[str]) -> None:
        self.denied = tuple(denied)
        super().__init__(self.denied)

    def __str__(self) -> str:
        return (
            f"tool(s) {list(self.denied)} are RISKY and not authorized by operator policy. "
            f"RISKY tools are denied by default — the operator must explicitly enable them "
            f"before a run declaring them can start."
        )


def check_tool_authorization(team: GeneratedTeam, policy: AuthorizationPolicy) -> None:
    """Evaluate RISKY-tool authorization for every agent's declared tools,
    before any agent is constructed (spec FR-055, FR-058, Amendment 1).

    Collect-don't-short-circuit, matching `check_credentials`: every denied
    tool is named in one refusal. Applies identically regardless of package
    provenance (FR-080) — this function takes only the team and the policy,
    never anything that could differ for a hand-edited or third-party
    package.
    """
    from team_maker.tools.authorization import check_authorization

    declared = sorted({t for agent in team.agents for t in agent.tools})
    denied = check_authorization(declared, policy)
    if denied:
        raise UnauthorizedToolError(denied)


class UnavailableToolError(Exception):
    """One or more declared tools are unknown, invalid, unresolvable in this
    package, or missing a required credential in this environment (spec
    FR-030, FR-031, FR-067, FR-068).

    Distinct from `UnauthorizedToolError` (T107, FR-058): a diagnostic can
    tell "not permitted here" (authorization — the tool could run if
    enabled) from "not available here" (this exception — the tool cannot
    run regardless of authorization). Collect-don't-short-circuit: every
    problem is named in one refusal (FR-031), never a credential's value
    (AD-9).
    """

    def __init__(self, problems: Sequence[str]) -> None:
        self.problems = tuple(problems)
        super().__init__(self.problems)

    def __str__(self) -> str:
        return "; ".join(self.problems)


class UnsafeMountPolicyError(Exception):
    """The operator's own mount allowlist contains an entry that itself
    resolves to a dangerous location (spec FR-032) — caught here, before
    any agent runs, rather than only when a `docker_runner` call is
    actually attempted deep into the run."""

    def __init__(self, aliases: Sequence[str]) -> None:
        self.aliases = tuple(aliases)
        super().__init__(self.aliases)

    def __str__(self) -> str:
        return (
            f"operator mount allowlist entries {list(self.aliases)} resolve to a "
            f"dangerous location and must be removed from the policy file"
        )


def check_tool_availability(team: GeneratedTeam, package_path: Path) -> None:
    """FR-030, FR-031, FR-058, FR-067, FR-068: hard-fail when a declared
    tool is unknown/invalid, missing a required credential, or unresolvable
    in this package — before any agent is constructed. Deliberately
    excludes authorization (T107; see `check_tool_authorization`), so a
    caller can tell "not permitted here" from "not available here" instead
    of one undifferentiated refusal.

    Applies identically regardless of package provenance (FR-080): this
    function consults only `team` and `package_path`, so a hand-edited or
    third-party package gets the exact same checks as a factory-built one.
    Collect-don't-short-circuit (FR-031): every problem is named in one
    refusal, naming the tool and what would satisfy it (FR-068), never a
    credential's value (AD-9).
    """
    from team_maker.adapters.tools.package_tool_resolver import (
        PackageToolResolver,
        PreRemediationPackageError,
    )
    from team_maker.ports.tool_resolver import (
        ToolPolicyError,
        UnknownToolError,
        UnresolvableToolError,
    )
    from team_maker.tools.catalog import CONDITIONALLY_AVAILABLE_TOOL_NAMES, TOOL_CATALOG
    from team_maker.tools.validation import validate_declarations

    declarations = [(name, agent.role) for agent in team.agents for name in agent.tools]
    if not declarations:
        return

    problems: list[str] = []

    outcome = validate_declarations(declarations, stage="preflight")
    problems.extend(str(rejection) for rejection in outcome.rejections)
    unknown_names = {rejection.tool_name for rejection in outcome.rejections}
    canonical_names = sorted({name for name, _ in declarations if name not in unknown_names})

    # FR-067/FR-068: required credentials, named never valued (AD-9).
    # Skips CONDITIONALLY_AVAILABLE_TOOL_NAMES (D-IMPL-007): those three
    # names' own missing-credential case is already handled leniently by
    # `PackageToolResolver.resolve_all` below (warn and omit, since Phase 7's
    # proper actionable-hard-failure treatment doesn't fully exist yet) —
    # hard-failing on the credential here would silently re-break exactly
    # what that mechanism exists to keep working.
    for name in canonical_names:
        if name in CONDITIONALLY_AVAILABLE_TOOL_NAMES:
            continue
        for env_var in TOOL_CATALOG[name].required_credentials:
            if not os.environ.get(env_var):
                problems.append(
                    f"tool '{name}' requires credential '{env_var}', which is not set "
                    f"in the environment — set {env_var} to use this tool"
                )

    try:
        PackageToolResolver(package_path).resolve_all(canonical_names)
    except PreRemediationPackageError as exc:
        problems.append(str(exc))
    except (UnresolvableToolError, UnknownToolError, ToolPolicyError) as exc:
        problems.append(str(exc))

    if problems:
        raise UnavailableToolError(problems)


def check_mount_allowlist_safety(policy: ToolPolicyConfig) -> None:
    """FR-032, FR-016, FR-079: every mount the operator's current policy
    would permit still satisfies the dangerous-location floor at run time.
    The rendered package already re-checks this on every actual
    `docker_runner` call (`tools.py.j2`'s `_evaluate_mount`); this is the
    same guarantee applied once, up front, so a policy file edited to add a
    dangerous entry between build and run is refused before the run starts
    rather than only when that call is eventually reached."""
    from team_maker.tools.policy import is_dangerous

    dangerous = [
        entry.alias
        for entry in policy.mount_allowlist.entries
        if is_dangerous(Path(entry.host_path).expanduser().resolve())
    ]
    if dangerous:
        raise UnsafeMountPolicyError(dangerous)


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
