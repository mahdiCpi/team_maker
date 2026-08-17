"""Tests for the compose from-starter endpoint (Story 3-2: Run and adapt a starter team).

Tests for POST /api/compose/sessions/from-starter endpoint.

No local `repo_root`/cleanup fixture here: `make_client()`'s app already gets
`TEAM_MAKER_OUTPUT_ROOT=tmp_path` from `tests/api/conftest.py`'s autouse
`isolated_key_config`, and every compose-session build path (`/from-starter`,
`/spec`, `/build`) derives its output directory through
`derive_output_path`/`output_root()`, so those already land under `tmp_path`
with no extra isolation needed. The one exception is `POST
/api/starters/{id}/run` (used below to build the *original*, unadapted
starter for comparison) — that route writes to its YAML's own literal,
relative `output_path` regardless of `TEAM_MAKER_OUTPUT_ROOT` (see
`test_starters_run.py`'s module docstring), so any test that calls it also
`monkeypatch.chdir(tmp_path)` first.
"""
from __future__ import annotations

from pathlib import Path


class TestCreateSessionFromStarter:
    """Tests for POST /api/compose/sessions/from-starter endpoint."""

    def test_create_session_from_baseline_education(self, make_client):
        """Test creating a session from the baseline education starter."""
        harness = make_client()
        response = harness.client.post(
            "/api/compose/sessions/from-starter",
            json={"starter_id": "baseline_education_team"}
        )

        assert response.status_code == 201

        data = response.json()
        assert data["status"] == "complete"
        assert "session_id" in data
        assert data["session_id"] is not None
        assert "spec" in data
        assert data["spec"] is not None

        # The spec should have the adapted name
        assert "Baseline Education Team-adapted" in data["spec"]["team_name"] or \
               data["spec"]["team_name"] == "Baseline Education Team-adapted"

    def test_create_session_from_research_content(self, make_client):
        """Test creating a session from the research content starter."""
        harness = make_client()
        response = harness.client.post(
            "/api/compose/sessions/from-starter",
            json={"starter_id": "research_content_team"}
        )

        assert response.status_code == 201

        data = response.json()
        assert data["status"] == "complete"
        assert "session_id" in data

        # The spec should have the adapted name
        assert "Research Content Team-adapted" in data["spec"]["team_name"]

    def test_create_session_from_starter_not_found(self, make_client):
        """Test that requesting a non-existent starter returns 404."""
        harness = make_client()
        response = harness.client.post(
            "/api/compose/sessions/from-starter",
            json={"starter_id": "nonexistent"}
        )

        assert response.status_code == 404

        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "not_found"

    def test_create_session_from_starter_costs_no_llm_call(self, make_client):
        """Test that creating a session from a starter doesn't cost an LLM call.

        The session should start with turn=0 (no turns spent) and the spec
        should be pre-loaded from the starter YAML.
        """
        harness = make_client()
        response = harness.client.post(
            "/api/compose/sessions/from-starter",
            json={"starter_id": "baseline_education_team"}
        )

        assert response.status_code == 201

        data = response.json()
        # Turn should be 0 because no LLM call was made
        assert data["turn"] == 0
        # turns_remaining should still be the full amount
        assert data["turns_remaining"] > 0

    def test_session_from_starter_can_be_edited(self, make_client):
        """Test that a session created from a starter can be edited via PUT /spec.

        This verifies AC 2: "the direct spec-edit path (PUT .../spec) works
        against it exactly as they do for a normally-composed team".
        """
        harness = make_client()
        client = harness.client
        # Create session from starter
        create_response = client.post(
            "/api/compose/sessions/from-starter",
            json={"starter_id": "baseline_education_team"}
        )
        assert create_response.status_code == 201
        create_data = create_response.json()
        session_id = create_data["session_id"]

        # Now edit the spec - only send editable fields (RoleEdit and TaskEdit)
        # Extract just the fields that are editable
        editable_roles = [
            {"name": r["name"], "description": r["description"]}
            for r in create_data["spec"]["desired_roles"]
        ]
        editable_tasks = [
            {"name": t["name"], "description": t["description"], "agent_role": t["agent_role"], "dependencies": t.get("dependencies", [])}
            for t in create_data["spec"]["desired_tasks"]
        ]

        edit_response = client.put(
            f"/api/compose/sessions/{session_id}/spec",
            json={
                "team_name": "Modified Team",
                "purpose": "A modified purpose",
                "desired_roles": editable_roles,
                "desired_tasks": editable_tasks,
            }
        )

        assert edit_response.status_code == 200
        edit_data = edit_response.json()

        # The edit should have been applied
        assert edit_data["spec"]["team_name"] == "Modified Team"
        assert edit_data["spec"]["purpose"] == "A modified purpose"

    def test_session_from_starter_has_valid_spec(self, make_client):
        """Test that a session created from a starter has a valid, complete spec.

        The spec should be structurally valid and contain all expected fields.
        """
        harness = make_client()
        response = harness.client.post(
            "/api/compose/sessions/from-starter",
            json={"starter_id": "baseline_education_team"}
        )

        assert response.status_code == 201

        data = response.json()
        spec = data["spec"]

        # Check required fields
        assert "team_name" in spec
        assert "purpose" in spec
        assert "desired_roles" in spec
        assert "desired_tasks" in spec

        # Check that it's adapted
        assert spec["team_name"].endswith("-adapted")

        # Check that roles are populated (tasks may be empty if they come from template)
        assert len(spec["desired_roles"]) > 0
        # Tasks may be empty in the spec - they're provided by the template during build
        # assert len(spec["desired_tasks"]) >= 0  # Always true, just checking it exists


