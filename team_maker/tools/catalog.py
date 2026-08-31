"""The canonical tool catalog (spec FR-001; audit RC-3).

`TOOL_CATALOG` is the single authoritative definition of tool identity. Every
other surface that names tools — the planner prompt (`llm/prompts.py`), the
authoring-schema filter (`schema/request.py`), and the generated registry
(`codegen/templates/tools.py.j2`) — derives its view from this module rather
than restating its own list. Before this remediation those three copies had
drifted (audit §2.2(a)): `prompts.py` had 13 names, `schema/request.py`'s
`_REGISTRY_TOOLS` had 14 (including the phantom `"linter"`), and the codegen
registry had 13 with a different key for the shell tool (`shell` vs the
decorator's `shell_command`).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class RiskClass(Enum):
    """Whether a tool needs explicit operator authorization to execute.

    SAFE tools may not execute host commands, write outside the sandbox
    workspace, open network connections on their own authority, or control
    the container runtime (spec FR-083). A tool that needs any of those is
    RISKY by definition and MUST be classified accordingly. RISKY tools are
    denied by default and execute only when the operator has explicitly
    enabled them (FR-052) — see `team_maker/tools/authorization.py`.

    Structural enforcement of the SAFE boundary against the *generated
    implementation* lives in `tests/security/test_safe_tool_boundary.py`
    (T089), added when the codegen template is touched in Phase 4: this
    module can only guarantee correct classification, not that a given
    implementation honours it.
    """

    SAFE = "safe"
    RISKY = "risky"


@dataclass(frozen=True)
class ToolDefinition:
    """The canonical identity of one tool (data-model.md §1)."""

    name: str
    description: str
    risk: RiskClass
    required_credentials: tuple[str, ...] = field(default_factory=tuple)
    requires_mounts: bool = False
    aliases: tuple[str, ...] = field(default_factory=tuple)


# ---------------------------------------------------------------------------
# The catalog. Populated from the 13 real entries previously hardcoded in
# `llm/prompts.py:12-62` (AVAILABLE_TOOLS). Risk classification per the
# approved remediation plan (spec FR-008, tasks.md T013): shell, code_writer,
# test_runner and docker_runner are the tools that execute host commands or
# containers — everything else is SAFE. `requires_mounts` is True only for
# docker_runner, the sole tool whose contract accepts a host mount argument.
# ---------------------------------------------------------------------------

TOOL_CATALOG: dict[str, ToolDefinition] = {
    "git_account": ToolDefinition(
        name="git_account",
        description=(
            "Full Git account management: create/clone/delete repos, manage branches, "
            "open/review/merge PRs, create issues, manage GitHub Projects boards. "
            "Requires a GitAccountConfig with a personal access token."
        ),
        risk=RiskClass.SAFE,
        required_credentials=("GIT_ACCOUNT_TOKEN",),
        aliases=("git_account_tool",),
    ),
    "filesystem": ToolDefinition(
        name="filesystem",
        description=(
            "Read, write, create, and list files and directories inside the Docker "
            "workspace (/workspace). Safe — cannot access paths outside the sandbox."
        ),
        risk=RiskClass.SAFE,
    ),
    "shell": ToolDefinition(
        name="shell",
        description=(
            "Execute arbitrary shell commands inside the Docker sandbox. "
            "Use for builds, package installs, script execution, and any CLI tool."
        ),
        # RISKY: executes arbitrary host/sandbox commands (FR-083).
        risk=RiskClass.RISKY,
        aliases=("shell_command", "shell_tool"),
    ),
    "docker_runner": ToolDefinition(
        name="docker_runner",
        description=(
            "Build Docker images, run containers, push to registries. "
            "Runs docker-in-docker inside the sandbox."
        ),
        # RISKY: controls the container runtime and accepts mount arguments (FR-083).
        risk=RiskClass.RISKY,
        requires_mounts=True,
    ),
    "web_search": ToolDefinition(
        name="web_search",
        description="Search the web for documentation, library APIs, best practices, and error solutions.",
        risk=RiskClass.SAFE,
        required_credentials=("SERPER_API_KEY",),
    ),
    "http_client": ToolDefinition(
        name="http_client",
        description=(
            "Make authenticated HTTP requests to external REST or GraphQL APIs "
            "(e.g. GitHub API, Jira, Slack, cloud provider APIs)."
        ),
        risk=RiskClass.SAFE,
    ),
    "test_runner": ToolDefinition(
        name="test_runner",
        description=(
            "Discover and run test suites: pytest, unittest, npm test, go test, cargo test, etc. "
            "Returns pass/fail counts, coverage, and failure details."
        ),
        # RISKY: executes the target project's build/test tooling as host commands (FR-083).
        risk=RiskClass.RISKY,
    ),
    "ci_tool": ToolDefinition(
        name="ci_tool",
        description=(
            "Trigger GitHub Actions / GitLab CI workflows and query their status. "
            "Use for deployment gating and automated pipeline management."
        ),
        risk=RiskClass.SAFE,
    ),
    "code_writer": ToolDefinition(
        name="code_writer",
        description=(
            "Write, overwrite, or patch source code files in the workspace. "
            "Preserves indentation and encoding."
        ),
        # RISKY: shares the sandboxed execution path with shell/test_runner (FR-083).
        risk=RiskClass.RISKY,
        aliases=("code_writer_tool",),
    ),
    "code_reader": ToolDefinition(
        name="code_reader",
        description=(
            "Read and summarise source code files. "
            "Useful for review agents and agents that need to understand existing code before modifying."
        ),
        risk=RiskClass.SAFE,
        required_credentials=("OPENAI_API_KEY",),
        aliases=("code_reader_tool",),
    ),
    "state_reader": ToolDefinition(
        name="state_reader",
        description=(
            "Read entries from the shared team state store. "
            "Use to check what other agents have completed or decided."
        ),
        risk=RiskClass.SAFE,
    ),
    "state_writer": ToolDefinition(
        name="state_writer",
        description=(
            "Write entries to the shared team state store. "
            "Use to publish decisions, artifacts, or status updates for other agents to consume."
        ),
        risk=RiskClass.SAFE,
    ),
    "context_reader": ToolDefinition(
        name="context_reader",
        description=(
            "Read files from the project context directory supplied by the user. "
            "Use to access background documents, specifications, or domain knowledge before starting work."
        ),
        risk=RiskClass.SAFE,
    ),
}


class CatalogIntegrityError(Exception):
    """The catalog itself is internally inconsistent — a build-time defect, not a user error."""


def _validate_catalog_integrity() -> None:
    """Guard against catalog drift: no name may double as another entry's alias,
    and every entry's own key must not appear in its own alias tuple."""
    all_aliases: dict[str, str] = {}
    for name, definition in TOOL_CATALOG.items():
        if definition.name != name:
            raise CatalogIntegrityError(f"catalog key {name!r} does not match ToolDefinition.name {definition.name!r}")
        if name in definition.aliases:
            raise CatalogIntegrityError(f"tool {name!r} lists itself as its own alias")
        for alias in definition.aliases:
            if alias in TOOL_CATALOG:
                raise CatalogIntegrityError(
                    f"alias {alias!r} of {name!r} collides with a canonical catalog name"
                )
            if alias in all_aliases:
                raise CatalogIntegrityError(
                    f"alias {alias!r} claimed by both {all_aliases[alias]!r} and {name!r}"
                )
            all_aliases[alias] = name


