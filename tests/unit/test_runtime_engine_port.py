"""Story 0.3 — RuntimeEngine port shape + adapter relocation under adapters/runtime_engines/.

Verifies the ports-and-adapters move: the RuntimeEngine ABC lives under team_maker/ports/,
each concrete engine subclasses it, get_runtime_engine's dict lookup preserves the exact
crewai fallback behavior of the old get_adapter, the dependency-pin lists are single-sourced
from the engines (locking the dedup so it can't silently drift from what requirements.txt
ships), and crewai is never imported at module scope anywhere in team_maker/ (AD-6 guard) —
**except** team_maker/adapters/runtime_crewai/, a single, deliberate exception carved out by
Story 1.5's in-process execution adapter (see that story's Dev Notes for why).
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from team_maker.adapters.runtime_engines import (
    AutoGenAdapter,
    CrewAIAdapter,
    LangGraphAdapter,
    get_runtime_engine,
)
from team_maker.pipeline.runner import PipelineRunner
from team_maker.ports.runtime_engine import RuntimeEngine
from team_maker.schema.request import StateBackend


def test_port_lives_in_ports_package():
    assert RuntimeEngine.__module__ == "team_maker.ports.runtime_engine"


def test_port_is_abstract():
    with pytest.raises(TypeError):
        RuntimeEngine()


@pytest.mark.parametrize(
    "framework,expected_type",
    [
        ("crewai", CrewAIAdapter),
        ("langgraph", LangGraphAdapter),
        ("autogen", AutoGenAdapter),
    ],
)
def test_get_runtime_engine_resolves_known_names(framework, expected_type):
    engine = get_runtime_engine(framework)
    assert isinstance(engine, expected_type)
    assert isinstance(engine, RuntimeEngine)
    assert engine.name == framework


def test_get_runtime_engine_unknown_falls_back_to_crewai():
    assert isinstance(get_runtime_engine("bogus"), CrewAIAdapter)


def test_crewai_extra_requirements_matches_single_sourced_list():
    assert CrewAIAdapter().extra_requirements() == [
        "crewai[google-genai]>=0.80.0",
        "crewai-tools>=0.25.0",
        "langchain-anthropic>=0.3.0",
        "langchain-google-genai>=2.0",
        "langchain-openai>=0.3.0",
        "langchain-ollama>=0.2.0",
    ]


def test_langgraph_extra_requirements_matches_single_sourced_list():
    assert LangGraphAdapter().extra_requirements() == [
        "langgraph>=0.2.0",
        "langchain-core>=0.3.0",
        "langchain-anthropic>=0.3.0",
        "langchain-google-genai>=2.0",
        "langchain-openai>=0.3.0",
        "langchain-ollama>=0.2.0",
    ]


def test_autogen_extra_requirements_matches_single_sourced_list():
    assert AutoGenAdapter().extra_requirements() == ["pyautogen>=0.2.0"]


@pytest.mark.parametrize(
    "framework,expected_type",
    [
        ("crewai", CrewAIAdapter),
        ("langgraph", LangGraphAdapter),
        ("autogen", AutoGenAdapter),
    ],
)
def test_render_requirements_plumbs_adapter_extra_requirements_through(framework, expected_type):
    """Locks the exact plumbing this story exists to protect: adapter.extra_requirements()
    must land verbatim in the generated requirements.txt, not a re-hardcoded copy."""
    engine = get_runtime_engine(framework)
    assert isinstance(engine, expected_type)
    rendered = PipelineRunner._render_requirements(
        framework, StateBackend.FILE, engine.extra_requirements()
    )
    for requirement in engine.extra_requirements():
        assert requirement in rendered


def _has_module_level_crewai_import(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.Import) and any(
            a.name == "crewai" or a.name.startswith("crewai.") for a in node.names
        ):
            return True
        if isinstance(node, ast.ImportFrom) and node.module and (
            node.module == "crewai" or node.module.startswith("crewai.")
        ):
            return True
    return False


def test_no_module_level_crewai_import_in_team_maker():
    """crewai may be imported at module scope in exactly one place:
    team_maker/adapters/runtime_crewai/ (Story 1.5's execution adapter,
    matching how team_maker/adapters/providers/anthropic_provider.py is the
    one legitimate place that imports the anthropic SDK). Everywhere else in
    team_maker/ — including the new team_maker/runtime/ package and
    team_maker/ports/execution_engine.py — must stay crewai-free."""
    root = Path(__file__).resolve().parents[2] / "team_maker"
    exempt_dir = root / "adapters" / "runtime_crewai"
    offenders = [
        str(path)
        for path in root.rglob("*.py")
        if not path.is_relative_to(exempt_dir) and _has_module_level_crewai_import(path)
    ]
    assert offenders == []


def test_runtime_and_execution_port_modules_stay_crewai_free():
    """Documents the intended boundary explicitly, rather than relying on it
    being incidentally true via the broader sweep above: the Runtime's own
    orchestration modules depend only on the ExecutionEngine port, never on
    crewai directly."""
    root = Path(__file__).resolve().parents[2] / "team_maker"
    must_stay_clean = [
        root / "runtime" / "executor.py",
        root / "runtime" / "loader.py",
        root / "runtime" / "ordering.py",
        root / "runtime" / "results.py",
        root / "ports" / "execution_engine.py",
    ]
    offenders = [str(path) for path in must_stay_clean if _has_module_level_crewai_import(path)]
    assert offenders == []
