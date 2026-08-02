"""Round-trip tests for the Team Package loader (Story 1.5, AC 1). Fully
offline — builds a real package with the existing Factory, then loads it back.
"""
from __future__ import annotations

import pytest

from team_maker.pipeline.runner import PipelineRunner
from team_maker.runtime.loader import TeamPackageError, load_team_package


def test_round_trip_minimal_request(minimal_request):
    result = PipelineRunner().run(minimal_request)

    team = load_team_package(result.output_path)

    assert team.team_name == minimal_request.team_name
    assert team.purpose == minimal_request.purpose
    assert [a.role for a in team.agents] == [a.role for a in result.team.agents]
    assert [t.name for t in team.tasks] == [t.name for t in result.team.tasks]


def test_round_trip_preserves_routing_and_orchestrator_flags(full_request):
    result = PipelineRunner().run(full_request)

    team = load_team_package(result.output_path)

    by_role = {a.role: a for a in team.agents}
    original_by_role = {a.role: a for a in result.team.agents}
    for role, agent in by_role.items():
        original = original_by_role[role]
        assert agent.routing.provider == original.routing.provider
        assert agent.routing.model == original.routing.model
        assert agent.routing.api_key_env == original.routing.api_key_env
        assert agent.is_orchestrator == original.is_orchestrator
        assert agent.is_optional == original.is_optional


def test_round_trip_preserves_task_dependencies(full_request):
    result = PipelineRunner().run(full_request)

    team = load_team_package(result.output_path)

    by_name = {t.name: t for t in team.tasks}
    original_by_name = {t.name: t for t in result.team.tasks}
    for name, task in by_name.items():
        original = original_by_name[name]
        assert task.agent_role == original.agent_role
        assert task.dependencies == original.dependencies


def test_round_trip_preserves_ollama_base_url(tmp_path):
    from team_maker.schema.request import ProviderConfig, RoleDefinition, TeamCreationRequest

    request = TeamCreationRequest(
        team_name="Ollama Team",
        purpose="A team routed through a local Ollama model for this test.",
        output_path=str(tmp_path / "ollama_team"),
        desired_roles=[
            RoleDefinition(
                name="architect",
                description="Designs system architecture and makes technical decisions.",
                llm=ProviderConfig(provider="ollama", model="llama3.2"),
            )
        ],
    )
    result = PipelineRunner().run(request)

    team = load_team_package(result.output_path)

    [agent] = team.agents
    assert agent.routing.provider == "ollama"
    # Compose-rewritten by the Factory (an Ollama agent triggers the sidecar
    # stack) — must survive the round-trip, not be silently discarded.
    assert agent.routing.base_url == "http://ollama:11434"


def test_missing_required_field_in_agent_file_raises_clear_error(minimal_request):
    import yaml

    result = PipelineRunner().run(minimal_request)
    agent_path = result.output_path / "agents" / "architect.yaml"
    data = yaml.safe_load(agent_path.read_text(encoding="utf-8"))
    del data["description"]
    agent_path.write_text(yaml.safe_dump(data), encoding="utf-8")

    with pytest.raises(TeamPackageError, match="description"):
        load_team_package(result.output_path)


def test_task_referencing_unknown_agent_role_raises_clear_error(minimal_request):
    import yaml

    result = PipelineRunner().run(minimal_request)
    task_files = list((result.output_path / "tasks").glob("*.yaml"))
    assert task_files, "expected at least one task file from minimal_request"
    task_path = task_files[0]
    data = yaml.safe_load(task_path.read_text(encoding="utf-8"))
    data["agent_role"] = "nonexistent_role"
    task_path.write_text(yaml.safe_dump(data), encoding="utf-8")

    with pytest.raises(TeamPackageError, match="unknown agent_role"):
        load_team_package(result.output_path)


def test_missing_package_directory_raises_clear_error(tmp_path):
    with pytest.raises(TeamPackageError, match="not found"):
        load_team_package(tmp_path / "does_not_exist")


def test_missing_team_config_raises_clear_error(tmp_path):
    package_dir = tmp_path / "broken_team"
    package_dir.mkdir()

    with pytest.raises(TeamPackageError, match="team_config.yaml"):
        load_team_package(package_dir)


def test_missing_agent_file_raises_clear_error(minimal_request):
    result = PipelineRunner().run(minimal_request)
    (result.output_path / "agents" / "architect.yaml").unlink()

    with pytest.raises(TeamPackageError, match="architect.yaml"):
        load_team_package(result.output_path)


def test_malformed_yaml_raises_clear_error(minimal_request):
    result = PipelineRunner().run(minimal_request)
    (result.output_path / "team_config.yaml").write_text(
        "not: valid: yaml: [unterminated", encoding="utf-8"
    )

    with pytest.raises(TeamPackageError, match="Malformed YAML"):
        load_team_package(result.output_path)
