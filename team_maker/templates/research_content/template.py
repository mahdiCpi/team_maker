"""Research/Content Team template.

Generates a content creation team: researcher gathers information, writer creates
content, fact_checker verifies accuracy, and editor finalizes the output.
This is the flagship showcase team mentioned in the PRD addendum.
"""
from __future__ import annotations

from typing import Any, Dict, List

from team_maker.domain.models import GeneratedTeam
from team_maker.schema.request import TeamCreationRequest
from team_maker.templates.base import BaseTeamTemplate
from team_maker.templates.registry import register
from team_maker.templates.role_based import RoleBasedTemplateMixin


# ---------------------------------------------------------------------------
# Defaults for each role in the research/content team
# ---------------------------------------------------------------------------

_ROLE_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "researcher": {
        "display_name": "Researcher",
        "description": "Gathers and verifies facts and sources on the topic.",
        "goal": "Collect accurate, well-sourced information to support content creation.",
        "backstory": (
            "A meticulous researcher with access to comprehensive knowledge bases. "
            "Expert at finding reliable sources, verifying claims, and organizing "
            "information for content creators."
        ),
        "capabilities": [
            "information_retrieval",
            "fact_verification",
            "source_evaluation",
            "data_analysis",
            "context_research",
        ],
        "tools": ["code_reader", "web_search", "data_analyser"],
        "is_orchestrator": False,
    },
    "writer": {
        "display_name": "Writer",
        "description": "Drafts content (article/report) from the research.",
        "goal": "Create engaging, well-structured content based on verified research.",
        "backstory": (
            "A skilled content creator with experience writing articles, reports, and "
            "documentation. Transforms research into compelling narratives."
        ),
        "capabilities": [
            "content_writing",
            "storytelling",
            "structural_organization",
            "audience_adaptation",
            "style_consistency",
        ],
        "tools": ["code_writer", "text_editor", "outline_generator"],
        "is_orchestrator": False,
    },
    "fact_checker": {
        "display_name": "Fact Checker",
        "description": "Verifies claims and citations in the draft.",
        "goal": "Ensure all factual statements are accurate and properly sourced.",
        "backstory": (
            "A detail-oriented fact checker with a background in journalism or research. "
            "Specializes in verifying claims, checking sources, and ensuring "
            "content integrity."
        ),
        "capabilities": [
            "fact_verification",
            "source_validation",
            "claim_assessment",
            "citation_checking",
            "accuracy_auditing",
        ],
        "tools": ["code_reader", "web_search", "source_validator"],
        "is_orchestrator": False,
    },
    "editor": {
        "display_name": "Editor",
        "description": "Edits for clarity, tone, and structure; owns final output.",
        "goal": "Polish content for maximum clarity, engagement, and quality before publication.",
        "backstory": (
            "An experienced editor with a keen eye for detail and a deep understanding "
            "of what makes content effective. Ensures the final output meets quality "
            "standards and resonates with the target audience."
        ),
        "capabilities": [
            "copy_editing",
            "structural_editing",
            "tone_adjustment",
            "clarity_improvement",
            "final_review",
        ],
        "tools": ["code_reader", "text_analyser", "style_guide"],
        "is_orchestrator": True,
    },
}

# Default task catalogue for research/content team
_DEFAULT_TASKS: List[Dict[str, Any]] = [
    {
        "name": "research_topic",
        "description": "Gather and verify facts, sources, and data on the assigned topic.",
        "expected_output": (
            "Comprehensive research package with verified facts, source citations, "
            "and organized notes for the writer."
        ),
        "agent_role": "researcher",
        "dependencies": [],
    },
    {
        "name": "draft_content",
        "description": "Create the initial content draft based on the research findings.",
        "expected_output": (
            "First draft of the article/report with clear structure, "
            "compelling narrative, and all key points covered."
        ),
        "agent_role": "writer",
        "dependencies": ["research_topic"],
    },
    {
        "name": "fact_check",
        "description": "Verify all claims, data points, and citations in the draft content.",
        "expected_output": (
            "Fact-checking report identifying any inaccuracies, unsupported claims, "
            "or missing citations that need to be addressed."
        ),
        "agent_role": "fact_checker",
        "dependencies": ["draft_content"],
    },
    {
        "name": "edit_content",
        "description": "Edit the content for clarity, tone, structure, and overall quality.",
        "expected_output": (
            "Final, polished content ready for publication, with improvements "
            "to clarity, flow, and reader engagement."
        ),
        "agent_role": "editor",
        "dependencies": ["fact_check"],
    },
]


@register("research_content_team")
class ResearchContentTeamTemplate(RoleBasedTemplateMixin, BaseTeamTemplate):
    """Research/Content team template for creating well-researched content."""

    description = (
        "A four-agent research team: researcher gathers facts, writer drafts content, "
        "fact checker verifies accuracy, and editor finalizes the output."
    )

    # Class-level defaults (override mixin's empty defaults)
    _ROLE_DEFAULTS = _ROLE_DEFAULTS
    _DEFAULT_TASKS = _DEFAULT_TASKS

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def generate(self, request: TeamCreationRequest) -> GeneratedTeam:
        agents = self._build_agents(request)
        tasks = self._build_tasks(request, agents)
        return GeneratedTeam(
            team_name=request.team_name,
            purpose=request.purpose,
            template_used=self.template_id,
            agents=agents,
            tasks=tasks,
            stack=request.stack,
            constraints=request.constraints,
            tags=request.tags,
            documentation_level=request.documentation_level.value,
            metadata=request.metadata,
        )

    def default_role_names(self) -> List[str]:
        return list(self._ROLE_DEFAULTS.keys())

    def default_task_names(self) -> List[str]:
        return [t["name"] for t in self._DEFAULT_TASKS]
