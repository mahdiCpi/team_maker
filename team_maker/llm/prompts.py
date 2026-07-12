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
    "context_reader": (
        "Read files from the project context directory supplied by the user. "
        "Use to access background documents, specifications, or domain knowledge before starting work."
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
9. If the user provided desired_tasks, use them as the DEFINITIVE task list. Generate exactly \
   those tasks, assigned to the agent roles specified. Do not collapse, merge, or omit any of them.
10. Estimate `estimated_repos` conservatively — it can grow at runtime.
11. Explain your key decisions clearly in the `reasoning` field.

## Planning phase — always generate before coding

Every software delivery team MUST begin with a collaborative planning phase \\
before any agent writes code. Generate these tasks in sequence at the start:

1. **project_initial_breakdown** (PM/orchestrator role): Read ALL context files, \\
   milestone docs, and specifications. Produce a task breakdown at ticket level \\
   (smaller than milestones — individual deliverables, not phases). Each ticket \\
   must have: name, description, acceptance_criteria (binary checkable), \\
   agent_role, dependencies, and demo_impact.

2. **architecture_breakdown_review** (architect/tech_lead role): Read the PM's \\
   breakdown. Validate technical feasibility, add component boundaries, identify \\
   API contracts, flag items that are too large (split) or too small (merge). \\
   Write architecture constraints doc.

3. **qa_risk_breakdown_review** (qa/reviewer role): Read PM and architect docs. \\
   For every ticket: add acceptance criteria, identify security/financial risks, \\
   flag items that affect the demo path, add rollback plan for high-risk items.

4. **project_plan_finalization** (PM/orchestrator role): Consolidate all three \\
   inputs. Write the final project plan with every deliverable, create GitHub \\
   issues for each, add to project board. This is the single source of truth \\
   every coding agent reads before starting work.

Only after these 4 tasks complete should any coding task begin.

## Mandatory coding agent workflow

Every agent that writes code MUST follow this workflow in its task description. \\
Generate tasks with these explicit steps (this is non-negotiable for any software team):

1. Read task + milestone goal + acceptance criteria + previous state of the code. \\
   Call git_account get_repo_file or context_reader to read existing work first.
2. State the scope explicitly: files to change, files NOT to touch, assumptions, risks.
3. Sync git: pull latest main, inspect diff, create feature branch.
4. Inspect existing tests and contracts before writing any code.
5. Write or update tests FIRST (or alongside code) — unit + smoke + contract if API changes.
6. Implement the smallest correct change that satisfies acceptance criteria.
7. Run lint/type checks, unit tests, integration tests, smoke test. ALL must pass.
8. Review own git diff — remove accidental changes.
9. Update documentation IN THE SAME BRANCH (README, API docs, env vars, known limits).
10. Commit and push the feature branch.
11. Open PR with evidence: diff summary, test results, API sample output, demo impact.
12. Request code review. Revise until reviewer approves.
13. Reviewer (or release manager) merges.
14. After merge: pull main, confirm state, notify PM with final status, changed files, \\
    test results, remaining risks, and next recommended tasks.

## Coding agent file-writing policy

Coding agents MUST use `code_writer` tool to write source files. \\
NEVER use bash echo/heredoc/printf for source code — bash single-quote escaping \\
corrupts Python f-strings with syntax errors the agent cannot detect at write time.

## Scope confirmation (required before any coding starts)

Every coding task must produce a scope_confirmation block before writing code:
- intended_change: what will be built
- files_expected_to_change: explicit list
- files_not_to_touch: explicit list of working components to protect
- acceptance_criteria: binary pass/fail checklist
- demo_impact: does this affect the investor demo? which step? fallback if broken?

## Security/risk check (required before any PR for FinTech products)

Before pushing, the coding agent must answer:
- Did I touch credentials or auth?
- Did I touch order execution or real-money logic?
- Did I touch user permissions or risk limits?
- Did I touch audit logs?
If yes to any: the PR requires elevated review (architect + QA must approve, not just one reviewer).

## No merge without evidence

Code reviewers must NOT approve based on description alone. Required evidence:
- test runner output (pass counts, no failures)
- lint/type check output (zero errors)
- smoke test result (service starts)
- git diff summary (only expected files changed)
- sample API response or screenshot if UI/backend changed
"""


SYSTEM_PROMPT = build_system_prompt()  # zero-arg default for backward compatibility


def _load_context_files(context_dir: str) -> str:
    """Read all text files under context_dir and return a formatted block."""
    from pathlib import Path
    root = Path(context_dir)
    if not root.is_dir():
        return ""
    parts: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        try:
            content = path.read_text(encoding="utf-8", errors="replace").strip()
        except Exception:
            continue
        if content:
            parts.append(f"### {rel}\n\n{content}")
    if not parts:
        return ""
    return "## Context files provided by the user\n\n" + "\n\n---\n\n".join(parts)


def build_user_message(request: TeamCreationRequest) -> str:
    role_hints = ""
    if request.desired_roles:
        lines = []
        for r in request.desired_roles:
            lines.append(f"  - {r.name}: {r.description}")
        role_hints = "Desired role hints (use as suggestions, expand if needed):\n" + "\n".join(lines)
    else:
        role_hints = "No role hints provided — infer all roles from the project purpose."

    task_hints = ""
    if request.desired_tasks:
        lines = []
        for t in request.desired_tasks:
            deps = f" (depends on: {', '.join(t.dependencies)})" if t.dependencies else ""
            lines.append(f"  - {t.name} → {t.agent_role}{deps}: {t.description}")
        task_hints = (
            "Desired task plan (treat as the definitive task list — do not omit these tasks):\n"
            + "\n".join(lines)
            + "\n"
        )

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

    context_section = ""
    if request.context_dir:
        loaded = _load_context_files(request.context_dir)
        if loaded:
            context_section = f"\n\n{loaded}\n"

    return f"""Design a complete multi-agent team for the following project.

Project name: {request.team_name}
Purpose: {request.purpose}
{stack_info}
{constraints_info}
{git_info}
{context_section}
{task_hints}
{role_hints}

{tools_note}Produce a full AgentPlan with every agent, their tools, all tasks, and the communication topology.
"""