class TestFromStarterOriginalNeverOverwritten:
    """Tests for AC 3: the original starter's build must never be overwritten."""

    def test_adapted_starter_has_different_output_path(self, make_client, monkeypatch, tmp_path: Path):
        """Test that an adapted starter targets a different directory than the original.

        This verifies the resolved decision: the seeded spec's team_name is
        automatically suffixed to ensure a distinct output path.
        """
        # The upcoming "Run" call writes to its YAML's own literal, relative
        # output_path — chdir first so that lands under tmp_path, not the
        # real repo's generated_teams/ (see this module's docstring).
        monkeypatch.chdir(tmp_path)
        harness = make_client()
        client = harness.client
        # First, run the original starter
        run_response = client.post("/api/starters/baseline_education_team/run")
        assert run_response.status_code == 200
        run_data = run_response.json()
        original_slug = run_data["team_slug"]

        # Then create a session from the same starter (which adapts it)
        session_response = client.post(
            "/api/compose/sessions/from-starter",
            json={"starter_id": "baseline_education_team"}
        )
        assert session_response.status_code == 201
        session_data = session_response.json()
        adapted_name = session_data["spec"]["team_name"]

        # The adapted name should be different from the original
        assert adapted_name != "Baseline Education Team"
        assert adapted_name.endswith("-adapted")

        # Now build the adapted session
        build_response = client.post(
            f"/api/compose/sessions/{session_data['session_id']}/build"
        )
        assert build_response.status_code == 200
        build_data = build_response.json()

        # The build should succeed into a directory distinct from the original
        adapted_slug = Path(build_data["output_path"]).name
        assert adapted_slug != original_slug

    def test_original_starter_unmodified_after_adapt_and_build(
        self, make_client, monkeypatch, tmp_path: Path
    ):
        """Test that the original starter's package is left byte-for-byte unmodified
        after adapting and building (AC 3).

        Regression note: an earlier version of this test built `original_path`
        from `repo_root / "generated_teams" / ...`, but the "Run" call actually
        writes under wherever the process's cwd is (its YAML's own literal,
        relative `output_path` — see this module's docstring). Without a
        matching `chdir`, that path never existed, so `original_path.rglob("*")`
        silently yielded nothing on both sides and every assertion below passed
        vacuously — this test verified nothing. `monkeypatch.chdir(tmp_path)`
        below is what makes `original_path` actually point at real files.
        """
        monkeypatch.chdir(tmp_path)
        harness = make_client()
        client = harness.client
        # First, run the original starter
        run_response = client.post("/api/starters/baseline_education_team/run")
        assert run_response.status_code == 200
        run_data = run_response.json()
        original_slug = run_data["team_slug"]
        original_path = tmp_path / "generated_teams" / original_slug
        assert original_path.exists(), "setup bug: the original starter build did not land where expected"

        # Capture original file contents (excluding timestamp files)
        original_files = {}
        for path in sorted(original_path.rglob("*")):
            if path.is_file():
                if path.name in ("generation_report.md", "team_config.yaml"):
                    continue
                relative = path.relative_to(original_path)
                original_files[str(relative)] = path.read_bytes()

        # Then create and build an adapted session
        session_response = client.post(
            "/api/compose/sessions/from-starter",
            json={"starter_id": "baseline_education_team"}
        )
        assert session_response.status_code == 201
        session_data = session_response.json()

        build_response = client.post(
            f"/api/compose/sessions/{session_data['session_id']}/build"
        )
        assert build_response.status_code == 200

        # Verify original starter files are unchanged
        for path in sorted(original_path.rglob("*")):
            if path.is_file():
                if path.name in ("generation_report.md", "team_config.yaml"):
                    continue
                relative = path.relative_to(original_path)
                key = str(relative)

                assert key in original_files, f"File {key} missing from original capture"
                assert path.read_bytes() == original_files[key], \
                    f"Original file {key} was modified after adapt and build"

    def test_second_adapt_collides_with_first(self, make_client):
        """Test that adapting the same starter twice without renaming hits 409 (AC 3).

        This is expected behavior: the auto-suffix ensures the first adapted build
        is in a distinct directory, and a second attempt to adapt without renaming
        will collide with the first.
        """
        harness = make_client()
        client = harness.client
        # First adapt and build
        session_response1 = client.post(
            "/api/compose/sessions/from-starter",
            json={"starter_id": "baseline_education_team"}
        )
        assert session_response1.status_code == 201
        session_data1 = session_response1.json()

        build_response1 = client.post(
            f"/api/compose/sessions/{session_data1['session_id']}/build"
        )
        assert build_response1.status_code == 200

        # Second adapt and build (without renaming)
        session_response2 = client.post(
            "/api/compose/sessions/from-starter",
            json={"starter_id": "baseline_education_team"}
        )
        assert session_response2.status_code == 201
        session_data2 = session_response2.json()

        build_response2 = client.post(
            f"/api/compose/sessions/{session_data2['session_id']}/build"
        )

        # Should get 409 because the output path already exists
        assert build_response2.status_code == 409


