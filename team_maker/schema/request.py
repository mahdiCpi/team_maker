"""Input schema for team creation requests. All validation lives here."""
from __future__ import annotations

import re
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class DocumentationLevel(str, Enum):
    MINIMAL = "minimal"
    STANDARD = "standard"
    FULL = "full"


class TeamTemplateId(str, Enum):
    SOFTWARE_DELIVERY = "software_delivery_team"
    CUSTOM = "custom"


class ProviderConfig(BaseModel):
    """LLM provider + model routing for a single agent."""

    provider: str = Field(..., description="Provider name (e.g. anthropic, openai, ollama)")
    model: str = Field(..., description="Model ID (e.g. claude-sonnet-4-6, gpt-4o)")
    api_key_env: Optional[str] = Field(
        None, description="Environment variable that holds the API key"
    )

    @field_validator("provider")
    @classmethod
    def normalise_provider(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("model")
    @classmethod
    def normalise_model(cls, v: str) -> str:
        return v.strip()


class RoleDefinition(BaseModel):
    """Specification for a single agent role within the team."""

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


class TeamCreationRequest(BaseModel):
    """Root input model for a single team generation request."""

    team_name: str = Field(..., min_length=2, description="Short, unique name for the team")
    purpose: str = Field(..., min_length=10, description="One-paragraph purpose statement")
    output_path: str = Field(..., description="Directory path where the team package is written")
    stack: Optional[str] = Field(None, description="Technology stack (informational)")
    desired_roles: List[RoleDefinition] = Field(..., min_length=1)
    default_llm: Optional[ProviderConfig] = Field(
        None, description="Fallback LLM for roles without a specific assignment"
    )
    tools: List[str] = Field(default_factory=list, description="Tools shared across all agents")
    constraints: List[str] = Field(default_factory=list)
    documentation_level: DocumentationLevel = DocumentationLevel.STANDARD
    template: TeamTemplateId = TeamTemplateId.SOFTWARE_DELIVERY
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
