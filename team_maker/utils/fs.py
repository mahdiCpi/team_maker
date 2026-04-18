"""Filesystem utilities — no business logic here."""
from __future__ import annotations

import os
from pathlib import Path


def safe_output_path(raw_path: str) -> Path:
    """Expand ~, resolve relative paths, and return an absolute Path."""
    return Path(raw_path).expanduser().resolve()


def ensure_dir(path: Path) -> None:
    """Create directory and all parents; no-op if it already exists."""
    path.mkdir(parents=True, exist_ok=True)


def path_is_empty_or_missing(path: Path) -> bool:
    if not path.exists():
        return True
    return not any(path.iterdir())


def relative_file_list(root: Path) -> list[str]:
    """Return all files under *root* as forward-slash relative paths."""
    result: list[str] = []
    for p in sorted(root.rglob("*")):
        if p.is_file():
            result.append(p.relative_to(root).as_posix())
    return result
