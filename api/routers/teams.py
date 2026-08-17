"""The teams routes (Story 2-5: Named teams — save, browse, rename, delete).

All handlers are `def`, not `async def` — nothing in the teams feature is async.
Every handler's first statement is `state = app_state(request)`.

Storage per AD-11: SQLite for metadata (`./data/teams.db`), filesystem for
team packages and run results (`./data/saved_teams/`).
"""
from __future__ import annotations

import json
import logging
import shutil
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Request, status

from api.deps import safe_label
from api.errors import (
    INTERNAL_ERROR,
    NOT_FOUND,
    OUTPUT_EXISTS,
    REQUEST_REJECTED,
    ApiError,
)
from api.output import output_root
from api.schemas import (
    MessageView,
    TeamListView,
    TeamRecentRequest,
    TeamRecordRunRequest,
    TeamRenameRequest,
    TeamSaveRequest,
    TeamSaveResponse,
    TeamView,
)
from api.state import app_state

logger = logging.getLogger("api.teams")

router = APIRouter(prefix="/teams", tags=["teams"])


# ---------------------------------------------------------------------------
# SQLite storage helpers (per AD-11)
# ---------------------------------------------------------------------------

DB_PATH = Path(__file__).parent.parent.parent / "data" / "teams.db"
SAVED_TEAMS_ROOT = Path(__file__).parent.parent.parent / "data" / "saved_teams"


class TeamMetadata:
    """A row in the teams SQLite table."""

    def __init__(
        self,
        name: str,
        created_at: str,
        last_run_at: Optional[str] = None,
        run_count: int = 0,
        storage_path: str = "",
    ):
        self.name = name
        self.created_at = created_at
        self.last_run_at = last_run_at
        self.run_count = run_count
        self.storage_path = storage_path


def _ensure_db_dirs() -> None:
    """Create data/ and data/saved_teams/ if they do not exist."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    SAVED_TEAMS_ROOT.mkdir(parents=True, exist_ok=True)


def _get_connection():
    """Return a sqlite3 connection to teams.db.

    WAL mode plus a busy timeout so a concurrent reader/writer gets a short
    wait instead of an immediate "database is locked" `OperationalError`.
    """
    _ensure_db_dirs()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    _init_schema(conn)
    return conn


def _init_schema(conn) -> None:
    """Create tables if they do not exist.

    `name` carries `COLLATE NOCASE` directly on the primary key so the
    database itself is the single source of truth for case-insensitive
    uniqueness — closing the check-then-act race a Python-side pre-check
    cannot close alone (two concurrent saves differing only in case could
    otherwise both pass a `SELECT` before either `INSERT` commits).
    """
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS teams (
            name TEXT PRIMARY KEY COLLATE NOCASE,
            created_at TEXT NOT NULL,
            last_run_at TEXT,
            run_count INTEGER NOT NULL DEFAULT 0,
            storage_path TEXT NOT NULL
        )
        """
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Reserved names
# ---------------------------------------------------------------------------

# Guessed ahead of Epic 3 shipping its real starter-team names; reconcile once
# it does (see deferred-work.md).
_RESERVED_STARTER_NAMES = frozenset({
    "starter", "example", "demo", "template", "sample",
    "baseline_education_team", "research_content_team",
})

# This router's own static path segments. A team saved under one of these
# names would otherwise be unreachable via `GET /{team_name}` (shadowed by the
# static route declared ahead of it) for "recent"/"browse", or would create a
# confusing dual meaning for "save"/"rename"/"delete".
_RESERVED_ROUTE_NAMES = frozenset({"recent", "browse", "save", "rename", "delete"})

RESERVED_TEAM_NAMES = _RESERVED_STARTER_NAMES | _RESERVED_ROUTE_NAMES


def _is_reserved(name: str) -> bool:
    """Return True if the name is reserved."""
    return name.lower() in RESERVED_TEAM_NAMES


def _validate_team_name(name: str, exclude_existing: Optional[str] = None) -> None:
    """Validate team name: non-empty, unique (case-insensitive), not reserved.

    This is a fast-fail pre-check for a friendly error message before any file
    I/O happens. The database's `COLLATE NOCASE` primary key is the actual
    authority — `save_team`/`rename_team` also catch `sqlite3.IntegrityError`
    at write time in case two requests race past this check.
    """
    name_stripped = name.strip()
    if not name_stripped or len(name_stripped) < 2:
        raise ApiError(
            REQUEST_REJECTED,
            "Team name must be at least 2 characters long and non-blank.",
        )

    if _is_reserved(name_stripped):
        raise ApiError(
            REQUEST_REJECTED,
            f"Team name '{safe_label(name_stripped)}' is reserved and cannot be used.",
        )

    conn = _get_connection()
    cursor = conn.execute(
        "SELECT name FROM teams WHERE LOWER(name) = LOWER(?)",
        (name_stripped,),
    )
    existing = cursor.fetchone()
    conn.close()

    if existing is not None and existing["name"] != exclude_existing:
        raise ApiError(
            OUTPUT_EXISTS,
            f"Team name '{safe_label(name_stripped)}' already exists (case-insensitive).",
        )


