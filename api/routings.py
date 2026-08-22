"""What provider/model each role asked for, before the pipeline normalises it.

Two routes need this and neither may re-derive it. The build route reports model
substitutions against it (`api/build.py`), and the key check resolves each role's
required provider from it (`api/routers/keys.py`, Story 2.3 AC 2).

It is obtained by running the same public template the pipeline runs
(``PipelineRunner._generate_from_template`` -> ``get_template(...).generate()``),
which is a pure in-memory transform: no disk, no network, no clock
(project-context, "Generators are pure string producers"). That is deliberate.
The alternative was re-encoding the ``role.llm -> default_llm ->
anthropic/claude-sonnet-4-6`` resolution order here, and a second source of truth
for a rule that already exists in one place is the defect class this repo has
shipped twice (Story 2.1's contrast test read a mirror of the shipped CSS).

Nothing under ``team_maker/`` is modified by calling this.
"""
from __future__ import annotations

import logging

from team_maker.domain.models import ProviderRouting
from team_maker.schema.request import TeamCreationRequest
from team_maker.utils.text_sanitizer import log_exception_safely

logger = logging.getLogger("api.routings")

def requested_routings(request: TeamCreationRequest) -> dict[str, ProviderRouting]:
    """``{role name: resolved routing}`` for every role the client asked for.

    Returns ``{}`` for the planner path (empty ``desired_roles``), where the team
    is invented by an LLM at build time and there is no client-requested routing
    to report — and ``{}`` if the template raises, because both callers use this
    for *reporting* and neither may fail on account of it.
    
    Uses the same template selection logic as the pipeline (PipelineRunner) to
    ensure consistency: request.template_id if provided, otherwise defaults to
    'software_delivery_team'.
    
    Story 4.6 Task 9: Fix hardcoded _TEMPLATE_ID in routings
    """
    if not request.desired_roles:
        logger.info("request has no desired_roles; per-role routings are unknown")
        return {}
    try:
        # Imported inside the guard, not at module scope. `api/routings` is imported
        # by `api/build` and `api/routers/keys`, hence by `api/main`, so a
        # module-scope import would turn any fault reachable from
        # `team_maker.templates` into a server that will not start — including
        # `/api/health` — where the contract below is that it degrades to `{}`.
        import team_maker.templates  # noqa: F401 — importing registers the templates
        from team_maker.templates.registry import DEFAULT_TEMPLATE_ID, get_template

        # Use the same template selection logic as PipelineRunner
        # to ensure reporting and builds use identical template resolution
        template_id = request.template_id or DEFAULT_TEMPLATE_ID
        pre = get_template(template_id).generate(request)
    except Exception as exc:  # never let reporting break a build or a status read
        # Use safe logging to prevent sensitive data from leaking
        # Per AD-9: keys and sensitive data must never be logged
        log_exception_safely(logger, "could not pre-resolve requested routings", exc)
        return {}
    return {agent.role: agent.routing for agent in pre.agents}


def routing_label(routing: ProviderRouting) -> str:
    """``provider/model`` — the form the build report and the UI both show."""
    return f"{routing.provider}/{routing.model}"
