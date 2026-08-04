"""The parametric authoring provider (Story 2.0, AC 10).

These assert that selection is *data* reaching `create_provider` as a
`ProviderConfig`, never a branch on provider name (`project-context.md:43`).
The factory is replaced by a recorder (a STUB) so the assertions can read the
config that would have been used — no adapter is constructed, no SDK is
imported, no network call is made.
"""
from __future__ import annotations

import pytest

from api.deps import DEFAULT_AUTHORING_MODEL, DEFAULT_AUTHORING_PROVIDER
from tests.api.conftest import SENTINEL_KEYS, SENTINEL_VALUES


def _start(harness, authoring=None, intent="I need a team to write docs."):
    body = {"intent": intent}
    if authoring is not None:
        body["authoring"] = authoring
    return harness.client.post("/api/compose/sessions", json=body)


def test_default_authoring_matches_the_cli(make_client, spec_payload, tmp_path):
    """Unspecified means `anthropic`/`claude-sonnet-4-6` — the same default the
    CLI uses (`cli.py:37-38`), so nothing changes for a user who configures
    nothing."""
    harness = make_client([spec_payload(tmp_path)])

    assert _start(harness).status_code == 201

    config = harness.configs[-1]
    assert config.provider == DEFAULT_AUTHORING_PROVIDER == "anthropic"
    assert config.model == DEFAULT_AUTHORING_MODEL == "claude-sonnet-4-6"
    assert config.api_key_env == "ANTHROPIC_API_KEY"


def test_direct_provider_shape(make_client, spec_payload, tmp_path):
    """Shape 1: a direct provider with its own key (`openai` + `OPENAI_API_KEY`).

    This is the case that used to be a dead Composer: a user holding only an
    OpenAI key can now author.
    """
    harness = make_client([spec_payload(tmp_path)])

    response = _start(harness, {"provider": "openai", "model": "gpt-4o"})

    assert response.status_code == 201
    config = harness.configs[-1]
    assert (config.provider, config.model) == ("openai", "gpt-4o")
    assert config.api_key_env == "OPENAI_API_KEY"


def test_gateway_shape(make_client, spec_payload, tmp_path):
    """Shape 2: one key, many models (`openrouter` + `OPENROUTER_API_KEY`)."""
    harness = make_client([spec_payload(tmp_path)])

    response = _start(
        harness, {"provider": "openrouter", "model": "anthropic/claude-sonnet-4-6"}
    )

    assert response.status_code == 201
    config = harness.configs[-1]
    assert config.provider == "openrouter"
    assert config.model == "anthropic/claude-sonnet-4-6"
    assert config.api_key_env == "OPENROUTER_API_KEY"


def test_keyless_local_shape_is_never_refused_for_a_missing_key(
    make_client, spec_payload, tmp_path
):
    """Shape 3: `ollama` has `env_var=None` and `keyless_local=True`
    (`registry.py:104`). The Key Config holds no ollama entry and must not need
    one — the gate is the catalog row, never "is there a key"."""
    harness = make_client([spec_payload(tmp_path)])

    response = _start(harness, {"provider": "ollama", "model": "llama3.2"})

    assert response.status_code == 201
    config = harness.configs[-1]
    assert config.provider == "ollama"
    assert config.api_key_env is None
    assert config.base_url == "http://localhost:11434"


def test_model_alone_can_be_overridden(make_client, spec_payload, tmp_path):
    harness = make_client([spec_payload(tmp_path)])

    assert _start(harness, {"model": "claude-haiku-4-5"}).status_code == 201

    config = harness.configs[-1]
    assert config.provider == "anthropic"
    assert config.model == "claude-haiku-4-5"


def test_provider_without_a_credential_names_the_key_config_entry(
    make_client, spec_payload, tmp_path
):
    """AC 10: never a bare "missing key". The Key Config here has no Google
    entry, so the 503 must name both the provider and the entry that fixes it."""
    harness = make_client([spec_payload(tmp_path)])

    response = _start(harness, {"provider": "google", "model": "gemini-1.5-pro"})

    assert response.status_code == 503
    error = response.json()["error"]
    assert error["code"] == "authoring_unavailable"
    assert "google" in error["message"]
    assert "GOOGLE_AI_API_KEY" in error["message"]
    assert harness.configs == [], "the adapter must not be constructed without a credential"


def test_unknown_provider_is_a_request_error_not_a_service_error(
    make_client, spec_payload, tmp_path
):
    """AC 10 says an unknown id lets `create_provider` raise its own
    `ValueError`. That is a malformed request, not "this service has no
    credential", so it maps to `spec_invalid` and carries a field path."""


    def exploding_factory(config):
        """Stands in for the real `create_provider`, which raises `ValueError`
        for an id `_ADAPTERS` does not resolve."""
        raise ValueError(f"Unknown provider '{config.provider}'.")

    harness = make_client(factory=exploding_factory)

    response = _start(harness, {"provider": "definitely-not-a-provider", "model": "x"})

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "spec_invalid"
    assert error["fields"] == [
        {
            "path": "authoring.provider",
            "message": "'definitely-not-a-provider' is not a known provider.",
        }
    ]


@pytest.mark.parametrize(
    "body",
    [
        {"intent": "docs team", "api_key": "sk-ant-ATTACKER-SUPPLIED"},
        {
            "intent": "docs team",
            "authoring": {"provider": "openai", "model": "gpt-4o", "api_key": "sk-ATTACKER"},
        },
        {
            "intent": "docs team",
            "authoring": {"provider": "openai", "model": "gpt-4o", "key": "sk-ATTACKER"},
        },
    ],
)
def test_a_request_carrying_a_key_is_rejected_not_honoured(
    make_client, spec_payload, tmp_path, body
):
    """AD-9 / AC 10: the request may name a provider; the key never comes with it."""
    harness = make_client([spec_payload(tmp_path)])

    response = harness.client.post("/api/compose/sessions", json=body)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "spec_invalid"
    # The rejected *value* must not be echoed. FastAPI's own 422 body includes
    # an `input` member holding exactly that value; the envelope reads only
    # `loc` and `msg`.
    assert "sk-ATTACKER" not in response.text
    assert "sk-ant-ATTACKER-SUPPLIED" not in response.text
    assert harness.configs == [], "no adapter is built for a rejected request"


def test_startup_bridges_key_config_credentials_without_logging_values(
    make_client, spec_payload, tmp_path, caplog
):
    """The bridge publishes provider *names*, never values (AD-9)."""
    import logging
    import os

    with caplog.at_level(logging.DEBUG):
        harness = make_client([spec_payload(tmp_path)])

    state = harness.client.app.state.team_maker_api
    assert set(state.bridged_providers) == {"anthropic", "openai", "openrouter"}
    # Each provider gets *its own* key. Membership in the sentinel tuple would
    # also pass if the OpenAI sentinel were bridged into ANTHROPIC_API_KEY,
    # which is precisely the mix-up this assertion exists to rule out.
    for env_var, expected in SENTINEL_KEYS.items():
        assert os.environ[env_var] == expected, env_var
    for sentinel in SENTINEL_VALUES:
        assert sentinel not in caplog.text
