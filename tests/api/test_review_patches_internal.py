"""Internal error handling tests from review patches.

An internal bug during refinement — contained, and not blamed on the upstream

These tests verify that internal errors are properly contained and don't
leak sensitive information or blame external providers.
"""
from __future__ import annotations

import logging

import pytest

from tests.api.test_review_patches_base import NEUTRAL_COMPOSE_FAILURE, SENTINEL_VALUES, _start, assert_envelope, assert_no_exception_leak, assert_no_sentinels


# ---------------------------------------------------------------------------
# An internal bug during refinement — contained, and not blamed on the upstream
# ---------------------------------------------------------------------------


def test_an_internal_typeerror_during_refinement_is_contained_and_neutral(
    make_client, spec_payload, tmp_path, caplog
):
    """A `TypeError` is our bug, not the provider's, and the API must not claim
    otherwise while still containing it completely.

    The `_guarded` fallback catches everything that is not a `ComposerError`,
    so a defect in this repo lands in the same branch as a network fault. It
    stays a 502 `compose_failed` — the code review deliberately did **not**
    add SDK-specific exception classification, because recognising provider
    exception types inside `api/` is what AD-8 keeps out of this layer. What
    changed is the copy: it no longer asserts a cause the code has not
    established.

    All four properties in one test on purpose — they describe a single
    behaviour, and separating them would let three pass while the fourth
    silently regressed.
    """
    poison = "sk-INTERNAL-BUG-DETAIL-DO-NOT-LEAK"
    harness = make_client(
        [
            {"is_team": True},
            spec_payload(tmp_path),
            TypeError(f"unsupported operand type(s) for +: 'int' and 'str' {poison}"),
        ]
    )
    created = _start(harness).json()
    session_id = created["session_id"]
    original_spec = created["spec"]

    with caplog.at_level(logging.ERROR):
        response = harness.client.post(
            f"/api/compose/sessions/{session_id}/messages",
            json={"message": "add a reviewer"},
        )

    # 1. It is a 502 `compose_failed`, in the AC 2 envelope and nothing else.
    assert response.status_code == 502
    error = assert_envelope(response, "compose_failed")

    # ...carrying causally neutral copy. It must not name the provider or
    # assert unreachability, because neither was established.
    assert error["message"] == NEUTRAL_COMPOSE_FAILURE
    lowered = error["message"].lower()
    assert "provider" not in lowered
    assert "reach" not in lowered and "network" not in lowered

    # 2. No exception detail, class name, or traceback reaches the client.
    assert_no_exception_leak(
        response.text, extra=(poison, "unsupported operand", "'int' and 'str'")
    )
    assert_no_sentinels(response.text, SENTINEL_VALUES)

    # 3. The previous valid specification is untouched — `ComposerSession.refine`
    #    only assigns `self.current` after a successful compose, and the API
    #    must not undo that (Story 1.3's AC 6 contract).
    readback = harness.client.put(f"/api/compose/sessions/{session_id}/spec", json={})
    assert readback.status_code == 200
    assert readback.json()["spec"] == original_spec

    # 4. The exception is diagnosable server-side — the other half of
    #    "log it, never serialise it". Story 4.1's review (decision D3)
    #    tightened this further: the logging path now redacts secret-shaped
    #    content exactly like the display path does, so the poison itself
    #    (shaped like a leaked key) is redacted even server-side, while the
    #    surrounding message and exception type stay diagnosable.
    assert "unsupported operand type(s) for +: 'int' and 'str'" in caplog.text
    assert "TypeError" in caplog.text
    assert poison not in caplog.text, "secret-shaped content must be redacted even server-side (D3)"
    assert "[REDACTED]" in caplog.text



def test_the_session_survives_an_internal_error_and_can_still_be_refined(
    make_client, spec_payload, tmp_path
):
    """Containment must not cost the conversation: a bug in one turn leaves the
    session usable, or the user loses a spec that cost up to four LLM calls."""
    harness = make_client(
        [
            {"is_team": True},
            spec_payload(tmp_path),
            TypeError("internal defect"),
            spec_payload(tmp_path, team_name="Docs Squad"),
        ]
    )
    session_id = _start(harness).json()["session_id"]

    failed = harness.client.post(
        f"/api/compose/sessions/{session_id}/messages", json={"message": "boom"}
    )
    assert failed.status_code == 502

    recovered = harness.client.post(
        f"/api/compose/sessions/{session_id}/messages", json={"message": "try again"}
    )
    assert recovered.status_code == 200
    assert recovered.json()["spec"]["team_name"] == "Docs Squad"
