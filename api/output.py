"""Where a built team package is allowed to land (Story 2.0 code review, D2).

The problem this closes
-----------------------
``SpecEditRequest`` refuses ``output_path`` and three docstrings in this package
call the field "server-owned". That was true only of the *edit body*: the field
is authored by the LLM from free-text intent, and
``POST /sessions/{id}/messages {"message": "change output_path to ..."}`` walks
straight around the guard. ``validate_output_path`` (``request.py``) only strips
and rejects empty, and ``safe_output_path`` (``utils/fs.py``) only does
``expanduser().resolve()`` — so nothing bounded where a build could write.

So the API now *makes* the claim true: it derives the path itself and overwrites
whatever the composer produced. The client cannot influence it except through
the team name, which is already validated to letters, digits, underscores,
hyphens and spaces (``request.py``'s ``validate_team_name``) and is slugged
again here.

Why the path is frozen per session rather than recomputed
---------------------------------------------------------
It is derived once, from the first spec a session produces, and reused for every
later turn. Deriving it fresh each turn would move the output directory whenever
the user renamed the team mid-conversation — surprising, and it would mean the
path in turn 3's response no longer described where turn 2 would have built.

Deriving from the team name rather than the session id is deliberate too: it
keeps ``output_exists`` (409) reachable, which AC 2's error table requires. A
session-id-derived path is unique by construction, so building the same team
twice would silently succeed into two directories instead of telling the user
the first one is already there.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from team_maker.schema.request import TeamCreationRequest

# Relative paths resolve against the server's working directory, which is the
# repo root under `make api-dev`. `generated_teams/` already exists there and is
# gitignored, so it is where a build would have been told to go anyway.
OUTPUT_ROOT_ENV = "TEAM_MAKER_OUTPUT_ROOT"
DEFAULT_OUTPUT_ROOT = "generated_teams"

_UNSAFE = re.compile(r"[^a-z0-9]+")


def output_root() -> Path:
    """The one directory every build writes beneath, resolved absolute."""
    configured = os.environ.get(OUTPUT_ROOT_ENV) or DEFAULT_OUTPUT_ROOT
    return Path(configured).expanduser().resolve()


def slugify_team_name(team_name: str) -> str:
    """A single safe path segment. Never empty, never a traversal."""
    slug = _UNSAFE.sub("_", team_name.strip().lower()).strip("_")
    return slug or "team"


def derive_output_path(team_name: str) -> str:
    """The server-chosen output directory for a team of this name."""
    return str(output_root() / slugify_team_name(team_name))


def with_output_path(spec: TeamCreationRequest, output_path: str) -> TeamCreationRequest:
    """Return ``spec`` with the server's path substituted in.

    ``model_copy`` rather than a reconstruction: the value is ours, not the
    client's, so it needs no validation, and rebuilding through the constructor
    would re-run ``_pre_process`` on an already-processed spec for no reason.
    """
    if spec.output_path == output_path:
        return spec
    return spec.model_copy(update={"output_path": output_path})