# ---------------------------------------------------------------------------
# Storage path helpers
# ---------------------------------------------------------------------------


def _team_storage_path(team_name: str) -> Path:
    """Return the directory path for a team's stored data.

    Contained to `SAVED_TEAMS_ROOT`: `team_name` reaches here from client
    input, and a value like `"../../etc"` — or an absolute path, which
    `Path.__truediv__` would let discard `SAVED_TEAMS_ROOT` entirely — would
    otherwise let save/rename/delete touch any path the process can reach.
    Mirrors `api/routers/run.py`'s `_resolve_team_path` containment check.
    """
    root = SAVED_TEAMS_ROOT.resolve()
    resolved = (root / team_name).resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        raise ApiError(REQUEST_REJECTED, "Invalid team name.") from None
    return resolved


def _run_storage_path(team_name: str, run_id: str) -> Path:
    """Return the directory path for a specific run's stored data."""
    return _team_storage_path(team_name) / "runs" / run_id


def resolve_saved_team_path(team_name: str) -> Optional[Path]:
    """The saved-team package directory for `team_name`, if one exists on disk.

    Story 2.8: `api/routers/run.py`'s `_load_team_or_404` reads only
    `output_root()` (the Factory's build-output directory) by default, which is
    a different root from `SAVED_TEAMS_ROOT`. A saved team's original build
    output is not guaranteed to still exist there (a different build session, a
    cleaned-up directory, or a name that no longer slugs to the same value), so
    the run group falls back to this lookup to let My Teams reopen a team's
    Workspace regardless. Returns `None` rather than raising for an
    invalid/traversal name or a name with no saved directory — the caller
    treats either as "no fallback available", not a reportable error, since the
    primary `output_root()` lookup already produced the authoritative
    `team_not_found` for a genuinely bad slug.
    """
    try:
        path = _team_storage_path(team_name)
    except ApiError:
        return None
    return path if path.is_dir() else None


def _save_team_files(team_name: str, team_package_path: Path, run_results: Optional[dict] = None) -> Path:
    """Copy the team package and optionally run results into the storage tree.

    Returns the team storage path. `team_package_path` is trusted to exist and
    be a directory here — `save_team` already validated both, together with
    containment under `output_root()`, before calling this.
    """
    storage_path = _team_storage_path(team_name)
    storage_path.mkdir(parents=True, exist_ok=True)

    for item in team_package_path.iterdir():
        dest = storage_path / item.name
        if item.is_dir():
            shutil.copytree(item, dest, dirs_exist_ok=True)
        else:
            shutil.copy2(item, dest)

    if run_results is not None:
        _save_run_results(storage_path, run_results)

    return storage_path


def _save_run_results(storage_path: Path, run_results: dict) -> Path:
    """Persist one run's results as JSON under the team's `runs/` directory.

    Shared by `save_team` (the initial run, if any) and `record_team_run`
    (every subsequent run) so both write the same shape.
    """
    runs_dir = storage_path / "runs"
    runs_dir.mkdir(exist_ok=True)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    run_dir = runs_dir / run_id
    run_dir.mkdir(exist_ok=True)
    (run_dir / "results.json").write_text(json.dumps(run_results, indent=2, default=str))
    return run_dir


def _delete_team_files(team_name: str) -> None:
    """Delete the team's storage directory and all its contents."""
    storage_path = _team_storage_path(team_name)
    if storage_path.exists():
        shutil.rmtree(storage_path)


# ---------------------------------------------------------------------------
# Recent teams (transient, not persisted to SQLite)
# ---------------------------------------------------------------------------

# In-memory cache for recent teams (cleared on restart, per AD-11: transient).
# Stores (team_name, recorded_at) pairs: a team that was run but never saved
# has no DB row, so `list_recent_teams` falls back to this timestamp instead
# of silently dropping the entry. Guarded by a lock — FastAPI's sync `def`
# handlers run on a thread pool, and list mutation here is not atomic.
_recent_teams: List[tuple] = []
_recent_teams_lock = threading.Lock()
_MAX_RECENT = 10


