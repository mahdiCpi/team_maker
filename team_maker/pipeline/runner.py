"""Core generation pipeline.

Orchestrates: planner/template → team generation → artifact building
→ writing → validation → report.

Strategy selection:
  - desired_roles empty  → LLM planner infers everything
  - desired_roles present → SoftwareDeliveryTemplate fills in defaults

Framework selection (from AgentPlan or request.framework):
  - crewai    → CrewAIAdapter
  - langgraph → LangGraphAdapter
  - autogen   → AutoGenAdapter
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List

from team_maker.artifacts.writer import ArtifactManifest, ArtifactWriter
from team_maker.codegen import render_template
from team_maker.domain.models import GeneratedTeam
from team_maker.frameworks import get_adapter
from team_maker.generators.agent import AgentGenerator
from team_maker.generators.docs import DocsGenerator
from team_maker.generators.report import ReportGenerator
from team_maker.generators.routing import RoutingGenerator
from team_maker.generators.task import TaskGenerator
from team_maker.schema.request import SandboxConfig, StateBackend, TeamCreationRequest
import team_maker.templates  # noqa: F401 – triggers template registration
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

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run(self, request: TeamCreationRequest) -> PipelineResult:
        output_path = safe_output_path(request.output_path)

        # Phase 1: choose generation strategy
        if request.desired_roles:
            team = self._generate_from_template(request)
        else:
            team = self._generate_from_planner(request)

        # Phase 4: pick framework adapter. The request (YAML/CLI) is the source of
        # truth — the planner's framework choice is advisory and only used when the
        # request left the field at its schema default (crewai).
        default_framework = type(request).model_fields["framework"].default.value
        if request.framework.value != default_framework:
            effective_framework = request.framework.value
        else:
            effective_framework = team.primary_framework or default_framework
        team.primary_framework = effective_framework
        adapter = get_adapter(effective_framework)

        manifest = self._build_manifest(team, request, adapter)
        written = self._writer.write(output_path, manifest, overwrite=request.overwrite)
        validation = self._validator.validate(output_path, team)

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
    # Generation strategies
    # ------------------------------------------------------------------

    @staticmethod
    def _generate_from_template(request: TeamCreationRequest) -> GeneratedTeam:
        from team_maker.templates.registry import get_template
        template = get_template("software_delivery_team")
        team = template.generate(request)
        # Populate framework fields from request
        team.primary_framework = request.framework.value
        team.topology_pattern = (
            "hierarchical" if any(a.is_orchestrator for a in team.agents) else "sequential"
        )
        return team

    @staticmethod
    def _generate_from_planner(request: TeamCreationRequest) -> GeneratedTeam:
        from team_maker.llm.planner import TeamPlanner
        from team_maker.llm.mapper import map_plan_to_team
        planner = TeamPlanner.from_request(request)
        plan = planner.plan(request)
        return map_plan_to_team(plan, request)

    # ------------------------------------------------------------------
    # Manifest construction
    # ------------------------------------------------------------------

    def _build_manifest(
        self,
        team: GeneratedTeam,
        request: TeamCreationRequest,
        adapter,
    ) -> ArtifactManifest:
        manifest: ArtifactManifest = {}

        # Detect whether any agent is routed to Ollama. If so, we emit a
        # docker-compose stack with an `ollama` sidecar and point that agent's
        # base_url at the in-network service instead of the host.
        ollama_models = self._ollama_models_in_team(team)
        in_compose = bool(ollama_models)
        team.uses_ollama_sidecar = in_compose

        manifest["README.md"] = self._docs_gen.render_readme(team)
        manifest["team_config.yaml"] = self._render_team_config(team)

        for agent in team.agents:
            manifest[f"agents/{self._agent_gen.filename(agent)}"] = self._agent_gen.render(agent)

        for task in team.tasks:
            manifest[f"tasks/{self._task_gen.filename(task)}"] = self._task_gen.render(task)

        manifest["docs/how_to_run.md"] = self._docs_gen.render_how_to_run(team)
        manifest["docs/how_to_extend.md"] = self._docs_gen.render_how_to_extend(team)
        manifest["docs/model_routing.md"] = self._docs_gen.render_model_routing(team)

        # Routing config — single LLM source of truth. When we're emitting a
        # compose stack the Ollama entries get their base_url rewritten to the
        # service hostname.
        manifest["routing_config.yaml"] = self._routing_gen.render(team, in_compose=in_compose)

        # Phase 2: full tool bindings module (sandbox-aware + user-suggested tools)
        manifest["tools.py"] = self._render_tools_module(request.sandbox, request.suggested_tools)

        # Phase 3: state store module
        manifest["state_store.py"] = self._render_state_store(request.state_backend)

        # Phase 4: framework-specific runner
        manifest["run_example.py"] = adapter.render_runner(team)

        # Runtime requirements (framework + state backend aware)
        manifest["requirements.txt"] = self._render_requirements(
            team.primary_framework, request.state_backend
        )

        # Ollama sidecar: docker-compose.yml + Dockerfile + .dockerignore
        if in_compose:
            manifest["docker-compose.yml"] = self._render_compose(team, ollama_models)
            manifest["Dockerfile"] = render_template("Dockerfile.j2")
            manifest[".dockerignore"] = render_template(".dockerignore.j2")

        return manifest

    # ------------------------------------------------------------------
    # Ollama sidecar helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _ollama_models_in_team(team: GeneratedTeam) -> list[str]:
        """Return the unique list of Ollama model tags this team needs, in
        request order. Empty if no agent is routed to Ollama.
        """
        seen: list[str] = []
        for agent in team.agents:
            if agent.routing.provider == "ollama" and agent.routing.model not in seen:
                seen.append(agent.routing.model)
        return seen

    @staticmethod
    def _render_compose(team: GeneratedTeam, ollama_models: list[str]) -> str:
        # Cloud provider env vars that should be passed through to the runner
        # container (only if the team actually uses them).
        cloud_env_vars: list[str] = []
        for agent in team.agents:
            env = agent.routing.api_key_env
            if agent.routing.provider != "ollama" and env and env not in cloud_env_vars:
                cloud_env_vars.append(env)
        if "OPENAI_API_KEY" in cloud_env_vars:
            cloud_env_vars.remove("OPENAI_API_KEY")

        # Docker compose project prefix — lowercase, alnum + underscore.
        project = "".join(
            ch if ch.isalnum() else "_" for ch in team.team_name.lower()
        ).strip("_") or "team"

        return render_template(
            "docker-compose.yml.j2",
            compose_project=project,
            ollama_models=ollama_models,
            cloud_env_vars=cloud_env_vars,
        )

    # ------------------------------------------------------------------
    # Static renderers
    # ------------------------------------------------------------------

    @staticmethod
    def _render_team_config(team: GeneratedTeam) -> str:
        from datetime import datetime, timezone
        data = {
            "team_name": team.team_name,
            "purpose": team.purpose,
            "template": team.template_used,
            "stack": team.stack,
            "documentation_level": team.documentation_level,
            "primary_framework": team.primary_framework,
            "topology_pattern": team.topology_pattern,
            "agents": [a.role for a in team.agents],
            "tasks": [t.name for t in team.tasks],
            "constraints": team.constraints,
            "tags": team.tags,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        if team.planner_reasoning:
            data["planner_reasoning"] = team.planner_reasoning
        return dump_yaml(data)

    @staticmethod
    def _render_tools_module(sandbox: SandboxConfig, suggested_tools: list) -> str:
        return render_template("tools.py.j2", sandbox=sandbox, suggested_tools=suggested_tools)

    @staticmethod
    def _render_state_store(state_backend: StateBackend) -> str:
        use_vector = state_backend in (StateBackend.VECTOR, StateBackend.BOTH)
        use_file = state_backend in (StateBackend.FILE, StateBackend.BOTH)
        return render_template(
            "state_store.py.j2",
            use_vector=use_vector,
            use_file=use_file,
        )

    @staticmethod
    def _render_requirements(framework: str, state_backend: StateBackend) -> str:
        base = [
            "pyyaml>=6.0",
            "PyGithub>=2.1",
        ]
        framework_deps = {
            "crewai": [
                "crewai>=0.80.0",
                "crewai-tools>=0.25.0",
                "langchain-anthropic>=0.3.0",
                "langchain-openai>=0.3.0",
                "langchain-ollama>=0.2.0",
            ],
            "langgraph": [
                "langgraph>=0.2.0",
                "langchain-core>=0.3.0",
                "langchain-anthropic>=0.3.0",
                "langchain-openai>=0.3.0",
                "langchain-ollama>=0.2.0",
            ],
            "autogen": [
                "pyautogen>=0.2.0",
            ],
        }
        deps = base + framework_deps.get(framework, framework_deps["crewai"])
        if state_backend in (StateBackend.VECTOR, StateBackend.BOTH):
            deps.append("chromadb>=0.5")

        lines = ["# Runtime dependencies — install with: pip install -r requirements.txt"]
        lines += sorted(deps)
        return "\n".join(lines) + "\n"
