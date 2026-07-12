"""CLI entrypoint for team_maker.

Usage:
    python -m team_maker create --config path/to/request.yaml
    python -m team_maker list-templates
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import click
from pydantic import ValidationError
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from team_maker.pipeline.runner import PipelineRunner
from team_maker.schema.request import TeamCreationRequest
from team_maker.utils.yaml_utils import load_yaml

console = Console()
err_console = Console(stderr=True, style="red")


@click.group()
@click.version_option(package_name="team_maker")
def main() -> None:
    """team_maker — generate standalone multi-agent team packages."""


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


@main.command()
@click.option(
    "--config",
    "-c",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Path to a YAML team creation request file.",
)
@click.option(
    "--output",
    "-o",
    default=None,
    type=click.Path(path_type=Path),
    help="Override the output_path defined in the config.",
)
@click.option(
    "--overwrite",
    is_flag=True,
    default=False,
    help="Overwrite an existing output directory.",
)
@click.option(
    "--framework",
    type=click.Choice(["crewai", "langgraph", "autogen"], case_sensitive=False),
    default=None,
    help="Override the runtime framework defined in the config.",
)
@click.option(
    "--state-backend",
    type=click.Choice(["file", "vector", "both"], case_sensitive=False),
    default=None,
    help="Override the shared state backend defined in the config.",
)
@click.option(
    "--planner-model",
    default=None,
    help="Override the default planner LLM model (e.g. gpt-4o, claude-sonnet-4-5).",
)
@click.option(
    "--no-planner",
    is_flag=True,
    default=False,
    help="Force the template path even when desired_roles is empty (uses fallback defaults).",
)
@click.option("--quiet", "-q", is_flag=True, default=False, help="Suppress progress output.")
def create(
    config: Path,
    output: Optional[Path],
    overwrite: bool,
    framework: Optional[str],
    state_backend: Optional[str],
    planner_model: Optional[str],
    no_planner: bool,
    quiet: bool,
) -> None:
    """Generate a team package from a YAML request file."""
    # 1. Load raw YAML
    try:
        raw = load_yaml(config)
    except Exception as exc:
        err_console.print(f"[bold]Failed to load config file:[/bold] {exc}")
        sys.exit(1)

    # 2. Apply CLI overrides
    if output is not None:
        raw["output_path"] = str(output)
    if overwrite:
        raw["overwrite"] = True
    if framework is not None:
        raw["framework"] = framework.lower()
    if state_backend is not None:
        raw["state_backend"] = state_backend.lower()
    if planner_model is not None:
        raw.setdefault("default_llm", {})["model"] = planner_model
    if no_planner and not raw.get("desired_roles"):
        # Force template path by injecting a minimal role list
        raw["desired_roles"] = [
            {"name": "coordinator", "description": "Coordinates the team and delegates work."},
            {"name": "engineer", "description": "Implements the deliverables."},
        ]

    # 3. Validate schema
    try:
        request = TeamCreationRequest.model_validate(raw)
    except ValidationError as exc:
        err_console.print("[bold]Invalid request config:[/bold]")
        for error in exc.errors():
            loc = " → ".join(str(l) for l in error["loc"])
            err_console.print(f"  • {loc}: {error['msg']}")
        sys.exit(1)

    if not quiet:
        console.print(
            Panel(
                f"[bold cyan]{request.team_name}[/bold cyan]\n"
                f"{request.purpose[:120]}",
                title="[bold]team_maker[/bold] · Creating team",
                expand=False,
            )
        )

    # 4. Run pipeline
    runner = PipelineRunner()
    try:
        result = runner.run(request)
    except FileExistsError as exc:
        err_console.print(f"[bold]Output conflict:[/bold] {exc}")
        sys.exit(1)
    except Exception as exc:
        err_console.print(f"[bold]Pipeline error:[/bold] {exc}")
        raise  # re-raise for full traceback in debug scenarios

    # 5. Report outcome
    if not quiet:
        _print_result(result)

    if not result.validation.passed:
        sys.exit(2)


# ---------------------------------------------------------------------------
# list-templates
# ---------------------------------------------------------------------------


@main.command("list-templates")
def list_templates() -> None:
    """Show all registered team templates."""
    import team_maker.templates  # noqa: F401 — ensure templates are registered
    from team_maker.templates.registry import list_templates as _list

    tmpl_map = _list()
    table = Table(title="Available Templates", show_lines=True)
    table.add_column("Template ID", style="cyan", no_wrap=True)
    table.add_column("Description")
    for tid, desc in tmpl_map.items():
        table.add_row(tid, desc)
    console.print(table)


# ---------------------------------------------------------------------------
# keys
# ---------------------------------------------------------------------------


@main.group()
def keys() -> None:
    """Inspect API-key / provider configuration."""


@keys.command("status")
@click.option(
    "--file",
    "-f",
    "key_file",
    default=None,
    # exists/dir_okay are only enforced when the user passes --file explicitly;
    # the default (None) path is allowed to be absent (reported as no keys).
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Path to the Key Config file (default: $TEAM_MAKER_KEYS or ./team_maker.keys).",
)
def keys_status(key_file: Optional[Path]) -> None:
    """Report which providers/models are usable. Never prints key values."""
    from rich.markup import escape

    from team_maker.keyconfig import KeyConfig
    from team_maker.providers.registry import report_availability

    config = KeyConfig.from_file(key_file)
    report = report_availability(config)

    resolved = key_file or KeyConfig.default_path()
    table = Table(title="Provider availability", show_lines=False)
    table.add_column("Provider", style="cyan", no_wrap=True)
    table.add_column("Status")
    table.add_column("Detail", style="dim")

    style_by_status = {
        "available": "green",
        "keyless-local": "green",
        "via-openrouter": "yellow",
        "missing": "red",
    }
    for status in report:
        colour = style_by_status.get(status.status, "white")
        table.add_row(status.name, f"[{colour}]{status.status}[/{colour}]", status.detail)

    console.print(table)
    console.print(f"[dim]Key Config: {escape(str(resolved))}[/dim]")
    for warning in config.load_warnings:
        console.print(f"[yellow]warning:[/yellow] {escape(warning)}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _print_result(result) -> None:  # type: ignore[no-untyped-def]
    from rich.tree import Tree

    status = "✅ [green]PASSED[/green]" if result.validation.passed else "❌ [red]FAILED[/red]"

    table = Table.grid(padding=(0, 1))
    table.add_row("Output:", str(result.output_path))
    table.add_row("Agents:", str(len(result.team.agents)))
    table.add_row("Tasks:", str(len(result.team.tasks)))
    table.add_row("Files written:", str(len(result.written_files)))
    table.add_row("Validation:", status)
    console.print(Panel(table, title="[bold green]Team generated[/bold green]", expand=False))

    if result.validation.issues:
        console.print("\n[bold red]Validation issues:[/bold red]")
        for issue in result.validation.issues:
            console.print(f"  • {issue}")

    if result.validation.warnings:
        console.print("\n[yellow]Warnings:[/yellow]")
        for warn in result.validation.warnings:
            console.print(f"  • {warn}")

    tree = Tree(f"[dim]{result.output_path}[/dim]")
    dirs: dict[str, "Tree"] = {}
    for path in sorted(result.written_files):
        parts = path.split("/")
        if len(parts) == 1:
            tree.add(parts[0])
        else:
            parent = parts[0]
            if parent not in dirs:
                dirs[parent] = tree.add(f"[bold]{parent}/[/bold]")
            dirs[parent].add(parts[-1])
    console.print(tree)
