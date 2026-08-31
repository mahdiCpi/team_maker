"""Advisory, read-only legacy tool-declaration scan (spec FR-039 to FR-042; D-9).

Reads `agents/*.yaml` across a directory of existing generated packages and
reports which ones declare a non-canonical tool name. Opens no file for
writing — this is deliberate, not a missing feature (FR-040): remediating an
existing package is a user action this report only informs, never performs.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from team_maker.tools.catalog import is_canonical, resolve_alias
from team_maker.utils.yaml_utils import load_yaml


@dataclass(frozen=True)
class MigrationFinding:
    """One non-canonical tool declaration in one existing package
    (data-model.md §8)."""

    package: str
    agent_role: str
    declared_name: str
    suggested_replacement: str | None
    requires_human_decision: bool


def scan_package(package_path: Path) -> list[MigrationFinding]:
    """Findings for one package. Empty list means every declared tool
    resolves safely — the package is unaffected and MUST NOT appear in the
    aggregate report (FR-038, FR-039)."""
    agents_dir = package_path / "agents"
    if not agents_dir.is_dir():
        return []

    findings: list[MigrationFinding] = []
    for agent_file in sorted(agents_dir.glob("*.yaml")):
        try:
            cfg = load_yaml(agent_file)
        except Exception:
            continue  # a malformed package's YAML integrity is validator.py's concern, not this scan's
        if not isinstance(cfg, dict):
            continue
        role = cfg.get("role", agent_file.stem)
        for tool_name in cfg.get("tools", []) or []:
            if is_canonical(tool_name):
                continue
            canonical = resolve_alias(tool_name)
            findings.append(
                MigrationFinding(
                    package=package_path.name,
                    agent_role=role,
                    declared_name=tool_name,
                    suggested_replacement=canonical,
                    requires_human_decision=canonical is None,
                )
            )
    return findings


def scan_directory(root: Path) -> list[MigrationFinding]:
    """Scan every immediate subdirectory of `root` as a candidate package.
    Reproducible and side-effect-free (FR-042): running this twice against an
    unchanged tree produces identical output."""
    findings: list[MigrationFinding] = []
    if not root.is_dir():
        return findings
    for entry in sorted(root.iterdir()):
        if entry.is_dir():
            findings.extend(scan_package(entry))
    return findings


def format_report(findings: list[MigrationFinding]) -> str:
    if not findings:
        return "No affected packages found — every declared tool resolves to a canonical name."
    by_package: dict[str, list[MigrationFinding]] = {}
    for f in findings:
        by_package.setdefault(f.package, []).append(f)
    lines = [f"{len(by_package)} affected package(s):\n"]
    for package, package_findings in sorted(by_package.items()):
        lines.append(f"- {package}:")
        for f in package_findings:
            if f.suggested_replacement:
                lines.append(
                    f"    '{f.declared_name}' (agent: {f.agent_role}) -> suggest '{f.suggested_replacement}'"
                )
            else:
                lines.append(
                    f"    '{f.declared_name}' (agent: {f.agent_role}) -> requires human decision (no unambiguous match)"
                )
    return "\n".join(lines)
