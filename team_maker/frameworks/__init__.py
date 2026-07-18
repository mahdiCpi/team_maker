from team_maker.adapters.runtime_crewai.crewai_engine import CrewAIAdapter
from team_maker.frameworks.autogen_adapter import AutoGenAdapter
from team_maker.frameworks.base import FrameworkAdapter
from team_maker.frameworks.langgraph_adapter import LangGraphAdapter

_ADAPTERS: dict[str, FrameworkAdapter] = {
    "crewai": CrewAIAdapter(),
    "langgraph": LangGraphAdapter(),
    "autogen": AutoGenAdapter(),
}


def get_adapter(framework: str) -> FrameworkAdapter:
    return _ADAPTERS.get(framework, _ADAPTERS["crewai"])


__all__ = [
    "FrameworkAdapter",
    "CrewAIAdapter",
    "LangGraphAdapter",
    "AutoGenAdapter",
    "get_adapter",
]
