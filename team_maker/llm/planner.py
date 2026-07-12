"""LLM-driven team planner — replaces the hardcoded template system."""
from __future__ import annotations

from team_maker.adapters.providers import create_provider
from team_maker.llm.prompts import build_system_prompt, build_user_message
from team_maker.llm.schemas import AgentPlan
from team_maker.ports.llm_provider import LLMProvider
from team_maker.schema.request import TeamCreationRequest


class TeamPlanner:
    """
    Calls the configured LLM to infer a complete AgentPlan from a TeamCreationRequest.

    Usage:
        planner = TeamPlanner.from_request(request)
        plan = planner.plan(request)
    """

    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    @classmethod
    def from_request(cls, request: TeamCreationRequest) -> "TeamPlanner":
        """Convenience constructor — reads provider config from the request itself."""
        provider = create_provider(request.planning_llm)
        return cls(provider)

    def plan(self, request: TeamCreationRequest) -> AgentPlan:
        """
        Run the planning LLM and return a validated AgentPlan.

        Raises:
            EnvironmentError: if the required API key env var is missing.
            ValueError: if the LLM returns output that cannot be parsed as AgentPlan.
            ImportError: if the provider's SDK is not installed.
        """
        user_message = build_user_message(request)

        # Merge suggested tools with the built-in catalog for the planner
        extra_tools = {t.name: t.description for t in request.suggested_tools} if request.suggested_tools else None
        system = build_system_prompt(extra_tools=extra_tools)

        plan = self._provider.complete_structured(
            system=system,
            user=user_message,
            response_model=AgentPlan,
        )

        # Always stamp the team name from the request to ensure consistency
        plan.team_name = request.team_name

        # If desired_tasks were explicitly provided, use them directly instead of
        # the planner's generated tasks — the planner consistently collapses many
        # tasks into few, ignoring the desired_tasks hint in the prompt.
        if request.desired_tasks:
            from team_maker.llm.schemas import TaskDesign
            plan.tasks = [
                TaskDesign(
                    name=t.name,
                    description=t.description,
                    expected_output=f"All deliverables for '{t.name}' completed and documented.",
                    assigned_to=t.agent_role,
                    depends_on=t.dependencies,
                )
                for t in request.desired_tasks
            ]

        return plan
