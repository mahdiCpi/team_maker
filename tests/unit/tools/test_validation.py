"""Compose and build stage validation tests (spec FR-002 to FR-005, FR-056 to
FR-060; audit RC-3, tasks T011, T017-T026, T032-T035).

Covers the two independently-testable stages this feature scopes into Phase 3
(compose and build). Preflight-stage rejection (FR-058) is verified separately
in Phase 7 (`tests/unit/runtime/test_preflight.py`), where preflight
enforcement is actually implemented — this file intentionally does not
duplicate that coverage (see F1 in the analysis remediation).
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from team_maker.llm.schemas import ToolAssignment
from team_maker.schema.request import TeamCreationRequest
from team_maker.tools.validation import (
    RejectionReason,
    ToolValidationError,
    validate_declarations,
    validate_suggested_tool_credentials,
)

# The eleven confirmed invented names from the audit (contracts/tool-catalog.md
# / audit §2.2(a)) plus the four CrewAI class-name leaks.
_CONFIRMED_INVENTED_NAMES = [
    "code_reader_tool", "file_writer_tool", "shell_tool", "file_read",
    "text_summarizer", "web_scraper", "url_reader", "twitter_search_tool",
    "git_account_tool", "search_tool", "file_writer",
    "FileReadTool", "FileWriterTool", "ScrapeWebsiteTool", "SerperDevTool",
]


def _minimal_request_kwargs() -> dict:
    return {
        "team_name": "Test Team",
        "purpose": "testing tool validation",
        "output_path": "test_output",
    }


class TestValidateDeclarationsCore:
    def test_canonical_declaration_accepted(self):
        outcome = validate_declarations([("shell", "worker")], stage="build")
        assert outcome.passed
        assert outcome.rejections == ()

    @pytest.mark.parametrize("invented_name", _CONFIRMED_INVENTED_NAMES)
    def test_invented_name_rejected(self, invented_name: str):
        """RC-3, audit §2.2(a): every confirmed invented name from the shipped
        packages must be rejected, naming its source surface (the agent)."""
        outcome = validate_declarations([(invented_name, "worker")], stage="compose")
        assert not outcome.passed
        assert len(outcome.rejections) == 1
        rejection = outcome.rejections[0]
        assert rejection.tool_name == invented_name
        assert rejection.agent_role == "worker"
        assert rejection.reason == RejectionReason.UNKNOWN

    def test_alias_only_match_rejected_not_silently_resolved(self):
        """D-2: `shell_command` is a legacy alias of `shell`, not itself
        canonical. It MUST be rejected, with the canonical name suggested."""
        outcome = validate_declarations([("shell_command", "worker")], stage="compose")
        assert not outcome.passed
        assert "shell" in outcome.rejections[0].detail

    def test_rejections_aggregate_collect_dont_short_circuit(self):
        """FR-060: every offending declaration is reported in one pass."""
        outcome = validate_declarations(
            [("text_summarizer", "a"), ("web_scraper", "b"), ("shell", "c")],
            stage="build",
        )
        assert len(outcome.rejections) == 2
        assert {r.tool_name for r in outcome.rejections} == {"text_summarizer", "web_scraper"}

    def test_raise_if_rejected_carries_every_rejection(self):
        outcome = validate_declarations([("a_fake", "x"), ("b_fake", "y")], stage="build")
        with pytest.raises(ToolValidationError) as exc_info:
            outcome.raise_if_rejected()
        assert len(exc_info.value.rejections) == 2

    def test_rejection_str_names_tool_agent_stage_and_reason(self):
        outcome = validate_declarations([("text_summarizer", "researcher")], stage="compose")
        message = str(outcome.rejections[0])
        assert "text_summarizer" in message
        assert "researcher" in message
        assert "compose" in message
        assert "unknown" in message


class TestSuggestedToolCredentialGate:
    def test_invented_credential_for_a_canonical_tool_is_rejected(self):
        """RC-3: closes the path that put SERPAPI_API_KEY (a name in no source
        file) into a shipped package. `web_search`'s real requirement is
        SERPER_API_KEY."""
        suggestion = {"name": "web_search", "description": "search", "env_vars": ["SERPAPI_API_KEY"]}
        outcome = validate_suggested_tool_credentials([suggestion])
        assert not outcome.passed
        assert "SERPAPI_API_KEY" in outcome.rejections[0].detail

    def test_matching_credential_for_a_canonical_tool_is_accepted(self):
        suggestion = {"name": "web_search", "description": "search", "env_vars": ["SERPER_API_KEY"]}
        outcome = validate_suggested_tool_credentials([suggestion])
        assert outcome.passed

    def test_non_canonical_suggestion_is_inert_not_rejected(self):
        """A genuinely novel suggestion that never resolves to a catalog name
        is harmless metadata — it is never promoted into an agent's tools and
        can never reach execution, so no credential check applies."""
        suggestion = {"name": "custom_novel_tool", "description": "x", "env_vars": ["ANYTHING"]}
        outcome = validate_suggested_tool_credentials([suggestion])
        assert outcome.passed


class TestComposeStageWiring:
    """FR-056: compose-stage validation runs inside `TeamCreationRequest`
    construction, which is exactly what `Composer.compose()` calls via
    `provider.complete_structured(response_model=TeamCreationRequest)`. An
    invalid tool name here raises pydantic's ValidationError, which the
    Composer's repair loop treats as retry-worthy and, if exhausted, surfaces
    visibly as `ComposerError` — never silently reaching a generated package."""

    def test_invented_tool_name_in_desired_roles_fails_schema_validation(self):
        kwargs = _minimal_request_kwargs()
        kwargs["desired_roles"] = [
            {"name": "researcher", "description": "does research", "tools": ["text_summarizer"]}
        ]
        with pytest.raises(ValidationError) as exc_info:
            TeamCreationRequest(**kwargs)
        assert "text_summarizer" in str(exc_info.value)

    def test_canonical_tool_name_in_desired_roles_is_accepted(self):
        kwargs = _minimal_request_kwargs()
        kwargs["desired_roles"] = [
            {"name": "researcher", "description": "does research", "tools": ["web_search"]}
        ]
        request = TeamCreationRequest(**kwargs)
        assert request.desired_roles[0].tools == ["web_search"]

    def test_crewai_class_name_leak_is_rejected(self):
        """Audit §2.2(a): `customer_persona_creator` shipped with Python class
        identifiers (FileReadTool etc.) instead of registry keys."""
        kwargs = _minimal_request_kwargs()
        kwargs["desired_roles"] = [
            {"name": "researcher", "description": "does research", "tools": ["FileReadTool"]}
        ]
        with pytest.raises(ValidationError):
            TeamCreationRequest(**kwargs)


class TestPlannerPathToolValidation:
    """The LLM planner's structured output (`AgentPlan` / `ToolAssignment`) is
    a *second* free-form surface, entirely distinct from
    `TeamCreationRequest.desired_roles`, discovered during Phase 3
    implementation to have had zero validation (see
    implementation-decision-log.md). `map_plan_to_team` reads `a.tools`
    directly into `AgentSpec.tools` with no gate — exactly RC-3's mechanism,
    for any team the LLM plans rather than builds from a template."""

    def test_invented_tool_name_in_planner_output_is_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            ToolAssignment(name="text_summarizer", reason="needs to summarize")
        assert "text_summarizer" in str(exc_info.value)

    def test_canonical_tool_name_in_planner_output_is_accepted(self):
        assignment = ToolAssignment(name="shell", reason="needs to run builds")
        assert assignment.name == "shell"

    def test_alias_in_planner_output_is_rejected_with_suggestion(self):
        with pytest.raises(ValidationError) as exc_info:
            ToolAssignment(name="shell_command", reason="needs shell")
        assert "shell" in str(exc_info.value)
