"""Input schema for team creation requests. All validation lives here."""
from __future__ import annotations

import re
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class DocumentationLevel(str, Enum):
    MINIMAL = "minimal"
    STANDARD = "standard"
    FULL = "full"


class FrameworkChoice(str, Enum):
    CREWAI = "crewai"
    LANGGRAPH = "langgraph"
    AUTOGEN = "autogen"


class StateBackend(str, Enum):
    FILE = "file"
    VECTOR = "vector"
    BOTH = "both"


class ProviderConfig(BaseModel):
    """LLM provider + model routing for a single agent or the planner."""

    provider: str = Field(..., description="Provider name: anthropic | openai | ollama")
    model: str = Field(..., description="Model ID (e.g. claude-sonnet-4-6, gpt-4o, llama3.2)")
    api_key_env: Optional[str] = Field(
        None, description="Environment variable that holds the API key"
    )
    base_url: Optional[str] = Field(
        None, description="Custom base URL — required for Ollama (e.g. http://localhost:11434)"
    )

    @field_validator("provider")
    @classmethod
    def normalise_provider(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("model")
    @classmethod
    def normalise_model(cls, v: str) -> str:
        return v.strip()


class GitAccountConfig(BaseModel):
    """Credentials and settings for a Git hosting account."""

    platform: Literal["github", "gitlab", "bitbucket"] = "github"
    token_env: str = Field(
        "GITHUB_TOKEN",
        description="Environment variable holding the personal access token",
    )
    org_or_user: str = Field(
        ..., description="GitHub org or username where repos will be created"
    )
    default_visibility: Literal["private", "public"] = "private"


class ToolSuggestion(BaseModel):
    """A custom tool the user wants the planner to consider assigning to agents."""

    name: str = Field(..., description="snake_case tool identifier, unique within the request")
    description: str = Field(
        ..., min_length=10, description="What the tool does — shown verbatim to the planner LLM"
    )
    env_vars: List[str] = Field(
        default_factory=list, description="Env vars required at runtime (e.g. SLACK_WEBHOOK_URL)"
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not re.match(r"^[a-z][a-z0-9_]*$", v):
            raise ValueError("Tool name must be snake_case (lowercase letters, digits, underscores)")
        return v


class SandboxConfig(BaseModel):
    """Docker sandbox settings for tool execution."""

    image: str = "python:3.12-slim"
    workspace_mount: str = Field(
        "./workspace",
        description="Host path mounted as /workspace inside the container",
    )
    extra_env: Dict[str, str] = Field(default_factory=dict)
    network: Literal["none", "host", "bridge"] = "bridge"


class RoleDefinition(BaseModel):
    """Optional hint for a single agent role — the LLM planner may expand or adjust these."""

    name: str = Field(..., description="snake_case role identifier, unique within the request")
    display_name: Optional[str] = Field(None, description="Human-readable role title")
    description: str = Field(..., min_length=5, description="What this role does")
    goal: Optional[str] = Field(None, description="The agent's primary goal statement")
    backstory: Optional[str] = Field(None, description="Narrative backstory for the agent")
    capabilities: List[str] = Field(default_factory=list)
    tools: List[str] = Field(default_factory=list)
    llm: Optional[ProviderConfig] = Field(None, description="Per-role LLM override")
    is_optional: bool = False

    @field_validator("name")
    @classmethod
    def validate_role_name(cls, v: str) -> str:
        if not re.match(r"^[a-z][a-z0-9_]*$", v):
            raise ValueError(
                f"Role name must be snake_case (lowercase letters, digits, underscores), got: {v!r}"
            )
        return v

    @property
    def resolved_display_name(self) -> str:
        return self.display_name or self.name.replace("_", " ").title()


_DEFAULT_PLANNING_LLM = ProviderConfig(
    provider="anthropic",
    model="claude-sonnet-4-6",
    api_key_env="ANTHROPIC_API_KEY",
)


class TeamCreationRequest(BaseModel):
    """Root input model for a single team generation request."""

    team_name: str = Field(..., min_length=2, description="Short, unique name for the team")
    purpose: str = Field(..., min_length=10, description="Natural-language description of what the team must build")
    output_path: str = Field(..., description="Directory path where the team package is written")
    stack: Optional[str] = Field(None, description="Technology stack hint (e.g. 'Python, FastAPI, PostgreSQL')")
    constraints: List[str] = Field(default_factory=list, description="Hard constraints the team must respect")

    # LLM used by team_maker to infer agents, tools, and topology
    planning_llm: ProviderConfig = Field(
        default=_DEFAULT_PLANNING_LLM,
        description="LLM used by the planner to design the team. Defaults to Anthropic claude-sonnet-4-6.",
    )

    # Agentic framework for the generated team
    framework: FrameworkChoice = Field(
        FrameworkChoice.CREWAI,
        description="Primary agentic framework. crewai is the default; langgraph/autogen used where they excel.",
    )

    # State persistence
    state_backend: StateBackend = Field(
        StateBackend.FILE,
        description="How agents persist state between tasks: file (JSON), vector (ChromaDB), or both.",
    )

    # Optional Git account for repo management tools
    git_account: Optional[GitAccountConfig] = Field(
        None,
        description="If set, agents that need it receive a GitAccountTool bound to this account.",
    )

    # Docker sandbox for tool execution
    sandbox: SandboxConfig = Field(
        default_factory=SandboxConfig,
        description="Docker sandbox configuration for executing tools safely.",
    )

    # Optional role hints — the LLM planner uses these as suggestions and may add more
    desired_roles: List[RoleDefinition] = Field(
        default_factory=list,
        description="Optional role hints. If empty, the planner infers all roles from purpose.",
    )

    # Optional tool suggestions — the planner merges these with the built-in tool catalog
    suggested_tools: List[ToolSuggestion] = Field(
        default_factory=list,
        description=(
            "Custom tools the planner may assign to agents. "
            "Stubs are generated in tools.py — fill in the implementation."
        ),
    )

    # Per-agent LLM fallback
    default_llm: Optional[ProviderConfig] = Field(
        None, description="Fallback LLM for agents without a specific assignment"
    )

    documentation_level: DocumentationLevel = DocumentationLevel.STANDARD
    overwrite: bool = Field(False, description="Allow overwriting an existing output directory")
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("team_name")
    @classmethod
    def validate_team_name(cls, v: str) -> str:
        if not re.match(r"^[a-zA-Z][a-zA-Z0-9_ \-]*$", v):
            raise ValueError(
                "team_name must start with a letter and contain only letters, digits, "
                "underscores, hyphens, or spaces"
            )
        return v.strip()

    @field_validator("output_path")
    @classmethod
    def validate_output_path(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("output_path must not be empty")
        return v

    @model_validator(mode="after")
    def check_unique_role_names(self) -> "TeamCreationRequest":
        names = [r.name for r in self.desired_roles]
        seen: set[str] = set()
        duplicates: list[str] = []
        for n in names:
            if n in seen:
                duplicates.append(n)
            seen.add(n)
        if duplicates:
            raise ValueError(f"Duplicate role names in desired_roles: {sorted(set(duplicates))}")
        return self
