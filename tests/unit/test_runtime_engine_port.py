"""Story 0.3 — RuntimeEngine port shape + CrewAIAdapter behind the port.

Verifies the ports-and-adapters move: the RuntimeEngine port lives under
team_maker/ports/, CrewAIAdapter satisfies it structurally (no ABC), it is reachable
from its new adapters/runtime_crewai location and through the back-compat frameworks
registry, and the exact crewai==1.14.6 pin (AD-7) is present.
"""
from __future__ import annotations

from team_maker.adapters.runtime_crewai import CrewAIAdapter
from team_maker.frameworks import get_adapter
from team_maker.pipeline.runner import PipelineRunner
from team_maker.ports.runtime_engine import RuntimeEngine
from team_maker.schema.request import StateBackend


def test_port_lives_in_ports_package():
    assert RuntimeEngine.__module__ == "team_maker.ports.runtime_engine"


def test_stub_with_all_members_satisfies_port():
    class Stub:
        @property
        def name(self):  # noqa: ANN201
            return "stub"

        def render_runner(self, team, notifications=None):  # noqa: ANN001, ANN201
            return ""

        def extra_requirements(self):  # noqa: ANN201
            return []

    assert isinstance(Stub(), RuntimeEngine)


def test_object_missing_members_does_not_satisfy_port():
    class NotAnEngine:
        pass

    assert not isinstance(NotAnEngine(), RuntimeEngine)


def test_crewai_adapter_satisfies_port():
    assert isinstance(CrewAIAdapter(), RuntimeEngine)


def test_crewai_adapter_pin_is_exactly_1_14_6():
    assert "crewai[google-genai]==1.14.6" in CrewAIAdapter().extra_requirements()


def test_backcompat_shim_still_importable():
    from team_maker.frameworks.crewai_adapter import CrewAIAdapter as ShimAdapter

    assert ShimAdapter is CrewAIAdapter


def test_get_adapter_crewai_still_satisfies_port():
    adapter = get_adapter("crewai")
    assert isinstance(adapter, RuntimeEngine)
    assert adapter.name == "crewai"


def test_runner_render_requirements_uses_exact_crewai_pin():
    reqs = PipelineRunner._render_requirements("crewai", StateBackend.FILE)
    assert "crewai[google-genai]==1.14.6" in reqs
