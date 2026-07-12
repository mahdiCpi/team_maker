"""Maps an LLM-produced AgentPlan into the domain's GeneratedTeam."""
from __future__ import annotations

from team_maker.domain.models import AgentSpec, GeneratedTeam, ProviderRouting, TaskSpec
from team_maker.llm.schemas import AgentPlan
from team_maker.schema.request import ProviderConfig, TeamCreationRequest

_DEFAULT_ROUTING = ProviderRouting(
    provider="anthropic",
    model="claude-sonnet-4-6",
    api_key_env="ANTHROPIC_API_KEY",
)


def _infer_provider(model: str) -> str:
    m = model.lower()
    if m.startswith(("gpt-", "o1-", "o3-", "o4-")):
        return "openai"
    if m.startswith(("grok-",)):
        return "xai"
    if m.startswith("claude-"):
        return "anthropic"
    return "ollama"


def _resolve_routing(
    llm_override: str | None,
    default_llm: ProviderConfig | None,
) -> ProviderRouting:
    if llm_override:
        provider = _infer_provider(llm_override)
        api_key_env = (
            "OPENAI_API_KEY" if provider == "openai"
            else "XAI_API_KEY" if provider == "xai"
            else "ANTHROPIC_API_KEY" if provider == "anthropic"
            else None
        )
        return ProviderRouting(provider=provider, model=llm_override, api_key_env=api_key_env)
    if default_llm:
        return ProviderRouting(
            provider=default_llm.provider,
            model=default_llm.model,
            api_key_env=default_llm.api_key_env,
        )
    return _DEFAULT_ROUTING


def map_plan_to_team(plan: AgentPlan, request: TeamCreationRequest) -> GeneratedTeam:
    """Convert a structured AgentPlan from the LLM planner into a GeneratedTeam."""
    agents = [
        AgentSpec(
            role=a.role,
            display_name=a.display_name,
            description=a.goal,
            goal=a.goal,
            backstory=a.backstory,
            capabilities=[],
            tools=[t.name for t in a.tools],
            routing=_resolve_routing(a.llm_override, request.default_llm),
            is_optional=False,
            is_orchestrator=a.is_orchestrator,
        )
        for a in plan.agents
    ]

    tasks = [
        TaskSpec(
            name=t.name,
            description=t.description,
            expected_output=t.expected_output,
            agent_role=t.assigned_to,
            dependencies=t.depends_on,
        )
        for t in plan.tasks
    ]

    # Infer topology_pattern from communication + agents
    topology_pattern = plan.communication.pattern
    if topology_pattern == "sequential" and any(a.is_orchestrator for a in agents):
        topology_pattern = "hierarchical"

    return GeneratedTeam(
        team_name=plan.team_name,
        purpose=request.purpose,
        template_used="llm_planner",
        agents=agents,
        tasks=tasks,
        stack=request.stack,
        constraints=request.constraints,
        tags=request.tags,
        documentation_level=request.documentation_level.value,
        primary_framework=plan.primary_framework,
        topology_pattern=topology_pattern,
        topology_edges=plan.communication.edges,
        planner_reasoning=plan.reasoning,
        metadata=request.metadata,
    )
