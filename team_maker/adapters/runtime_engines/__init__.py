from team_maker.adapters.runtime_engines.autogen_engine import AutoGenAdapter
from team_maker.adapters.runtime_engines.crewai_engine import CrewAIAdapter
from team_maker.adapters.runtime_engines.langgraph_engine import LangGraphAdapter
from team_maker.ports.runtime_engine import RuntimeEngine

_ENGINES: dict[str, RuntimeEngine] = {
    "crewai": CrewAIAdapter(),
    "langgraph": LangGraphAdapter(),
    "autogen": AutoGenAdapter(),
}


def get_runtime_engine(name: str) -> RuntimeEngine:
    return _ENGINES.get(name, _ENGINES["crewai"])


__all__ = [
    "RuntimeEngine",
    "CrewAIAdapter",
    "LangGraphAdapter",
    "AutoGenAdapter",
    "get_runtime_engine",
]
