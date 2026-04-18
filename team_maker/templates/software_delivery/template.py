"""Software Delivery Team template.

Generates a startup-friendly engineering team covering architecture, backend,
frontend, QA/review, DevOps, and an optional coordinator.  User-supplied
RoleDefinitions take precedence; this template fills in sensible defaults for
any fields left blank.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from team_maker.domain.models import AgentSpec, GeneratedTeam, ProviderRouting, TaskSpec
from team_maker.schema.request import ProviderConfig, RoleDefinition, TeamCreationRequest
from team_maker.templates.base import BaseTeamTemplate
from team_maker.templates.registry import register

# ---------------------------------------------------------------------------
# Defaults for each well-known role
# ---------------------------------------------------------------------------

_ROLE_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "architect": {
        "display_name": "Software Architect",
        "description": "Designs system architecture and makes high-level technical decisions.",
        "goal": (
            "Produce a clear, scalable architecture that the rest of the team can implement "
            "without ambiguity."
        ),
        "backstory": (
            "A seasoned architect with 15+ years designing distributed systems. "
            "Balances pragmatism with long-term maintainability and always documents decisions."
        ),
        "capabilities": [
            "system_design",
            "architecture_review",
            "api_design",
            "database_design",
            "technical_leadership",
        ],
        "tools": ["code_reader", "diagram_generator"],
    },
    "backend_engineer": {
        "display_name": "Backend Engineer",
        "description": "Implements server-side logic, APIs, and data persistence.",
        "goal": "Build robust, performant backend services that are well-tested and maintainable.",
        "backstory": (
            "A pragmatic engineer specialising in Python and cloud-native services. "
            "Cares deeply about code quality, test coverage, and API contracts."
        ),
        "capabilities": [
            "api_development",
            "database_design",
            "performance_optimisation",
            "unit_testing",
            "code_review",
        ],
        "tools": ["code_writer", "test_runner", "linter"],
    },
    "frontend_engineer": {
        "display_name": "Frontend Engineer",
        "description": "Implements user interfaces and client-side logic.",
        "goal": "Build intuitive, accessible, and performant user-facing applications.",
        "backstory": (
            "A creative frontend developer with deep knowledge of modern JavaScript frameworks "
            "and a strong focus on accessibility and UX best practices."
        ),
        "capabilities": [
            "ui_development",
            "state_management",
            "accessibility",
            "performance_optimisation",
            "component_testing",
        ],
        "tools": ["code_writer", "browser_preview", "linter"],
    },
    "reviewer_qa": {
        "display_name": "Code Reviewer & QA Engineer",
        "description": "Reviews code quality, catches bugs, and maintains testing standards.",
        "goal": "Ensure every merged change is correct, well-tested, and secure.",
        "backstory": (
            "A meticulous engineer who treats code review as a collaborative teaching tool. "
            "Has a track record of finding subtle bugs before they reach production."
        ),
        "capabilities": [
            "code_review",
            "test_strategy",
            "bug_detection",
            "security_review",
            "documentation_review",
        ],
        "tools": ["code_reader", "test_runner", "static_analyser"],
    },
    "devops": {
        "display_name": "DevOps / Platform Engineer",
        "description": "Handles CI/CD, deployment, infrastructure, and operational guidance.",
        "goal": (
            "Deliver reliable, automated deployment pipelines and keep the system observable "
            "and easy to operate."
        ),
        "backstory": (
            "A platform engineer with expertise in cloud-native infrastructure, GitOps, "
            "and SRE practices. Automates everything that can be automated."
        ),
        "capabilities": [
            "ci_cd",
            "infrastructure_as_code",
            "monitoring",
            "deployment_automation",
            "security_hardening",
        ],
        "tools": ["cli_runner", "config_generator", "monitoring_dashboard"],
    },
    "coordinator": {
        "display_name": "Team Coordinator",
        "description": "Coordinates workflow, tracks progress, and ensures team alignment.",
        "goal": "Keep the team moving, unblock engineers, and surface risks early.",
        "backstory": (
            "An experienced technical project manager who bridges engineering, product, "
            "and stakeholders. Turns ambiguity into clear action items."
        ),
        "capabilities": [
            "project_planning",
            "risk_management",
            "stakeholder_communication",
            "blocker_resolution",
            "progress_reporting",
        ],
        "tools": ["task_tracker", "communication_channel"],
    },
}

# Default task catalogue
_DEFAULT_TASKS: List[Dict[str, Any]] = [
    {
        "name": "architecture_design",
        "description": (
            "Design the overall system architecture: components, data flows, API contracts, "
            "and key technical decisions."
        ),
        "expected_output": (
            "Architecture document with component diagram, API contracts, data model, "
            "and ADR (Architecture Decision Records)."
        ),
        "agent_role": "architect",
        "dependencies": [],
    },
    {
        "name": "backend_implementation",
        "description": "Implement backend services, REST/GraphQL APIs, and data persistence layer.",
        "expected_output": (
            "Working backend codebase with unit tests, integration tests, and OpenAPI spec."
        ),
        "agent_role": "backend_engineer",
        "dependencies": ["architecture_design"],
    },
    {
        "name": "frontend_implementation",
        "description": "Implement the user interface and integrate with backend APIs.",
        "expected_output": "Working frontend application with component tests and storybook.",
        "agent_role": "frontend_engineer",
        "dependencies": ["architecture_design"],
    },
    {
        "name": "code_review",
        "description": (
            "Review all changed code for correctness, security vulnerabilities, "
            "test coverage, and adherence to coding standards."
        ),
        "expected_output": "Review report with actionable feedback items and an approval/block decision.",
        "agent_role": "reviewer_qa",
        "dependencies": ["backend_implementation", "frontend_implementation"],
    },
    {
        "name": "testing",
        "description": (
            "Execute integration and end-to-end test suites; validate acceptance criteria "
            "and non-functional requirements."
        ),
        "expected_output": "Test results report with pass/fail summary and coverage metrics.",
        "agent_role": "reviewer_qa",
        "dependencies": ["code_review"],
    },
    {
        "name": "deployment_guidance",
        "description": (
            "Prepare deployment configuration, CI/CD pipeline definition, "
            "infrastructure-as-code, and operational runbook."
        ),
        "expected_output": (
            "Deployment artifacts: Dockerfile, CI config, Terraform/Pulumi snippets, "
            "monitoring setup, and runbook."
        ),
        "agent_role": "devops",
        "dependencies": ["testing"],
    },
]

_DEFAULT_PROVIDER = ProviderConfig(provider="anthropic", model="claude-sonnet-4-6")


@register("software_delivery_team")
class SoftwareDeliveryTemplate(BaseTeamTemplate):
    """Startup-friendly software delivery team template."""

    description = (
        "A full-cycle software engineering team: architect, backend, frontend, "
        "QA/reviewer, DevOps, and optional coordinator."
    )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def generate(self, request: TeamCreationRequest) -> GeneratedTeam:
        agents = self._build_agents(request)
        tasks = self._build_tasks(request, agents)
        return GeneratedTeam(
            team_name=request.team_name,
            purpose=request.purpose,
            template_used=self.template_id,
            agents=agents,
            tasks=tasks,
            stack=request.stack,
            constraints=request.constraints,
            tags=request.tags,
            documentation_level=request.documentation_level.value,
            metadata=request.metadata,
        )

    def default_role_names(self) -> List[str]:
        return list(_ROLE_DEFAULTS.keys())

    def default_task_names(self) -> List[str]:
        return [t["name"] for t in _DEFAULT_TASKS]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_routing(
        self,
        role_llm: Optional[ProviderConfig],
        default_llm: Optional[ProviderConfig],
    ) -> ProviderRouting:
        cfg = role_llm or default_llm or _DEFAULT_PROVIDER
        return ProviderRouting(
            provider=cfg.provider,
            model=cfg.model,
            api_key_env=cfg.api_key_env,
        )

    def _build_agent_from_role(
        self,
        role: RoleDefinition,
        default_llm: Optional[ProviderConfig],
    ) -> AgentSpec:
        defaults = _ROLE_DEFAULTS.get(role.name, {})
        return AgentSpec(
            role=role.name,
            display_name=role.display_name or defaults.get("display_name", role.resolved_display_name),
            description=role.description or defaults.get("description", ""),
            goal=role.goal or defaults.get("goal", f"Complete tasks assigned to the {role.name} role."),
            backstory=role.backstory or defaults.get("backstory", f"An experienced {role.name}."),
            capabilities=role.capabilities or defaults.get("capabilities", []),
            tools=role.tools or defaults.get("tools", []),
            routing=self._resolve_routing(role.llm, default_llm),
            is_optional=role.is_optional,
        )

    def _build_agents(self, request: TeamCreationRequest) -> List[AgentSpec]:
        return [
            self._build_agent_from_role(role, request.default_llm)
            for role in request.desired_roles
        ]

    def _build_tasks(
        self, request: TeamCreationRequest, agents: List[AgentSpec]
    ) -> List[TaskSpec]:
        agent_roles = {a.role for a in agents}
        tasks: List[TaskSpec] = []
        for task_def in _DEFAULT_TASKS:
            if task_def["agent_role"] in agent_roles:
                tasks.append(
                    TaskSpec(
                        name=task_def["name"],
                        description=task_def["description"],
                        expected_output=task_def["expected_output"],
                        agent_role=task_def["agent_role"],
                        dependencies=[
                            d for d in task_def["dependencies"] if self._task_dep_available(d, agent_roles)
                        ],
                    )
                )
        return tasks

    @staticmethod
    def _task_dep_available(dep_task_name: str, agent_roles: set[str]) -> bool:
        """Only include a dependency if its owning agent role is present."""
        task_to_role = {t["name"]: t["agent_role"] for t in _DEFAULT_TASKS}
        owning_role = task_to_role.get(dep_task_name)
        return owning_role is None or owning_role in agent_roles
