"""Execution policy: the mount allowlist and dangerous-location floor (spec
FR-012 to FR-017, FR-079; audit RC-10; data-model.md §4).

This module is the build-time / preflight-time authority. The evaluation
order below (resolve -> allow-check -> deny-check -> apply mode) is the
security property (D-8): a symlinked allowlist entry cannot launder a
dangerous path because resolution happens before either check runs.

The SAME algorithm is rendered as self-contained Python into
`codegen/templates/tools.py.j2` (no team_maker import in a generated
package) so a standalone package enforces identically to the product's own
run path (FR-081). This module is that algorithm's single source; the
Jinja template's `_evaluate_mount` mirrors it exactly — see
`tests/security/test_mount_allowlist.py` for the parity check.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath


class MountRefused(Exception):
    """A mount request was refused. Callers must not degrade to running the
    tool without the mount (FR-017) — this is always a hard stop."""


@dataclass(frozen=True)
class MountAllowlistEntry:
    alias: str
    host_path: str
    writable: bool = False


@dataclass(frozen=True)
class MountAllowlist:
    entries: tuple[MountAllowlistEntry, ...] = field(default_factory=tuple)

    def find_alias(self, host_path: str) -> str | None:
        for entry in self.entries:
            if entry.alias == host_path or entry.host_path == host_path:
                return entry.alias
        return None


EMPTY_ALLOWLIST = MountAllowlist()


# Dangerous-location floor (FR-016, FR-079). Extendable, never reducible, and
# no allowlist entry can override a match against it.
#
# Patterns are plain strings compared against a *normalized* form of the
# resolved path (forward slashes, lowercased) rather than through
# `Path(pattern).resolve()`, deliberately: resolving a Unix-style pattern
# like "/etc" on a Windows build host reinterprets it as "C:\etc" — a
# different, harmless location — which would silently defeat the floor on
# any Windows-hosted build. String comparison has no such platform-specific
# reinterpretation.
_DANGEROUS_ROOT_MARKERS: tuple[str, ...] = ("/",)
_DANGEROUS_PREFIXES: tuple[str, ...] = (
    "/root", "/etc", "/boot", "/usr", "/var/run", "/dev", "/proc", "/sys",
    "c:/windows", "c:/users",
)


def _normalize(path_str: str) -> str:
    return path_str.replace("\\", "/").rstrip("/").lower()


def _home_prefix() -> str | None:
    home = os.path.expanduser("~")
    return _normalize(home) if home and home != "~" else None


def _resolve(raw_path: str) -> Path:
    """Fully resolve symlinks, `..` segments and normalization (D-8 step 1)."""
    return Path(raw_path).expanduser().resolve()


def is_dangerous(resolved: Path) -> bool:
    normalized = _normalize(str(resolved))
    if normalized in ("", "c:", "d:") or normalized in _DANGEROUS_ROOT_MARKERS:
        return True
    for prefix in _DANGEROUS_PREFIXES:
        if normalized == prefix or normalized.startswith(prefix + "/"):
            return True
    home_prefix = _home_prefix()
    if home_prefix and (normalized == home_prefix or normalized.startswith(home_prefix + "/")):
        return True
    return False


def evaluate_mount(requested_host_path: str, allowlist: MountAllowlist) -> MountAllowlistEntry:
    """The binding evaluation order (D-8): resolve -> allow-check -> deny-check
    -> caller applies mode. Raises `MountRefused` naming the violated rule on
    any failure; never returns a degraded/partial result (FR-017).

    Refusal messages name the mount by operator alias or, when no allowlist
    entry matched at all, by a sanitized identifier (FR-070) — never by the
    raw resolved host path (FR-071)."""
    from team_maker.tools.identifiers import sanitized_id

    resolved = _resolve(requested_host_path)

    matched: MountAllowlistEntry | None = None
    for entry in allowlist.entries:
        entry_resolved = _resolve(entry.host_path)
        if resolved == entry_resolved or _is_within(resolved, entry_resolved):
            matched = entry
            break
    if matched is None:
        raise MountRefused(
            f"mount '{sanitized_id(requested_host_path)}' is not in the operator-configured allowlist"
        )

    if is_dangerous(resolved):
        raise MountRefused(
            f"mount '{matched.alias}' resolves to a location on the dangerous-location floor "
            f"and is refused regardless of allowlist contents"
        )

    return matched


def _is_within(path: Path, ancestor: Path) -> bool:
    try:
        path.relative_to(ancestor)
        return True
    except ValueError:
        return False
