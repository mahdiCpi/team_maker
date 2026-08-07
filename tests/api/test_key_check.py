"""The per-team key check: `GET /api/keys/check/{session_id}` (Story 2.3, AC 2 / AC 4).

Whether *one team* can run, role by role — including the planner path, which is the
one build that genuinely needs a credential to start. What the machine has is
`tests/api/test_key_status.py`.

Offline by construction; the only LLM is a stub (CLAUDE.md test transparency).
"""
from __future__ import annotations

from tests.api.conftest import SENTINEL_VALUES
from tests.api.containment import (
    assert_envelope,
    assert_no_exception_leak,
    assert_no_sentinels,
)
from tests.api.keyroutes import STATUS_PATH, start_session

# ---------------------------------------------------------------------------
# AC 2 — the per-role check
# ---------------------------------------------------------------------------


def test_check_resolves_each_role_against_the_server_side_default(
    make_client, spec_payload, tmp_path
):
    """A role that names no `llm` inherits `role.llm -> default_llm -> anthropic`.
    The browser cannot know that default (`spec-draft.ts:9-13` forbids inventing
    it), so the server does the join."""
    harness = make_client([spec_payload(tmp_path)])
    session_id = start_session(harness)

    body = harness.client.get(f"/api/keys/check/{session_id}").json()

    assert [r["role"] for r in body["roles"]] == ["writer"]
    writer = body["roles"][0]
    assert writer["provider"] == "anthropic"
    assert writer["model"] == "claude-sonnet-4-6"
    assert writer["inherited_default"] is True
    assert writer["status"] == "available"
    assert writer["usable"] is True


def test_check_marks_an_explicit_role_routing_as_not_inherited(
    make_client, spec_payload, tmp_path
):
    harness = make_client(
        [
            spec_payload(
                tmp_path,
                desired_roles=[
                    {
                        "name": "writer",
                        "description": "Writes documentation.",
                        "llm": {"provider": "openai", "model": "gpt-4o"},
                    }
                ],
            )
        ]
    )
    session_id = start_session(harness)

    writer = harness.client.get(f"/api/keys/check/{session_id}").json()["roles"][0]

    assert writer["provider"] == "openai"
    assert writer["inherited_default"] is False


def test_check_blocks_and_explains_when_a_required_key_is_missing(
    make_client, spec_payload, tmp_path, write_key_config
):
    write_key_config({"ANTHROPIC_API_KEY": "sk-ant-x"})
    harness = make_client(
        [
            spec_payload(
                tmp_path,
                desired_roles=[
                    {
                        "name": "judge",
                        "description": "Judges the output.",
                        "llm": {"provider": "openai", "model": "gpt-4o"},
                    }
                ],
            )
        ]
    )
    session_id = start_session(harness)

    body = harness.client.get(f"/api/keys/check/{session_id}").json()

    assert body["overall"] == "missing-key"
    assert body["blocked"] is True
    assert body["blocking_reason"]
    judge = body["roles"][0]
    assert judge["usable"] is False
    assert "OPENAI_API_KEY" in judge["fix_hint"]


def test_check_reports_all_good_when_every_role_resolves_directly(
    make_client, spec_payload, tmp_path
):
    harness = make_client([spec_payload(tmp_path)])
    session_id = start_session(harness)

    body = harness.client.get(f"/api/keys/check/{session_id}").json()

    assert body["overall"] == "all-good"
    assert body["blocked"] is False
    assert body["blocking_reason"] is None


def test_check_reports_via_openrouter_when_that_is_the_route(
    make_client, spec_payload, tmp_path, write_key_config
):
    write_key_config({"OPENROUTER_API_KEY": "sk-or-x"})
    harness = make_client([spec_payload(tmp_path)])
    session_id = start_session(harness, provider="openrouter", model="x")

    body = harness.client.get(f"/api/keys/check/{session_id}").json()

    assert body["roles"][0]["status"] == "via-openrouter"
    assert body["overall"] == "via-openrouter"
    assert body["blocked"] is False


