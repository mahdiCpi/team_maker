"""Loads an already-built Team Package back into a GeneratedTeam (Story 1.5).

The inverse of the Factory's generators — reads what PipelineRunner wrote,
never writes anything itself (AD-5: Runtime only executes). Has no access to
the build-time OutputValidator's report, so it does its own defensive checks
against a package that may have been hand-edited or partially deleted since
it was built.
"""
from __future__ import annotations

from pathlib import Path

from team_maker.domain.models import AgentSpec, GeneratedTeam, ProviderRouting, TaskSpec
from team_maker.utils.yaml_utils import load_yaml


class TeamPackageError(Exception):
    """A Team Package on disk is missing, incomplete, or malformed."""


def load_team_package(package_path: Path) -> GeneratedTeam:
    """Read a Team Package directory back into a GeneratedTeam."""
    package_path = Path(package_path)
    if not package_path.is_dir():
        raise TeamPackageError(f"Team Package directory not found: {package_path}")

    team_config = _load_yaml_file(package_path / "team_config.yaml", "team_config.yaml")
    routing = _load_yaml_file(
        package_path / "routing_config.yaml", "routing_config.yaml"
    ).get("routing", {})

    agents = [
        _load_agent(package_path, role, routing) for role in team_config.get("agents", [])
    ]
    tasks = [_load_task(package_path, name) for name in team_config.get("tasks", [])]

    known_roles = {agent.role for agent in agents}
    for task in tasks:
        if task.agent_role not in known_roles:
            raise TeamPackageError(
                f"Task '{task.name}' references unknown agent_role: {task.agent_role}"
            )

    return GeneratedTeam(
        team_name=team_config.get("team_name", ""),
        purpose=team_config.get("purpose", ""),
        template_used=team_config.get("template", ""),
        agents=agents,
        tasks=tasks,
        stack=team_config.get("stack"),
        constraints=team_config.get("constraints", []),
        tags=team_config.get("tags", []),
        documentation_level=team_config.get("documentation_level", "standard"),
        primary_framework=team_config.get("primary_framework", "crewai"),
        topology_pattern=team_config.get("topology_pattern", "sequential"),
        planner_reasoning=team_config.get("planner_reasoning", ""),
    )


def _load_yaml_file(path: Path, rel_label: str) -> dict:
    if not path.exists():
        raise TeamPackageError(f"Missing required file: {rel_label}")
    try:
        return load_yaml(path)
    except Exception as exc:
        raise TeamPackageError(f"Malformed YAML in {rel_label}: {exc}") from exc


def _require(cfg: dict, key: str, rel_label: str) -> object:
    """Fetch a required field, raising TeamPackageError (not a raw KeyError)
    if it's missing — covers a structurally-incomplete-but-parseable file
    (e.g. hand-edited), not just outright-missing or malformed-YAML files.
    """
    if key not in cfg:
        raise TeamPackageError(f"Missing required field '{key}' in {rel_label}")
    return cfg[key]


def _load_agent(package_path: Path, role: str, routing: dict) -> AgentSpec:
    rel = f"agents/{role}.yaml"
    cfg = _load_yaml_file(package_path / rel, rel)
    route_cfg = routing.get(role)
    if route_cfg is None:
        raise TeamPackageError(f"Missing routing entry for agent: {role}")
    resolved_role = _require(cfg, "role", rel)
    return AgentSpec(
        role=resolved_role,
        display_name=cfg.get("display_name", resolved_role),
        description=_require(cfg, "description", rel),
        goal=cfg.get("goal", ""),
        backstory=cfg.get("backstory", ""),
        capabilities=cfg.get("capabilities", []),
        tools=cfg.get("tools", []),
        routing=ProviderRouting(
            provider=_require(route_cfg, "provider", f"routing_config.yaml ({role})"),
            model=_require(route_cfg, "model", f"routing_config.yaml ({role})"),
            api_key_env=route_cfg.get("api_key_env"),
            base_url=route_cfg.get("base_url"),
        ),
        is_optional=cfg.get("is_optional", False),
        is_orchestrator=cfg.get("is_orchestrator", False),
    )


def _load_task(package_path: Path, name: str) -> TaskSpec:
    rel = f"tasks/{name}.yaml"
    cfg = _load_yaml_file(package_path / rel, rel)
    return TaskSpec(
        name=_require(cfg, "name", rel),
        description=_require(cfg, "description", rel),
        expected_output=cfg.get("expected_output", ""),
        agent_role=_require(cfg, "agent_role", rel),
        dependencies=cfg.get("dependencies", []),
        is_optional=cfg.get("is_optional", False),
    )
