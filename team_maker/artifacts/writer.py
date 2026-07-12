"""Writes a manifest of {relative_path: content} entries to an output directory."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Dict

from team_maker.utils.fs import ensure_dir

# Type alias for clarity
ArtifactManifest = Dict[str, str]

# Subdirectories team_maker owns — cleared on overwrite so stale files
# from previous runs don't confuse the loader.
_OWNED_SUBDIRS = ("agents", "tasks", "docs")

# Root-level files that team_maker owns conditionally (e.g. only when an
# Ollama sidecar is needed). Removed on overwrite so a re-run with a
# different config doesn't leave stale Compose/Docker files behind.
_OWNED_ROOT_FILES = ("docker-compose.yml", "Dockerfile", ".dockerignore")


class ArtifactWriter:
    """Writes all generated files to the output directory.

    Raises FileExistsError if the directory is non-empty and overwrite=False.
    """

    def write(
        self,
        output_path: Path,
        manifest: ArtifactManifest,
        *,
        overwrite: bool = False,
    ) -> list[str]:
        """Write every entry in *manifest* to *output_path*.

        Returns the list of written relative paths.
        """
        self._check_output_path(output_path, overwrite)
        ensure_dir(output_path)

        if overwrite:
            self._clear_owned_subdirs(output_path)

        written: list[str] = []
        for rel_path, content in manifest.items():
            dest = output_path / rel_path
            ensure_dir(dest.parent)
            dest.write_text(content, encoding="utf-8")
            written.append(rel_path)
        return written

    @staticmethod
    def _clear_owned_subdirs(output_path: Path) -> None:
        """Wipe team_maker-owned subdirs and conditional root files so stale
        artifacts from previous runs don't persist.

        Runtime artifacts (.venv, state/, workspace/, runner.log, __pycache__)
        are intentionally left alone so repeated overwrites don't blow away
        the user's venv or the team's state.
        """
        for sub in _OWNED_SUBDIRS:
            sub_path = output_path / sub
            if sub_path.is_dir():
                shutil.rmtree(sub_path)
        for fname in _OWNED_ROOT_FILES:
            f = output_path / fname
            if f.exists():
                f.unlink()

    @staticmethod
    def _check_output_path(path: Path, overwrite: bool) -> None:
        if path.exists() and any(path.iterdir()):
            if not overwrite:
                raise FileExistsError(
                    f"Output directory already exists and is not empty: {path}\n"
                    "Pass --overwrite (or set overwrite: true in your request) to replace it."
                )
