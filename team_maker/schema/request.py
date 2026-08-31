"""Input schema for team creation requests. All validation lives here."""
from __future__ import annotations

import re
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from team_maker.tools.catalog import is_canonical
from team_maker.tools.validation import validate_declarations, validate_suggested_tool_credentials


class DocumentationLevel(str, Enum):
    MINIMAL = "minimal"
    STANDARD = "standard"
    FULL = "full"
    DETAILED = "detailed"


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

    provider: str = Field(..., description="Provider name: anthropic | openai | xai | google | ollama")
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


class NotificationConfig(BaseModel):
    """Alert configuration for webhook, email, and Telegram notifications."""

    webhook_url_env: str = Field(
        "ALERT_WEBHOOK_URL",
        description=(
            "Name of the env var holding the webhook URL "
            "(Slack, Discord, Teams, or any HTTP endpoint accepting JSON {\"text\": ...})."
        ),
    )
    email_to: Optional[str] = Field(None, description="Recipient email address for alerts.")
    smtp_host: str = Field("smtp.gmail.com", description="SMTP server hostname.")
    smtp_port: int = Field(587, description="SMTP port — 587 for STARTTLS, 465 for SSL.")
    smtp_user_env: str = Field(
        "SMTP_USER",
        description="Env var holding the SMTP username / sender address.",
    )
    smtp_password_env: str = Field(
        "SMTP_PASSWORD",
        description="Env var holding the SMTP password.",
    )
    telegram_enabled: bool = Field(False, description="Enable Telegram notifications.")
    telegram_bot_token_env: str = Field(
        "TELEGRAM_BOT_TOKEN",
        description="Env var holding the Telegram bot token.",
    )
    telegram_chat_id_env: str = Field(
        "TELEGRAM_CHAT_ID",
        description="Env var holding the Telegram chat ID.",
    )


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
    # FR-073: network denied by default; "host" removed entirely — it defeats
    # the sandbox regardless of who requests it (spec Amendment 6, D-IMPL-003).
    # The operator's tool-policy `network_allowed` flag is the actual gate: this
    # field only narrows further, it never widens past what the operator permits.
    network: Literal["none", "bridge"] = "none"


