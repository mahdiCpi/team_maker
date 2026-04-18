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
