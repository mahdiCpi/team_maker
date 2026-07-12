"""Structured output schemas returned by the LLM planner."""
from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class ToolAssignment(BaseModel):
    name: str = Field(..., description="Tool name from the registry (e.g. git_account, shell)")
    reason: str = Field(..., description="Why this agent needs this specific tool")


class AgentDesign(BaseModel):
    role: str = Field(..., description="snake_case unique identifier for this agent")
    display_name: str
    goal: str = Field(..., description="The agent's primary objective in one sentence")
    backstory: str = Field(..., description="Narrative context that shapes the agent's persona")
    tools: List[ToolAssignment] = Field(default_factory=list)
    is_orchestrator: bool = Field(
        False, description="True if this agent manages and delegates to others"
    )
    can_delegate: bool = Field(
        False, description="True if this agent may hand work to other agents"
    )
    preferred_framework: Literal["crewai", "langgraph", "autogen"] = Field(
        "crewai",
        description=(
            "crewai: default for most agents. "
            "autogen: when back-and-forth negotiation with another agent is needed. "
            "langgraph: when this agent is a conditional routing node."
        ),
    )
    llm_override: Optional[str] = Field(
        None, description="Model override for this agent (e.g. gpt-4o). Null = use team default."
    )


class TaskDesign(BaseModel):
    name: str = Field(..., description="snake_case task identifier")
    description: str = Field(..., description="Detailed instructions for the agent")
    expected_output: str = Field(..., description="What a successful output looks like")
    assigned_to: str = Field(..., description="Role name of the agent that executes this task")
    depends_on: List[str] = Field(
        default_factory=list, description="Names of tasks that must complete first"
    )


class CommunicationTopology(BaseModel):
    pattern: Literal["sequential", "hierarchical", "graph", "group_chat"] = Field(
        ...,
        description=(
            "sequential: tasks run in order, output flows forward. "
            "hierarchical: orchestrator delegates to sub-agents. "
            "graph: explicit edges control message routing (langgraph). "
            "group_chat: all agents share a conversation thread (autogen)."
        ),
    )
    description: str = Field(..., description="Plain-English explanation of why this pattern fits")
    edges: List[List[str]] = Field(
        default_factory=list,
        description="For graph pattern: [[from_role, to_role], ...] directed edges",
    )


class AgentPlan(BaseModel):
    """Complete team design produced by the LLM planner."""

    team_name: str
    agents: List[AgentDesign] = Field(..., min_length=1)
    tasks: List[TaskDesign] = Field(..., min_length=1)
    orchestrator_role: Optional[str] = Field(
        None, description="Role name of the orchestrator agent, if one is needed"
    )
    communication: CommunicationTopology
    primary_framework: Literal["crewai", "langgraph", "autogen"] = Field(
        "crewai", description="Framework used for the majority of agents"
    )
    needs_git_account: bool = Field(
        False, description="True if any agent requires GitAccountTool"
    )
    estimated_repos: Optional[int] = Field(
        None, description="Rough estimate of how many Git repos the team will create"
    )
    reasoning: str = Field(
        ..., description="Concise explanation of the key design decisions made"
    )
