"""Inject a run's goal and attached documents into a team (Story 2.4 AC 5, AC 6).

Pure: no disk, no network, no clock. Returns a *new* `GeneratedTeam` whose
`TaskSpec`s carry the goal (and any documents) appended to their
`description` — the only field a run's own text belongs in. An agent's
`goal`/`backstory` are its standing identity across every run; the user's
goal belongs to *this* run's work, which is what a task's description is for.

## Why every task, not only the first in topological order

Every task receives the same run context rather than only the first: crewai's
inter-task ``context=`` wiring (`crewai_execution_engine.py`) forwards a prior
task's *output* to a dependent task, never the original run text, so a later
task's agent would otherwise never see the goal or the documents at all. The
cost is real — the goal and every document's text is repeated into every
task's prompt — and is declared, not hidden, in the story's Completion Notes.

## Why every object here is rebuilt rather than mutated

`GeneratedTeam`, `AgentSpec` and `TaskSpec` are all plain, mutable
`@dataclass`es (`domain/models.py:58,88,110`) and none of them is frozen —
correcting this story's own Dev Notes, which named `ProviderRouting`
(`:11-12`) as the one frozen dataclass in that file. The dataclass that is
actually frozen, at `:29-30`, is `ResolvedCredential`, which this module never
touches. Since nothing here is frozen, a bare `dataclasses.replace()` on the
team would still share the *same* `TaskSpec` instances underneath, and writing
a new description through it would mutate the caller's team object. New
`TaskSpec` instances are built instead, so neither `team` nor any of its tasks
is ever mutated in place.

## Why `crew.kickoff()` is never called with `inputs=` once this runs

Measured against the installed crewai (1.14.6): ``crew.kickoff(inputs={...})``
runs crewai's own ``{token}`` template interpolation over every task
description, and a description holding an unrelated, unmatched ``{brace}``
raises ``ValueError`` from crewai itself — so a user pasting a goal or a
document containing ``{``/``}`` would crash the run. Omitting ``inputs=``
disables that interpolation entirely and literal braces pass through as plain
text, which is what lets this module inject arbitrary user text safely. See
`crewai_execution_engine.py` for the call site this justifies.
"""
from __future__ import annotations

import dataclasses
from collections.abc import Sequence

from team_maker.domain.models import GeneratedTeam

#: The heading that marks an injected run-context block. Written by
#: `_run_context_block` and read back by `goal_is_injected` — the two live in
#: this one module deliberately, so the guard checks the mechanism's own
#: marker rather than a second, driftable copy of the format.
_GOAL_HEADING = "--- This run's goal ---"


class GoalNotInjectedError(Exception):
    """An engine was handed a goal the run-context path never wove into the tasks.

    A caller that builds an `ExecutionEngine` and calls `run(team, credentials,
    goal)` on a team straight out of `load_team_package` gets a run that
    executes the package's stock task descriptions and silently discards the
    goal — the exact defect Story 2.4 AC 5 exists to fix, reintroduced one
    layer down. `ExecutionEngine.run`'s signature is pinned by Story 1.7 AC 7
    and cannot grow a parameter to make the dependency explicit, so the
    contract is enforced instead: engines refuse a goal they cannot honour
    rather than accepting one they will ignore.
    """


@dataclasses.dataclass(frozen=True)
class RunDocument:
    """One attached, already-decoded text document (Story 2.4 AC 6)."""

    name: str
    text: str


def augment_team_for_run(
    team: GeneratedTeam,
    goal: str,
    *,
    documents: Sequence[RunDocument] = (),
) -> GeneratedTeam:
    """Return a new `GeneratedTeam` whose every task carries *goal* and *documents*.

    Neither `team` nor any of its `TaskSpec` objects is mutated — see the
    module docstring for why that matters here specifically.
    """
    suffix = _run_context_block(goal, documents)
    new_tasks = [
        dataclasses.replace(task, description=task.description + suffix) for task in team.tasks
    ]
    return dataclasses.replace(team, tasks=new_tasks)


def goal_is_injected(team: GeneratedTeam, goal: str) -> bool:
    """Whether *goal* has actually been woven into *team*'s task descriptions.

    True when every task carries both this module's own heading (proving the
    run-context path ran at all) and the goal text itself (proving it was
    *this* goal). Checking both is what makes the guard robust: the heading
    alone would pass a team augmented with a different goal, and the goal text
    alone could coincide with a package's stock wording for a very short goal.

    Two cases are satisfied vacuously, and deliberately:

    * **A goal that is blank once stripped.** There is nothing that could be
      silently ignored, so there is nothing to refuse. `api/schemas.py` already
      rejects a blank goal at the edge; the CLI does not, and failing a CLI run
      that never had a goal to lose would be a new refusal, not a fixed defect.
    * **A team with no tasks.** No description exists to carry the goal, so no
      agent can be handed one — the run has a different problem, and reporting
      this one would misname it.
    """
    if not goal.strip():
        return True
    return all(
        _GOAL_HEADING in task.description and goal in task.description for task in team.tasks
    )


def require_goal_injected(team: GeneratedTeam, goal: str) -> None:
    """Raise `GoalNotInjectedError` unless *goal* reached *team*'s descriptions.

    Called by an engine before it starts work. `run_team_package` satisfies
    this by construction — it calls `augment_team_for_run` before reaching the
    engine — so the only callers this can fire for are ones that bypassed the
    Runtime's single run-context path.
    """
    if goal_is_injected(team, goal):
        return
    raise GoalNotInjectedError(
        "This engine was given a goal that is not present in the team's task "
        "descriptions, so running would silently discard it. Build the runnable "
        "team with `run_context.augment_team_for_run(team, goal, documents=...)` "
        "first — `runtime.executor.run_team_package` already does."
    )


def _run_context_block(goal: str, documents: Sequence[RunDocument]) -> str:
    lines = ["", "", _GOAL_HEADING, goal]
    for document in documents:
        lines += ["", f'--- Attached document: "{document.name}" ---', document.text]
    return "\n".join(lines)
