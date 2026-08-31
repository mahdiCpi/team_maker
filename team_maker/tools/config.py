"""The single operator-owned tool-policy source (spec FR-085; closes CHK001,
CHK005).

Mirrors `team_maker/keyconfig.py`'s established precedence: an explicit path
wins, then `$TEAM_MAKER_TOOL_POLICY`, then a default project-root file. The
file is deliberately separate from `team_maker.keys` (credentials) and from
`TeamCreationRequest`/`SandboxConfig` (user-authored per-request config) —
authorization and the mount allowlist are an operator decision, not
something the requesting user or the team specification controls (FR-051).

Never raises. An absent, empty or malformed file is not a permissive
default: it resolves to `AuthorizationPolicy()` (deny every RISKY tool),
an empty `MountAllowlist()` (no mounts), `network_allowed=False`, and the
unmodified `DEFAULT_CONTROLS` — the same posture as a policy that explicitly
denies everything (FR-054). A diagnostic naming the unreadable source is
attached, never the file's contents.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from team_maker.tools.authorization import AuthorizationPolicy
from team_maker.tools.limits import DEFAULT_CONTROLS, SandboxControls
from team_maker.tools.policy import EMPTY_ALLOWLIST, MountAllowlist, MountAllowlistEntry
from team_maker.utils.yaml_utils import load_yaml

TOOL_POLICY_ENV = "TEAM_MAKER_TOOL_POLICY"
DEFAULT_FILENAME = "team_maker.tools.yaml"


@dataclass(frozen=True)
class ToolPolicyConfig:
    authorization: AuthorizationPolicy
    mount_allowlist: MountAllowlist
    network_allowed: bool
    controls: SandboxControls
    source: str
    diagnostic: str | None = None


def default_path() -> Path:
    """`$TEAM_MAKER_TOOL_POLICY` or `./team_maker.tools.yaml` (FR-085)."""
    override = os.environ.get(TOOL_POLICY_ENV)
    return Path(override) if override else Path.cwd() / DEFAULT_FILENAME


def _deny_all(source: str, diagnostic: str | None = None) -> ToolPolicyConfig:
    return ToolPolicyConfig(
        authorization=AuthorizationPolicy(source=source),
        mount_allowlist=EMPTY_ALLOWLIST,
        network_allowed=False,
        controls=DEFAULT_CONTROLS,
        source=source,
        diagnostic=diagnostic,
    )


def load_tool_policy(path: Path | str | None = None) -> ToolPolicyConfig:
    target = Path(path) if path is not None else default_path()

    if not target.exists() or not target.is_file():
        return _deny_all(str(target), diagnostic=f"tool policy file not found at {target}")

    try:
        raw = load_yaml(target)
    except Exception as exc:
        return _deny_all(
            str(target),
            diagnostic=f"tool policy file at {target} could not be parsed: {exc.__class__.__name__}",
        )

    if not isinstance(raw, dict):
        return _deny_all(str(target), diagnostic=f"tool policy file at {target} is not a mapping")

    enabled_tools = frozenset(raw.get("enabled_tools", []) or [])
    authorization = AuthorizationPolicy(enabled_tools=enabled_tools, source=str(target))

    allowlist_entries = tuple(
        MountAllowlistEntry(
            alias=entry.get("alias", ""),
            host_path=entry.get("host_path", ""),
            writable=bool(entry.get("writable", False)),
        )
        for entry in (raw.get("mount_allowlist", []) or [])
        if isinstance(entry, dict) and entry.get("alias") and entry.get("host_path")
    )

    network_allowed = bool(raw.get("network_allowed", False))

    overrides = raw.get("controls", {}) or {}
    controls = DEFAULT_CONTROLS
    if isinstance(overrides, dict) and overrides:
        controls = SandboxControls(
            timeout_process_seconds=int(overrides.get("timeout_process_seconds", DEFAULT_CONTROLS.timeout_process_seconds)),
            timeout_container_seconds=int(overrides.get("timeout_container_seconds", DEFAULT_CONTROLS.timeout_container_seconds)),
            timeout_http_seconds=int(overrides.get("timeout_http_seconds", DEFAULT_CONTROLS.timeout_http_seconds)),
            max_output_bytes=int(overrides.get("max_output_bytes", DEFAULT_CONTROLS.max_output_bytes)),
            cpu_limit=str(overrides.get("cpu_limit", DEFAULT_CONTROLS.cpu_limit)),
            memory_limit=str(overrides.get("memory_limit", DEFAULT_CONTROLS.memory_limit)),
            max_processes=int(overrides.get("max_processes", DEFAULT_CONTROLS.max_processes)),
            storage_limit=str(overrides.get("storage_limit", DEFAULT_CONTROLS.storage_limit)),
        )

    return ToolPolicyConfig(
        authorization=authorization,
        mount_allowlist=MountAllowlist(allowlist_entries),
        network_allowed=network_allowed,
        controls=controls,
        source=str(target),
    )