def _add_to_recent(team_name: str) -> None:
    """Record a team as recently accessed, most-recent first.

    Does not require a saved DB row — a team whose save was declined still
    gets a recent-teams entry (the AC this satisfies).
    """
    global _recent_teams
    now = datetime.now(timezone.utc).isoformat()
    with _recent_teams_lock:
        _recent_teams = [(name, ts) for name, ts in _recent_teams if name != team_name]
        _recent_teams.insert(0, (team_name, now))
        _recent_teams = _recent_teams[:_MAX_RECENT]


def _remove_from_recent(team_name: str) -> None:
    """Remove a team from the recent teams list."""
    global _recent_teams
    with _recent_teams_lock:
        _recent_teams = [(name, ts) for name, ts in _recent_teams if name != team_name]


# ---------------------------------------------------------------------------
# GET /api/teams/recent, POST /api/teams/recent
# ---------------------------------------------------------------------------


@router.get("/recent", response_model=List[TeamView])
def list_recent_teams(request: Request) -> List[TeamView]:
    """List recently accessed teams (transient, not persisted).

    A name with no matching DB row — recorded via `POST /recent` for a run
    whose save was declined — still gets an entry, using its recorded-at time
    and zeroed metadata rather than being silently dropped.
    """
    state = app_state(request)
    with _recent_teams_lock:
        snapshot = list(_recent_teams)

    result: List[TeamView] = []
    for team_name, recorded_at in snapshot:
        conn = _get_connection()
        cursor = conn.execute(
            "SELECT name, created_at, last_run_at, run_count FROM teams WHERE name = ?",
            (team_name,),
        )
        row = cursor.fetchone()
        conn.close()

        if row is not None:
            result.append(
                TeamView(
                    name=row["name"],
                    created_at=row["created_at"],
                    last_run_at=row["last_run_at"],
                    run_count=row["run_count"],
                )
            )
        else:
            result.append(
                TeamView(name=team_name, created_at=recorded_at, last_run_at=None, run_count=0)
            )

    return result


@router.post("/recent", response_model=MessageView)
def add_recent_team(payload: TeamRecentRequest, request: Request) -> MessageView:
    """Record a team as recently accessed without saving it.

    Backs the AC "declining the save prompt persists nothing beyond a
    recent-teams entry": a completed-but-unsaved run has no DB row, so before
    this endpoint existed it could never appear in `_recent_teams` at all.
    """
    state = app_state(request)
    name = payload.team_name.strip()
    if _is_reserved(name):
        raise ApiError(
            REQUEST_REJECTED, f"Team name '{safe_label(name)}' is reserved and cannot be used."
        )
    _add_to_recent(name)
    return MessageView(message=f"'{safe_label(name)}' added to recent teams.")


# ---------------------------------------------------------------------------
# GET /api/teams/browse (or GET /api/teams)
# ---------------------------------------------------------------------------


@router.get("", response_model=TeamListView)
@router.get("/browse", response_model=TeamListView)
def list_teams(request: Request) -> TeamListView:
    """List all saved teams with metadata."""
    state = app_state(request)

    conn = _get_connection()
    cursor = conn.execute(
        "SELECT name, created_at, last_run_at, run_count FROM teams ORDER BY name COLLATE NOCASE"
    )
    rows = cursor.fetchall()
    conn.close()

    teams: List[TeamView] = []
    for row in rows:
        teams.append(
            TeamView(
                name=row["name"],
                created_at=row["created_at"],
                last_run_at=row["last_run_at"],
                run_count=row["run_count"],
            )
        )

    return TeamListView(teams=teams)


# ---------------------------------------------------------------------------
# GET /api/teams/{team_name}
# ---------------------------------------------------------------------------


@router.get("/{team_name}", response_model=TeamView)
def get_team(team_name: str, request: Request) -> TeamView:
    """Get metadata for a specific team."""
    state = app_state(request)

    conn = _get_connection()
    cursor = conn.execute(
        "SELECT name, created_at, last_run_at, run_count FROM teams WHERE name = ?",
        (team_name,),
    )
    row = cursor.fetchone()
    conn.close()

    if row is None:
        raise ApiError(NOT_FOUND, f"Team '{safe_label(team_name)}' not found.")

    _add_to_recent(team_name)

    return TeamView(
        name=row["name"],
        created_at=row["created_at"],
        last_run_at=row["last_run_at"],
        run_count=row["run_count"],
    )


# ---------------------------------------------------------------------------
# POST /api/teams/save
# ---------------------------------------------------------------------------


