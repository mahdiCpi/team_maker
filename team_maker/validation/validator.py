"""Post-generation validation: checks that required artifacts exist and are valid."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List

import yaml

from team_maker.domain.models import GeneratedTeam

# Paths that MUST be present for a valid team package (relative to output root)
_REQUIRED_FILES = [
    "README.md",
    "team_config.yaml",
    "run_example.py",
    "docs/how_to_run.md",
    "docs/how_to_extend.md",
    "docs/model_routing.md",
]

# generation_report.md is written after validation completes; not checked here.


@dataclass
class ValidationResult:
    passed: bool
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def add_issue(self, msg: str) -> None:
        self.issues.append(msg)
        self.passed = False

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)


class OutputValidator:
    """Validates a generated team package directory."""

    def validate(self, output_path: Path, team: GeneratedTeam) -> ValidationResult:
        result = ValidationResult(passed=True)

        self._check_required_files(output_path, result)
        self._check_agent_files(output_path, team, result)
        self._check_task_files(output_path, team, result)
        self._check_yaml_integrity(output_path, result)
        self._check_tool_declarations(output_path, team, result)

        return result

    # ------------------------------------------------------------------

    def _check_required_files(self, root: Path, result: ValidationResult) -> None:
        for rel in _REQUIRED_FILES:
            if not (root / rel).exists():
                result.add_issue(f"Missing required file: {rel}")

    def _check_agent_files(
        self, root: Path, team: GeneratedTeam, result: ValidationResult
    ) -> None:
        for agent in team.agents:
            path = root / "agents" / f"{agent.role}.yaml"
            if not path.exists():
                result.add_issue(f"Missing agent config: agents/{agent.role}.yaml")

    def _check_task_files(
        self, root: Path, team: GeneratedTeam, result: ValidationResult
    ) -> None:
        if not team.tasks:
            result.add_warning("No tasks were generated for this team.")
            return
        tasks_dir = root / "tasks"
        if not tasks_dir.exists():
            result.add_issue("Missing tasks/ directory")
            return
        for task in team.tasks:
            path = tasks_dir / f"{task.name}.yaml"
            if not path.exists():
                result.add_issue(f"Missing task config: tasks/{task.name}.yaml")

    def _check_yaml_integrity(self, root: Path, result: ValidationResult) -> None:
        """Attempt to parse every .yaml file; flag malformed ones."""
        for yaml_file in sorted(root.rglob("*.yaml")):
            try:
                with yaml_file.open("r", encoding="utf-8") as fh:
                    yaml.safe_load(fh)
            except yaml.YAMLError as exc:
                rel = yaml_file.relative_to(root).as_posix()
                result.add_issue(f"Malformed YAML in {rel}: {exc}")

    def _check_tool_declarations(
        self, root: Path, team: GeneratedTeam, result: ValidationResult
    ) -> None:
        """FR-030, FR-037, FR-038: a package declaring a tool that is
        unknown, invalid, unresolvable, unauthorized or unsafe MUST NOT
        report validation passed. Scoped to the offending declarations only
        (FR-038, SC-011) — four safe tools plus one invented one names only
        the invented one; an all-canonical package is unaffected.

        Runs after `_writer.write` (spec: called from `PipelineRunner.run`
        once every file exists on disk), so the built `tools.py` registry
        is available to check resolvability against, not merely catalog
        membership."""
        from team_maker.adapters.tools.package_tool_resolver import (
            PackageToolResolver,
            PreRemediationPackageError,
        )
        from team_maker.ports.tool_resolver import (
            ToolPolicyError,
            UnknownToolError,
            UnresolvableToolError,
        )
        from team_maker.tools.authorization import check_authorization
        from team_maker.tools.config import load_tool_policy
        from team_maker.tools.validation import validate_declarations

        declarations = [(name, agent.role) for agent in team.agents for name in agent.tools]
        if not declarations:
            return

        outcome = validate_declarations(declarations, stage="validate")
        for rejection in outcome.rejections:
            result.add_issue(str(rejection))
        unknown_names = {rejection.tool_name for rejection in outcome.rejections}

        policy = load_tool_policy()
        resolver = PackageToolResolver(root)
        for agent in team.agents:
            canonical_tools = [t for t in agent.tools if t not in unknown_names]
            if not canonical_tools:
                continue
            denied = set(check_authorization(canonical_tools, policy.authorization))
            for name in denied:
                result.add_issue(
                    f"[validate] tool '{name}' declared by agent '{agent.role}' rejected "
                    f"(unauthorized): RISKY and not authorized by operator policy"
                )
            resolvable_tools = [t for t in canonical_tools if t not in denied]
            if not resolvable_tools:
                continue
            try:
                resolver.resolve_all(resolvable_tools)
            except PreRemediationPackageError as exc:
                result.add_issue(f"[validate] agent '{agent.role}': {exc}")
            except (UnresolvableToolError, UnknownToolError, ToolPolicyError) as exc:
                result.add_issue(
                    f"[validate] agent '{agent.role}' declares an unresolvable tool: {exc}"
                )
