"""Unit tests for context_dir feature."""
from __future__ import annotations

import pytest
from pathlib import Path
from pydantic import ValidationError

from team_maker.codegen import render_template
from team_maker.llm.prompts import build_user_message, _load_context_files
from team_maker.schema.request import RoleDefinition, SandboxConfig, TeamCreationRequest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_request(context_dir=None, **kwargs) -> TeamCreationRequest:
    defaults = dict(
        team_name="Ctx Team",
        purpose="A team that reads context files to inform its decisions.",
        output_path="/tmp/ctx_out",
        desired_roles=[RoleDefinition(name="analyst", description="Analyses context.")],
    )
    defaults.update(kwargs)
    if context_dir is not None:
        defaults["context_dir"] = str(context_dir)
    return TeamCreationRequest(**defaults)


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------

def test_context_dir_defaults_to_none():
    req = _make_request()
    assert req.context_dir is None


def test_context_dir_valid_directory(tmp_path):
    req = _make_request(context_dir=tmp_path)
    assert req.context_dir == str(tmp_path.resolve())


def test_context_dir_resolved_to_absolute(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    sub = tmp_path / "docs"
    sub.mkdir()
    req = _make_request(context_dir="docs")
    assert Path(req.context_dir).is_absolute()


def test_context_dir_nonexistent_raises(tmp_path):
    with pytest.raises(ValidationError) as exc_info:
        _make_request(context_dir=tmp_path / "does_not_exist")
    assert "context_dir" in str(exc_info.value)


def test_context_dir_file_path_raises(tmp_path):
    f = tmp_path / "file.txt"
    f.write_text("hello")
    with pytest.raises(ValidationError):
        _make_request(context_dir=f)


# ---------------------------------------------------------------------------
# _load_context_files helper
# ---------------------------------------------------------------------------

def test_load_context_files_empty_dir(tmp_path):
    assert _load_context_files(str(tmp_path)) == ""


def test_load_context_files_returns_content(tmp_path):
    (tmp_path / "spec.md").write_text("# My Spec\nDo something important.")
    (tmp_path / "notes.txt").write_text("Some domain notes.")
    result = _load_context_files(str(tmp_path))
    assert "spec.md" in result
    assert "My Spec" in result
    assert "notes.txt" in result
    assert "domain notes" in result


def test_load_context_files_nested(tmp_path):
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "deep.md").write_text("Deep content.")
    result = _load_context_files(str(tmp_path))
    assert "sub" in result
    assert "Deep content" in result


def test_load_context_files_nonexistent_dir():
    assert _load_context_files("/nonexistent/path/xyz") == ""


# ---------------------------------------------------------------------------
# build_user_message injects context
# ---------------------------------------------------------------------------

def test_user_message_without_context_dir():
    req = _make_request()
    msg = build_user_message(req)
    assert "Context files" not in msg


def test_user_message_injects_context_files(tmp_path):
    (tmp_path / "architecture.md").write_text("Use hexagonal architecture.")
    req = _make_request(context_dir=tmp_path)
    msg = build_user_message(req)
    assert "Context files provided by the user" in msg
    assert "architecture.md" in msg
    assert "hexagonal architecture" in msg


def test_user_message_skips_empty_context_dir(tmp_path):
    req = _make_request(context_dir=tmp_path)
    msg = build_user_message(req)
    assert "Context files" not in msg


# ---------------------------------------------------------------------------
# tools.py.j2 template rendering
# ---------------------------------------------------------------------------

def test_tools_template_no_context_dir():
    out = render_template("tools.py.j2", sandbox=SandboxConfig(), suggested_tools=[], context_dir=None)
    assert "context_reader" not in out
    assert "CONTEXT_DIR" not in out


def test_tools_template_with_context_dir(tmp_path):
    out = render_template(
        "tools.py.j2",
        sandbox=SandboxConfig(),
        suggested_tools=[],
        context_dir=str(tmp_path),
    )
    assert "CONTEXT_DIR" in out
    assert "context_reader_tool" in out
    assert str(tmp_path) in out
    assert '"context_reader": context_reader_tool' in out


def test_tools_template_context_reader_lists_files(tmp_path):
    out = render_template(
        "tools.py.j2",
        sandbox=SandboxConfig(),
        suggested_tools=[],
        context_dir=str(tmp_path),
    )
    assert "CONTEXT_DIR.rglob" in out
    assert "path.read_text" in out