class TaskHint(BaseModel):
    """Optional hint for a single task — the LLM planner may adjust or expand these."""

    name: str = Field(..., description="snake_case task identifier, unique within the request")
    description: str = Field(..., min_length=10, description="What the task does")
    agent_role: str = Field(..., description="Which role should own this task")
    dependencies: List[str] = Field(default_factory=list, description="Task names this task depends on")

    @field_validator("name")
    @classmethod
    def validate_task_name(cls, v: str) -> str:
        """Mirror of ``RoleDefinition.validate_role_name`` — and load-bearing.

        This field reaches the filesystem: the task generator emits one file per
        task and ``ArtifactWriter.write`` joins the name onto the output
        directory, so an unconstrained name is a path-traversal primitive. A
        task named ``../../escaped`` writes outside ``output_path`` entirely and
        bypasses the ``overwrite=False`` guard, which only inspects
        ``output_path`` itself. Verified before this validator existed.

        Added by the Story 2.0 code review as a declared exception to that
        story's ``team_maker/`` freeze: the HTTP seam made the hole remotely
        reachable, but the hole is here, and fixing it here protects the CLI and
        every future surface rather than just the one door.
        """
        if not re.match(r"^[a-z][a-z0-9_]*$", v):
            raise ValueError(
                f"Task name must be snake_case (lowercase letters, digits, underscores), got: {v!r}"
            )
        return v


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

    # Optional task hints — the LLM planner treats these as the task plan to follow
    desired_tasks: List[TaskHint] = Field(
        default_factory=list,
        description="Explicit task plan. If provided, the planner uses these as the task list.",
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

    notifications: Optional[NotificationConfig] = Field(
        None,
        description=(
            "Webhook / email alert config. "
            "Set the env var named in webhook_url_env at runtime to receive alerts "
            "on API errors, token limits, agent crashes, and run completion."
        ),
    )

    context_dir: Optional[str] = Field(
        None,
        description=(
            "Path to a directory of context files (docs, specs, domain knowledge). "
            "Injected into the planner prompt at generation time and accessible to agents "
            "via the context_reader tool at runtime."
        ),
    )

    model_registry: Optional[Dict[str, Any]] = Field(
        None,
        description=(
            "Named LLM configurations. String references to registry keys in "
            "llm fields (default_llm, planning_llm, per-role llm) are resolved "
            "to inline ProviderConfig objects before validation."
        ),
    )

    documentation_level: DocumentationLevel = DocumentationLevel.STANDARD
    overwrite: bool = Field(False, description="Allow overwriting an existing output directory")
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    template_id: Optional[str] = Field(
        None,
        description="Optional template ID to use for team generation. If not provided, defaults to 'software_delivery_team'.",
    )

    @field_validator("template_id")
    @classmethod
    def validate_template_id_exists(cls, v: Optional[str]) -> Optional[str]:
        """Validate that template_id, if provided, exists in the registry.
        
        This provides fast-fail validation at request time rather than waiting
        for get_template() to be called at runtime.
        
        Story 4.6 Task 3: Template existence check at request time
        """
        if v is None:
            return v
        
        # Import here to avoid circular imports
        from team_maker.templates.registry import list_templates
        
        valid_templates = list_templates()
        if v not in valid_templates:
            available = sorted(valid_templates.keys())
            raise ValueError(
                f"Unknown template_id '{v}'. Available templates: {available}"
            )
        return v

    @model_validator(mode="before")
    @classmethod
    def _pre_process(cls, values: Any) -> Any:
        """Run before field validation to normalise inputs that can arrive in
        non-standard but common forms: dict stacks, registry-key LLM references,
        and the auxiliary_resources_dir alias for context_dir."""
        if not isinstance(values, dict):
            return values

        # 1. Flatten a dict-valued `stack` to a readable string.
        if isinstance(values.get("stack"), dict):
            parts = [
                v for v in values["stack"].values()
                if isinstance(v, str)
                and not v.startswith("deferred")
                and not re.match(r"^[a-z][a-z0-9_]*$", v)
            ]
            values["stack"] = ", ".join(parts)

        # 2. Map auxiliary_resources_dir → context_dir (alternative field name).
        if "auxiliary_resources_dir" in values and "context_dir" not in values:
            values["context_dir"] = values["auxiliary_resources_dir"]

        # 2.5. Map template → template_id (alternative field name for backwards compatibility).
        if "template" in values and "template_id" not in values:
            values["template_id"] = values["template"]

        # 3. Map notification_channels.telegram → notifications.telegram_* fields.
        nc = values.get("notification_channels")
        if isinstance(nc, dict):
            tg = nc.get("telegram", {})
            if isinstance(tg, dict) and tg.get("enabled"):
                creds = tg.get("credentials", {})
                existing = values.get("notifications") or {}
                if isinstance(existing, dict):
                    existing.setdefault("telegram_enabled", True)
                    existing.setdefault(
                        "telegram_bot_token_env",
                        creds.get("bot_token_env", "TELEGRAM_BOT_TOKEN"),
                    )
                    existing.setdefault(
                        "telegram_chat_id_env",
                        creds.get("chat_id_env", "TELEGRAM_CHAT_ID"),
                    )
                    values["notifications"] = existing
                elif existing is None:
                    values["notifications"] = {
                        "telegram_enabled": True,
                        "telegram_bot_token_env": creds.get("bot_token_env", "TELEGRAM_BOT_TOKEN"),
                        "telegram_chat_id_env": creds.get("chat_id_env", "TELEGRAM_CHAT_ID"),
                    }

        # 4. Promote recognized tools from suggested_tools -> tools in desired_roles.
        #    suggested_tools may contain domain-specific names the planner reads as
        #    hints; only names in the canonical catalog (spec FR-001) are surfaced
        #    as concrete tool assignments on the AgentSpec. Previously checked
        #    against a locally-hardcoded `_REGISTRY_TOOLS` copy that had drifted
        #    from the other two allowlists and carried a phantom "linter" entry
        #    (audit RC-3, §2.2(a)) — now derives from the single canonical source.
        for role in values.get("desired_roles", []):
            if isinstance(role, dict) and "suggested_tools" in role and not role.get("tools"):
                known = [t for t in role["suggested_tools"] if is_canonical(t)]
                if known:
                    role["tools"] = known

        # 4.5. Gate every declared tool name against the canonical catalog (spec
        #      FR-002, FR-003, FR-004; audit RC-3). This is the surface the old
        #      `_REGISTRY_TOOLS` filter never saw: explicit `desired_roles[].tools`
        #      declarations, not just the suggested_tools promotion above. An
        #      unknown or alias-only name here fails schema validation, which the
        #      Composer's repair loop treats as retry-worthy and, if the repair
        #      budget is exhausted, surfaces visibly to the user (FR-056) rather
        #      than silently reaching a generated package.
        _tool_declarations: list[tuple[str, str]] = []
        for role in values.get("desired_roles", []):
            if isinstance(role, dict):
                role_name = role.get("name", "<unnamed role>")
                for tool_name in role.get("tools", []) or []:
                    _tool_declarations.append((tool_name, role_name))
        _outcome = validate_declarations(_tool_declarations, stage="compose")
        if values.get("suggested_tools"):
            _cred_outcome = validate_suggested_tool_credentials(values["suggested_tools"])
        else:
            _cred_outcome = None
        _all_rejections = list(_outcome.rejections) + (
            list(_cred_outcome.rejections) if _cred_outcome else []
        )
        if _all_rejections:
            raise ValueError(
                "Invalid tool declaration(s): " + "; ".join(str(r) for r in _all_rejections)
            )

        # 5. Resolve model_registry string references.
        registry = values.get("model_registry")
        if registry and isinstance(registry, dict):
            _PROVIDER_FIELDS = {"provider", "model", "api_key_env", "base_url"}

            def _resolve(ref: Any) -> Any:
                if isinstance(ref, str) and ref in registry:
                    entry = registry[ref]
                    if isinstance(entry, dict):
                        return {k: v for k, v in entry.items() if k in _PROVIDER_FIELDS}
                return ref

            for key in ("default_llm", "planning_llm"):
                if key in values:
                    values[key] = _resolve(values[key])

            for role in values.get("desired_roles", []):
                if isinstance(role, dict) and "llm" in role:
                    role["llm"] = _resolve(role["llm"])

        return values

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

    @field_validator("context_dir")
    @classmethod
    def validate_context_dir(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        p = Path(v).expanduser()
        # Note: We no longer require the directory to exist at validation time
        # (Task 4, Story 4.5: Fix spec round-trip mutation). The existence check
        # happens at runtime when the directory is actually used (see llm/prompts.py:
        # _load_context_files returns "" if the directory doesn't exist).
        # This allows the spec to round-trip cleanly even if the context_dir
        # is removed after the spec is created.
        return str(p.resolve())

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