def test_the_planner_path_is_gated_on_planning_llm(
    make_client, spec_payload, tmp_path
):
    """The planner path is the one build that genuinely needs a credential to start:
    `PipelineRunner` takes `_generate_from_planner`, which calls
    `create_provider(request.planning_llm)`. Reporting it as "nothing to check" left
    the only path needing a key as the only path ungated (code review, 2026-08-04).

    `planning_llm` defaults to anthropic, which the sentinel config satisfies, so
    this asserts the role is *reported and marked required* rather than absent.
    """
    harness = make_client([spec_payload(tmp_path, desired_roles=[])])
    session_id = start_session(harness)

    body = harness.client.get(f"/api/keys/check/{session_id}").json()

    assert [r["role"] for r in body["roles"]] == ["(the planner)"]
    planner = body["roles"][0]
    assert planner["provider"] == "anthropic"
    assert planner["required"] is True
    assert planner["usable"] is True
    assert body["overall"] == "all-good"
    assert body["blocked"] is False


def test_the_planner_path_blocks_when_its_provider_has_no_credential(
    make_client, spec_payload, tmp_path, write_key_config
):
    """A required role blocks: there is no way to build this team without it, so the
    UI must not offer to route around it."""
    write_key_config({"OPENAI_API_KEY": "sk-openai-x"})
    harness = make_client([spec_payload(tmp_path, desired_roles=[])])
    session_id = start_session(harness, provider="openai", model="gpt-4o")

    body = harness.client.get(f"/api/keys/check/{session_id}").json()

    planner = body["roles"][0]
    assert planner["provider"] == "anthropic"  # planning_llm, not the authoring pick
    assert planner["usable"] is False
    assert planner["required"] is True
    assert body["overall"] == "missing-key"
    assert body["blocked"] is True
    # A required role cannot be switched away from, so the copy must not suggest it.
    assert "cannot be built without it" in body["blocking_reason"]
    assert "Switch the affected agents" not in body["blocking_reason"]


def test_check_404s_for_an_unknown_session(make_client):
    response = make_client().client.get("/api/keys/check/not-a-session")

    assert response.status_code == 404
    assert_envelope(response, "session_not_found")


# ---------------------------------------------------------------------------
# AC 4 — the aggregate keeps `unsupported` apart from `missing-key`
# ---------------------------------------------------------------------------


def test_an_unsupported_required_provider_is_not_aggregated_as_missing_key(
    make_client, spec_payload, tmp_path
):
    """AC 4: `unsupported-by-runtime` is its own state. Folding it into `missing-key`
    tells a user who added the correct key that they did not — and an earlier version
    of this module did exactly that."""
    harness = make_client(
        [
            spec_payload(
                tmp_path,
                desired_roles=[
                    {
                        "name": "judge",
                        "description": "Judges the output.",
                        "llm": {"provider": "groq", "model": "llama-3.1-70b"},
                    }
                ],
            )
        ]
    )
    session_id = start_session(harness)

    body = harness.client.get(f"/api/keys/check/{session_id}").json()

    assert body["overall"] == "unsupported"
    assert body["blocked"] is True
    assert "not supported by the installed runtime engine" in body["blocking_reason"]
    # The two statements that must never be made about groq.
    assert "no usable credential" not in body["blocking_reason"]
    assert "GROQ_API_KEY" not in body["blocking_reason"]


def test_the_blocking_reason_agrees_with_its_subject_in_number(
    make_client, spec_payload, tmp_path, write_key_config
):
    write_key_config({"ANTHROPIC_API_KEY": "sk-ant-x"})
    harness = make_client(
        [
            spec_payload(
                tmp_path,
                desired_roles=[
                    {
                        "name": "writer",
                        "description": "Writes it.",
                        "llm": {"provider": "openai", "model": "gpt-4o"},
                    },
                    {
                        "name": "judge",
                        "description": "Judges it.",
                        "llm": {"provider": "xai", "model": "grok"},
                    },
                ],
            )
        ]
    )
    session_id = start_session(harness)

    reason = harness.client.get(f"/api/keys/check/{session_id}").json()[
        "blocking_reason"
    ]

    # Two distinct causes, each described correctly, and the verb agrees.
    assert "'openai' has no usable credential" in reason
    assert "'xai' has not supported" not in reason
    assert "not supported by the installed runtime engine" in reason