_validate_catalog_integrity()


class AvailabilityState(Enum):
    """The three non-collapsible states a tool declaration can be in (spec
    FR-065; audit RC-3/RC-8, Amendment 4). Distinct from `RejectionReason`:
    these describe *why a canonical tool might not run here*, not why a
    declaration is invalid. Modeled here (Phase 3/Step 1 build side); the
    run-time check against actual credentials/dependencies is Phase 7/Step 6
    preflight work (`team_maker/runtime/preflight.py`)."""

    UNKNOWN = "unknown"  # not in TOOL_CATALOG at all — a validation rejection, not this
    NO_IMPLEMENTATION = "no_implementation"  # canonical, but codegen has no binding for it
    UNAVAILABLE_HERE = "unavailable_here"  # canonical, implemented, but a required credential is absent
    AVAILABLE = "available"


# The three catalog entries whose codegen binding
# (`codegen/templates/tools.py.j2`) is conditional on an optional dependency
# (`crewai-tools`, never a team_maker dependency itself — only ever a
# generated *package's* `requirements.txt` entry) and, for two of them, a
# credential in `required_credentials`. Single-sourced here so Phase 5's
# `PackageToolResolver` and Phase 7's preflight (T132/T133) share one
# definition of "this absence is UNAVAILABLE_HERE, not NO_IMPLEMENTATION"
# rather than each re-deriving it (audit RC-3's exact mistake, in miniature).
CONDITIONALLY_AVAILABLE_TOOL_NAMES: frozenset[str] = frozenset({"filesystem", "code_reader", "web_search"})


def build_time_availability(name: str) -> AvailabilityState:
    """FR-066: what build can determine from the catalog definition alone,
    without knowing the deployment environment's actual credentials. Every
    current catalog entry has a real codegen binding (`tools.py.j2`), so
    NO_IMPLEMENTATION cannot occur today — this exists so Phase 4's codegen
    build-failure gate (FR-010) and any future catalog entry share one
    definition of the state instead of inventing a second."""
    if not is_canonical(name):
        return AvailabilityState.UNKNOWN
    return AvailabilityState.AVAILABLE


def required_credentials_for(names: list[str]) -> dict[str, tuple[str, ...]]:
    """FR-066: the dependency/credential requirements build must emit into
    the generated package for every declared tool, so Phase 7 preflight can
    validate actual availability without re-deriving it from the catalog."""
    return {name: TOOL_CATALOG[name].required_credentials for name in names if is_canonical(name)}


def is_canonical(name: str) -> bool:
    """True only for an exact canonical name — never for an alias (spec D-2)."""
    return name in TOOL_CATALOG


def resolve_alias(name: str) -> str | None:
    """The canonical name a legacy alias maps to, or None if `name` is not a
    recognized alias of exactly one catalog entry. Used only by the migration
    report (FR-041) — aliases are never accepted as a valid declaration."""
    matches = [canonical for canonical, definition in TOOL_CATALOG.items() if name in definition.aliases]
    return matches[0] if len(matches) == 1 else None
