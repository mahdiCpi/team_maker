"""Migration report tests (spec FR-038 to FR-042; D-9; tasks T038-T041)."""
from __future__ import annotations

from pathlib import Path

import pytest

from team_maker.tools.migration import format_report, scan_directory, scan_package


def _write_agent_yaml(agents_dir: Path, role: str, tools: list[str]) -> None:
    agents_dir.mkdir(parents=True, exist_ok=True)
    content = f"role: {role}\ndescription: test agent\ntools:\n" + "\n".join(f"  - {t}" for t in tools)
    (agents_dir / f"{role}.yaml").write_text(content, encoding="utf-8")


@pytest.fixture
def packages_root(tmp_path: Path) -> Path:
    return tmp_path


def test_all_canonical_package_is_absent_from_report(packages_root: Path):
    pkg = packages_root / "clean_team"
    _write_agent_yaml(pkg / "agents", "worker", ["shell", "code_reader"])

    findings = scan_package(pkg)
    assert findings == []


def test_mixed_package_names_only_the_offending_declaration(packages_root: Path):
    pkg = packages_root / "mixed_team"
    _write_agent_yaml(
        pkg / "agents", "worker",
        ["shell", "code_reader", "web_search", "state_reader", "text_summarizer"],
    )

    findings = scan_package(pkg)
    assert len(findings) == 1
    assert findings[0].declared_name == "text_summarizer"
    assert findings[0].agent_role == "worker"


def test_ambiguous_name_flagged_for_human_decision_with_no_suggestion(packages_root: Path):
    pkg = packages_root / "ambiguous_team"
    _write_agent_yaml(pkg / "agents", "worker", ["web_scraper"])

    findings = scan_package(pkg)
    assert len(findings) == 1
    assert findings[0].suggested_replacement is None
    assert findings[0].requires_human_decision is True


def test_unambiguous_alias_gets_a_suggestion(packages_root: Path):
    pkg = packages_root / "legacy_team"
    _write_agent_yaml(pkg / "agents", "worker", ["shell_command"])

    findings = scan_package(pkg)
    assert findings[0].suggested_replacement == "shell"
    assert findings[0].requires_human_decision is False


def test_report_writes_nothing(packages_root: Path):
    pkg = packages_root / "mixed_team"
    agent_file_dir = pkg / "agents"
    _write_agent_yaml(agent_file_dir, "worker", ["text_summarizer"])
    agent_file = agent_file_dir / "worker.yaml"
    before = agent_file.read_bytes()

    scan_package(pkg)
    scan_directory(packages_root)

    assert agent_file.read_bytes() == before


def test_two_runs_produce_identical_output(packages_root: Path):
    pkg = packages_root / "mixed_team"
    _write_agent_yaml(pkg / "agents", "worker", ["text_summarizer", "shell_command"])

    first = format_report(scan_directory(packages_root))
    second = format_report(scan_directory(packages_root))
    assert first == second


def test_scan_directory_excludes_all_canonical_packages_from_aggregate(packages_root: Path):
    clean = packages_root / "clean_team"
    _write_agent_yaml(clean / "agents", "worker", ["shell"])
    mixed = packages_root / "mixed_team"
    _write_agent_yaml(mixed / "agents", "worker", ["text_summarizer"])

    findings = scan_directory(packages_root)
    packages_with_findings = {f.package for f in findings}
    assert packages_with_findings == {"mixed_team"}
