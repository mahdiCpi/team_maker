---
baseline_commit: e4a4fd840eae25e064927b4d0c69fe68ec2734bb
---

# Story 2-5: Named teams — save, browse, rename, delete

Status: done

## Overview
Enable users to save, browse, rename, and delete teams, ensuring `My Teams` remains meaningful and under user control. This story owns the `api/` teams group (save, browse, rename, delete, recent) and leverages local storage (SQLite + files) per AD-11.

---

## Functional Requirements
- FR-25: Save teams and results
- FR-26: Recent-teams list
- FR-28: Name/rename/delete teams
- AD-11: Local storage (SQLite + files)

---

## User Story
**As a user**, I want to save, name, rename, and delete teams, so that `My Teams` stays organized and reflects only the teams I care about.

---

## Acceptance Criteria
### Saving a Team
- **Given** a completed run, **when** the user is prompted to save, **then**:
  - Declining the prompt persists nothing beyond a recent-teams entry.
  - Accepting the prompt stores the team under a **human-readable name** (proposed by the Composer, editable at save time, and unique within `My Teams`).
  - The team and its results (run outputs) are stored locally (SQLite + files).

### Browsing Teams
- **Given** `My Teams` is open, **when** the user views the list, **then**:
  - All built teams are listed by name.
  - The user can reopen a team's workspace, re-run it, or rename it.

### Renaming a Team
- **Given** a team in `My Teams`, **when** the user renames it, **then**:
  - The new name must be **case-insensitively unique** within `My Teams`.
  - The new name must not conflict with reserved starter team names (Epic 3).
  - The change is reflected immediately in `My Teams` and recent teams.

### Deleting a Team
- **Given** a team in `My Teams`, **when** the user deletes it, **then**:
  - An explicit confirmation dialog specifies what will be deleted (the team and its saved runs/results).
  - After deletion, the team disappears from `My Teams` and recent teams.

---

## Technical Requirements
### API Endpoints (Owned by this Story)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/teams/save` | POST | Save a team and its results under a user-provided name. |
| `/api/teams/browse` | GET | List all saved teams (name, timestamp, last run). |
| `/api/teams/rename` | PUT | Rename a team (unique name constraint). |
| `/api/teams/delete` | DELETE | Delete a team and its saved runs/results. |
| `/api/teams/recent` | GET | List recently accessed teams (transient, not persisted). |

### Storage
- **SQLite**: Store team metadata (name, timestamp, last run, file paths).
- **Files**: Store team packages and run results (transcripts, outputs).
- **No external services**: All data resides in `./data/` (SQLite for metadata, filesystem for team packages/runs). Per AD-11.

### Dependencies
- **Story 2-0**: FastAPI app and compose endpoints must be in place.
- **Story 2-4**: Team Workspace functionality must be available for re-running teams.

---

## Developer Notes
> **Note**: Uses **team names** as stable references (not `session_id` per Epic 2.0).

### Implementation Guidance
1. **Team Name**:
   - Use the existing `TeamCreationRequest.team_name` field (`team_maker/schema/request.py`).
   - Ensure **case-insensitive uniqueness** within `My Teams`.

2. **Storage Structure**:
   ```
   team_maker/
   ├── data/
   │   ├── teams.db          # SQLite database (metadata)
   │   └── saved_teams/
   │       ├── <team_name_1>/  # Team package + results
   │       │   ├── team_config.yaml
   │       │   ├── routing_config.yaml
   │       │   ├── agents/
   │       │   ├── tasks/
   │       │   └── runs/
   │       │       ├── <run_id_1>/  # Run outputs + transcript
   │       │       └── <run_id_2>/
   │       └── <team_name_2>/
   ```

3. **API Contract**:
   - **Save**: Accept `team_name` (editable), `team_package_path`, and `run_results`.
   - **Browse**: Return a list of teams with metadata (name, last run timestamp, run count).
   - **Rename**: Accept `old_name` and `new_name` (validate uniqueness).
   - **Delete**: Accept `team_name` and confirm deletion of all associated data.

4. **Edge Cases**:
   - **Duplicate Names**: Reject with a clear error message (case-insensitive check).
   - **Deletion Confirmation**: Explicitly state what will be deleted (team + runs/results).
   - **Storage Limits**: Warn if disk space is low (optional).
   - **Reserved Names**: Reject names that conflict with starter team names (Epic 3).

---

## Tasks/Subtasks

### API Implementation
- [x] Create `api/routers/teams.py` with all endpoints
- [x] Add team schemas to `api/schemas.py`
- [x] Register teams router in `api/main.py`

### Storage Implementation
- [x] Implement SQLite database for team metadata
- [x] Implement filesystem storage for team packages and runs
- [x] Create data directory structure on demand

### Validation
- [x] Case-insensitive uniqueness for team names
- [x] Reserved name checking
- [x] Team name minimum length validation
- [x] Team package path validation

