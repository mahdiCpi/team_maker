"""Shared mixin for role-based team templates.

This module contains reusable helper methods that are generic to any
role/task-catalog template. These methods are extracted from
SoftwareDeliveryTemplate to avoid code duplication across templates.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from team_maker.domain.models import AgentSpec, ProviderRouting, TaskSpec
from team_maker.schema.request import ProviderConfig, RoleDefinition, TeamCreationRequest

# Default provider configuration for templates
_DEFAULT_PROVIDER = ProviderConfig(provider="anthropic", model="claude-sonnet-4-6")


class RoleBasedTemplateMixin:
    """Mixin class providing shared role/task-building logic for team templates.
    
    This mixin contains methods that are generic to any role/task-catalog template,
    not specific to any particular domain (software delivery, education, research, etc.).
    
    Templates using this mixin should:
    1. Define their own _ROLE_DEFAULTS dict with role-specific configurations
    2. Define their own _DEFAULT_TASKS list with task definitions
    3. Subclass both this mixin and BaseTeamTemplate
    4. Implement the three abstract methods from BaseTeamTemplate:
       - generate()
       - default_role_names()
       - default_task_names()
    """

    # Subclasses should override this with their domain-specific defaults
    _ROLE_DEFAULTS: Dict[str, Dict[str, Any]] = {}
    _DEFAULT_TASKS: List[Dict[str, Any]] = []

    def _resolve_routing(
        self,
        role_llm: Optional[ProviderConfig],
        default_llm: Optional[ProviderConfig],
    ) -> ProviderRouting:
        """Resolve the provider routing for an agent.
        
        Priority: role_llm > default_llm > _DEFAULT_PROVIDER
        """
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
        """Build an AgentSpec from a RoleDefinition, filling in defaults from _ROLE_DEFAULTS."""
        defaults = self._ROLE_DEFAULTS.get(role.name, {})
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
            is_orchestrator=defaults.get("is_orchestrator", False),
        )

    def _build_agents(self, request: TeamCreationRequest) -> List[AgentSpec]:
        """Build a list of AgentSpec from the request's desired_roles."""
        return [
            self._build_agent_from_role(role, request.default_llm)
            for role in request.desired_roles
        ]

    def _build_tasks(
        self, request: TeamCreationRequest, agents: List[AgentSpec]
    ) -> List[TaskSpec]:
        """Build a list of TaskSpec from the template's _DEFAULT_TASKS and request.
        
        If desired_tasks are provided in the request, use those instead of the defaults.
        """
        agent_roles = {a.role for a in agents}

        # Use desired_tasks from the request when explicitly provided
        if request.desired_tasks:
            tasks = []
            for t in request.desired_tasks:
                if t.agent_role in agent_roles:
                    tasks.append(
                        TaskSpec(
                            name=t.name,
                            description=t.description,
                            expected_output=f"All deliverables for '{t.name}' completed and documented.",
                            agent_role=t.agent_role,
                            dependencies=[d for d in t.dependencies if any(
                                dt.name == d for dt in request.desired_tasks
                            )],
                        )
                    )
            if tasks:
                return tasks

        tasks: List[TaskSpec] = []
        for task_def in self._DEFAULT_TASKS:
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

    def _task_dep_available(self, dep_task_name: str, agent_roles: set[str]) -> bool:
        """Check if a dependency task's owning agent role is present in the team.
        
        Only include a dependency if its owning agent role is present.
        """
        task_to_role = {t["name"]: t["agent_role"] for t in self._DEFAULT_TASKS}
        owning_role = task_to_role.get(dep_task_name)
        return owning_role is None or owning_role in agent_roles