class TestFromStarterChatWorks:
    """Tests for AC 2: chat messages work against a starter-seeded session."""

    def test_send_message_to_starter_seeded_session(self, make_client, spec_payload, tmp_path):
        """Test that sending a chat message to a starter-seeded session succeeds.

        This verifies that refine() works correctly after seed() (AC 2).
        """
        # Need to provide a response for the refine() call
        harness = make_client([spec_payload(tmp_path)])
        client = harness.client
        # Create session from starter
        session_response = client.post(
            "/api/compose/sessions/from-starter",
            json={"starter_id": "baseline_education_team"}
        )
        assert session_response.status_code == 201
        session_data = session_response.json()
        session_id = session_data["session_id"]

        # Send a message (this calls refine() under the hood)
        message_response = client.post(
            f"/api/compose/sessions/{session_id}/messages",
            json={"message": "Add a new role called test_role that tests things"}
        )

        # Should succeed (not 500 from the _started gate)
        assert message_response.status_code == 200
        message_data = message_response.json()

        # Should have updated spec
        assert message_data["spec"] is not None
        assert message_data["turn"] == 1  # First turn after seeding


class TestFromStarterProviderResolutionDeferred:
    """Tests for the resolved decision (2026-08-16 code review): 'Adapt with
    Composer' and direct spec-editing must work with zero configured provider
    credentials — the credential gate defers to the first operation that
    actually needs the LLM. See api/routers/compose.py's "Provider resolution
    architecture" note.
    """

    def test_create_session_from_starter_succeeds_without_any_credentials(
        self, make_client, write_key_config
    ):
        """Seeding never calls the LLM, so creating the session must not
        require a usable authoring credential (AC 2)."""
        write_key_config({})  # No provider has a usable credential.
        harness = make_client()
        response = harness.client.post(
            "/api/compose/sessions/from-starter",
            json={"starter_id": "baseline_education_team"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["spec"] is not None
        assert data["turn"] == 0

    def test_spec_edit_on_credential_free_seeded_session_succeeds(
        self, make_client, write_key_config
    ):
        """Direct spec-editing (PUT .../spec) makes no LLM call either, so it
        must also work with zero configured credentials."""
        write_key_config({})
        harness = make_client()
        client = harness.client
        session_response = client.post(
            "/api/compose/sessions/from-starter",
            json={"starter_id": "baseline_education_team"},
        )
        assert session_response.status_code == 201
        session_data = session_response.json()

        editable_roles = [
            {"name": r["name"], "description": r["description"]}
            for r in session_data["spec"]["desired_roles"]
        ]
        edit_response = client.put(
            f"/api/compose/sessions/{session_data['session_id']}/spec",
            json={"team_name": "Renamed Without Any Key", "desired_roles": editable_roles},
        )

        assert edit_response.status_code == 200
        assert edit_response.json()["spec"]["team_name"] == "Renamed Without Any Key"

    def test_message_on_credential_free_seeded_session_fails_clearly(
        self, make_client, write_key_config
    ):
        """The gate is deferred, not removed: the first real LLM-invoking
        operation (a chat message) still resolves/fails on the provider, with
        a clean 503 `authoring_unavailable` — not a generic 500/COMPOSE_FAILED
        from `ComposerSession.refine()` reaching an unusable provider."""
        write_key_config({})
        harness = make_client()
        client = harness.client
        session_response = client.post(
            "/api/compose/sessions/from-starter",
            json={"starter_id": "baseline_education_team"},
        )
        assert session_response.status_code == 201
        session_id = session_response.json()["session_id"]

        message_response = client.post(
            f"/api/compose/sessions/{session_id}/messages",
            json={"message": "Add a new role called test_role that tests things"},
        )

        assert message_response.status_code == 503
        assert message_response.json()["error"]["code"] == "authoring_unavailable"
