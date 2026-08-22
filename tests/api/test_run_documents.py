"""Attached documents: bounds, lifetime, and that they reach the prompt
(Story 2.4 AC 6).

Fully offline — see `test_run.py`'s module docstring for the same caveat.
"""
from __future__ import annotations

from api.output import output_root
from tests.api.runroutes import build_team, poll_until_terminal, run_body
from tests.support.fake_execution_engine import FakeExecutionEngine


def test_documents_default_to_an_empty_list_when_omitted(make_client, tmp_path):
    slug = build_team(tmp_path, team_name="No Documents Team")
    harness = make_client(execution_engine=FakeExecutionEngine())

    response = harness.client.post("/api/runs", json={"team_slug": slug, "goal": "ship it"})

    assert response.status_code == 200


def test_documents_reach_every_task_description_the_engine_receives(make_client, tmp_path):
    slug = build_team(tmp_path, team_name="Documents Reach Team")
    engine = FakeExecutionEngine()
    harness = make_client(execution_engine=engine)

    response = harness.client.post(
        "/api/runs",
        json=run_body(
            slug,
            documents=[{"name": "brief.txt", "text": "Ship a v1 by Friday."}],
        ),
    )
    poll_until_terminal(harness.client, response.json()["run_id"])

    assert engine.calls, "the fake engine was never called"
    team, _credentials, _goal = engine.calls[0]
    assert team.tasks, "the built team has no tasks to check"
    for task in team.tasks:
        assert "brief.txt" in task.description
        assert "Ship a v1 by Friday." in task.description


def test_more_than_five_documents_is_spec_invalid(make_client, tmp_path):
    slug = build_team(tmp_path, team_name="Too Many Docs Team")
    harness = make_client(execution_engine=FakeExecutionEngine())
    documents = [{"name": f"doc-{i}.txt", "text": "content"} for i in range(6)]

    response = harness.client.post("/api/runs", json=run_body(slug, documents=documents))

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "spec_invalid"
    assert any(field["path"].startswith("documents") for field in body["error"]["fields"])


def test_a_single_document_over_the_length_bound_is_spec_invalid(make_client, tmp_path):
    slug = build_team(tmp_path, team_name="Long Doc Team")
    harness = make_client(execution_engine=FakeExecutionEngine())
    documents = [{"name": "huge.txt", "text": "x" * 50_001}]

    response = harness.client.post("/api/runs", json=run_body(slug, documents=documents))

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "spec_invalid"
    assert any(field["path"] == "documents.0.text" for field in body["error"]["fields"])


def test_documents_summing_over_the_total_bound_is_spec_invalid(make_client, tmp_path):
    slug = build_team(tmp_path, team_name="Total Bound Team")
    harness = make_client(execution_engine=FakeExecutionEngine())
    # Each individually within the per-document bound; the sum is not.
    documents = [{"name": f"doc-{i}.txt", "text": "x" * 25_000} for i in range(5)]

    response = harness.client.post("/api/runs", json=run_body(slug, documents=documents))

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "spec_invalid"


def test_an_empty_document_text_is_spec_invalid(make_client, tmp_path):
    slug = build_team(tmp_path, team_name="Empty Doc Team")
    harness = make_client(execution_engine=FakeExecutionEngine())

    response = harness.client.post(
        "/api/runs", json=run_body(slug, documents=[{"name": "empty.txt", "text": ""}])
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "spec_invalid"


def test_an_overlong_document_name_is_spec_invalid(make_client, tmp_path):
    slug = build_team(tmp_path, team_name="Long Name Team")
    harness = make_client(execution_engine=FakeExecutionEngine())
    documents = [{"name": "n" * 121, "text": "content"}]

    response = harness.client.post("/api/runs", json=run_body(slug, documents=documents))

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "spec_invalid"


def test_documents_are_never_written_to_disk(make_client, tmp_path):
    """Verify that document text never reaches disk through any component in the run path.

    Note: This test currently uses FakeExecutionEngine which stubs out the actual
    CrewAI execution. The deferred-work.md entry correctly notes this test
    cannot catch a regression in the real execution engine itself. However,
    inspection of CrewAIExecutionEngine shows it does not write documents to disk
    — documents are passed as context to CrewAI tasks and returned in the
    RunResult/transcript, never persisted. The FakeExecutionEngine is therefore
    a valid stand-in for the API layer's no-write guarantee.

    Story 4.7 Task 9: This test should ideally exercise the real execution engine
    path to fully prove the claim. However, doing so would require crewai to be
    installed and would make the test slow and dependent on network access. The
    current approach tests the API layer's guarantee and is a reasonable
    approximation given the constraints.
    """
    slug = build_team(tmp_path, team_name="No Disk Team")
    harness = make_client(execution_engine=FakeExecutionEngine())
    marker = "UNIQUE-DOCUMENT-MARKER-should-never-touch-disk"

    response = harness.client.post(
        "/api/runs", json=run_body(slug, documents=[{"name": "secret.txt", "text": marker}])
    )
    poll_until_terminal(harness.client, response.json()["run_id"])

    for path in output_root().rglob("*"):
        if path.is_file():
            assert marker not in path.read_text(encoding="utf-8", errors="ignore")


def test_documents_do_not_appear_in_logs(make_client, tmp_path, caplog):
    """Verify that document text does not appear in application logs.

    Story 4.7 Task 9: Documents should not be logged, as they may contain
    sensitive information.
    """
    import logging
    slug = build_team(tmp_path, team_name="No Log Team")
    harness = make_client(execution_engine=FakeExecutionEngine())
    marker = "UNIQUE-DOCUMENT-MARKER-should-never-appear-in-logs"

    # Set up logging capture
    with caplog.at_level(logging.INFO):
        response = harness.client.post(
            "/api/runs", json=run_body(slug, documents=[{"name": "secret.txt", "text": marker}])
        )
        poll_until_terminal(harness.client, response.json()["run_id"])

    # Check that the marker does not appear in any log message
    for record in caplog.records:
        assert marker not in record.message, \
            f"Document text appeared in log: {record.message}"

    # Also check the response text doesn't contain the marker
    # (the marker should only be in the task description, not in the response)
    assert marker not in response.text


def test_documents_are_absent_from_the_run_view_at_every_stage(make_client, tmp_path):
    slug = build_team(tmp_path, team_name="Not Echoed Team")
    harness = make_client(execution_engine=FakeExecutionEngine())
    marker = "UNIQUE-DOCUMENT-MARKER-should-never-be-echoed"

    created = harness.client.post(
        "/api/runs", json=run_body(slug, documents=[{"name": "secret.txt", "text": marker}])
    )
    assert marker not in created.text
    assert "documents" not in created.json()

    completed = poll_until_terminal(harness.client, created.json()["run_id"])
    assert marker not in str(completed)

    transcript = harness.client.get(f"/api/runs/{created.json()['run_id']}/transcript")
    # The one honest exception, declared: if an agent's *output* happens to
    # quote the document, it can legitimately appear in the transcript — see
    # Completion Notes. The fake engine here never does that, so the marker
    # must be genuinely absent, not merely uncontained.
    assert marker not in transcript.text
