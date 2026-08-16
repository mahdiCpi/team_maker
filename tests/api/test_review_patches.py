"""Guards for the fixes applied by the Story 2.0 code review.

Every assertion here was written against the *unpatched* behaviour first and
watched fail, because this story's own Dev Notes open with the defect class
"the guard that cannot fail" — a guard protecting the highest-risk decision
that caught nothing. What each one measured before the fix is recorded in its
docstring.

All providers here are STUBS (`tests.support.fake_llm`). No LLM is contacted.
"""
from __future__ import annotations

import threading

import pytest
from fastapi import HTTPException

from api.errors import STATUS_BY_CODE
from api.output import derive_output_path, slugify_team_name
from api.sessions import SessionRegistry
from tests.api.conftest import SENTINEL_VALUES
from tests.api.containment import assert_envelope, assert_no_exception_leak, assert_no_sentinels

# The exact copy the 502 must carry. Pinned as a literal so a well-meaning
# rewrite back towards "the provider could not be reached" fails here.
NEUTRAL_COMPOSE_FAILURE = (
    "The team specification could not be created. Retry once; if the "
    "problem repeats, stop and report it."
)


def _start(harness, intent="I need a team to write docs.", authoring=None):
    body = {"intent": intent}
    if authoring is not None:
        body["authoring"] = authoring
    return harness.client.post("/api/compose/sessions", json=body)


# ---------------------------------------------------------------------------
# D1 — task names reach the filesystem
# ---------------------------------------------------------------------------


