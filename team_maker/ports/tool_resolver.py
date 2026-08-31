"""Port: resolves a declared tool name to a usable instance (spec FR-019 to
FR-025; audit RC-5, P0-1; contracts/tool-resolver-port.md).

`GeneratedTeam` carries no package path and `ExecutionEngine.run` carries
none either, so `_build_agent` has no route to a package's `tools.py`. This
port is that missing boundary: the one named, testable seam where a
declaration becomes an instance, and — per its adapter,
`adapters/tools/package_tool_resolver.py` — the only place a generated
package's tool module is ever loaded.

Engine-agnostic by construction: no crewai import, enforced by the same
guard as `ports/execution_engine.py`
(`tests/unit/adapters/test_runtime_engine_port.py`).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any


class UnknownToolError(Exception):
    """A requested name is not in `TOOL_CATALOG` (spec FR-019).

    Should not occur for a name that passed Step 1's compose/build gate;
    exists for a hand-edited or pre-remediation package (FR-080, FR-084)."""


class UnresolvableToolError(Exception):
    """A canonical name has no implementation this resolver can produce
    right now (spec FR-019) — e.g. no binding in this package's registry, or
    an aggregate raised by `resolve_all` for one or more failed names."""


class ToolPolicyError(Exception):
    """Resolving this tool would violate execution policy (spec FR-019,
    FR-050 to FR-055) — e.g. a RISKY tool without operator authorization."""


@dataclass(frozen=True)
class ResolvedTool:
    """A usable tool instance plus its canonical name (data-model.md §3).

    Holds no credential value (spec FR-022, FR-029): any credential a tool
    needs is resolved into `instance` itself by the adapter, never carried
    alongside it where a caller could log or serialize it."""

    name: str
    instance: Any


class ToolResolver(ABC):
    """Resolves declared tool names to usable instances — the only seam
    where a declaration becomes one (audit §2.1, P0-1)."""

    @abstractmethod
    def resolve(self, name: str) -> ResolvedTool:
        """Resolve one canonical tool name.

        Precondition: `name` is canonical (validated upstream at Step 1).

        Raises:
            UnknownToolError: name is not in TOOL_CATALOG.
            UnresolvableToolError: canonical, but no implementation available here.
            ToolPolicyError: resolution would violate execution policy.

        Never returns a partially-usable tool. Never returns None.
        """

    def resolve_all(self, names: Sequence[str]) -> list[ResolvedTool]:
        """Resolve every name or raise, collecting every failure first
        (spec FR-023) — matches `runtime.preflight.check_credentials`'s
        collect-don't-short-circuit convention. Fails closed: any failure
        refuses the whole batch, never a partially-resolved list."""
        resolved: list[ResolvedTool] = []
        failures: list[str] = []
        for name in names:
            try:
                resolved.append(self.resolve(name))
            except (UnknownToolError, UnresolvableToolError, ToolPolicyError) as exc:
                failures.append(f"{name} ({type(exc).__name__}): {exc}")
        if failures:
            raise UnresolvableToolError(
                "cannot resolve declared tool(s): " + "; ".join(failures)
            )
        return resolved
