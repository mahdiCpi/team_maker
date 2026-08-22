"""The provider-level key read: `GET /api/keys/status` (Story 2.3, AC 1 / AC 3).

What the *machine* has. Whether one particular team can run is
`tests/api/test_key_check.py`.

Offline by construction, like the rest of `tests/api/`: the Key Config holds only
sentinels and the only LLM is a stub. A green run here is NOT evidence that any real
provider is reachable (CLAUDE.md test transparency).

Every status is a projection of `registry.classify()`, which is the single source of
truth shared with the runtime's credential resolution. These tests assert the
*projection*; `tests/unit/adapters/test_provider_availability.py` owns `classify()`.
"""
from __future__ import annotations

from tests.api.keyroutes import STATUS_PATH, by_name, statuses

# ---------------------------------------------------------------------------
# AC 1 — the provider-level read
# ---------------------------------------------------------------------------


def test_status_reports_every_catalog_provider(make_client):
    response = make_client().client.get(STATUS_PATH)

    assert response.status_code == 200
    body = response.json()
    assert set(statuses(body)) == {
        "anthropic",
        "openai",
        "google",
        "groq",
        "xai",
        "ollama",
        "openrouter",
    }


def test_status_projects_classify_verbatim(make_client):
    """The default sentinel set is anthropic + openai + openrouter, which exercises
    four of the five statuses at once — including the two that are *derived* rather
    than read: `via-openrouter` for a gateway-reachable provider with no direct key,
    and `unsupported-by-runtime` for one the gateway cannot reach either."""
    body = make_client().client.get(STATUS_PATH).json()

    assert statuses(body) == {
        "anthropic": "available",
        "openai": "available",
        # runtime cannot call Google directly, but the OpenRouter key reaches it.
        "google": "via-openrouter",
        # an inference host with no vendor namespace on OpenRouter — no route at all.
        "groq": "unsupported-by-runtime",
        # Story 4.2 Task 5.1 fixed the catalog inconsistency: `xai` now has
        # `openrouter_reachable=True` to match its existing `openrouter_slug="x-ai"`,
        # so the OpenRouter key in this default sentinel set reaches it.
        "xai": "via-openrouter",
        "ollama": "keyless-local",
        "openrouter": "available",
    }


def test_usable_follows_is_usable_not_a_string_comparison(make_client):
    body = make_client().client.get(STATUS_PATH).json()

    usable = {p["name"]: p["usable"] for p in body["providers"]}
    assert usable == {
        "anthropic": True,
        "openai": True,
        "google": True,
        "groq": False,
        # Story 4.2 Task 5.1: xai is now reachable via OpenRouter.
        "xai": True,
        "ollama": True,
        "openrouter": True,
    }


def test_status_reports_the_key_config_path_so_the_hint_is_actionable(
    make_client, key_config_path
):
    """Story 1.6's precedent: "add the key to your Key Config" is only actionable
    if the user knows which file that is. The path is not a secret."""
    body = make_client().client.get(STATUS_PATH).json()

    assert body["key_config_path"] == str(key_config_path)


def test_status_surfaces_load_warnings(make_client, write_key_config):
    write_key_config({"ANTHROPIC_API_KEY": "sk-ant-x", "NOT_A_REAL_KEY": "whatever"})

    body = make_client().client.get(STATUS_PATH).json()

    assert any("NOT_A_REAL_KEY" in w for w in body["load_warnings"])


def test_a_usable_provider_gets_no_fix_hint(make_client):
    body = make_client().client.get(STATUS_PATH).json()

    assert by_name(body, "anthropic")["fix_hint"] is None


# ---------------------------------------------------------------------------
# AC 4 — the fifth status, and the two hints that must not lie
# ---------------------------------------------------------------------------


def test_a_present_google_key_is_still_unsupported_not_missing(
    make_client, write_key_config
):
    """`deferred-work.md:85`: adding the correct key broke the run. A user with a
    valid GOOGLE_AI_API_KEY and no OpenRouter key must not be told the key is
    missing — it is present, and it is the runtime that cannot use it."""
    write_key_config({"GOOGLE_AI_API_KEY": "sk-google-x"})

    body = make_client().client.get(STATUS_PATH).json()
    google = by_name(body, "google")

    assert google["status"] == "unsupported-by-runtime"
    assert google["usable"] is False
    # The one thing it must never say to someone who already did this.
    assert "add GOOGLE_AI_API_KEY" not in (google["fix_hint"] or "")
    assert "crewai[google-genai]" in google["fix_hint"]


