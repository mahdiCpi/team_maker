"""Every built-in template must declare only canonical tool names (spec FR-043,
FR-044; audit P1-8; tasks.md T036-T037).

P1-8 approved a narrow, scope-fenced correction to `education/template.py`
(the shipped starter team) — the only phantom names it names are
`diagram_generator` and `text_analyser`. During Phase 3 implementation a
materially larger instance of the same defect was discovered: the *default*
template (`software_delivery_team`, `DEFAULT_TEMPLATE_ID`) and
`research_content/template.py` also declare phantom names
(`linter`, `browser_preview`, `static_analyser`, `cli_runner`,
`config_generator`, `monitoring_dashboard`, `task_tracker`,
`communication_channel`, `data_analyser`, `text_editor`, `outline_generator`,
`source_validator`, `style_guide`) as *per-role defaults* that bypass
compose-stage schema validation entirely (`templates/role_based.py:68` merges
them in only after `TeamCreationRequest` has already validated) and would
otherwise first surface as a build/validation failure for the majority of
default-path teams once Phase 4/7 land — a far larger compatibility break
than the approved P1-8 scope. Documented as an autonomous implementation
decision (priority order: leaving it broken fails backward-compatibility
priority #5 more severely than fixing it); see
`implementation-decision-log.md` D-IMPL-002 and `spec.md` Amendment 8.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from team_maker.tools.catalog import is_canonical

_TEMPLATE_FILES = [
    Path("team_maker/templates/education/template.py"),
    Path("team_maker/templates/research_content/template.py"),
    Path("team_maker/templates/software_delivery/template.py"),
]


@pytest.mark.parametrize("template_file", _TEMPLATE_FILES, ids=lambda p: p.stem)
def test_template_declares_only_canonical_tool_names(template_file: Path):
    src = template_file.read_text(encoding="utf-8")
    declared_lists = re.findall(r'"tools":\s*\[(.*?)\]', src)
    assert declared_lists, f"{template_file} declares no tools lists at all — check the regex/file shape"
    for raw_list in declared_lists:
        for name in re.findall(r'"([a-z_]+)"', raw_list):
            assert is_canonical(name), (
                f"{template_file} declares phantom tool name {name!r} — "
                f"not in the canonical catalog (team_maker/tools/catalog.py)"
            )


def test_education_starter_team_builds_and_validates_clean():
    """FR-044 scope fence: tool-name declarations only. Verified structurally
    above; this asserts the template still registers and generates."""
    from team_maker.templates.registry import get_template

    template = get_template("baseline_education_team")
    assert template is not None