def test_a_traversing_task_name_is_rejected(make_client, spec_payload, tmp_path):
    """Before the fix this returned 200 and `POST /build` then wrote a file
    *outside* `output_path` — measured: `output_path=<tmp>/nested/out` produced
    `<tmp>/nested/ESCAPED.yaml`, with client-controlled content, bypassing the
    `overwrite=False` guard (which only inspects `output_path` itself)."""
    harness = make_client([{"is_team": True}, spec_payload(tmp_path)])
    session_id = _start(harness).json()["session_id"]

    response = harness.client.put(
        f"/api/compose/sessions/{session_id}/spec",
        json={
            "desired_roles": [{"name": "writer", "description": "Writes docs."}],
            "desired_tasks": [
                {
                    "name": "../../../../escaped",
                    "description": "Attacker-controlled file content.",
                    "agent_role": "writer",
                }
            ],
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "spec_invalid"


def test_the_core_schema_rejects_it_too_not_just_the_api(tmp_path):
    """The fix went into `TaskHint`, not into `api/`, so the CLI is covered as
    well. If someone later "simplifies" it into an api/-only constraint, this
    is what fails."""
    from pydantic import ValidationError

    from team_maker.schema.request import TaskHint

    with pytest.raises(ValidationError, match="snake_case"):
        TaskHint(name="../escaped", description="Ten characters.", agent_role="writer")


# ---------------------------------------------------------------------------
# D2 — output_path is the server's
# ---------------------------------------------------------------------------


def test_output_path_is_the_servers_not_the_composers(make_client, spec_payload, tmp_path):
    """The composer emits an `output_path`; the server replaces it. Before the
    fix the composer's value was used verbatim, which made a free-text message
    able to choose where a build wrote."""
    harness = make_client(
        [{"is_team": True}, spec_payload(tmp_path, output_path="/somewhere/attacker/chose")]
    )

    spec = _start(harness).json()["spec"]

    assert spec["output_path"] == derive_output_path("Docs Team")
    assert "attacker" not in spec["output_path"]


def test_a_refine_cannot_move_the_output_path(make_client, spec_payload, tmp_path):
    """`POST .../messages` re-authors the whole spec, so this was the route
    around `SpecEditRequest`'s refusal of the field."""
    harness = make_client(
        [
            {"is_team": True},
            spec_payload(tmp_path),
            spec_payload(tmp_path, output_path="/tmp/moved-by-a-message"),
        ]
    )
    session_id = _start(harness).json()["session_id"]

    body = harness.client.post(
        f"/api/compose/sessions/{session_id}/messages",
        json={"message": "put the output in /tmp/moved-by-a-message"},
    ).json()

    assert body["spec"]["output_path"] == derive_output_path("Docs Team")


def test_the_path_is_pinned_for_the_session_even_if_the_team_is_renamed(
    make_client, spec_payload, tmp_path
):
    """Derived once, from the first spec. Recomputing per turn would move the
    output directory under the user mid-conversation.

    The composer is made to emit a *different* path on purpose: the default
    fixture path happens to equal the derived one, so with that payload this
    test passed even with the whole feature disabled — true by construction,
    which is the second defect class the story's Dev Notes list.
    """
    harness = make_client(
        [{"is_team": True}, spec_payload(tmp_path, output_path=str(tmp_path / "composer_chose"))]
    )
    session_id = _start(harness).json()["session_id"]
    original = derive_output_path("Docs Team")
    assert original != str(tmp_path / "composer_chose"), "sanity: the two must differ"

    body = harness.client.put(
        f"/api/compose/sessions/{session_id}/spec", json={"team_name": "Renamed Team"}
    ).json()

    assert body["spec"]["team_name"] == "Renamed Team"
    assert body["spec"]["output_path"] == original


@pytest.mark.parametrize(
    "team_name,expected",
    [
        ("Docs Team", "docs_team"),
        ("  Spaced  Out  ", "spaced_out"),
        ("../../etc", "etc"),
        ("!!!", "team"),
    ],
)
def test_the_slug_is_always_one_safe_segment(team_name, expected):
    slug = slugify_team_name(team_name)

    assert slug == expected
    assert "/" not in slug and "\\" not in slug and ".." not in slug


# ---------------------------------------------------------------------------
# D3 — the per-conversation lock is bounded
# ---------------------------------------------------------------------------


def test_a_busy_session_answers_rather_than_blocking():
    """Before the fix `entry.lock` was acquired with no timeout while wrapping
    network calls, so a hung provider held the lock, the session and a
    threadpool thread indefinitely, and every queued request held another."""
    registry = SessionRegistry(lock_timeout=0.05)
    entry = registry.create(object(), _choice())  # type: ignore[arg-type]

    holder_has_it = threading.Event()
    release = threading.Event()

    def hold_it():
        with registry.hold(entry):
            holder_has_it.set()
            release.wait(timeout=5)

    worker = threading.Thread(target=hold_it)
    worker.start()
    try:
        assert holder_has_it.wait(timeout=5)
        with pytest.raises(Exception) as caught:
            with registry.hold(entry):
                pass
        assert caught.value.code == "session_busy"
        assert caught.value.status_code == 409
    finally:
        release.set()
        worker.join(timeout=5)


def test_the_waiter_queue_is_bounded():
    registry = SessionRegistry(lock_timeout=5.0, max_waiters=1)
    entry = registry.create(object(), _choice())  # type: ignore[arg-type]

    with registry.hold(entry):
        # The second request does not even wait out the timeout — there is
        # already one holder, and max_waiters is 1.
        with pytest.raises(Exception) as caught:
            with registry.hold(entry):
                pass
    assert caught.value.code == "session_busy"


def test_session_busy_is_a_real_code_with_a_status():
    assert STATUS_BY_CODE["session_busy"] == 409


# ---------------------------------------------------------------------------
# D3/P2 — eviction never takes a live conversation
# ---------------------------------------------------------------------------


def test_an_in_flight_session_is_not_evicted_when_idle(monkeypatch):
    """A turn can outlast the idle TTL (four sequential LLM calls, each with a
    two-minute ceiling). Before the fix the sweeper deleted it mid-call and the
    handler then returned 200 with a `session_id` that 404s immediately."""
    clock = _FakeClock()
    registry = SessionRegistry(clock=clock, idle_ttl=10.0)
    entry = registry.create(object(), _choice())  # type: ignore[arg-type]

    with registry.hold(entry):
        clock.advance(1_000)
        registry.create(object(), _choice())  # type: ignore[arg-type]  # triggers the sweep
        assert registry.get(entry.session_id) is entry


def test_an_in_flight_session_is_not_evicted_by_overflow():
    registry = SessionRegistry(max_sessions=2)
    entry = registry.create(object(), _choice())  # type: ignore[arg-type]

    with registry.hold(entry):
        for _ in range(5):
            registry.create(object(), _choice())  # type: ignore[arg-type]
        assert registry.get(entry.session_id) is entry


def test_a_zero_capacity_registry_does_not_explode():
    """`while len >= 0` used to reach `min()` on an empty dict."""
    registry = SessionRegistry(max_sessions=0)

    entry = registry.create(object(), _choice())  # type: ignore[arg-type]

    assert registry.get(entry.session_id) is entry


# ---------------------------------------------------------------------------
# D4 — the process-wide spend ceiling
# ---------------------------------------------------------------------------


def test_the_window_cap_bounds_turns_across_sessions():
    """The per-session cap is not a spend ceiling: `POST /sessions` is
    unlimited and each call costs 1–4 LLM round-trips. This is the cap that
    actually bounds it."""
    registry = SessionRegistry(max_turns_per_window=3)
    entries = [registry.create(object(), _choice()) for _ in range(4)]  # type: ignore[arg-type]

    for entry in entries[:3]:
        registry.begin_turn(entry)

    with pytest.raises(Exception) as caught:
        registry.begin_turn(entries[3])
    assert caught.value.code == "turn_cap_reached"
    assert "server" in caught.value.message.lower()


def test_the_window_rolls_forward():
    clock = _FakeClock()
    registry = SessionRegistry(max_turns_per_window=1, window_seconds=100.0, clock=clock)
    first = registry.create(object(), _choice())  # type: ignore[arg-type]
    second = registry.create(object(), _choice())  # type: ignore[arg-type]

    registry.begin_turn(first)
    with pytest.raises(Exception):
        registry.begin_turn(second)

    clock.advance(101)
    registry.begin_turn(second)  # the window has moved on


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


# ---------------------------------------------------------------------------
# P7 / P8 — task edits the core would have discarded silently
# ---------------------------------------------------------------------------


def test_duplicate_task_names_are_rejected(make_client, spec_payload, tmp_path):
    """Both collapse onto one manifest key, so one file is written while
    `task_count` reports two."""
    harness = make_client([{"is_team": True}, spec_payload(tmp_path)])
    session_id = _start(harness).json()["session_id"]

    response = harness.client.put(
        f"/api/compose/sessions/{session_id}/spec",
        json={
            "desired_tasks": [
                {"name": "dup", "description": "First task here.", "agent_role": "writer"},
                {"name": "dup", "description": "Second task here.", "agent_role": "writer"},
            ]
        },
    )

    assert response.status_code == 422
    assert any("uniq" in f["message"].lower() for f in response.json()["error"]["fields"])


def test_renaming_a_role_no_longer_silently_orphans_its_tasks(
    make_client, spec_payload, tmp_path
):
    """The template drops a task whose `agent_role` is not an agent, and if
    *every* task drops it substitutes its own defaults — so the built package
    could contain tasks the user never authored."""
    harness = make_client(
        [
            {"is_team": True},
            spec_payload(
                tmp_path,
                desired_tasks=[
                    {
                        "name": "draft_guide",
                        "description": "Draft the onboarding guide.",
                        "agent_role": "writer",
                    }
                ],
            )
        ]
    )
    session_id = _start(harness).json()["session_id"]

    response = harness.client.put(
        f"/api/compose/sessions/{session_id}/spec",
        json={"desired_roles": [{"name": "editor", "description": "Edits docs."}]},
    )

    assert response.status_code == 422
    fields = response.json()["error"]["fields"]
    assert any("agent_role" in f["path"] for f in fields)
    assert any("editor" not in f["message"] and "writer" in f["message"] for f in fields)


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
    import logging

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
    #    "log it, never serialise it".
    assert poison in caplog.text
    assert "TypeError" in caplog.text


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


# ---------------------------------------------------------------------------
# P1 — liveness does not share the compose threadpool
# ---------------------------------------------------------------------------


def test_health_is_a_coroutine_handler(make_client):
    """It does no I/O, so as `def` it consumed one of the same 40 anyio
    threadpool tokens the blocking compose handlers occupy — meaning enough
    concurrent turns could queue the liveness probe behind exactly the work it
    exists to report on. The compose handlers stay `def`; that is AC 3."""
    import inspect

    from api.main import health
    from api.routers import compose

    assert inspect.iscoroutinefunction(health)
    for handler in (
        compose.create_session,
        compose.send_message,
        compose.replace_spec,
        compose.build_session,
    ):
        assert not inspect.iscoroutinefunction(handler), f"{handler.__name__} must stay `def`"


def test_no_new_route_leaks_a_credential(make_client, spec_payload, tmp_path):
    """The AC 4 sweep, re-run against the paths these patches added."""
    harness = make_client([spec_payload(tmp_path)])

    responses = [
        _start(harness, authoring={"provider": "groq", "model": "x"}),
        _start(harness, authoring={"provider": "", "model": ""}),
        harness.client.delete("/api/health"),
    ]

    for response in responses:
        assert_no_sentinels(response.text, SENTINEL_VALUES)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


class _FakeClock:
    """STUB clock, so window and TTL behaviour is tested in microseconds."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _choice():
    from api.deps import resolve_authoring_choice

    return resolve_authoring_choice(None, None)
