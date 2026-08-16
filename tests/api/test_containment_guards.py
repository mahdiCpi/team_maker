"""Do the AC 4 and AC 8 guards actually fail when the property is violated?

Story 2.1's review found that its self-declared highest-risk guard "protected
the decision and caught nothing", and its own commit body concluded: *"Writing
the warning down was not enough to avoid it."* So every containment assertion
in `containment.py` is fed a deliberately violating payload here and required
to go red.

Without this file the containment suite would be a green run that proves
nothing — the exact defect class the story's Dev Notes list first.
"""
from __future__ import annotations

import pytest

from team_maker.runtime.results import RunResult, TaskResult, TranscriptEntry
from tests.api.conftest import SENTINEL_VALUES
from tests.api.containment import (
    assert_envelope,
    assert_no_exception_leak,
    assert_no_sentinels,
)
from tests.api.runroutes import build_team, poll_until_terminal, run_body
from tests.support.fake_execution_engine import FakeExecutionEngine


class _FakeResponse:
    """A response-shaped object carrying whatever body the test wants to plant."""

    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def json(self) -> dict:
        return self._payload


def test_envelope_guard_rejects_a_body_with_extra_top_level_keys():
    response = _FakeResponse({"error": {"code": "spec_invalid", "message": "no"}, "detail": []})

    with pytest.raises(AssertionError, match="outside the envelope"):
        assert_envelope(response, "spec_invalid")


def test_envelope_guard_rejects_fields_on_a_non_spec_invalid_code():
    response = _FakeResponse(
        {"error": {"code": "build_failed", "message": "no", "fields": [{"path": "a", "message": "b"}]}}
    )

    with pytest.raises(AssertionError, match="only for spec_invalid"):
        assert_envelope(response, "build_failed")


def test_envelope_guard_rejects_an_empty_message():
    response = _FakeResponse({"error": {"code": "build_failed", "message": "   "}})

    with pytest.raises(AssertionError):
        assert_envelope(response, "build_failed")


@pytest.mark.parametrize(
    "leak",
    [
        'Traceback (most recent call last):\n  File "api/main.py", line 1',
        '{"error":{"code":"build_failed","message":"RuntimeError: boom"}}',
        '{"error":{"code":"compose_failed","message":"ValidationError raised"}}',
    ],
)
def test_exception_leak_guard_catches_a_leak(leak):
    with pytest.raises(AssertionError):
        assert_no_exception_leak(leak)


def test_exception_leak_guard_catches_an_injected_marker():
    with pytest.raises(AssertionError, match="POISON"):
        assert_no_exception_leak("all is well: POISON-123", extra=("POISON-123",))


def test_exception_leak_guard_passes_on_authored_copy():
    assert_no_exception_leak(
        '{"error":{"code":"build_failed","message":"The team package could not be built."}}'
    )


def test_sentinel_guard_catches_a_credential_in_a_body():
    body = f'{{"error":{{"code":"spec_invalid","message":"bad {SENTINEL_VALUES[0]}"}}}}'

    with pytest.raises(AssertionError, match="credential value reached the client"):
        assert_no_sentinels(body, SENTINEL_VALUES)


def test_sentinel_guard_catches_a_credential_from_a_real_response(
    make_client, spec_payload, tmp_path, monkeypatch
):
    """The strongest form: make the *app* leak, and confirm the sweep notices.

    `fields_from_error_list` is patched to echo pydantic's `input` member —
    which for an `extra_forbidden` error is the rejected value, i.e. the key the
    client tried to smuggle. That is the concrete mistake the real code avoids.
    """
    from api.errors import FieldError

    def leaky_fields(errors, *, strip_prefix=""):
        return [
            FieldError(
                ".".join(str(part) for part in error.get("loc", ())),
                f"{error.get('msg')} (got {error.get('input')!r})",
            )
            for error in errors
        ]

    monkeypatch.setattr("api.main.fields_from_error_list", leaky_fields)
    harness = make_client([spec_payload(tmp_path)])

    response = harness.client.post(
        "/api/compose/sessions",
        json={"intent": "docs", "api_key": SENTINEL_VALUES[0]},
    )

    assert response.status_code == 422
    with pytest.raises(AssertionError, match="credential value reached the client"):
        assert_no_sentinels(response.text, SENTINEL_VALUES)


def test_sentinel_guard_catches_a_credential_planted_in_a_run_result(make_client, tmp_path):
    """Story 2.4 AC 10: a run response carries raw LLM output, which no other
    route in `api/` does. A fake engine plants a sentinel in every field that
    actually renders — `final_output`, a `task_results[].output`, and a
    `transcript[].content` — proving the sweep genuinely reaches all three,
    not just the ones that happen to be easy to check."""
    slug = build_team(tmp_path, team_name="Sentinel Result Team")
    sentinel = SENTINEL_VALUES[0]
    result = RunResult(
        final_output=f"the final output, oh and by the way: {sentinel}",
        task_results=[TaskResult(name="draft", agent_role="architect", output=sentinel)],
        transcript=[
            TranscriptEntry(
                sequence=1, kind="agent_message", agent_role="architect", task_name="draft", content=sentinel
            )
        ],
    )
    harness = make_client(execution_engine=FakeExecutionEngine(result=result))

    created = harness.client.post("/api/runs", json=run_body(slug))
    body = poll_until_terminal(harness.client, created.json()["run_id"])
    transcript = harness.client.get(f"/api/runs/{created.json()['run_id']}/transcript")

    assert sentinel in body["result"]["final_output"]
    assert sentinel in body["result"]["task_results"][0]["output"]
    assert sentinel in transcript.json()["entries"][0]["content"]
    with pytest.raises(AssertionError, match="credential value reached the client"):
        assert_no_sentinels(str(body) + transcript.text, SENTINEL_VALUES)
