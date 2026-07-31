"""CrewAI execution adapter (Story 1.5, AD-6, AD-7).

The only module in `team_maker/` allowed to import `crewai` at module scope —
`tests/unit/test_runtime_engine_port.py`'s guard test is narrowed to exclude
this package specifically (Task 6). Mirrors the proven LLM-construction shape
already used by the *generated* `crewai_runner.py.j2` template, but passes
credentials explicitly per agent (AD-7), never via a global `os.environ`
fallback like the template does.
"""
from __future__ import annotations

from crewai import LLM, Agent, Crew, Process, Task

from team_maker.domain.models import AgentSpec, GeneratedTeam, ProviderRouting
from team_maker.keyconfig import KeyConfig
from team_maker.ports.execution_engine import ExecutionEngine
from team_maker.runtime.ordering import topological_sort
from team_maker.runtime.results import RunResult, TaskResult

_OLLAMA_BASE_URL = "http://localhost:11434"


class CrewAIExecutionEngine(ExecutionEngine):
    """Executes a `GeneratedTeam` via real crewai `Agent`/`Task`/`Crew` objects."""

    def run(self, team: GeneratedTeam, key_config: KeyConfig, goal: str) -> RunResult:
        agents_by_role = {
            agent.role: self._build_agent(agent, key_config) for agent in team.agents
        }

        ordered_tasks = topological_sort(team.tasks)
        crewai_tasks: list[Task] = []
        crewai_tasks_by_name: dict[str, Task] = {}
        for task_spec in ordered_tasks:
            context = [
                crewai_tasks_by_name[dep]
                for dep in task_spec.dependencies
                if dep in crewai_tasks_by_name
            ]
            crewai_task = Task(
                description=task_spec.description,
                expected_output=task_spec.expected_output,
                agent=agents_by_role[task_spec.agent_role],
                context=context or None,
            )
            crewai_tasks_by_name[task_spec.name] = crewai_task
            crewai_tasks.append(crewai_task)

        crew = self._build_crew(team, agents_by_role, crewai_tasks)
        output = crew.kickoff(inputs={"goal": goal})

        if len(output.tasks_output) != len(ordered_tasks):
            raise RuntimeError(
                f"CrewAI returned {len(output.tasks_output)} task output(s) for "
                f"{len(ordered_tasks)} submitted task(s) — cannot map results reliably."
            )

        task_results = [
            TaskResult(
                name=task_spec.name,
                agent_role=task_spec.agent_role,
                output=str(task_output.raw),
            )
            for task_spec, task_output in zip(ordered_tasks, output.tasks_output)
        ]
        return RunResult(final_output=str(output.raw), task_results=task_results)

    @staticmethod
    def _build_crew(
        team: GeneratedTeam, agents_by_role: dict[str, Agent], tasks: list[Task]
    ) -> Crew:
        orchestrator = next((a for a in team.agents if a.is_orchestrator), None)
        if orchestrator is not None:
            # CrewAI validates that a hierarchical crew's manager_agent is NOT
            # also present in agents (crewai>=1.x — this rejects the pattern
            # the *generated* run_example.py template still uses; fixing that
            # template is out of this story's scope, see Dev Notes).
            workers = [
                agent
                for role, agent in agents_by_role.items()
                if role != orchestrator.role
            ]
            return Crew(
                agents=workers,
                tasks=tasks,
                process=Process.hierarchical,
                manager_agent=agents_by_role[orchestrator.role],
            )
        return Crew(
            agents=list(agents_by_role.values()),
            tasks=tasks,
            process=Process.sequential,
        )

    @classmethod
    def _build_agent(cls, agent: AgentSpec, key_config: KeyConfig) -> Agent:
        return Agent(
            role=agent.role,
            goal=agent.goal,
            backstory=agent.backstory,
            llm=cls._build_llm(agent.routing, key_config),
            allow_delegation=agent.is_orchestrator,
        )

    @staticmethod
    def _build_llm(routing: ProviderRouting, key_config: KeyConfig) -> LLM:
        if routing.provider == "ollama":
            return LLM(
                model=f"ollama/{routing.model}",
                base_url=routing.base_url or _OLLAMA_BASE_URL,
            )
        api_key = (
            key_config.keys[routing.provider].get_secret_value()
            if key_config.has(routing.provider)
            else None
        )
        return LLM(model=f"{routing.provider}/{routing.model}", api_key=api_key)
