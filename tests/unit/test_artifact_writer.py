"""Unit tests for ArtifactWriter."""
from __future__ import annotations

import pytest

from team_maker.artifacts.writer import ArtifactWriter


def test_writes_files_to_output_path(tmp_path):
    writer = ArtifactWriter()
    manifest = {
        "README.md": "# Hello",
        "agents/architect.yaml": "role: architect\n",
        "docs/how_to_run.md": "# Run guide",
    }
    written = writer.write(tmp_path / "out", manifest)
    assert len(written) == 3
    assert (tmp_path / "out" / "README.md").read_text() == "# Hello"
    assert (tmp_path / "out" / "agents" / "architect.yaml").read_text() == "role: architect\n"


def test_creates_nested_directories(tmp_path):
    writer = ArtifactWriter()
    manifest = {"a/b/c/deep.txt": "deep content"}
    writer.write(tmp_path / "out", manifest)
    assert (tmp_path / "out" / "a" / "b" / "c" / "deep.txt").exists()


def test_raises_when_dir_non_empty_and_no_overwrite(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "existing.txt").write_text("existing")

    writer = ArtifactWriter()
    with pytest.raises(FileExistsError, match="not empty"):
        writer.write(out, {"README.md": "new content"}, overwrite=False)


def test_overwrites_when_flag_set(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "README.md").write_text("old content")

    writer = ArtifactWriter()
    writer.write(out, {"README.md": "new content"}, overwrite=True)
    assert (out / "README.md").read_text() == "new content"


def test_creates_output_dir_if_missing(tmp_path):
    out = tmp_path / "brand_new_dir"
    assert not out.exists()
    writer = ArtifactWriter()
    writer.write(out, {"file.txt": "hello"})
    assert out.exists()


def test_returns_list_of_written_paths(tmp_path):
    writer = ArtifactWriter()
    manifest = {"a.txt": "a", "sub/b.txt": "b"}
    written = writer.write(tmp_path / "out", manifest)
    assert set(written) == {"a.txt", "sub/b.txt"}


def test_empty_manifest_writes_nothing(tmp_path):
    writer = ArtifactWriter()
    written = writer.write(tmp_path / "out", {})
    assert written == []
    assert (tmp_path / "out").exists()
