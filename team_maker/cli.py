"""CLI entrypoint for team_maker.

Usage:
    python -m team_maker create --config path/to/request.yaml
    python -m team_maker run --package path/to/team "the goal"
    python -m team_maker list-templates
"""
from __future__ import annotations

import contextlib
import os
import sys
from pathlib import Path
from typing import Optional

import click
from pydantic import ValidationError
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from team_maker.adapters.providers import create_provider
from team_maker.adapters.providers.credential_utils import bridged_credential_context
from team_maker.adapters.providers.registry import PROVIDERS
from team_maker.composer.composer import Composer, ComposerError
from team_maker.composer.session import ComposerSession
from team_maker.keyconfig import KeyConfig
from team_maker.pipeline.runner import PipelineRunner
from team_maker.runtime.executor import UnsupportedFrameworkError, run_team_package
from team_maker.runtime.loader import TeamPackageError
from team_maker.runtime.preflight import InvalidPackageError, MissingCredentialsError
from team_maker.schema.request import ProviderConfig, TeamCreationRequest
from team_maker.utils.text_sanitizer import (
    sanitize_control_characters,
    sanitize_exception_for_display,
    sanitize_text_for_display,
)
from team_maker.utils.yaml_utils import dump_yaml, load_yaml

console = Console()
err_console = Console(stderr=True, style="red")

_DEFAULT_AUTHORING_PROVIDER = "anthropic"
_DEFAULT_AUTHORING_MODEL = "claude-sonnet-4-6"


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
            loc = " → ".join(str(part) for part in error["loc"])
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
# compose
# ---------------------------------------------------------------------------


def _resolve_authoring_provider(key_config: KeyConfig, model_override: Optional[str]) -> ProviderConfig:
    """Build the ProviderConfig for the Composer's own authoring model.

    Pure — no env mutation here. Credential resolution happens separately in
    `_bridged_credential`, scoped to the single call that needs it.
    """
    env_var = next(
        (p.env_var for p in PROVIDERS if p.name == _DEFAULT_AUTHORING_PROVIDER), None
    )
    return ProviderConfig(
        provider=_DEFAULT_AUTHORING_PROVIDER,
        model=model_override or _DEFAULT_AUTHORING_MODEL,
        api_key_env=env_var,
    )


@contextlib.contextmanager
def _bridged_credential(key_config: KeyConfig, provider: str, env_var: Optional[str]):
    """Temporarily bridge the Key Config's credential for `provider` into `env_var`.

    The existing adapters (Story 0.1) read credentials via `os.environ.get(...)`
    internally, so this is the point where `.get_secret_value()` is called (AD-9),
    only for the duration of the wrapped block — whatever was in `env_var` before
    is restored on exit, so the secret never persists past this single CLI call.
    
    Uses shared credential utilities from adapters/providers/credential_utils.py
    (Story 4.2) for consistency with API credential resolution.
    """
    with bridged_credential_context(key_config, provider, env_var):
        yield


