"""Live integration test for context_dir: injects context files into the planner and tools.py.

Skipped automatically when ANTHROPIC_API_KEY is not set.
Run with: pytest tests/integration/test_context_dir_live.py -v -s
"""
from __future__ import annotations

import os
import pytest
from pathlib import Path

from team_maker.pipeline.runner import PipelineRunner
from team_maker.schema.request import ProviderConfig, TeamCreationRequest

pytestmark = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set",
)

_PLANNING_LLM = ProviderConfig(
    provider="anthropic",
    model="claude-sonnet-4-6",
    api_key_env="ANTHROPIC_API_KEY",
)


@pytest.fixture()
def context_dir(tmp_path) -> Path:
    ctx = tmp_path / "context"
    ctx.mkdir()
    (ctx / "domain_overview.md").write_text(
        "# Inventory Domain\n\n"
        "This system tracks warehouse stock levels in real time.\n"
        "Key entities: Product, Warehouse, StockMovement.\n"
        "Critical constraint: stock can never go negative (enforce at DB level).\n"
    )
    (ctx / "tech_decisions.txt").write_text(
        "Database: PostgreSQL 16\n"
        "API layer: FastAPI + Pydantic v2\n"
        "Deployment: Kubernetes on AWS EKS\n"
        "No ORM — raw asyncpg for all queries.\n"
    )
    return ctx


def test_context_dir_injects_into_planner_and_tools(tmp_path, context_dir):
    """Full pipeline: context files appear in tools.py and the plan reflects domain knowledge."""
    request = TeamCreationRequest(
        team_name="Inventory Service Team",
        purpose=(
            "Build a warehouse inventory management service that tracks stock levels, "
            "prevents negative stock, and exposes a REST API."
        ),
        output_path=str(tmp_path / "inventory_team"),
        planning_llm=_PLANNING_LLM,
        context_dir=str(context_dir),
        overwrite=True,
    )

    result = PipelineRunner().run(request)

    # --- pipeline must succeed ---
    assert result.validation.passed, f"Validation issues: {result.validation.issues}"

    # --- context_reader must appear in tools.py ---
    tools_py = (result.output_path / "tools.py").read_text()
    assert "context_reader_tool" in tools_py, "context_reader_tool not found in tools.py"
    assert "CONTEXT_DIR" in tools_py, "CONTEXT_DIR not set in tools.py"
    assert str(context_dir) in tools_py, "context_dir path not embedded in tools.py"
    assert '"context_reader": context_reader_tool' in tools_py

    # --- context path is stored in team config ---
    report = (result.output_path / "generation_report.md").read_text()
    assert result.output_path.exists()

    # --- planner produced agents and tasks ---
    assert len(result.team.agents) >= 2
    assert len(result.team.tasks) >= 2
