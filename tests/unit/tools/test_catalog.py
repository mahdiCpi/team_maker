"""Catalog identity tests (spec FR-001, FR-083; audit RC-3; tasks T016, T029, T035)."""
from __future__ import annotations

from team_maker.tools.catalog import TOOL_CATALOG, RiskClass, is_canonical, resolve_alias


def test_one_entry_per_canonical_name_no_dict_collisions():
    # dict construction itself guarantees this, but assert the invariant explicitly
    # so a future edit that introduces a duplicate key fails loudly rather than
    # silently overwriting an entry.
    names = list(TOOL_CATALOG.keys())
    assert len(names) == len(set(names))


def test_no_canonical_name_appears_in_any_alias_list():
    canonical_names = set(TOOL_CATALOG.keys())
    for definition in TOOL_CATALOG.values():
        for alias in definition.aliases:
            assert alias not in canonical_names, (
                f"alias {alias!r} of {definition.name!r} collides with a canonical name"
            )


def test_linter_phantom_is_absent():
    """RC-3: `_REGISTRY_TOOLS` contained a `"linter"` entry that exists in no
    other allowlist and was never a real tool. It must not survive into the
    canonical catalog, as a name or as an alias."""
    assert "linter" not in TOOL_CATALOG
    for definition in TOOL_CATALOG.values():
        assert "linter" not in definition.aliases


def test_risky_tools_match_the_approved_classification():
    """FR-008 / tasks.md T013: exactly shell, code_writer, test_runner and
    docker_runner are RISKY. Every other catalog entry is SAFE."""
    risky = {name for name, d in TOOL_CATALOG.items() if d.risk is RiskClass.RISKY}
    assert risky == {"shell", "code_writer", "test_runner", "docker_runner"}


def test_only_docker_runner_requires_mounts():
    mount_tools = {name for name, d in TOOL_CATALOG.items() if d.requires_mounts}
    assert mount_tools == {"docker_runner"}


def test_is_canonical_rejects_aliases():
    """D-2: an alias is never itself canonical — only the real name is."""
    assert is_canonical("shell")
    assert not is_canonical("shell_command")
    assert not is_canonical("nonexistent_tool")


def test_resolve_alias_maps_known_single_candidate_aliases():
    assert resolve_alias("shell_command") == "shell"
    assert resolve_alias("code_reader_tool") == "code_reader"
    assert resolve_alias("git_account_tool") == "git_account"


def test_resolve_alias_returns_none_for_unknown_names():
    assert resolve_alias("text_summarizer") is None
    assert resolve_alias("web_scraper") is None
    assert resolve_alias("SerperDevTool") is None


def test_unknown_name_is_unknown_availability():
    from team_maker.tools.catalog import AvailabilityState, build_time_availability

    assert build_time_availability("text_summarizer") == AvailabilityState.UNKNOWN


def test_canonical_tool_with_optional_credential_is_available_at_build_time():
    """FR-065: a canonical tool whose credential is merely absent in THIS
    environment is 'known but unavailable' at preflight (Phase 7), never
    'unknown' or a build failure. Build-time availability only asks whether
    the catalog defines the tool at all."""
    from team_maker.tools.catalog import AvailabilityState, build_time_availability

    assert build_time_availability("web_search") == AvailabilityState.AVAILABLE
    assert build_time_availability("code_reader") == AvailabilityState.AVAILABLE


def test_required_credentials_for_emits_only_tools_with_requirements():
    from team_maker.tools.catalog import required_credentials_for

    result = required_credentials_for(["shell", "web_search", "code_reader", "text_summarizer"])
    assert result["shell"] == ()
    assert result["web_search"] == ("SERPER_API_KEY",)
    assert result["code_reader"] == ("OPENAI_API_KEY",)
    assert "text_summarizer" not in result  # not canonical — silently excluded, not a KeyError


def test_no_hardcoded_tool_name_set_survives_outside_catalog_in_python_source():
    """FR-001, T035: the two Python-side drifted copies must be gone.
    `AVAILABLE_TOOLS` derives from `TOOL_CATALOG`; `_REGISTRY_TOOLS` is
    deleted entirely. The codegen template's `TOOL_REGISTRY` literal is
    explicitly out of scope here — Phase 4 (T046) derives it from the same
    catalog key as part of the atomic stub-removal unit, not before."""
    import re
    from pathlib import Path

    request_src = Path("team_maker/schema/request.py").read_text(encoding="utf-8")
    assert not re.search(r"_REGISTRY_TOOLS\s*=", request_src), (
        "the historical drifted allowlist may be mentioned in a comment, "
        "but its assignment must be gone"
    )

    prompts_src = Path("team_maker/llm/prompts.py").read_text(encoding="utf-8")
    match = re.search(r"AVAILABLE_TOOLS[^=]*=\s*(.+)", prompts_src)
    assert match is not None
    assert "TOOL_CATALOG" in match.group(1), "AVAILABLE_TOOLS must derive from TOOL_CATALOG, not restate it"
