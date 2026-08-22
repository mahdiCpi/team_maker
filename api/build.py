"""The build route's call into `PipelineRunner`, and its response mapping (AC 2).

Between "spec is valid" and "package built" the CLI does almost nothing
(`cli.py:316-339`) — and neither does this. The one thing the API must add is
visibility into a silent rewrite: `normalize_team_routings` makes live calls to
each provider's `models.list()` and may substitute the chosen model with a
fuzzy nearest match, reporting it only to **stderr**
(`model_resolver.py:156-185`). Without surfacing that, the UI would tell the
user it built `gpt-4o` when it built `gpt-4o-mini`.
"""
from __future__ import annotations

import logging

from api.errors import BUILD_FAILED, OUTPUT_EXISTS, SPEC_INVALID, ApiError, FieldError, log_and_wrap
from api.routings import requested_routings, routing_label
from api.schemas import BuildView, ModelSubstitution, ValidationView
from team_maker.domain.models import GeneratedTeam
from team_maker.pipeline.runner import PipelineResult, PipelineRunner
from team_maker.schema.request import TeamCreationRequest

logger = logging.getLogger("api.build")


def run_build(request: TeamCreationRequest) -> BuildView:
    """Build the team package, mapping every failure onto an AC 2 error code."""
    # Task 5, Story 4.5: Guard empty desired_roles in build path
    # Align with edit route behavior (api/routers/compose.py:339-347)
    if not request.desired_roles:
        raise ApiError(
            SPEC_INVALID,
            "A team needs at least one role.",
            fields=[FieldError("desired_roles", "Add at least one role.")],
        )
    
    requested = _requested_labels(request)
    try:
        result = PipelineRunner().run(request)
    except FileExistsError as exc:
        raise log_and_wrap(
            OUTPUT_EXISTS,
            # Story 2.3 owns error copy, and this was the concrete defect
            # `deferred-work.md:153` recorded: the old wording said "choose a
            # different output path", which is the one remedy no client can take.
            # `output_path` is server-owned and read-only to the browser (AC 13),
            # derived from the team name and pinned for the session's life — so the
            # only remedies are the two named here, and the API tells the truth
            # about who owns the destination.
            "A directory already exists where this team would be written, so the "
            "build stopped rather than overwrite it. The destination is chosen by "
            "the server from the team's name; build a differently-named team, or "
            "remove the existing directory.",
            exc,
        ) from exc
    except Exception as exc:  # AC 8 — catch broadly, leak nothing
        raise log_and_wrap(
            BUILD_FAILED,
            "The team package could not be built. The error has been logged on "
            "the server.",
            exc,
        ) from exc
    return _to_view(result, requested)


def _to_view(result: PipelineResult, requested: dict[str, str]) -> BuildView:
    return BuildView(
        team_name=result.team.team_name,
        output_path=str(result.output_path),
        agent_count=len(result.team.agents),
        task_count=len(result.team.tasks),
        written_file_count=len(result.written_files),
        model_substitutions=_substitutions(requested, result.team),
        validation=ValidationView(
            passed=result.validation.passed,
            issues=list(result.validation.issues),
            warnings=list(result.validation.warnings),
        ),
    )


def _requested_labels(request: TeamCreationRequest) -> dict[str, str]:
    """`{role: "provider/model"}` for what each role asked for, pre-normalisation.

    The resolution itself lives in `api/routings.py`, shared with the key check
    (Story 2.3 AC 2) so the `role.llm -> default_llm -> default` order is not
    encoded twice. This only re-labels it into the form the report compares on.
    """
    return {
        role: routing_label(routing)
        for role, routing in requested_routings(request).items()
    }


def _substitutions(requested: dict[str, str], team: GeneratedTeam) -> list[ModelSubstitution]:
    changes: list[ModelSubstitution] = []
    for agent in team.agents:
        before = requested.get(agent.role)
        after = routing_label(agent.routing)
        if before is not None and before != after:
            changes.append(
                ModelSubstitution(role=agent.role, requested=before, resolved=after)
            )
    return changes
