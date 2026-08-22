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


# ---------------------------------------------------------------------------
# Thread safety tests (Story 4.6 Task 7)
# ---------------------------------------------------------------------------


def test_concurrent_get_template_access():
    """Test that concurrent calls to get_template are thread-safe.
    
    This verifies that multiple threads can safely call get_template
    concurrently without corrupting the registry or causing race conditions.
    """
    import threading
    from team_maker.templates.registry import get_template
    
    template_ids = ["software_delivery_team", "baseline_education_team", "research_content_team"]
    results = []
    errors = []
    
    def get_template_worker():
        try:
            for template_id in template_ids:
                tmpl = get_template(template_id)
                results.append((template_id, type(tmpl).__name__))
        except Exception as e:
            errors.append(e)
    
    # Create multiple threads that all access get_template concurrently
    threads = [threading.Thread(target=get_template_worker) for _ in range(10)]
    
    # Start all threads
    for t in threads:
        t.start()
    
    # Wait for all threads to complete
    for t in threads:
        t.join()
    
    # Verify no errors occurred
    assert len(errors) == 0, f"Errors occurred: {errors}"
    
    # Verify we got results from all threads
    assert len(results) == len(threads) * len(template_ids)
    
    # Verify each template was retrieved correctly
    for template_id in template_ids:
        template_results = [r for r in results if r[0] == template_id]
        assert len(template_results) == len(threads)
        # All results for the same template_id should be the same type
        assert len(set(r[1] for r in template_results)) == 1


def test_concurrent_list_templates_access():
    """Test that concurrent calls to list_templates are thread-safe.
    
    This verifies that multiple threads can safely call list_templates
    concurrently without corrupting the registry.
    """
    import threading
    from team_maker.templates.registry import list_templates
    
    results = []
    errors = []
    
    def list_templates_worker():
        try:
            templates = list_templates()
            results.append(len(templates))
        except Exception as e:
            errors.append(e)
    
    # Create multiple threads that all access list_templates concurrently
    threads = [threading.Thread(target=list_templates_worker) for _ in range(10)]
    
    # Start all threads
    for t in threads:
        t.start()
    
    # Wait for all threads to complete
    for t in threads:
        t.join()
    
    # Verify no errors occurred
    assert len(errors) == 0, f"Errors occurred: {errors}"
    
    # Verify all threads got the same number of templates
    assert len(set(results)) == 1
    assert results[0] == 3  # We have 3 templates


def test_concurrent_mixed_operations():
    """Test that concurrent mixed operations (get_template + list_templates) are thread-safe.
    
    This verifies that the registry can handle concurrent reads from different functions.
    """
    import threading
    from team_maker.templates.registry import get_template, list_templates
    
    errors = []
    results = []
    
    def mixed_operations_worker():
        try:
            # Perform a mix of operations
            templates = list_templates()
            results.append(("list", len(templates)))
            
            for template_id in templates.keys():
                tmpl = get_template(template_id)
                results.append(("get", template_id, type(tmpl).__name__))
        except Exception as e:
            errors.append(e)
    
    # Create multiple threads
    threads = [threading.Thread(target=mixed_operations_worker) for _ in range(5)]
    
    # Start all threads
    for t in threads:
        t.start()
    
    # Wait for all threads to complete
    for t in threads:
        t.join()
    
    # Verify no errors occurred
    assert len(errors) == 0, f"Errors occurred: {errors}"
    
    # Verify we got results
    list_results = [r for r in results if r[0] == "list"]
    get_results = [r for r in results if r[0] == "get"]
    
    assert len(list_results) == len(threads)
    assert len(get_results) == len(threads) * 3  # 3 templates per thread
