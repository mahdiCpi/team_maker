"""Declaration validation: the enforcement gate for canonical tool identity
(spec FR-002 to FR-005, FR-056 to FR-060; audit RC-3, §2.2(a)).

One shared core (`validate_declarations`) is invoked at three named stages —
compose (`team_maker/composer/composer.py`), build (`team_maker/pipeline/runner.py`)
and preflight (`team_maker/runtime/preflight.py`) — so the verdict for a given
declaration cannot differ between stages (contracts/tool-catalog.md). Compose
and build call this module directly (Phase 3, Step 1); preflight additionally
layers resolvability, authorization and sandbox-policy checks on top of it
(Phase 7, Step 6) using the same `RejectionReason` vocabulary, defined here so
both stages report failures identically (FR-060).

No path through this module may substitute a different tool, emit a stub,
skip the declaration, or fall back to a degraded path (FR-059): the outcome
of validating a declaration is exactly ACCEPT or REJECT, with no third case.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from team_maker.tools.catalog import TOOL_CATALOG, is_canonical, resolve_alias


class RejectionReason(Enum):
    """The five reason classes a stage rejection must report as exactly one of
    (FR-060). Shared across compose, build and preflight so a diagnostic can
    always tell *why* a declaration was refused, not just *that* it was."""

    UNKNOWN = "unknown"  # not in the catalog
    INVALID = "invalid"  # in the catalog, but the declaration is malformed
    UNRESOLVABLE = "unresolvable"  # canonical, but no instance can be produced here
    UNAUTHORIZED = "unauthorized"  # resolvable, but operator policy does not permit it
    UNSAFE = "unsafe"  # authorized, but execution policy cannot be satisfied


@dataclass(frozen=True)
class ToolRejection:
    """One rejected declaration, carrying everything FR-060 requires a
    rejection to name: the tool, the declaring agent, the stage, and exactly
    one reason class."""

    tool_name: str
    agent_role: str
    stage: str
    reason: RejectionReason
    detail: str

    def __str__(self) -> str:
        return (
            f"[{self.stage}] tool '{self.tool_name}' declared by agent '{self.agent_role}' "
            f"rejected ({self.reason.value}): {self.detail}"
        )


@dataclass(frozen=True)
class ValidationOutcome:
    """The result of validating every declaration in one batch. Rejections are
    aggregated (FR-060, collect-don't-short-circuit) — a user learns about
    every offending declaration in one pass, not one at a time."""

    rejections: tuple[ToolRejection, ...]

    @property
    def passed(self) -> bool:
        return len(self.rejections) == 0

    def raise_if_rejected(self) -> None:
        """Stage-appropriate hard failure. Callers name their own exception
        type per stage (FR-056/057/058 have distinct stage semantics); this
        raises a stage-agnostic error carrying every rejection for callers
        that don't need a stage-specific type."""
        if not self.passed:
            raise ToolValidationError(list(self.rejections))


class ToolValidationError(Exception):
    """Raised when one or more declarations fail validation. Carries every
    rejection (FR-060 aggregation), never just the first."""

    def __init__(self, rejections: list[ToolRejection]) -> None:
        self.rejections = rejections
        super().__init__("; ".join(str(r) for r in rejections))


def validate_declarations(
    declarations: list[tuple[str, str]],
    *,
    stage: str,
) -> ValidationOutcome:
    """Validate a batch of (tool_name, agent_role) declarations against the
    canonical catalog. This is the compose/build-stage check (FR-002, FR-003):
    catalog membership only. It does not check resolvability, authorization or
    sandbox policy — those are preflight-stage concerns layered on top in
    Phase 7 (FR-058), using the same `RejectionReason` vocabulary.

    An alias-only match is rejected, not silently resolved (D-2): the
    suggested canonical replacement is included in the rejection detail, but
    the declaration itself never succeeds on an alias.
    """
    rejections: list[ToolRejection] = []
    for tool_name, agent_role in declarations:
        if is_canonical(tool_name):
            continue
        canonical = resolve_alias(tool_name)
        if canonical is not None:
            detail = f"'{tool_name}' is a legacy alias - use the canonical name '{canonical}'"
        else:
            detail = f"'{tool_name}' is not in the canonical tool catalog"
        rejections.append(
            ToolRejection(
                tool_name=tool_name,
                agent_role=agent_role,
                stage=stage,
                reason=RejectionReason.UNKNOWN,
                detail=detail,
            )
        )
    return ValidationOutcome(rejections=tuple(rejections))


def validate_suggested_tool_credentials(
    suggested_tools: list,
) -> ValidationOutcome:
    """FR-004: gate a model-authored `suggested_tools` entry's proposed
    `env_vars` against the catalog when its name resolves to a canonical
    tool. Closes the path that put `SERPAPI_API_KEY` — a name in no source
    file — into a shipped package: the planner suggested a near-miss of the
    real `web_search` tool with an invented credential variable instead of
    the catalog's actual `SERPER_API_KEY`.

    A suggestion whose name is not canonical and not a recognized alias is
    left alone here — it is inert metadata that is never promoted into an
    agent's `tools` list (see `schema/request.py`'s promotion step) and can
    never reach execution, so no credential check applies to it.
    """
    rejections: list[ToolRejection] = []
    for suggestion in suggested_tools:
        name = getattr(suggestion, "name", None) or (suggestion.get("name") if isinstance(suggestion, dict) else None)
        env_vars = getattr(suggestion, "env_vars", None)
        if env_vars is None and isinstance(suggestion, dict):
            env_vars = suggestion.get("env_vars", [])
        env_vars = env_vars or []
        if name is None:
            continue
        canonical_name = name if is_canonical(name) else resolve_alias(name)
        if canonical_name is None:
            continue  # not canonical, not an alias — inert, never executed
        allowed = set(TOOL_CATALOG[canonical_name].required_credentials)
        for env_var in env_vars:
            if env_var not in allowed:
                rejections.append(
                    ToolRejection(
                        tool_name=canonical_name,
                        agent_role="<suggested_tools>",
                        stage="compose",
                        reason=RejectionReason.INVALID,
                        detail=(
                            f"suggested credential '{env_var}' for '{canonical_name}' does not "
                            f"match its catalog requirement(s) {sorted(allowed) or '(none)'}"
                        ),
                    )
                )
    return ValidationOutcome(rejections=tuple(rejections))
