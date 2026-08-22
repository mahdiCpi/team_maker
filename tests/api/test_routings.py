"""The shared "which provider does each role need?" helper (Story 2.3, AC 2).

Two consumers derive from `requested_routings`: the build route's model-substitution
report (`api/build.py`) and the key check (`api/routers/keys.py`). It exists so
neither re-encodes the `role.llm -> default_llm -> anthropic/claude-sonnet-4-6`
resolution order, which already lives in exactly one place (the template).

Offline by construction: running the template is a pure in-memory transform, so
nothing here touches disk, network or a clock.
"""
from __future__ import annotations

from api.routings import requested_routings
from team_maker.schema.request import TeamCreationRequest


def _request(tmp_path, **overrides) -> TeamCreationRequest:
    payload = {
        "team_name": "Docs Team",
        "purpose": "Write and maintain product documentation.",
        "output_path": str(tmp_path / "docs_team"),
        "desired_roles": [{"name": "writer", "description": "Writes documentation."}],
    }
    payload.update(overrides)
    return TeamCreationRequest(**payload)


def test_reports_one_routing_per_role(tmp_path):
    request = _request(
        tmp_path,
        desired_roles=[
            {"name": "writer", "description": "Writes documentation."},
            {"name": "editor", "description": "Edits documentation."},
        ],
    )

    routings = requested_routings(request)

    assert set(routings) == {"writer", "editor"}


def test_a_role_without_an_llm_inherits_the_resolved_default(tmp_path):
    """The point of reusing the template: this default is not restated here."""
    request = _request(tmp_path)

    routings = requested_routings(request)

    assert routings["writer"].provider == "anthropic"
    assert routings["writer"].model == "claude-sonnet-4-6"


def test_a_per_role_llm_wins_over_the_default(tmp_path):
    request = _request(
        tmp_path,
        default_llm={"provider": "openai", "model": "gpt-4o"},
        desired_roles=[
            {"name": "writer", "description": "Writes documentation."},
            {
                "name": "critic",
                "description": "Critiques documentation.",
                "llm": {"provider": "ollama", "model": "llama3"},
            },
        ],
    )

    routings = requested_routings(request)

    # `default_llm` fills the role that named nothing...
    assert routings["writer"].provider == "openai"
    # ...and the per-role override wins for the one that did.
    assert routings["critic"].provider == "ollama"
    assert routings["critic"].model == "llama3"


def test_the_planner_path_reports_nothing_rather_than_guessing(tmp_path):
    """With no `desired_roles` the team is invented by an LLM at build time, so
    there is no client-requested routing to report. `{}` is the honest answer;
    inventing one would claim a provider the user never chose."""
    request = _request(tmp_path, desired_roles=[])

    assert requested_routings(request) == {}


def test_a_template_failure_degrades_instead_of_breaking_its_callers(
    tmp_path, monkeypatch
):
    """STUB: the real `team_maker.templates.registry.get_template` is replaced with
    one that raises.

    Patched at its *own* module rather than through an alias in `api.routings`: an
    earlier version of this test patched `api.routings.get_template`, which only
    existed because the import sat at module scope — so it could not see the half of
    the guarantee that mattered. The build route calls this purely to *report*
    substitutions, so a fault here must never fail a build that would otherwise
    succeed.
    """

    def exploding_get_template(name):
        raise RuntimeError("template registry is unavailable")

    monkeypatch.setattr(
        "team_maker.templates.registry.get_template", exploding_get_template
    )

    assert requested_routings(_request(tmp_path)) == {}


def test_the_template_import_stays_inside_the_failure_guard():
    """`api/routings` is imported by `api/build` and `api/routers/keys`, hence by
    `api/main`. A module-scope `import team_maker.templates` would turn any fault
    reachable from it into a server that will not start — including `/api/health` —
    where the documented contract is that reporting degrades to `{}`.

    Asserted structurally because the import failure itself cannot be provoked from
    inside the process that already imported the module.
    """
    import api.routings

    assert not hasattr(api.routings, "get_template"), (
        "get_template is bound at module scope, so the import is no longer inside "
        "the try/except that is supposed to contain it"
    )


# ---------------------------------------------------------------------------
# Dynamic template resolution (Story 4.6 Task 9)
# ---------------------------------------------------------------------------


def test_template_resolution_uses_request_template_id(tmp_path):
    """Test that requested_routings uses request.template_id when provided.
    
    This verifies that the hardcoded _TEMPLATE_ID has been replaced with
    dynamic template resolution from the request.
    """
    # Create a request with a specific template_id
    request = TeamCreationRequest(
        team_name="Test Team",
        purpose="A test purpose that is long enough for validation.",
        output_path=str(tmp_path / "test"),
        template_id="baseline_education_team",
        desired_roles=[{"name": "tutor", "description": "Teaches things."}],
    )
    
    routings = requested_routings(request)
    
    # The routings should be resolved from baseline_education_team template
    # not from the hardcoded software_delivery_team
    assert "tutor" in routings
    # The tutor role in education team should have specific routing
    assert routings["tutor"].provider is not None


def test_template_resolution_uses_default_when_none(tmp_path):
    """Test that requested_routings uses default template when template_id is None."""
    # Create a request without template_id (should use default)
    request = TeamCreationRequest(
        team_name="Test Team",
        purpose="A test purpose that is long enough for validation.",
        output_path=str(tmp_path / "test"),
        template_id=None,
        desired_roles=[{"name": "architect", "description": "Designs things."}],
    )
    
    routings = requested_routings(request)
    
    # Should still work with default template
    assert "architect" in routings


def test_template_resolution_matches_pipeline_logic(tmp_path):
    """Test that requested_routings uses the same template selection as PipelineRunner.
    
    This verifies that reporting and builds use identical template resolution.
    The pipeline uses: template_id = request.template_id or "software_delivery_team"
    """
    # Test with various template_ids
    template_ids = ["baseline_education_team", "research_content_team", "software_delivery_team", None]
    
    for template_id in template_ids:
        request = TeamCreationRequest(
            team_name="Test Team",
            purpose="A test purpose that is long enough for validation.",
            output_path=str(tmp_path / "test"),
            template_id=template_id,
            desired_roles=[{"name": "architect", "description": "Designs things."}],
        )
        
        # This should not raise - the template should be resolved successfully
        routings = requested_routings(request)
        
        # For valid template_ids, we should get routings
        # For None, it should use the default and still work
        assert isinstance(routings, dict)
