"""Integration: the product's own run path and the standalone generated
package agree on which tools a declaration resolves to (spec FR-025, FR-047;
contracts/tool-resolver-port.md; tasks.md T111).

Before Phase 5, `codegen/templates/crewai_runner.py.j2:105` already called
`get_tools_for(cfg.get("tools", []))` in the standalone path, while the
product's own `_build_agent` silently dropped every declared tool (RC-5).
The two paths could not have agreed on anything, because one side attached
nothing. This test is the closure of that divergence.
"""
from __future__ import annotations

import sys
from pathlib import Path

from team_maker.adapters.tools.package_tool_resolver import PackageToolResolver
from team_maker.pipeline.runner import PipelineRunner
from team_maker.schema.request import RoleDefinition, TeamCreationRequest


def _build(tmp_path, output_dir: str) -> Path:
    request = TeamCreationRequest(
        team_name="Parity Team",
        purpose="A team for verifying tool-resolution path parity.",
        output_path=str(tmp_path / output_dir),
        desired_roles=[
            RoleDefinition(
                name="coordinator",
                description="Coordinates the team.",
                tools=["state_reader", "state_writer"],
            ),
        ],
    )
    build = PipelineRunner().run(request)
    return build.output_path


def _standalone_tool_names(package_path: Path, names: list[str]) -> set:
    """The standalone path: import the package's own `tools.py` and call
    `get_tools_for`, exactly as the generated `run_example.py` does."""
    for stale in ("tools", "state_store"):
        sys.modules.pop(stale, None)
    package_path_str = str(package_path)
    sys.path.insert(0, package_path_str)
    try:
        import tools as generated_tools  # type: ignore[import-not-found]

        instances = generated_tools.get_tools_for(names)
    finally:
        sys.path.remove(package_path_str)
        for stale in ("tools", "state_store"):
            sys.modules.pop(stale, None)
    return {getattr(t, "name", None) for t in instances}


def test_product_and_standalone_paths_attach_the_same_tool_names(tmp_path):
    package_path = _build(tmp_path, "parity_team")
    declared = ["state_reader", "state_writer"]

    resolver = PackageToolResolver(package_path)
    product_names = {r.name for r in resolver.resolve_all(declared)}

    standalone_names = _standalone_tool_names(package_path, declared)

    assert product_names == standalone_names == set(declared)


def test_a_safely_resolving_package_still_runs_standalone_unchanged(tmp_path):
    """FR-047: a package whose declared tools all resolve safely is
    unaffected by this remediation — the breaking changes (release note,
    T146) are scoped to unknown, invalid, unresolvable, unauthorized or
    unsafe declarations, never to one that was already fine."""
    package_path = _build(tmp_path, "unaffected_team")
    names = _standalone_tool_names(package_path, ["state_reader"])
    assert names == {"state_reader"}
