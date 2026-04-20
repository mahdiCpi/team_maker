"""Prompt construction for the LLM team planner."""
from __future__ import annotations

from team_maker.schema.request import TeamCreationRequest

# Registry of available tools the planner can assign to agents.
# Phase 2 will add real implementations; this drives planner awareness now.
AVAILABLE_TOOLS: dict[str, str] = {
    "git_account": (
        "Full Git account management: create/clone/delete repos, manage branches, "
        "open/review/merge PRs, create issues, manage GitHub Projects boards. "
        "Requires a GitAccountConfig with a personal access token."
    ),
    "filesystem": (
        "Read, write, create, and list files and directories inside the Docker workspace (/workspace). "
        "Safe — cannot access paths outside the sandbox."
    ),
    "shell": (
        "Execute arbitrary shell commands inside the Docker sandbox. "
        "Use for builds, package installs, script execution, and any CLI tool."
    ),
    "docker_runner": (
        "Build Docker images, run containers, push to registries. "
        "Runs docker-in-docker inside the sandbox."
    ),
    "web_search": "Search the web for documentation, library APIs, best practices, and error solutions.",
    "http_client": (
        "Make authenticated HTTP requests to external REST or GraphQL APIs "
        "(e.g. GitHub API, Jira, Slack, cloud provider APIs)."
    ),
    "test_runner": (
        "Discover and run test suites: pytest, unittest, npm test, go test, cargo test, etc. "
        "Returns pass/fail counts, coverage, and failure details."
    ),
    "ci_tool": (
        "Trigger GitHub Actions / GitLab CI workflows and query their status. "
        "Use for deployment gating and automated pipeline management."
    ),
    "code_writer": (
        "Write, overwrite, or patch source code files in the workspace. "
        "Preserves indentation and encoding."
    ),
    "code_reader": (
        "Read and summarise source code files. "
        "Useful for review agents and agents that need to understand existing code before modifying."
    ),
    "state_reader": (
        "Read entries from the shared team state store. "
        "Use to check what other agents have completed or decided."
    ),
    "state_writer": (
        "Write entries to the shared team state store. "
        "Use to publish decisions, artifacts, or status updates for other agents to consume."
    ),
}


def build_system_prompt(extra_tools: dict[str, str] | None = None) -> str:
    """Build the system prompt with optional user-supplied tools merged into the catalog."""
    merged = {**AVAILABLE_TOOLS, **(extra_tools or {})}
    catalog_text = "\n".join(f"- **{name}**: {desc}" for name, desc in merged.items())

    user_tools_note = ""
    if extra_tools:
        names = ", ".join(f"`{n}`" for n in extra_tools)
        user_tools_note = (
            f"\n\n> **User-supplied tools** ({names}) are valid assignments. "
            "Prefer them over built-in tools when they are a better fit for the task."
        )

    return f"""You are a senior software architect designing a multi-agent AI team.
Your job is to produce a complete, executable team plan given a project description.

## Available tools

{catalog_text}{user_tools_note}

## Framework selection rules

- **crewai** (default): Use for the majority of agents. Supports sequential pipelines and \\
hierarchical delegation. Always start here unless a specific agent genuinely needs more.
- **autogen**: Use only for agents that must negotiate back-and-forth with another agent \\
(e.g. a code-review agent debating changes with the developer agent).
- **langgraph**: Use only for agents that act as conditional routing nodes \\
(e.g. "if tests pass → merge, else → return to developer").

## Design rules

1. Always include an orchestrator agent when the project involves multiple services or repos. \\
   The orchestrator uses `crewai`, `is_orchestrator=true`, `can_delegate=true`.
2. Assign `git_account` to any agent that creates, clones, or manages repositories.
3. Assign `shell` + `test_runner` to any agent that runs builds or tests.
4. Assign `code_writer` + `filesystem` to any implementation agent.
5. Assign `state_reader` + `state_writer` to agents that coordinate with others.
6. The orchestrator maintains the live repo registry in shared state.
7. Do not invent tool names — only assign tools from the catalog above.
8. If the user provided desired_roles, treat them as hints. Expand, split, or rename as needed.
9. Estimate `estimated_repos` conservatively — it can grow at runtime.
10. Explain your key decisions clearly in the `reasoning` field.
"""


SYSTEM_PROMPT = build_system_prompt()  # zero-arg default for backward compatibility


def build_user_message(request: TeamCreationRequest) -> str:
    role_hints = ""
    if request.desired_roles:
        lines = []
        for r in request.desired_roles:
            lines.append(f"  - {r.name}: {r.description}")
        role_hints = "Desired role hints (use as suggestions, expand if needed):\n" + "\n".join(lines)
    else:
        role_hints = "No role hints provided — infer all roles from the project purpose."

    tools_note = ""
    if request.suggested_tools:
        lines = [f"  - **{t.name}**: {t.description}" for t in request.suggested_tools]
        tools_note = "User-supplied tools (treat as first-class assignments):\n" + "\n".join(lines) + "\n\n"

    git_info = (
        f"Git account configured: yes (platform={request.git_account.platform}, "
        f"org/user={request.git_account.org_or_user})"
        if request.git_account
        else "Git account configured: no"
    )

    stack_info = f"Technology stack: {request.stack}" if request.stack else "Technology stack: not specified"

    constraints_info = (
        "Constraints:\n" + "\n".join(f"  - {c}" for c in request.constraints)
        if request.constraints
        else "Constraints: none"
    )

    return f"""Design a complete multi-agent team for the following project.

Project name: {request.team_name}
Purpose: {request.purpose}
{stack_info}
{constraints_info}
{git_info}

{role_hints}

{tools_note}Produce a full AgentPlan with every agent, their tools, all tasks, and the communication topology.
"""
