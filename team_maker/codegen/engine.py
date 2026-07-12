"""Jinja2 rendering engine for all generated file templates."""
from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

_TEMPLATES_DIR = Path(__file__).parent / "templates"

_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES_DIR)),
    autoescape=False,          # generating Python code, not HTML
    keep_trailing_newline=True,
    trim_blocks=True,          # removes newline after block tags
    lstrip_blocks=True,        # strips leading whitespace before block tags
    undefined=StrictUndefined, # fail fast on missing context variables
)


def render_template(name: str, **context: object) -> str:
    """Render a Jinja2 template from the templates/ directory."""
    return _env.get_template(name).render(**context)
