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
import re
import uuid
from collections.abc import Sequence
from typing import Final

from team_maker.domain.models import GeneratedTeam

#: The heading that marks an injected run-context block. Written by
#: `_run_context_block` and read back by `goal_is_injected` — the two live in
#: this one module deliberately, so the guard checks the mechanism's own
#: marker rather than a second, driftable copy of the format.
#:
#: To prevent spoofing (deferred-work.md:243), the delimiter now includes a UUID
#: that is unique per run and cannot be guessed by document content.
#: The delimiter format is: --- RUN_CONTEXT:<uuid>:GOAL ---
#: This ensures that even if document text contains similar patterns, it cannot
#: spoof the actual delimiter because the UUID is unique and non-guessable.
_GOAL_HEADING_PREFIX: Final = "--- RUN_CONTEXT:"
_GOAL_HEADING_SUFFIX: Final = ":GOAL ---"
_DOCUMENT_HEADING_PREFIX: Final = "--- RUN_CONTEXT:"
_DOCUMENT_HEADING_SUFFIX: Final = ":DOCUMENT ---"


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
    run_context_id: str | None = None,
) -> GeneratedTeam:
    """Return a new `GeneratedTeam` whose every task carries *goal* and *documents*.

    Neither `team` nor any of its `TaskSpec` objects is mutated — see the
    module docstring for why that matters here specifically.
    
    Args:
        team: The team to augment.
        goal: The goal to inject.
        documents: The documents to inject.
        run_context_id: Optional unique identifier for this run context. If not
                       provided, a new UUID will be generated to prevent delimiter
                       spoofing (per deferred-work.md:243).
    """
    if run_context_id is None:
        run_context_id = str(uuid.uuid4())
    
    suffix = _run_context_block(goal, documents, run_context_id)
    new_tasks = [
        dataclasses.replace(task, description=task.description + suffix) for task in team.tasks
    ]
    return dataclasses.replace(team, tasks=new_tasks)


_GOAL_HEADING_PATTERN: Final = re.compile(
    r"\-\-\- RUN_CONTEXT:([a-f0-9\-]+):GOAL \-\-\-"
)


def goal_is_injected(team: GeneratedTeam, goal: str) -> bool:
    """Whether *goal* has actually been woven into *team*'s task descriptions.

    True when every task carries this module's own heading, immediately
    followed by the goal text itself, and every task's heading carries the
    *same* run-context id.

    Checking structural adjacency (heading directly followed by the goal, the
    exact shape `_run_context_block` builds) rather than "heading present
    somewhere and goal text present somewhere" is what closes the gap a code
    review found (P5/deferred-work.md:243): a document or goal that merely
    contains a heading-shaped string *and*, independently, the goal text
    elsewhere in the description would have satisfied the old, looser check.
    Requiring every task to share one id additionally proves all of them came
    from the same `augment_team_for_run` call, not from independently
    spoofed per-task headings.

    This still cannot compare against the run's *actual* `run_context_id`:
    `augment_team_for_run` generates it internally and `ExecutionEngine.run`'s
    signature is pinned (Story 1.7 AC 7) and cannot grow a parameter to carry
    it through to this check. `run_team_package` is the only caller today and
    always generates a fresh UUID before the goal/documents are processed, so
    this is not currently exploitable — but the fix above is the strongest
    available without widening that pinned interface.

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
    if not team.tasks:
        return True

    run_context_ids: set[str] = set()
    for task in team.tasks:
        match = _GOAL_HEADING_PATTERN.search(task.description)
        if match is None:
            return False
        if f"{match.group(0)}\n{goal}" not in task.description:
            return False
        run_context_ids.add(match.group(1))

    return len(run_context_ids) == 1


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


def _run_context_block(goal: str, documents: Sequence[RunDocument], run_context_id: str) -> str:
    """Build the run context block with unique, non-guessable delimiters.
    
    Args:
        goal: The goal text to inject.
        documents: The documents to inject.
        run_context_id: The unique identifier for this run context.
    
    Returns:
        The formatted run context block with secure delimiters.
    """
    # Use unique delimiters with the run context ID to prevent spoofing
    # Format: --- RUN_CONTEXT:<uuid>:GOAL ---
    goal_heading = f"{_GOAL_HEADING_PREFIX}{run_context_id}{_GOAL_HEADING_SUFFIX}"
    
    lines = ["", "", goal_heading, goal]
    for document in documents:
        # Format: --- RUN_CONTEXT:<uuid>:DOCUMENT:<doc_name> ---
        # The UUID ensures this cannot be spoofed by document content
        doc_heading = f"{_DOCUMENT_HEADING_PREFIX}{run_context_id}:DOCUMENT:{document.name}{_DOCUMENT_HEADING_SUFFIX}"
        lines += ["", doc_heading, document.text]
    return "\n".join(lines)
