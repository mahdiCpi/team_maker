"""CrewAI execution adapter (Story 1.5, AD-6, AD-7; Story 1.6).

The only module in `team_maker/` allowed to import `crewai` at module scope —
the guard test in `tests/.../test_runtime_engine_port.py` is narrowed to exclude
this package specifically.

Since Story 1.6 this adapter is a pure translator: it receives per-agent
credentials already resolved by `runtime/preflight.py` and turns them into
crewai objects. It never sees a `KeyConfig`, never consults the provider
catalog, and performs no credential lookup of its own (AD-7). Provider-specific
facts (local endpoints, OpenRouter gateway form) are resolved upstream from
catalog data, which is why no `provider == "..."` branch survives here.

Note the precise scope of that guarantee: this adapter does no ambient lookup,
but crewai *will* read the provider's env var if it is handed an `LLM` with no
`api_key`. That is why `_build_llm` always passes `api_key` explicitly, even
when it is `None` — see the comment there.
"""
from __future__ import annotations

from crewai import LLM, Agent, Crew, Process, Task

from team_maker.adapters.runtime_crewai.transcript_capture import TranscriptRecorder
from team_maker.domain.models import AgentSpec, GeneratedTeam, ResolvedCredential
from team_maker.ports.execution_engine import ExecutionEngine
from team_maker.runtime.ordering import topological_sort
from team_maker.runtime.results import RunResult, TaskResult, TranscriptEntry
from team_maker.runtime.run_context import require_goal_injected


class CrewAIExecutionEngine(ExecutionEngine):
    """Executes a `GeneratedTeam` via real crewai `Agent`/`Task`/`Crew` objects."""

    def run(
        self,
        team: GeneratedTeam,
        credentials: dict[str, ResolvedCredential],
        goal: str,
    ) -> RunResult:
        # Before anything is built, and before any spend: refuse a goal this
        # engine cannot honour. `goal` is not read anywhere below — the run's
        # goal reaches the model through every task's `description`, woven in
        # by `run_context.augment_team_for_run` upstream — so an unaugmented
        # team would execute the package's stock descriptions and discard the
        # user's goal in silence. `ExecutionEngine.run`'s signature is pinned
        # by Story 1.7 AC 7 and cannot express that dependency in types, so it
        # is enforced here instead (Story 2.4 review, decision 2).
        require_goal_injected(team, goal)

        agents_by_role = {
            agent.role: self._build_agent(agent, credentials[agent.role])
            for agent in team.agents
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
                # `name` matters beyond cosmetics: crewai stamps it onto the
                # run events the transcript is built from, and without it crewai
                # falls back to the description. The transcript would then
                # attribute entries to "Design it." while `task_results` calls
                # the same task "design", leaving a consumer unable to line the
                # two up (Story 1.7).
                name=task_spec.name,
                description=task_spec.description,
                expected_output=task_spec.expected_output,
                agent=agents_by_role[task_spec.agent_role],
                context=context or None,
            )
            crewai_tasks_by_name[task_spec.name] = crewai_task
            crewai_tasks.append(crewai_task)

        crew = self._build_crew(team, agents_by_role, crewai_tasks)

        # Capture is unconditional and the recorder is local to this call — never
        # on `self`, which is stateless by design and reused across runs. The
        # context manager guarantees handlers come off the process-global event
        # bus even if kickoff raises (Story 1.7).
        # Declared owners, so a task-boundary entry is attributed to the role
        # that owns the task rather than to the manager crewai rebinds onto it
        # in a hierarchical crew — which would contradict `task_results`.
        task_owners = {spec.name: spec.agent_role for spec in ordered_tasks}

        # AC 1: Return partial transcript on failed runs (Story 4.4). The
        # recorder variable is assigned by __enter__ before the block executes,
        # so it remains accessible even if kickoff raises.
        recorder = None
        try:
            with TranscriptRecorder(task_owners) as recorder:
                # No `inputs=` (Story 2.4 AC 5): the goal already lives in every
                # task's `description` by the time this method runs
                # (`run_context.augment_team_for_run`, called from
                # `executor.run_team_package` before the engine is ever reached).
                # Measured against the installed crewai: passing `inputs=` here
                # runs crewai's own `{token}` template interpolation over every
                # description, and an unrelated, unmatched brace in user-typed
                # text raises `ValueError` — exactly the shape of text a pasted
                # goal or document can contain. Omitting `inputs=` disables that
                # interpolation entirely, so literal braces survive as plain
                # text. `goal` stays a parameter of this method only because
                # `ExecutionEngine.run`'s signature is pinned (Story 1.7 AC 7, for
                # the v2 streaming retrofit); it is not read here, and the guard at
                # the top of this method is what stops that from meaning "silently
                # discarded".
                output = crew.kickoff()
            transcript: list[TranscriptEntry] = recorder.entries() if recorder else []
        except Exception as exc:
            # Kickoff failed: return the partial transcript (AC 1) *and* the
            # failure itself via `RunResult.error` — a caller must still learn
            # the run failed (Story 4.4 review finding). Even though kickoff
            # raised, the context manager's __exit__ has already run, flushing
            # the bus and unsubscribing, so the entries collected before the
            # failure are safe to read from `recorder`.
            partial_transcript: list[TranscriptEntry] = recorder.entries() if recorder else []
            return RunResult(
                final_output="",
                task_results=[],
                transcript=partial_transcript,
                error=str(exc),
            )

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
        return RunResult(
            final_output=str(output.raw),
            task_results=task_results,
            transcript=transcript,
        )

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
    def _build_agent(cls, agent: AgentSpec, credential: ResolvedCredential) -> Agent:
        return Agent(
            role=agent.role,
            goal=agent.goal,
            backstory=agent.backstory,
            llm=cls._build_llm(credential),
            allow_delegation=agent.is_orchestrator,
        )

    @staticmethod
    def _build_llm(credential: ResolvedCredential) -> LLM:
        """Translate one resolved credential into a crewai `LLM`.

        ``api_key`` is always passed, including when it is ``None``. Omitting it
        is not neutral: crewai falls back to reading the provider's environment
        variable, which is exactly the ambient-credential path AD-7 forbids.
        Verified against the installed engine — ``LLM(model="anthropic/...")``
        with the kwarg omitted comes back holding whatever ``ANTHROPIC_API_KEY``
        happens to be in the process environment.

        ``base_url`` *is* omitted when unset, so crewai can apply its own
        per-provider default (notably the OpenRouter gateway's).
        """
        kwargs: dict[str, object] = {
            "model": credential.model,
            "api_key": credential.api_key,
        }
        if credential.base_url is not None:
            kwargs["base_url"] = credential.base_url
        return LLM(**kwargs)