def test_the_groq_dead_end_is_told_neither_to_add_a_key_nor_to_use_openrouter(
    make_client, write_key_config
):
    """Both halves of the original defect, asserted together.

    Story 2.0's review found a 503 that said "add a GROQ_API_KEY entry" — advice
    that cannot work, because the engine has no groq adapter — and which then led
    the user to "'groq' is not a known provider". Asserting only the OpenRouter
    half left the *first* false statement uncaught: a hint generator that treats
    every failure as a missing key passes that check while telling the user to do
    the one thing that provably does not help.
    """
    write_key_config({"ANTHROPIC_API_KEY": "sk-ant-x"})

    body = make_client().client.get(STATUS_PATH).json()
    groq = by_name(body, "groq")

    assert groq["status"] == "unsupported-by-runtime"
    assert "GROQ_API_KEY" not in groq["fix_hint"]
    # groq is an inference host with no vendor namespace on OpenRouter, so the
    # gateway is not an escape hatch for it either.
    assert "OpenRouter" not in groq["fix_hint"]
    # Proof the hint is a real sentence rather than an empty string that would
    # satisfy every "not in" assertion above.
    assert "no native groq provider" in groq["fix_hint"]


def test_a_missing_key_names_its_env_var_and_the_gateway(make_client, write_key_config):
    write_key_config({"ANTHROPIC_API_KEY": "sk-ant-x"})

    body = make_client().client.get(STATUS_PATH).json()
    openai = by_name(body, "openai")

    assert openai["status"] == "missing"
    assert openai["env_var"] == "OPENAI_API_KEY"
    assert "OPENAI_API_KEY" in openai["fix_hint"]
    assert "OPENROUTER_API_KEY" in openai["fix_hint"]


def test_an_openrouter_only_config_reaches_the_direct_providers(
    make_client, write_key_config
):
    write_key_config({"OPENROUTER_API_KEY": "sk-or-x"})

    body = make_client().client.get(STATUS_PATH).json()

    assert statuses(body)["anthropic"] == "via-openrouter"
    assert statuses(body)["openai"] == "via-openrouter"


# ---------------------------------------------------------------------------
# AC 4 — "no keys at all" is not "no usable provider"
# ---------------------------------------------------------------------------


def test_no_keys_is_reported_even_though_ollama_is_always_usable(
    make_client, write_key_config
):
    """The trap this test exists for: `ollama` is unconditionally `keyless-local`
    and therefore `is_usable()`, so "is any provider usable?" is True on a
    completely empty Key Config. Deriving the no-keys state from usability would
    be a value true by construction, and this assertion is what makes that
    implementation fail."""
    write_key_config({})

    body = make_client().client.get(STATUS_PATH).json()

    assert body["any_key_present"] is False
    assert body["overall"] == "no-keys"
    # Both halves of the trap, asserted together so the distinction is the test.
    assert by_name(body, "ollama")["usable"] is True
    assert any(p["usable"] for p in body["providers"])


def test_has_keys_once_a_single_key_exists(make_client, write_key_config):
    write_key_config({"ANTHROPIC_API_KEY": "sk-ant-x"})

    body = make_client().client.get(STATUS_PATH).json()

    assert body["any_key_present"] is True
    assert body["overall"] == "has-keys"


def test_the_provider_read_does_not_claim_a_per_team_verdict(make_client):
    """`all-good` / `missing-key` are judgements about a *specific* team's roles,
    and this route has no team. Reporting one here would be guesswork: `groq` and
    a keyless `ollama` are permanent residents of the catalog, so any whole-catalog
    aggregate is meaningless."""
    body = make_client().client.get(STATUS_PATH).json()

    assert body["overall"] in {"no-keys", "has-keys"}


# ---------------------------------------------------------------------------
# AC 3 — a key added after startup
# ---------------------------------------------------------------------------


def test_a_key_added_after_startup_is_reflected_without_a_restart(
    make_client, write_key_config
):
    """The whole point of a fix hint is that the user acts on it and re-checks. A
    boot-time snapshot would report the pre-edit truth forever, which breaks the
    feature in exactly the flow it exists for."""
    write_key_config({"ANTHROPIC_API_KEY": "sk-ant-x"})
    harness = make_client()
    assert statuses(harness.client.get(STATUS_PATH).json())["openai"] == "missing"

    # The user edits the file while the server is running.
    write_key_config({"ANTHROPIC_API_KEY": "sk-ant-x", "OPENAI_API_KEY": "sk-openai-x"})

    assert statuses(harness.client.get(STATUS_PATH).json())["openai"] == "available"


