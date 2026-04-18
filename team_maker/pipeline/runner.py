"""Core generation pipeline.

Orchestrates: template selection → team generation → artifact building
→ writing → validation → report.

No business logic lives here — this is pure orchestration.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List

from team_maker.artifacts.writer import ArtifactManifest, ArtifactWriter
from team_maker.domain.models import GeneratedTeam
from team_maker.generators.agent import AgentGenerator
from team_maker.generators.docs import DocsGenerator
from team_maker.generators.report import ReportGenerator
from team_maker.generators.routing import RoutingGenerator
from team_maker.generators.task import TaskGenerator
from team_maker.schema.request import TeamCreationRequest
from team_maker.templates import registry as template_registry  # noqa: F401 – triggers registration
import team_maker.templates  # noqa: F401 – ensure all templates are registered
from team_maker.utils.fs import safe_output_path
from team_maker.utils.yaml_utils import dump_yaml
from team_maker.validation.validator import OutputValidator, ValidationResult


@dataclass
class PipelineResult:
    output_path: Path
    team: GeneratedTeam
    written_files: List[str]
    validation: ValidationResult


class PipelineRunner:
    """Runs the full team-generation pipeline for a single request."""

    def __init__(self) -> None:
        self._agent_gen = AgentGenerator()
        self._task_gen = TaskGenerator()
        self._docs_gen = DocsGenerator()
        self._routing_gen = RoutingGenerator()
        self._report_gen = ReportGenerator()
        self._writer = ArtifactWriter()
        self._validator = OutputValidator()

    def run(self, request: TeamCreationRequest) -> PipelineResult:
        # 1. Resolve output path
        output_path = safe_output_path(request.output_path)

        # 2. Select template and generate domain model
        from team_maker.templates.registry import get_template
        template = get_template(request.template.value)
        team = template.generate(request)

        # 3. Build artifact manifest (all file contents in memory)
        manifest = self._build_manifest(team, request)

        # 4. Write to disk (raises FileExistsError if dir non-empty and !overwrite)
        written = self._writer.write(output_path, manifest, overwrite=request.overwrite)

        # 5. Validate output (post-write)
        validation = self._validator.validate(output_path, team)

        # 6. Write generation report (includes validation result)
        report_content = self._report_gen.render(team, request, written, validation)
        report_path = output_path / "generation_report.md"
        report_path.write_text(report_content, encoding="utf-8")
        if "generation_report.md" not in written:
            written.append("generation_report.md")

        return PipelineResult(
            output_path=output_path,
            team=team,
            written_files=written,
            validation=validation,
        )

    # ------------------------------------------------------------------
    # Manifest construction
    # ------------------------------------------------------------------

    def _build_manifest(
        self, team: GeneratedTeam, request: TeamCreationRequest
    ) -> ArtifactManifest:
        manifest: ArtifactManifest = {}

        # Top-level README
        manifest["README.md"] = self._docs_gen.render_readme(team)

        # Team config
        manifest["team_config.yaml"] = self._render_team_config(team)

        # Agent configs
        for agent in team.agents:
            manifest[f"agents/{self._agent_gen.filename(agent)}"] = self._agent_gen.render(agent)

        # Task configs
        for task in team.tasks:
            manifest[f"tasks/{self._task_gen.filename(task)}"] = self._task_gen.render(task)

        # Docs
        manifest["docs/how_to_run.md"] = self._docs_gen.render_how_to_run(team)
        manifest["docs/how_to_extend.md"] = self._docs_gen.render_how_to_extend(team)
        manifest["docs/model_routing.md"] = self._docs_gen.render_model_routing(team)

        # Routing config
        manifest["routing_config.yaml"] = self._routing_gen.render(team)

        # Runner script
        manifest["run_example.py"] = self._render_run_example(team)

        # generation_report.md is written separately after validation (see run())
        return manifest

    @staticmethod
    def _render_team_config(team: GeneratedTeam) -> str:
        from datetime import datetime, timezone
        data = {
            "team_name": team.team_name,
            "purpose": team.purpose,
            "template": team.template_used,
            "stack": team.stack,
            "documentation_level": team.documentation_level,
            "agents": [a.role for a in team.agents],
            "tasks": [t.name for t in team.tasks],
            "constraints": team.constraints,
            "tags": team.tags,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        return dump_yaml(data)

    @staticmethod
    def _render_run_example(team: GeneratedTeam) -> str:
        agent_lines = "\n".join(
            f'    "{a.role}": {{'
            f'"role": "{a.role}", '
            f'"goal": "{a.goal[:60].rstrip()}...", '
            f'"backstory": "{a.backstory[:60].rstrip()}..."'
            f'}},'
            for a in team.agents
        )
        task_lines = "\n".join(
            f'    Task(description="{t.description[:80].rstrip()}...", '
            f'expected_output="{t.expected_output[:60].rstrip()}...", '
            f'agent=agents["{t.agent_role}"]),'
            for t in team.tasks
        )
        return f'''\
"""
run_example.py — Example runner for {team.team_name}

This script is a starting point.  Edit agent configs in agents/ and task
configs in tasks/ then re-run this script.

Requirements:
    pip install crewai pyyaml

Usage:
    python run_example.py
"""
from __future__ import annotations

import os
import yaml
from pathlib import Path
from crewai import Agent, Task, Crew, Process


TEAM_ROOT = Path(__file__).parent


def load_agent(role: str) -> Agent:
    cfg_path = TEAM_ROOT / "agents" / f"{{role}}.yaml"
    with cfg_path.open() as f:
        cfg = yaml.safe_load(f)

    # Resolve LLM from routing config (simple env-var-based approach)
    llm_cfg = cfg.get("llm", {{}})
    api_key_env = llm_cfg.get("api_key_env")
    if api_key_env and not os.environ.get(api_key_env):
        print(f"[warn] {{api_key_env}} is not set; agent {{role}} may fail at runtime.")

    return Agent(
        role=cfg["role"],
        goal=cfg["goal"],
        backstory=cfg["backstory"],
        verbose=True,
        allow_delegation=False,
    )


def load_task(name: str, agents: dict[str, Agent]) -> Task:
    cfg_path = TEAM_ROOT / "tasks" / f"{{name}}.yaml"
    with cfg_path.open() as f:
        cfg = yaml.safe_load(f)
    agent = agents[cfg["agent_role"]]
    return Task(
        description=cfg["description"],
        expected_output=cfg["expected_output"],
        agent=agent,
    )


def main() -> None:
    # Load agents
    agent_roles = {", ".join(f'"{a.role}"' for a in team.agents[:6])}
    agents = {{role: load_agent(role) for role in agent_roles}}

    # Load tasks in dependency order
    task_names = {", ".join(f'"{t.name}"' for t in team.tasks)}
    tasks = [load_task(name, agents) for name in task_names]

    # Assemble the crew
    crew = Crew(
        agents=list(agents.values()),
        tasks=tasks,
        process=Process.sequential,
        verbose=True,
    )

    # Kick off with your goal
    goal = (
        "Build a production-ready {team.team_name.lower()} following best practices."
    )
    result = crew.kickoff(inputs={{"goal": goal}})
    print("\\n--- RESULT ---")
    print(result)


if __name__ == "__main__":
    main()
'''
