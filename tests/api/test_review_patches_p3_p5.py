"""P3 and P5 tests from review patches.

P3 — a catalog provider with no authoring adapter
P5 — the envelope is a shape promise, not a status rewrite

These tests verify provider handling and HTTP status code preservation.
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from tests.api.test_review_patches_base import _start

# ---------------------------------------------------------------------------
# P3 — a catalog provider with no authoring adapter
# ---------------------------------------------------------------------------


def test_groq_is_told_the_truth_not_told_to_add_a_key(make_client, spec_payload, tmp_path):
    """`groq` is in the key catalog but has no adapter. The old pair of answers
    was a 503 saying "add a `GROQ_API_KEY` entry" followed — once the user
    complied — by a 422 saying "'groq' is not a known provider". Both false."""
    harness = make_client([spec_payload(tmp_path)])

    response = _start(harness, authoring={"provider": "groq", "model": "llama-3.3-70b"})

    assert response.status_code == 503
    message = response.json()["error"]["message"]
    assert "groq" in message
    assert "GROQ_API_KEY" not in message, "adding a key cannot help; do not ask for one"
    assert "not a known provider" not in message, "groq is known — it just cannot author"
    # It must point somewhere useful.
    assert "anthropic" in message and "openrouter" in message
    assert harness.configs == []


# ---------------------------------------------------------------------------
# P5 — the envelope is a shape promise, not a status rewrite
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("status", [400, 401, 403, 413, 429, 503])
def test_a_non_404_http_exception_keeps_its_status(make_client, status):
    """Before the fix every status but 404/405 was rewritten to 500
    `internal_error`, so a client could not tell "you sent a bad request" from
    "the server broke"."""
    harness = make_client()
    app = harness.client.app

    @app.get("/api/_probe")
    def _probe():
        raise HTTPException(status_code=status)

    response = harness.client.get("/api/_probe")

    assert response.status_code == status
    body = response.json()
    assert set(body) == {"error"}
    assert body["error"]["code"] != "internal_error" or status >= 500



def test_a_405_keeps_its_allow_header(make_client):
    """`exc.headers` used to be dropped, taking the 405's mandatory `Allow`."""
    harness = make_client()

    response = harness.client.delete("/api/health")

    assert response.status_code == 405
    assert "allow" in {name.lower() for name in response.headers}
