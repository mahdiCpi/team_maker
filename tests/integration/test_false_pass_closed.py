"""Verification against the recorded false-pass reproduction (spec P0-3,
SC-008; tasks.md T140).

`evidence/baseline-false-pass.txt` recorded four checked-in packages
(`generated_teams/`) whose `generation_report.md` claimed
"Validation status: ✅ PASSED" despite declaring tool names the audit
identified as invented or invalid. Re-running the current
`OutputValidator` against these same on-disk packages (no LLM replan —
they predate this remediation and there is no stored request to
regenerate them from) is how "now closed" is verified without inspection
alone (Constitution IV, SC-013).

**Only two of the four are in this feature's scope.** `fusion_policy_research_team`
and `devops_team` declare invented/legacy-alias/unauthorized tool names and
now correctly fail. `tagline_forge` and `scifi_story_team` declare **no**
tools at all in any agent (`tools: []` throughout) — whatever made their
original validation a "false pass" is a defect outside tool declarations
entirely, and this remediation's tool-focused checks have nothing to catch
there. Recorded in `evidence/step6-false-pass-verification.txt`, and
documented rather than silently assumed closed.
"""
from __future__ import annotations

from pathlib import Path

from team_maker.runtime.loader import load_team_package
from team_maker.validation.validator import OutputValidator

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _validate(package_name: str):
    path = _REPO_ROOT / "generated_teams" / package_name
    team = load_team_package(path)
    return OutputValidator().validate(path, team)


def test_fusion_policy_research_team_no_longer_false_passes():
    result = _validate("fusion_policy_research_team")
    assert not result.passed
    assert any("web_scraper" in issue for issue in result.issues)


def test_devops_team_no_longer_false_passes():
    result = _validate("devops_team")
    assert not result.passed
    assert any("shell_command" in issue for issue in result.issues)
    assert any("unauthorized" in issue for issue in result.issues)
