"""Tool authorization policy: may this tool run at all (spec FR-050 to
FR-055; Amendment 1; D-10).

Distinct from `team_maker/tools/policy.py`'s mount allowlist, which governs
*what a tool may see* once it is already authorized to run. A team
declaring a tool is not authorization (FR-051) — this module is the only
place that decision is made, and it is made from operator-owned data, never
from anything an agent or team specification supplies.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from team_maker.tools.catalog import TOOL_CATALOG, RiskClass, is_canonical


@dataclass(frozen=True)
class AuthorizationPolicy:
    """`enabled_tools` is the operator's explicit RISKY-tool allowlist.
    SAFE tools never need to appear in it (FR-050's third condition is
    trivially satisfied for them). Absence of a name is a denial, not a
    permission (FR-052) — there is deliberately no `disabled_tools` list,
    since that shape would make "forgot to disable" a silent grant."""

    enabled_tools: frozenset[str] = field(default_factory=frozenset)
    source: str = "(no operator policy configured)"


DENY_ALL_RISKY = AuthorizationPolicy()


def is_authorized(tool_name: str, assigned_tools: set[str], policy: AuthorizationPolicy) -> bool:
    """FR-050: all three conditions are necessary.
    1. assigned to the team  2. canonical  3. SAFE, or explicitly RISKY-enabled.
    """
    if tool_name not in assigned_tools:
        return False
    if not is_canonical(tool_name):
        return False
    definition = TOOL_CATALOG[tool_name]
    if definition.risk is RiskClass.SAFE:
        return True
    return tool_name in policy.enabled_tools


def check_authorization(
    tool_names: list[str], policy: AuthorizationPolicy
) -> list[str]:
    """Collect-don't-short-circuit (matches `runtime/preflight.py`'s existing
    convention): returns every RISKY tool that is not authorized, rather than
    stopping at the first."""
    assigned = set(tool_names)
    denied = []
    for name in tool_names:
        if is_canonical(name) and TOOL_CATALOG[name].risk is RiskClass.RISKY:
            if not is_authorized(name, assigned, policy):
                denied.append(name)
    return denied