def test_a_key_added_after_startup_is_flagged_as_needing_a_restart_to_author(
    make_client, write_key_config
):
    """Measured, not assumed: the authoring adapters read `os.environ`, and the
    credential bridge runs once at startup (`api/deps.py:12-24` documents the race
    that forbids doing it per request). So a key added now is usable for a team
    *run* — `resolve_credential` reads the Key Config directly — but not yet for
    *composing*. Saying nothing would let the check show green while the Composer
    returns 503."""
    write_key_config({"ANTHROPIC_API_KEY": "sk-ant-x"})
    harness = make_client()
    assert harness.client.get(STATUS_PATH).json()["needs_restart_to_author"] == []

    write_key_config({"ANTHROPIC_API_KEY": "sk-ant-x", "OPENAI_API_KEY": "sk-openai-x"})

    body = harness.client.get(STATUS_PATH).json()
    assert body["needs_restart_to_author"] == ["openai"]
    # Still honestly `available`: a run resolves it from the file, not the env.
    assert statuses(body)["openai"] == "available"


# ---------------------------------------------------------------------------
# Credential source — the two documented sources, reported accurately
# ---------------------------------------------------------------------------


def test_a_key_from_the_file_is_attributed_to_the_key_config(make_client):
    body = make_client().client.get(STATUS_PATH).json()

    anthropic = by_name(body, "anthropic")
    assert anthropic["credential_source"] == "key-config"
    assert anthropic["detail"] == "key found in Key Config"


def test_a_key_only_in_the_environment_is_attributed_to_the_environment(
    make_client, write_key_config, monkeypatch
):
    """The documented priority is file first, then the provider's env var, and both
    are legitimate — so the fallback is preserved and the source is named."""
    write_key_config({})
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-from-the-shell")

    body = make_client().client.get(STATUS_PATH).json()
    openai = by_name(body, "openai")

    assert openai["status"] == "available"
    assert openai["credential_source"] == "environment"
    assert "not in your Key Config" in openai["detail"]
    # The catalog's own status wording is still available, unmodified.
    assert openai["status_detail"] == "key found in Key Config"


def test_a_key_deleted_from_the_file_stops_claiming_the_file_supplies_it(
    make_client, write_key_config
):
    """The bug this exists for: `bridge_credentials` copies every file value into
    `os.environ` at startup and never removes it, so after a deletion the env
    fallback keeps returning the bridged value. The credential is real — it is not
    hidden — but "key found in Key Config" would be false."""
    write_key_config({"ANTHROPIC_API_KEY": "sk-ant-x"})
    harness = make_client()
    assert by_name(harness.client.get(STATUS_PATH).json(), "anthropic")[
        "credential_source"
    ] == "key-config"

    write_key_config({})  # the user deletes the key while the server runs

    anthropic = by_name(harness.client.get(STATUS_PATH).json(), "anthropic")
    assert anthropic["credential_source"] == "startup-leftover"
    assert "no longer in your Key Config" in anthropic["detail"]
    assert "restart" in anthropic["detail"]


def test_a_gateway_reached_provider_reports_the_gateways_source(
    make_client, write_key_config
):
    write_key_config({"OPENROUTER_API_KEY": "sk-or-x"})

    body = make_client().client.get(STATUS_PATH).json()
    google = by_name(body, "google")

    assert google["status"] == "via-openrouter"
    # The answering credential is OpenRouter's, so that is whose source is reported.
    assert google["credential_source"] == "key-config"


def test_a_keyless_provider_reports_no_source(make_client):
    ollama = by_name(make_client().client.get(STATUS_PATH).json(), "ollama")

    assert ollama["credential_source"] == "none"


# ---------------------------------------------------------------------------
# needs_restart_to_author — added AND changed
# ---------------------------------------------------------------------------


def test_a_key_changed_in_place_after_startup_needs_a_restart_to_author(
    make_client, write_key_config
):
    """The likely real remedy is *editing* a wrong or expired key, not adding one. A
    provider-name membership test cannot see that: the name is in `bridged` and the
    file still has the provider, so only comparing the values reveals it."""
    write_key_config({"ANTHROPIC_API_KEY": "sk-ant-EXPIRED"})
    harness = make_client()
    assert harness.client.get(STATUS_PATH).json()["needs_restart_to_author"] == []

    write_key_config({"ANTHROPIC_API_KEY": "sk-ant-CORRECTED"})

    assert harness.client.get(STATUS_PATH).json()["needs_restart_to_author"] == [
        "anthropic"
    ]