def test_the_blocking_reason_carries_no_spatial_pointer(
    make_client, spec_payload, tmp_path, write_key_config
):
    """The same sentence is rendered above the action bar and inside the review
    dialog, where no key check exists, so any direction it named was wrong
    somewhere."""
    write_key_config({"ANTHROPIC_API_KEY": "sk-ant-x"})
    harness = make_client(
        [
            spec_payload(
                tmp_path,
                desired_roles=[
                    {
                        "name": "judge",
                        "description": "Judges it.",
                        "llm": {"provider": "openai", "model": "gpt-4o"},
                    }
                ],
            )
        ]
    )
    session_id = start_session(harness)

    reason = harness.client.get(f"/api/keys/check/{session_id}").json()[
        "blocking_reason"
    ]

    assert "below" not in reason
    assert "above" not in reason


def test_a_role_on_an_unknown_provider_is_reported_and_sanitised(
    make_client, spec_payload, tmp_path
):
    """`ProviderSelection.provider` is a free-form bounded string the catalog does
    not constrain, so this branch is client-reachable — and AC 7 requires any
    client-supplied string echoed into a message to go through `safe_label`."""
    harness = make_client(
        [
            spec_payload(
                tmp_path,
                desired_roles=[
                    {
                        "name": "writer",
                        "description": "Writes it.",
                        "llm": {"provider": "not\na\rprovider", "model": "m"},
                    }
                ],
            )
        ]
    )
    session_id = start_session(harness)

    body = harness.client.get(f"/api/keys/check/{session_id}").json()
    writer = body["roles"][0]

    assert writer["status"] == "unrecognized"
    assert writer["usable"] is False
    assert "unrecognized provider" in writer["fix_hint"]
    # Control characters stripped before the name reaches an authored sentence: a
    # newline here forges a log line and breaks the message.
    assert "\n" not in body["blocking_reason"]
    assert "\r" not in body["blocking_reason"]


# ---------------------------------------------------------------------------
# AC 7 — containment
# ---------------------------------------------------------------------------


def test_neither_route_leaks_a_credential(
    make_client, spec_payload, tmp_path, caplog
):
    import logging

    harness = make_client([spec_payload(tmp_path)])
    session_id = start_session(harness)

    with caplog.at_level(logging.DEBUG):
        responses = [
            harness.client.get(STATUS_PATH),
            harness.client.get(f"/api/keys/check/{session_id}"),
            harness.client.get("/api/keys/check/unknown"),
        ]

    # Fail loudly rather than vacuously: before these routes existed this whole
    # test passed, because a 404 envelope contains no credential either.
    assert [r.status_code for r in responses] == [200, 200, 404], [
        r.status_code for r in responses
    ]
    assert SENTINEL_VALUES[0] in harness.client.app.state.team_maker_api.key_config.keys[
        "anthropic"
    ].get_secret_value(), "the sweep must run against a config that really holds a sentinel"

    for response in responses:
        assert_no_sentinels(response.text, SENTINEL_VALUES)
        assert_no_exception_leak(response.text)
        for name, value in response.headers.items():
            assert_no_sentinels(f"{name}: {value}", SENTINEL_VALUES)
    assert_no_sentinels(caplog.text, SENTINEL_VALUES)


def test_neither_key_route_exposes_a_method_that_could_accept_a_key(make_client):
    """AD-9: no endpoint accepts a key value.

    Asserted against the OpenAPI document rather than by POSTing and expecting 405.
    A 405 is FastAPI's default for any undeclared method, so that test passed without
    saying anything about *these* routes — it would have passed identically had the
    routes not existed. What actually matters is that no body-bearing method is
    declared for them at all.
    """
    client = make_client().client

    paths = client.get("/openapi.json").json()["paths"]
    for path in ("/api/keys/status", "/api/keys/check/{session_id}"):
        assert path in paths, f"{path} is missing, so this guard proves nothing"
        assert set(paths[path]) == {"get"}, (
            f"{path} declares {sorted(paths[path])}; only `get` may exist, or a "
            "client could send a body containing a credential"
        )

    # And the request really is refused rather than silently ignored.
    response = client.post(STATUS_PATH, json={"api_key": SENTINEL_VALUES[0]})
    assert response.status_code == 405
    assert_no_sentinels(response.text, SENTINEL_VALUES)
