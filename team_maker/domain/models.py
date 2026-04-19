"""Core domain models produced by the generation pipeline.

These are plain dataclasses — no external dependencies, easy to test.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ProviderRouting:
    """LLM provider + model assignment for one agent."""

    provider: str
    model: str
    api_key_env: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"provider": self.provider, "model": self.model}
        if self.api_key_env:
            d["api_key_env"] = self.api_key_env
        return d


@dataclass
class AgentSpec:
    """Fully-resolved specification for a single agent."""

    role: str
    display_name: str
    description: str
    goal: str
    backstory: str
    capabilities: List[str]
    tools: List[str]
    routing: ProviderRouting
    is_optional: bool = False
    is_orchestrator: bool = False

    def to_dict(self) -> Dict[str, Any]:
        # LLM config is intentionally absent here — routing_config.yaml is the single source of truth.
        return {
            "role": self.role,
            "display_name": self.display_name,
            "description": self.description,
            "goal": self.goal,
            "backstory": self.backstory,
            "capabilities": self.capabilities,
            "tools": self.tools,
            "is_optional": self.is_optional,
            "is_orchestrator": self.is_orchestrator,
        }


@dataclass
class TaskSpec:
    """Specification for a workflow task assigned to one agent role."""

    name: str
    description: str
    expected_output: str
    agent_role: str
    dependencies: List[str] = field(default_factory=list)
    is_optional: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "expected_output": self.expected_output,
            "agent_role": self.agent_role,
            "dependencies": self.dependencies,
            "is_optional": self.is_optional,
        }


@dataclass
class GeneratedTeam:
    """Everything needed to write the team package to disk."""

    team_name: str
    purpose: str
    template_used: str
    agents: List[AgentSpec]
    tasks: List[TaskSpec]
    stack: Optional[str] = None
    constraints: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    documentation_level: str = "standard"
    # Framework selection and topology (set by planner; template path defaults to crewai/sequential)
    primary_framework: str = "crewai"
    topology_pattern: str = "sequential"
    topology_edges: List[List[str]] = field(default_factory=list)
    planner_reasoning: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
