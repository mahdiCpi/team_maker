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

from api.errors import BUILD_FAILED, OUTPUT_EXISTS, log_and_wrap
from api.schemas import BuildView, ModelSubstitution, ValidationView
from team_maker.domain.models import GeneratedTeam, ProviderRouting
from team_maker.pipeline.runner import PipelineResult, PipelineRunner
from team_maker.schema.request import TeamCreationRequest

logger = logging.getLogger("api.build")


def run_build(request: TeamCreationRequest) -> BuildView:
    """Build the team package, mapping every failure onto an AC 2 error code."""
    requested = _requested_routings(request)
    try:
        result = PipelineRunner().run(request)
    except FileExistsError as exc:
        raise log_and_wrap(
            OUTPUT_EXISTS,
            "A directory already exists at the team's output path, and this build "
            "will not overwrite it. Choose a different output path, or remove the "
            "existing directory.",
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


def _requested_routings(request: TeamCreationRequest) -> dict[str, str]:
    """What model each role asked for, *before* the pipeline normalises it.

    Obtained by running the same public template the pipeline runs
    (`PipelineRunner._generate_from_template` -> `get_template(...).generate()`),
    which is a pure in-memory transform: no disk, no network, no clock
    (project-context, "Generators are pure string producers"). That is
    deliberate — the alternative was re-encoding the
    `role.llm -> default_llm -> anthropic/claude-sonnet-4-6` resolution order
    here, which would be a second source of truth for a rule that already
    exists in one place. Nothing under `team_maker/` is modified.

    Returns `{}` for the planner path (empty `desired_roles`), where the team
    is invented by an LLM and there is no client-requested model to compare to.
    """
    if not request.desired_roles:
        logger.info("build has no desired_roles; model substitutions cannot be reported")
        return {}
    try:
        import team_maker.templates  # noqa: F401 — triggers template registration
        from team_maker.templates.registry import get_template

        pre = get_template("software_delivery_team").generate(request)
    except Exception:  # never let reporting break a build
        logger.exception("could not pre-resolve requested routings")
        return {}
    return {agent.role: _routing_label(agent.routing) for agent in pre.agents}


def _substitutions(requested: dict[str, str], team: GeneratedTeam) -> list[ModelSubstitution]:
    changes: list[ModelSubstitution] = []
    for agent in team.agents:
        before = requested.get(agent.role)
        after = _routing_label(agent.routing)
        if before is not None and before != after:
            changes.append(
                ModelSubstitution(role=agent.role, requested=before, resolved=after)
            )
    return changes


def _routing_label(routing: ProviderRouting) -> str:
    return f"{routing.provider}/{routing.model}"