@router.post("/save", response_model=TeamSaveResponse, status_code=status.HTTP_201_CREATED)
def save_team(payload: TeamSaveRequest, request: Request) -> TeamSaveResponse:
    """Save a team and its results under a user-provided name.

    Accepts:
    - team_name: the human-readable name (proposed by Composer, editable at save time)
    - team_package_path: path to the team package directory
    - run_results: optional run results to store alongside the team

    Returns the saved team's metadata.
    """
    state = app_state(request)

    team_name = payload.team_name.strip()
    _validate_team_name(team_name)

    # Contained to `output_root()` — every real team package the Composer's
    # build step produces lands there (`api/output.py:derive_output_path`), so
    # a `team_package_path` outside it is either a mistake or an attempt to
    # have this endpoint copy and re-serve an arbitrary directory the server
    # process can read.
    team_package_path = Path(payload.team_package_path).expanduser().resolve()
    try:
        team_package_path.relative_to(output_root())
    except ValueError:
        raise ApiError(
            REQUEST_REJECTED,
            "Team package path must be within the generated teams output directory.",
        ) from None
    if not team_package_path.exists():
        raise ApiError(
            REQUEST_REJECTED,
            f"Team package path '{safe_label(payload.team_package_path)}' does not exist.",
        )
    if not team_package_path.is_dir():
        raise ApiError(
            REQUEST_REJECTED,
            f"Team package path '{safe_label(payload.team_package_path)}' is not a directory.",
        )

    now = datetime.now(timezone.utc).isoformat()
    storage_path = _save_team_files(team_name, team_package_path, payload.run_results)

    conn = _get_connection()
    try:
        conn.execute(
            """
            INSERT INTO teams (name, created_at, last_run_at, run_count, storage_path)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                team_name,
                now,
                now if payload.run_results is not None else None,
                1 if payload.run_results is not None else 0,
                str(storage_path),
            ),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        # A concurrent save of the same (case-insensitive) name won the race
        # to `INSERT` — undo the file copy above rather than leave an orphaned
        # directory with no owning DB row.
        shutil.rmtree(storage_path, ignore_errors=True)
        raise ApiError(
            OUTPUT_EXISTS,
            f"Team name '{safe_label(team_name)}' already exists (case-insensitive).",
        ) from None
    conn.close()

    _add_to_recent(team_name)

    return TeamSaveResponse(
        name=team_name,
        created_at=now,
        storage_path=str(storage_path),
        message="Team saved successfully.",
    )


# ---------------------------------------------------------------------------
# PUT /api/teams/rename
# ---------------------------------------------------------------------------


@router.put("/rename", response_model=TeamView)
def rename_team(payload: TeamRenameRequest, request: Request) -> TeamView:
    """Rename a team. New name must be case-insensitively unique and not reserved."""
    state = app_state(request)

    old_name = payload.old_name.strip()
    new_name = payload.new_name.strip()

    if old_name == new_name:
        raise ApiError(
            REQUEST_REJECTED,
            "Old and new team names are identical.",
        )

    _validate_team_name(new_name, exclude_existing=old_name)

    conn = _get_connection()
    cursor = conn.execute(
        "SELECT name, created_at, last_run_at, run_count, storage_path FROM teams WHERE name = ?",
        (old_name,),
    )
    row = cursor.fetchone()

    if row is None:
        conn.close()
        raise ApiError(NOT_FOUND, f"Team '{safe_label(old_name)}' not found.")

    old_storage_path = Path(row["storage_path"])
    new_storage_path = _team_storage_path(new_name)

    if not old_storage_path.exists():
        # Only ever updating the DB here (the original bug) would leave the
        # row pointing at a directory that was never created — refuse instead
        # of silently drifting metadata from the filesystem.
        conn.close()
        raise ApiError(
            INTERNAL_ERROR,
            f"Team '{safe_label(old_name)}' has no storage directory to rename; its data may be corrupted.",
        )

    old_storage_path.rename(new_storage_path)
    try:
        conn.execute(
            "UPDATE teams SET name = ?, storage_path = ? WHERE name = ?",
            (new_name, str(new_storage_path), old_name),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        # The DB write lost a race a concurrent request won between our
        # uniqueness pre-check and this update — reverse the filesystem move
        # rather than leave it renamed with no matching DB row.
        new_storage_path.rename(old_storage_path)
        conn.close()
        raise ApiError(
            OUTPUT_EXISTS,
            f"Team name '{safe_label(new_name)}' already exists (case-insensitive).",
        ) from None

    _remove_from_recent(old_name)
    _add_to_recent(new_name)

    cursor = conn.execute(
        "SELECT name, created_at, last_run_at, run_count FROM teams WHERE name = ?",
        (new_name,),
    )
    updated_row = cursor.fetchone()
    conn.close()

    if updated_row is None:
        raise ApiError(INTERNAL_ERROR, "Failed to rename team in database.")

    return TeamView(
        name=updated_row["name"],
        created_at=updated_row["created_at"],
        last_run_at=updated_row["last_run_at"],
        run_count=updated_row["run_count"],
    )


# ---------------------------------------------------------------------------
# DELETE /api/teams/delete and DELETE /api/teams/{team_name}
#
# Both perform the identical operation. `/delete` is the literal path this
# story's Technical Requirements table documents; `/{team_name}` addresses it
# RESTfully. `/delete` is declared first, deliberately — Starlette resolves by
# declaration order, and declaring the dynamic route first would swallow it.
# ---------------------------------------------------------------------------


@router.delete("/delete", response_model=MessageView)
def delete_team_by_name(request: Request, team_name: str) -> MessageView:
    """Delete a team, addressed by a `team_name` query parameter.

    A query parameter rather than a request body: `httpx`/`TestClient.delete()`
    (and several browser `fetch` configurations) do not send a body on DELETE,
    so a body-based design here would be a real interoperability trap.
    """
    state = app_state(request)
    return _delete_team(team_name)


@router.delete("/{team_name}", response_model=MessageView)
def delete_team(team_name: str, request: Request) -> MessageView:
    """Delete a team and all its saved runs/results."""
    state = app_state(request)
    return _delete_team(team_name)


def _delete_team(team_name: str) -> MessageView:
    conn = _get_connection()
    cursor = conn.execute("SELECT name FROM teams WHERE name = ?", (team_name,))
    row = cursor.fetchone()

    if row is None:
        conn.close()
        raise ApiError(NOT_FOUND, f"Team '{safe_label(team_name)}' not found.")

    # Delete from filesystem first (so we can't orphan files).
    _delete_team_files(team_name)

    try:
        conn.execute("DELETE FROM teams WHERE name = ?", (team_name,))
        conn.commit()
    except Exception as exc:
        conn.close()
        # Logged server-side only (api/errors.py's rule) — the message tells
        # the client the true, unrecoverable-by-them state rather than a bare
        # 500, since a retry will keep hitting the same stale-row conflict.
        logger.error(
            "team %r: files were deleted but its database record could not be removed",
            safe_label(team_name),
            exc_info=exc,
        )
        raise ApiError(
            INTERNAL_ERROR,
            f"Team '{safe_label(team_name)}' files were deleted, but its database "
            f"record could not be removed. This name will stay blocked until the "
            f"record is repaired manually.",
        ) from exc
    conn.close()

    _remove_from_recent(team_name)

    return MessageView(
        message=f"Team '{safe_label(team_name)}' and all its saved runs/results have been deleted."
    )


# ---------------------------------------------------------------------------
# POST /api/teams/{team_name}/record-run
# ---------------------------------------------------------------------------


@router.post("/{team_name}/record-run", response_model=TeamView)
def record_team_run(team_name: str, payload: TeamRecordRunRequest, request: Request) -> TeamView:
    """Record that a saved team was just run again.

    `last_run_at`/`run_count` were previously set once, at save time, and
    never touched again — Story 2-4's re-run flow calls this so Browse
    reflects reality after a re-run. Two segments under `/teams`, so it cannot
    collide with any single-segment static route (`/recent`, `/browse`, ...).
    """
    state = app_state(request)

    conn = _get_connection()
    cursor = conn.execute(
        "SELECT storage_path FROM teams WHERE name = ?",
        (team_name,),
    )
    row = cursor.fetchone()
    if row is None:
        conn.close()
        raise ApiError(NOT_FOUND, f"Team '{safe_label(team_name)}' not found.")

    if payload.run_results is not None:
        _save_run_results(Path(row["storage_path"]), payload.run_results)

    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "UPDATE teams SET last_run_at = ?, run_count = run_count + 1 WHERE name = ?",
        (now, team_name),
    )
    conn.commit()

    cursor = conn.execute(
        "SELECT name, created_at, last_run_at, run_count FROM teams WHERE name = ?",
        (team_name,),
    )
    updated_row = cursor.fetchone()
    conn.close()

    _add_to_recent(team_name)

    return TeamView(
        name=updated_row["name"],
        created_at=updated_row["created_at"],
        last_run_at=updated_row["last_run_at"],
        run_count=updated_row["run_count"],
    )
