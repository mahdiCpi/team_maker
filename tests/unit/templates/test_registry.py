"""Unit tests for the template registry."""
from __future__ import annotations

import pytest

import team_maker.templates  # noqa: F401 — registers templates
from team_maker.templates.registry import get_template, list_templates
from team_maker.templates.software_delivery.template import SoftwareDeliveryTemplate
from team_maker.templates.education.template import EducationTeamTemplate
from team_maker.templates.research_content.template import ResearchContentTeamTemplate


def test_software_delivery_template_is_registered():
    templates = list_templates()
    assert "software_delivery_team" in templates


def test_education_template_is_registered():
    templates = list_templates()
    assert "baseline_education_team" in templates


def test_research_content_template_is_registered():
    templates = list_templates()
    assert "research_content_team" in templates


def test_all_templates_registered():
    templates = list_templates()
    expected = {
        "software_delivery_team",
        "baseline_education_team",
        "research_content_team",
    }
    assert set(templates.keys()) == expected


def test_unknown_template_raises():
    with pytest.raises(ValueError, match="Unknown template"):
        get_template("nonexistent_template")


def test_get_template_software_delivery():
    tmpl = get_template("software_delivery_team")
    assert isinstance(tmpl, SoftwareDeliveryTemplate)


def test_get_template_education():
    tmpl = get_template("baseline_education_team")
    assert isinstance(tmpl, EducationTeamTemplate)


def test_get_template_research_content():
    tmpl = get_template("research_content_team")
    assert isinstance(tmpl, ResearchContentTeamTemplate)


def test_get_template_returns_fresh_instance():
    tmpl1 = get_template("software_delivery_team")
    tmpl2 = get_template("software_delivery_team")
    assert tmpl1 is not tmpl2