### Testing
- [x] Create comprehensive test suite in `tests/api/test_teams.py`
- [x] Test all endpoints (save, browse, get, rename, delete, recent)
- [x] Test edge cases (duplicates, reserved names, short names)
- [x] Update existing tests to account for new routes

### Integration
- [x] Update `test_health.py` to include new routes
- [x] Update `test_secret_containment.py` to include new routes

### Review Findings

**Decision needed (resolved during review — see Patch below):**
- [x] [Review][Decision] DELETE route path deviates from the spec's Technical Requirements table — **Resolved by Guru: add a literal `/api/teams/delete` route to match the table**, keeping the existing `/api/teams/{team_name}` route too. [api/routers/teams.py:216]
- [x] [Review][Decision] "Recent teams" cannot satisfy "declining the save prompt persists nothing beyond a recent-teams entry" — **Resolved by Guru: add backend support now** for a lightweight, unsaved/name-only recent entry not backed by a DB row. [api/routers/teams.py:158,247,313]
- [x] [Review][Decision] No mechanism updates `last_run_at`/`run_count` when a saved team is re-run — **Resolved by Guru: add a small endpoint now** that Story 2-4's re-run flow can call. [api/routers/teams.py:369-374]

**Patch (all applied — see Dev Agent Record's Fix Pass below):**
- [x] [Review][Patch] Add a literal `/api/teams/delete` DELETE route matching the spec's table, alongside the existing `/api/teams/{team_name}` DELETE route [api/routers/teams.py; api/schemas.py]
- [x] [Review][Patch] Add `POST /api/teams/recent` to record a name-only recent entry not backed by a saved DB row, and adjust `list_recent_teams` to render a fallback view for such entries [api/routers/teams.py:143-161,247; api/schemas.py]
- [x] [Review][Patch] Add an endpoint (e.g. `POST /api/teams/{team_name}/record-run`) that Story 2-4's re-run flow can call to update `last_run_at`/`run_count` after a re-run [api/routers/teams.py:369-374]
- [x] [Review][Patch] Unsanitized `team_name` used directly as a filesystem path segment enables path traversal in save/rename/delete (mirror `api/routers/run.py`'s existing `resolve()`+`relative_to(root)` containment check) [api/routers/teams.py:166-168,306-313,350-354]
- [x] [Review][Patch] `team_package_path` accepted verbatim from the client with no containment check, allowing arbitrary local directories to be copied into storage and served back (restrict to the canonical team-package output root, same pattern as run.py) [api/routers/teams.py:316-334]
- [x] [Review][Patch] TOCTOU race on the case-insensitive uniqueness check in save and rename — separate un-transactioned connections for the check vs. the write, and the resulting `sqlite3.IntegrityError`/lock errors are unhandled (perform check+write in one transaction or catch `IntegrityError` as the guard; enable WAL mode/busy_timeout) [api/routers/teams.py:267-298]
- [x] [Review][Patch] `rename_team`'s filesystem move and DB update are not transactional — DB is updated even when the source directory never existed, and a DB-commit failure after a successful move leaves no rollback [api/routers/teams.py:577-586]
- [x] [Review][Patch] `delete_team` has no error handling around the DB delete after files are removed — a failure there permanently strands a row with no backing files, blocking that name forever with `OUTPUT_EXISTS` [api/routers/teams.py:633-639]
- [x] [Review][Patch] Reserved-name check omits the router's own static path segments (`recent`, `browse`, `save`, `rename`) — a team saved under one of these names becomes unreachable via `GET /api/teams/{team_name}` (empirically confirmed for "recent"/"browse") [api/routers/teams.py:251-259]
- [x] [Review][Patch] `team_name` is interpolated unsanitized into `ApiError` messages — `api/routers/run.py` established a `safe_label()` precedent to stop injected control characters from forging log records; teams.py doesn't reuse it [api/routers/teams.py:274-297,467,572,631]
- [x] [Review][Patch] `run_results: {}` (present but empty) is silently treated as "no run" due to a truthiness check instead of `is not None`, dropping the fact that a run happened [api/routers/teams.py:337,525]
- [x] [Review][Patch] `test_list_teams_empty` doesn't monkeypatch `DB_PATH`/`SAVED_TEAMS_ROOT` like every other test in the file — it hits the real `./data/teams.db`, confirmed by this review's own `git status` showing an untracked `data/` directory created as a side effect [tests/api/test_teams.py:701-707]
- [x] [Review][Patch] `test_save_team_reserved_name`/`test_rename_team_reserved` assert on the error-message substring instead of the error code, unlike the sibling duplicate-name tests which correctly check `error.code` [tests/api/test_teams.py:800-828,997-1031]
- [x] [Review][Patch] `_save_team_files` re-checks `team_package_path.exists()`/`is_dir()` and only logs a warning on failure, duplicating (and, under a race, potentially disagreeing with) the handler's own check [api/routers/teams.py:316-334]
- [x] [Review][Patch] `_recent_teams` module-level global is mutated from multiple handlers with no lock, under FastAPI's threaded sync-handler execution — low severity given local single-user usage [api/routers/teams.py:143-161]

**Deferred:**
- [x] [Review][Defer] `RESERVED_TEAM_NAMES` is a hardcoded guess at Epic 3's starter-team names, which don't exist yet [api/routers/teams.py:111-119] — deferred, pre-existing (Epic 3 not started)
- [x] [Review][Defer] No authentication/authorization exists anywhere on this API surface [api/routers/teams.py] — deferred, pre-existing (consistent with the rest of the `api/` layer's local-only design per AD-11)

---

## File List
**New Files:**
- `api/routers/teams.py`
- `tests/api/test_teams.py`

**Modified Files:**
- `api/main.py` - Added teams router import and registration
- `api/schemas.py` - Added TeamView, TeamListView, TeamSaveRequest, TeamSaveResponse, TeamRenameRequest, MessageView, TeamRecentRequest, TeamRecordRunRequest (the last two added during the code review's fix pass)
- `tests/api/test_health.py` - Added new routes to authored routes set (including the code review's `/delete`, `POST /recent`, `/record-run` additions)
- `tests/api/test_secret_containment.py` - Added teams routes to sweep and templating (including the code review's additions)

---

## Change Log
- **2026-08-12**: Started implementation of Story 2-5
  - Created teams router with all 5 endpoints
  - Added SQLite storage for team metadata
  - Added filesystem storage for team packages and runs
  - Implemented validation for team names (uniqueness, reserved names, minimum length)
  - Created comprehensive test suite with 13 tests
  - Updated existing tests to account for new routes
- **2026-08-12**: Code review fix pass (3 decisions resolved to patches, 15 patches applied — see Review Findings above and Dev Agent Record's Fix Pass below)

---

## Dev Agent Record

### Implementation Plan
- Created new router `api/routers/teams.py` following existing patterns from `run.py` and `keys.py`
- Used FastAPI's APIRouter with prefix "/teams"
- Implemented SQLite database at `./data/teams.db` for metadata (name, created_at, last_run_at, run_count, storage_path)
- Implemented filesystem storage at `./data/saved_teams/<team_name>/` for team packages and runs
- Added validation for team names (case-insensitive uniqueness, reserved names, minimum 2 characters)
- Created in-memory recent teams cache (transient, cleared on restart per AD-11)

### Debug Log
- All tests passing (239 total, including 13 new tests for teams)

### Fix Pass (code review, 2026-08-12)

All 3 decision-needed findings and all 15 patch findings applied to `api/routers/teams.py` / `api/schemas.py` / `tests/api/test_teams.py` / `tests/api/test_health.py` / `tests/api/test_secret_containment.py`:

- **Security**: `team_name` now goes through a `_team_storage_path` containment check (mirrors `run.py`'s `_resolve_team_path`) before touching the filesystem in save/rename/delete; `team_package_path` must resolve under `output_root()`.
- **Concurrency**: `teams.name` is now `PRIMARY KEY COLLATE NOCASE` (the DB, not a Python pre-check, is the uniqueness authority); WAL mode + a busy timeout are set on every connection; `save_team`/`rename_team` catch `sqlite3.IntegrityError` and roll back their filesystem side effect on that path; `_recent_teams` mutations are lock-guarded.
- **Consistency**: `rename_team` refuses (rather than silently drifting) if the source directory is missing, and reverses its filesystem move if the DB write then fails; `delete_team`'s DB-delete failure is caught and logged rather than crashing after files are already gone.
- **New endpoints** (from the 3 resolved decisions): `DELETE /api/teams/delete?team_name=...` (query param — a JSON body on DELETE is unreliable across HTTP clients, including `TestClient.delete()`), `POST /api/teams/recent` (a name-only recent entry with no DB row, for a declined save), `POST /api/teams/{team_name}/record-run` (updates `last_run_at`/`run_count` on re-run).
- **`team_name` sanitized** via `api/deps.safe_label` everywhere it reaches an error message.
- **Test fixes**: `test_list_teams_empty` and the two reserved-name tests fixed per the review; 8 new tests added for the 3 new endpoints and the 2 security fixes.
- **Incidental bug found while fixing**: `_recent_teams` is module-level global state never reset between tests — pre-existing, not one of the 15 findings, surfaced only once the new `/recent` tests exercised it enough to trip an exact-length assertion. Fixed with an autouse reset fixture in `tests/api/test_teams.py`.
- **Verification**: full suite (`pytest tests/`) — 676 passed, 7 skipped (pre-existing, unrelated), 0 failed. `ruff check` clean except the pre-existing, deliberately-dismissed `state = app_state(request)` unused-variable pattern (matches every handler in this file, including the ones predating this review) and pre-existing style nits in `test_teams.py` untouched by this pass.
- No regressions in existing tests

### Completion Notes
- All acceptance criteria satisfied
- All tasks completed
- All tests passing
- Ready for review