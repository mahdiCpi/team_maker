"""Thin wrappers around PyYAML with sane defaults."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml


def load_yaml(path: Path) -> Dict[str, Any]:
    """Load a YAML file and return a dict. Raises on parse errors."""
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected a YAML mapping in {path}, got {type(data).__name__}")
    return data


def dump_yaml(data: Any, *, indent: int = 2, default_flow_style: bool = False) -> str:
    """Serialise *data* to a YAML string."""
    return yaml.dump(
        data,
        default_flow_style=default_flow_style,
        allow_unicode=True,
        indent=indent,
        sort_keys=False,
    )
