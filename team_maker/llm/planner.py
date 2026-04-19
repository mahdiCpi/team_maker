"""LLM-driven team planner — replaces the hardcoded template system."""
from __future__ import annotations

from team_maker.llm.prompts import SYSTEM_PROMPT, build_user_message
from team_maker.llm.providers import LLMProvider, create_provider
from team_maker.llm.schemas import AgentPlan
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

        plan = self._provider.complete_structured(
            system=SYSTEM_PROMPT,
            user=user_message,
            response_model=AgentPlan,
        )

        # Always stamp the team name from the request to ensure consistency
        plan.team_name = request.team_name

        return plan