@main.command()
@click.argument("intent")
@click.option(
    "--out",
    "-o",
    default=None,
    type=click.Path(path_type=Path),
    help="Write the composed spec as YAML to this path (default: print to stdout).",
)
@click.option(
    "--key-file",
    "-f",
    "key_file",
    default=None,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Path to the Key Config file (default: $TEAM_MAKER_KEYS or ./team_maker.keys).",
)
@click.option("--model", default=None, help="Override the authoring model (default: claude-sonnet-4-6).")
@click.option(
    "--build",
    "build_now",
    is_flag=True,
    default=False,
    help="Immediately build the composed spec via the pipeline runner.",
)
@click.option(
    "--interactive",
    "-i",
    is_flag=True,
    default=False,
    help="Refine the spec over a back-and-forth; type 'run now' at any turn to build immediately.",
)
@click.option("--quiet", "-q", is_flag=True, default=False, help="Suppress progress output.")
def compose(
    intent: str,
    out: Optional[Path],
    key_file: Optional[Path],
    model: Optional[str],
    build_now: bool,
    interactive: bool,
    quiet: bool,
) -> None:
    """Describe a team in plain language and get a valid Team Spec."""
    from rich.markup import escape

    key_config = KeyConfig.from_file(key_file)
    authoring_config = _resolve_authoring_provider(key_config, model)

    # Widened to cover the whole flow — interactive turns AND an optional
    # "run now"/--build — since the bridged credential is restored the
    # instant this `with` block exits, and the build's own model-resolution
    # step may also want the authoring provider's key present.
    with _bridged_credential(key_config, _DEFAULT_AUTHORING_PROVIDER, authoring_config.api_key_env):
        try:
            llm_provider = create_provider(authoring_config)
            composer = Composer(llm_provider, key_config=key_config)

            if interactive:
                session = ComposerSession(composer)
                request = session.start(intent)
                # Story 2.10: `start()` returns None when the intent does not
                # describe a team, instead of fabricating one. The CLI has no
                # multi-turn "needs_clarification" surface like the API does,
                # so this is a clean exit rather than a crash on
                # `request.model_dump(...)` below.
                if request is None:
                    err_console.print(
                        "[bold]That doesn't look like a description of a team to build.[/bold] "
                        "Try again with a plain-language description of the team you want."
                    )
                    sys.exit(2)
                if not quiet:
                    _print_spec_summary(request, title="Composed team spec")

                while True:
                    if not quiet:
                        console.print(
                            "[dim]Refine further, type 'run now' to build, or 'done' to finish:[/dim]"
                        )
                    try:
                        line = input().strip()
                    except EOFError:
                        line = ""
                    lowered = line.lower()
                    if lowered in ("", "done", "exit"):
                        break
                    if lowered in ("run now", "run", "build"):
                        build_now = True
                        break
                    try:
                        request = session.refine(line)
                    except ComposerError as exc:
                        # Sanitize before display to prevent secrets from leaking
                        # (AD-9) -- this loop shares the exact `ComposerError`
                        # surface as the handlers below and must not skip the
                        # same sanitization (code review P6).
                        sanitized_msg = sanitize_exception_for_display(exc)
                        err_console.print(
                            f"[bold]Could not apply that change:[/bold] {escape(sanitized_msg)}"
                        )
                        for error in exc.errors:
                            err_console.print(f"  • {escape(sanitize_text_for_display(error))}")
                        continue
                    if request is None:
                        err_console.print(
                            "[bold]That doesn't look like a description of a team to build.[/bold] "
                            "Describe the team you want, or type 'done' to finish."
                        )
                        continue
                    if not quiet:
                        _print_spec_summary(request, title="Updated team spec")
            else:
                request = composer.compose(intent)
        except ComposerError as exc:
            # Sanitize exception message before display to prevent secrets from leaking
            # Per AD-9: keys and sensitive data must never be exposed to users
            sanitized_msg = sanitize_exception_for_display(exc)
            err_console.print(f"[bold]Could not compose a valid team specification:[/bold] {escape(sanitized_msg)}")
            for error in exc.errors:
                err_console.print(f"  • {escape(sanitize_text_for_display(error))}")
            sys.exit(2)
        except Exception as exc:
            # Sanitize exception message before display to prevent secrets from leaking
            # Per AD-9: keys and sensitive data must never be exposed to users
            sanitized_msg = sanitize_exception_for_display(exc)
            err_console.print(f"[bold]Compose failed:[/bold] {escape(sanitized_msg)}")
            sys.exit(1)

        # The spec is the command's actual deliverable — always emit it somewhere,
        # even under --quiet (which only suppresses the decorative summary below).
        spec_yaml = dump_yaml(request.model_dump(mode="json", exclude_none=True))
        if out is not None:
            try:
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(spec_yaml, encoding="utf-8")
            except OSError as exc:
                err_console.print(f"[bold]Could not write spec to {escape(str(out))}:[/bold] {escape(str(exc))}")
                sys.exit(1)
            if not quiet:
                console.print(f"[dim]Spec written to {escape(str(out))}[/dim]")
        else:
            console.print(spec_yaml)

        # Interactive mode already showed the up-to-date panel before every
        # prompt (start + each successful refine) — don't reprint it here.
        if not quiet and not interactive:
            _print_spec_summary(request, title="Composed team spec")

        if build_now:
            runner = PipelineRunner()
            try:
                result = runner.run(request)
            except FileExistsError as exc:
                err_console.print(f"[bold]Output conflict:[/bold] {exc}")
                sys.exit(1)
            except Exception as exc:
                err_console.print(f"[bold]Pipeline error:[/bold] {exc}")
                raise  # re-raise for full traceback in debug scenarios

            if not quiet:
                _print_result(result)
            if not result.validation.passed:
                sys.exit(2)


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------


