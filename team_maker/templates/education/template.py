"""Baseline Education Team template.

Generates a team for creating educational content: a tutor who explains topics,
a researcher who gathers facts, and a clarity reviewer who ensures understanding.
"""
from __future__ import annotations

from typing import Any, Dict, List

from team_maker.domain.models import GeneratedTeam
from team_maker.schema.request import TeamCreationRequest
from team_maker.templates.base import BaseTeamTemplate
from team_maker.templates.registry import register
from team_maker.templates.role_based import RoleBasedTemplateMixin


# ---------------------------------------------------------------------------
# Defaults for each role in the education team
# ---------------------------------------------------------------------------

_ROLE_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "tutor": {
        "display_name": "Tutor",
        "description": "Explains the requested topic at the learner's level.",
        "goal": "Give a clear, correctly-leveled explanation, checking understanding as it goes.",
        "backstory": (
            "An experienced educator with a talent for breaking down complex topics into "
            "understandable concepts. Passionate about helping learners grasp difficult "
            "material and verifying their comprehension."
        ),
        "capabilities": [
            "explanation",
            "teaching",
            "knowledge_assessment",
            "curriculum_design",
            "adaptive_learning",
        ],
        "tools": ["code_reader"],
        "is_orchestrator": True,
    },
    "researcher": {
        "display_name": "Researcher",
        "description": "Gathers accurate supporting facts and examples on the topic before the tutor explains.",
        "goal": "Find accurate, relevant, and comprehensive information to support the learning objective.",
        "backstory": (
            "A thorough researcher with access to vast knowledge repositories. "
            "Skilled at finding reliable sources and verifying factual accuracy."
        ),
        "capabilities": [
            "information_retrieval",
            "fact_verification",
            "source_evaluation",
            "context_gathering",
        ],
        "tools": ["code_reader", "web_search"],
        "is_orchestrator": False,
    },
    "clarity_reviewer": {
        "display_name": "Clarity Reviewer",
        "description": "Checks the tutor's draft for jargon, correctness, and level; simplifies where needed.",
        "goal": "Ensure explanations are clear, accurate, and appropriate for the intended audience level.",
        "backstory": (
            "A detail-oriented editor with a background in education. "
            "Specializes in identifying confusing language, technical errors, and "
            "opportunities to improve clarity for learners."
        ),
        "capabilities": [
            "proofreading",
            "technical_review",
            "simplification",
            "quality_assurance",
            "audience_analysis",
        ],
        "tools": ["code_reader"],
        "is_orchestrator": False,
    },
}

# Default task catalogue for education team
_DEFAULT_TASKS: List[Dict[str, Any]] = [
    {
        "name": "research_topic",
        "description": "Gather accurate facts, examples, and resources about the requested topic.",
        "expected_output": (
            "Comprehensive research notes with verified facts, relevant examples, "
            "and source citations for the topic."
        ),
        "agent_role": "researcher",
        "dependencies": [],
    },
    {
        "name": "draft_explanation",
        "description": "Create a clear, structured explanation of the topic tailored to the learner's level.",
        "expected_output": (
            "Well-structured educational content that explains the topic conceptually, "
            "with appropriate depth and clarity checks built in."
        ),
        "agent_role": "tutor",
        "dependencies": ["research_topic"],
    },
    {
        "name": "review_for_clarity",
        "description": "Review the draft explanation for clarity, accuracy, and appropriateness for the target audience.",
        "expected_output": (
            "Review report identifying any jargon that needs explanation, factual errors, "
            "or areas where the explanation could be simplified or improved."
        ),
        "agent_role": "clarity_reviewer",
        "dependencies": ["draft_explanation"],
    },
]


@register("baseline_education_team")
class EducationTeamTemplate(RoleBasedTemplateMixin, BaseTeamTemplate):
    """Baseline education team template for creating educational content."""

    description = (
        "A three-agent education team: researcher gathers facts, tutor creates explanations, "
        "and clarity reviewer ensures understanding."
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
