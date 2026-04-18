"""Writes a manifest of {relative_path: content} entries to an output directory."""
from __future__ import annotations

from pathlib import Path
from typing import Dict

from team_maker.utils.fs import ensure_dir

# Type alias for clarity
ArtifactManifest = Dict[str, str]


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

        written: list[str] = []
        for rel_path, content in manifest.items():
            dest = output_path / rel_path
            ensure_dir(dest.parent)
            dest.write_text(content, encoding="utf-8")
            written.append(rel_path)
        return written

    @staticmethod
    def _check_output_path(path: Path, overwrite: bool) -> None:
        if path.exists() and any(path.iterdir()):
            if not overwrite:
                raise FileExistsError(
                    f"Output directory already exists and is not empty: {path}\n"
                    "Pass --overwrite (or set overwrite: true in your request) to replace it."
                )