def _is_crewai_missing(exc: ImportError) -> bool:
    """True only when crewai itself is absent, not when a provider module is.

    `import crewai` failing and `LLM(model="groq/...")` failing both raise
    ImportError, but they need opposite advice: install the runtime extra, or
    stop routing to a provider this engine cannot reach.
    """
    name = getattr(exc, "name", None) or ""
    if name == "crewai" or name.startswith("crewai."):
        return True
    return "crewai" in str(exc).lower() and "no module named" in str(exc).lower()


@main.command()
@click.option(
    "--package",
    "-p",
    "package",
    required=True,
    # No exists=True: a missing/malformed package is handled uniformly by our
    # own TeamPackageError below (exit 1), not Click's usage-error path
    # (which would exit 2 before our error handling ever ran).
    type=click.Path(path_type=Path),
    help="Path to an already-built Team Package directory.",
)
@click.argument("goal")
@click.option(
    "--key-file",
    "-f",
    "key_file",
    default=None,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Path to the Key Config file (default: $TEAM_MAKER_KEYS or ./team_maker.keys).",
)
@click.option("--quiet", "-q", is_flag=True, default=False, help="Suppress progress output.")
@click.option(
    "--transcript",
    "-t",
    is_flag=True,
    default=False,
    help="Also print the full agent transcript (every message, handoff, and delegation).",
)
@click.option(
    "--transcript-out",
    type=click.Path(dir_okay=False, path_type=Path),
    help="Write the full agent transcript to this file.",
)
def run(
    package: Path,
    goal: str,
    key_file: Optional[Path],
    quiet: bool,
    transcript: bool,
    transcript_out: Optional[Path],
) -> None:
    """Run a built Team Package against a goal and print the results."""
    from rich.markup import escape

    key_config = KeyConfig.from_file(key_file)

    if not quiet:
        console.print(
            Panel(
                f"[bold cyan]{escape(str(package))}[/bold cyan]\n{escape(goal[:120])}",
                title="[bold]team_maker[/bold] · Running team",
                expand=False,
            )
        )

    try:
        result = run_team_package(package, goal, key_config)
    except (TeamPackageError, UnsupportedFrameworkError) as exc:
        err_console.print(f"[bold]Cannot run this package:[/bold] {escape(str(exc))}")
        sys.exit(1)
    except InvalidPackageError as exc:
        # Duplicate agent roles, blank or duplicated task names: the package
        # contradicts itself and no key would fix it.
        err_console.print(f"[bold]Invalid package:[/bold] {escape(str(exc))}", soft_wrap=True)
        sys.exit(1)
    except MissingCredentialsError as exc:
        # A configuration problem, not a broken package — kept as its own
        # category so the message tells the user what to actually do, and
        # echoing the resolved Key Config path makes "add the key" actionable.
        # soft_wrap: the message is a pre-rendered hanging-indent list, and
        # letting Rich re-wrap it at the console width destroys the alignment.
        err_console.print(
            f"[bold]Missing credentials:[/bold] {escape(str(exc))}", soft_wrap=True
        )
        # Any warning from loading the Key Config is very likely the explanation
        # (a typo'd key name is silently ignored at load time), so surface it
        # here rather than leaving the user staring at a file that looks right.
        for warning in key_config.load_warnings:
            err_console.print(f"[yellow]Note:[/yellow] {escape(str(warning))}")
        resolved = key_file or KeyConfig.default_path()
        err_console.print(f"[dim]Key Config: {escape(str(resolved))}[/dim]")
        sys.exit(1)
    except ImportError as exc:
        # Only a genuinely absent crewai gets the install hint. Provider modules
        # raise ImportError too (crewai has no native groq/xai, and google needs
        # an extra), and telling that user to install a package they already
        # have sends them down the wrong path entirely.
        if _is_crewai_missing(exc):
            err_console.print(
                "[bold]CrewAI is required to run a team.[/bold] Install it with: "
                + escape("pip install 'team_maker[runtime]'")
                + f" ({escape(str(exc))})"
            )
        else:
            err_console.print(
                "[bold]This provider is not available in the installed runtime:[/bold] "
                + escape(str(exc)),
                soft_wrap=True,
            )
        sys.exit(1)
    except Exception as exc:
        err_console.print(f"[bold]Run failed:[/bold] {escape(str(exc))}")
        sys.exit(1)

    if not quiet:
        _print_run_result(result)
        if transcript:
            _print_transcript(result)

    # Written even under --quiet: the file is a deliverable the user explicitly
    # asked for, matching how `compose` still writes its spec when quiet.
    if transcript_out is not None:
        if not result.transcript:
            # Never claim success for a zero-byte file — the console path says
            # the same thing, and a silently empty deliverable is worse than
            # none at all.
            err_console.print(
                "[bold]No transcript was captured for this run,[/bold] so nothing "
                f"was written to {escape(str(transcript_out))}."
            )
            sys.exit(1)
        try:
            transcript_out.parent.mkdir(parents=True, exist_ok=True)
            transcript_out.write_text(_format_transcript(result), encoding="utf-8")
        # ValueError covers UnicodeEncodeError: raw model output can contain
        # lone surrogates, which encode() rejects — and that is a far likelier
        # failure here than a disk error.
        except (OSError, ValueError) as exc:
            err_console.print(
                f"[bold]Could not write the transcript:[/bold] {escape(str(exc))}"
            )
            sys.exit(1)
        if not quiet:
            console.print(f"[dim]Transcript written to {escape(str(transcript_out))}[/dim]")


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

    from team_maker.adapters.providers.registry import report_availability
    from team_maker.keyconfig import KeyConfig

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


