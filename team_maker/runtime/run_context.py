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


def _run_context_block(goal: str, documents: Sequence[RunDocument]) -> str:
    lines = ["", "", "--- This run's goal ---", goal]
    for document in documents:
        lines += ["", f'--- Attached document: "{document.name}" ---', document.text]
    return "\n".join(lines)
