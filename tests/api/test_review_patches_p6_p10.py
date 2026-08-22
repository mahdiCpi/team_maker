"""P6 and P10 tests from review patches.

P6 / P10 — bounded, non-empty client input

These tests verify that client input is properly bounded and validated.
"""
from __future__ import annotations

import pytest

from tests.api.test_review_patches_base import _start

# ---------------------------------------------------------------------------
# P6 / P10 — bounded, non-empty client input
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("authoring", [{"provider": ""}, {"model": ""}, {"provider": "", "model": ""}])
def test_an_empty_selection_is_rejected_not_defaulted(
    make_client, spec_payload, tmp_path, authoring
):
    """`{"provider": ""}` silently became `anthropic`, and `{"model": ""}`
    became `claude-sonnet-4-6` — so asking `openai` for an empty model produced
    `openai` + a Claude model id and a later, unactionable 502."""
    harness = make_client([spec_payload(tmp_path)])

    response = _start(harness, authoring=authoring)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "spec_invalid"
    assert harness.configs == []



def test_an_oversized_intent_is_refused(make_client):
    harness = make_client()

    response = harness.client.post("/api/compose/sessions", json={"intent": "x" * 50_000})

    assert response.status_code == 422



def test_a_forged_log_line_cannot_be_smuggled_through_the_provider_name(
    make_client, spec_payload, tmp_path, caplog
):
    """The provider id is echoed into a log record and into the response.

    Echoing it back is deliberate — it is the client's own input, and naming it
    is what makes the error actionable. What was not deliberate is that the raw
    string went through unbounded and unsanitised, so a newline forged a second
    log record. The fix strips non-printables and bounds the length; it does
    not stop the value being named, so that is not what this asserts.
    """
    import logging

    def exploding_factory(config):
        """Stands in for the real `create_provider`, which raises `ValueError`
        for an id `_ADAPTERS` cannot resolve. The default harness factory
        accepts anything, so without this the sanitising path is never reached.
        """
        raise ValueError(f"Unknown provider '{config.provider}'.")

    harness = make_client(factory=exploding_factory)
    forged = "nope\nWARNING:api.deps:credential bridge disabled"

    with caplog.at_level(logging.DEBUG):
        response = _start(harness, authoring={"provider": forged, "model": "x"})

    assert response.status_code in (422, 503)
    # The forging attempt is defeated by the newline being gone, not by the
    # text being absent: one record, on one line.
    forging = [r for r in caplog.records if "credential bridge disabled" in r.getMessage()]
    assert len(forging) == 1
    assert "\n" not in forging[0].getMessage()
    # And nothing control-charactered reaches the client either.
    message = response.json()["error"]["message"]
    assert "\n" not in message and "\r" not in message
    assert all(ch.isprintable() for ch in message)



def test_an_over_long_provider_id_never_reaches_the_echo(make_client):
    """The schema bound (64) stops it before `_safe_label` has to."""
    harness = make_client()

    response = harness.client.post(
        "/api/compose/sessions",
        json={"intent": "docs", "authoring": {"provider": "x" * 5_000, "model": "y"}},
    )

    assert response.status_code == 422
    assert len(response.text) < 2_000, "the rejected value must not be echoed back wholesale"