def _print_spec_summary(request: TeamCreationRequest, *, title: str) -> None:
    from rich.markup import escape

    console.print(
        Panel(
            f"[bold cyan]{escape(request.team_name)}[/bold cyan]\n"
            f"Roles: {len(request.desired_roles)} · Tasks: {len(request.desired_tasks)}",
            title=f"[bold]team_maker[/bold] · {title}",
            expand=False,
        )
    )


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


def _print_run_result(result) -> None:  # type: ignore[no-untyped-def]
    from rich.markup import escape

    console.print(
        Panel(
            escape(result.final_output),
            title="[bold green]Final result[/bold green]",
            expand=False,
        )
    )
    if result.task_results:
        table = Table(title="Per-task results", show_lines=True)
        table.add_column("Task", style="cyan", no_wrap=True)
        table.add_column("Agent", style="magenta", no_wrap=True)
        table.add_column("Output")
        for task_result in result.task_results:
            table.add_row(
                escape(task_result.name),
                escape(task_result.agent_role),
                escape(task_result.output),
            )
        console.print(table)


def _format_transcript(result) -> str:  # type: ignore[no-untyped-def]
    """Render the transcript as plain text, for the console or a file.

    One line per entry so the output stays greppable and diffable, and so the
    written file is the same thing the user saw on screen.
    """
    lines: list[str] = []
    # `or []` rather than assuming a list: RunResult is a plain dataclass with
    # no validation, and any ExecutionEngine implementation may hand back None.
    for entry in result.transcript or []:
        target = f" -> {entry.target_role}" if entry.target_role else ""
        header = f"[{entry.sequence}] {entry.task_name} / {entry.agent_role}{target} ({entry.kind})"
        lines.append(header)
        content = (entry.content or "").strip()
        if content:
            lines.extend(f"    {line}" for line in content.splitlines())
    return "\n".join(lines)


def _print_transcript(result) -> None:  # type: ignore[no-untyped-def]
    from rich.markup import escape

    if not result.transcript:
        console.print("[dim]No transcript was captured for this run.[/dim]")
        return
    console.print("\n[bold]Run transcript[/bold]")
    # Sanitize control characters (ANSI/OSC sequences) before displaying to prevent
    # terminal manipulation attacks. escape() only handles Rich markup brackets.
    # soft_wrap: the text is pre-indented, and re-wrapping destroys the layout.
    transcript_text = _format_transcript(result)
    sanitized_text = sanitize_control_characters(transcript_text)
    console.print(escape(sanitized_text), soft_wrap=True)
