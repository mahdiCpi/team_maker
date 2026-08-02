"""Shared in-memory `GeneratedTeam` builders for runtime/adapter/conformance tests.

Extracted in Story 1.6: the adapter and preflight test modules were building the
same AgentSpec / TaskSpec / GeneratedTeam shapes by hand. These are plain factory
functions, not pytest fixtures, because callers need to vary provider and
topology per case. (The conformance test deliberately does not use them — it
builds a real package on disk via `PipelineRunner` instead.)
"""
from __future__ import annotations

from typing import Optional

from team_maker.domain.models import AgentSpec, GeneratedTeam, ProviderRouting, TaskSpec


def agent_spec(
    role: str,
    *,
    provider: str = "anthropic",
    model: str = "claude-sonnet-4-6",
    api_key_env: Optional[str] = "ANTHROPIC_API_KEY",
    base_url: Optional[str] = None,
    is_orchestrator: bool = False,
) -> AgentSpec:
    return AgentSpec(
        role=role,
        display_name=role.title(),
        description=f"{role} description",
        goal=f"{role} goal",
        backstory=f"{role} backstory",
        capabilities=[],
        tools=[],
        routing=ProviderRouting(
            provider=provider, model=model, api_key_env=api_key_env, base_url=base_url
        ),
        is_orchestrator=is_orchestrator,
    )


def task_spec(
    name: str, agent_role: str, dependencies: Optional[list[str]] = None
) -> TaskSpec:
    return TaskSpec(
        name=name,
        description=f"do {name}",
        expected_output="an output",
        agent_role=agent_role,
        dependencies=dependencies or [],
    )


def generated_team(agents: list[AgentSpec], tasks: list[TaskSpec]) -> GeneratedTeam:
    return GeneratedTeam(
        team_name="Test Team",
        purpose="testing",
        template_used="software_delivery_team",
        agents=agents,
        tasks=tasks,
    )
