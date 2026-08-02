"""Story 1.6 Task 2 — pre-run credential gate (AC 1, 2, 3, 5, 6).

AD-9 requires key-aware resolution to run *before* any work begins and to fail
fast with a plain-language reason. These tests pin the two things that are easy
to get wrong: reporting **every** unusable provider rather than short-circuiting
on the first, and never letting a key value into the message.

Fully offline — no crewai, no network, no filesystem.
"""
from __future__ import annotations

import pickle

import pytest
from pydantic import SecretStr

from team_maker.domain.models import AgentSpec, GeneratedTeam
from team_maker.keyconfig import KeyConfig
from team_maker.runtime.preflight import (
    DuplicateAgentRoleError,
    InvalidPackageError,
    InvalidTaskNamesError,
    MissingCredentialsError,
    check_credentials,
)
from tests.support.team_factories import agent_spec, generated_team, task_spec


def _agent(role: str, provider: str, model: str = "some-model") -> AgentSpec:
    return agent_spec(role, provider=provider, model=model, api_key_env=None)


def _team(agents: list[AgentSpec]) -> GeneratedTeam:
    return generated_team(agents, [task_spec(f"{a.role}_task", a.role) for a in agents])


def test_all_providers_usable_returns_a_credential_for_every_role():
    team = _team([_agent("architect", "anthropic"), _agent("reviewer", "openai")])
    key_config = KeyConfig(
        keys={"anthropic": SecretStr("sk-ant"), "openai": SecretStr("sk-oai")}
    )

    resolved = check_credentials(team, key_config)

    assert set(resolved) == {"architect", "reviewer"}
    assert resolved["architect"].model == "anthropic/some-model"
    assert resolved["architect"].api_key == "sk-ant"
    assert resolved["reviewer"].api_key == "sk-oai"


def test_missing_key_names_the_provider_the_key_and_the_affected_role():
    team = _team([_agent("architect", "anthropic"), _agent("reviewer", "openai")])
    key_config = KeyConfig(keys={"anthropic": SecretStr("sk-ant")})

    with pytest.raises(MissingCredentialsError) as exc_info:
        check_credentials(team, key_config)

    message = str(exc_info.value)
    assert "openai" in message
    assert "OPENAI_API_KEY" in message
    assert "reviewer" in message
    # The provider that *is* usable must not be dragged into the error.
    assert "anthropic" not in message


def test_every_unusable_provider_is_reported_not_just_the_first():
    """AC 2: a user missing two keys should learn both in one run, not discover
    the second only after fixing the first."""
    team = _team(
        [
            _agent("architect", "anthropic"),
            _agent("reviewer", "openai"),
            _agent("researcher", "google"),
        ]
    )

    with pytest.raises(MissingCredentialsError) as exc_info:
        check_credentials(team, KeyConfig(keys={"anthropic": SecretStr("sk-ant")}))

    message = str(exc_info.value)
    assert "openai" in message
    assert "google" in message
    assert len(exc_info.value.unresolved) == 2


def test_roles_sharing_one_missing_provider_are_grouped_into_a_single_entry():
    """Five agents on one missing provider is one problem, not five."""
    team = _team(
        [_agent("reviewer", "openai"), _agent("editor", "openai"), _agent("critic", "openai")]
    )

    with pytest.raises(MissingCredentialsError) as exc_info:
        check_credentials(team, KeyConfig(keys={}))

    [unresolved] = exc_info.value.unresolved
    assert unresolved.provider == "openai"
    assert unresolved.roles == ("reviewer", "editor", "critic")


def test_keyless_local_provider_never_blocks_with_an_empty_key_config():
    """AC 3 / FR-13: a local-only team runs with no Key Config at all."""
    team = _team([_agent("local_agent", "ollama", "llama3.2")])

    resolved = check_credentials(team, KeyConfig(keys={}))

    assert resolved["local_agent"].api_key is None
    assert resolved["local_agent"].base_url == "http://localhost:11434"


def test_openrouter_key_alone_admits_a_reachable_provider():
    """AC 4: the gate accepts `via-openrouter` — and Task 4 makes the engine
    actually honor it, so this is not a promise the run cannot keep."""
    team = _team([_agent("reviewer", "openai", "gpt-4o")])

    resolved = check_credentials(team, KeyConfig(keys={"openrouter": SecretStr("sk-or")}))

    assert resolved["reviewer"].via_openrouter is True
    assert resolved["reviewer"].model == "openrouter/openai/gpt-4o"
    assert resolved["reviewer"].api_key == "sk-or"


def test_unrecognized_provider_is_reported_as_unrecognized():
    """AC 5: closes the Story 1.5 defer where a typo degraded to api_key=None."""
    team = _team([_agent("helper", "antropic")])

    with pytest.raises(MissingCredentialsError) as exc_info:
        check_credentials(team, KeyConfig(keys={"anthropic": SecretStr("sk-ant")}))

    [unresolved] = exc_info.value.unresolved
    assert unresolved.provider == "antropic"
    assert unresolved.expected_key is None
    assert "unrecognized" in str(exc_info.value).lower()
    # The message should help the user spot the typo.
    assert "anthropic" in str(exc_info.value)


def test_zero_keys_blocks_the_run():
    """FR-21: with no keys at all, the run is blocked before it starts."""
    team = _team([_agent("architect", "anthropic")])

    with pytest.raises(MissingCredentialsError):
        check_credentials(team, KeyConfig(keys={}))


def test_message_never_contains_a_key_value():
    """AD-9: keys are never in output. The message names the *variable*, never
    its value — including for the provider that actually failed.

    The secret is deliberately attached to `openai`, the provider that lands in
    the failure path. Putting it on a provider that resolves cleanly (as an
    earlier version of this test did) makes the assertion unfalsifiable: the
    rendering code would never have been handed that secret in the first place.
    Here `check_credentials` really does hold the openai secret and really does
    build a message about openai — it just must not include the value.
    """
    secret = "sk-oai-SUPER-SECRET-VALUE"
    team = _team([_agent("architect", "anthropic"), _agent("reviewer", "openai")])
    # openai's key is present but empty, so `has()` reports it absent and openai
    # is the provider that fails — with its secret sitting in the KeyConfig.
    key_config = KeyConfig(
        keys={"anthropic": SecretStr(secret), "openai": SecretStr("")}
    )

    with pytest.raises(MissingCredentialsError) as exc_info:
        check_credentials(team, key_config)

    rendered = str(exc_info.value)
    assert "openai" in rendered  # the failing provider IS named...
    assert "OPENAI_API_KEY" in rendered  # ...as is its key *variable*...
    assert secret not in rendered  # ...but never any key value.
    assert "SUPER-SECRET" not in repr(exc_info.value)


def test_openrouter_hint_offered_only_for_reachable_providers():
    team = _team([_agent("reviewer", "openai"), _agent("grokker", "xai")])

    with pytest.raises(MissingCredentialsError) as exc_info:
        check_credentials(team, KeyConfig(keys={}))

    by_provider = {u.provider: u for u in exc_info.value.unresolved}
    assert "OpenRouter" in by_provider["openai"].reason
    # xai is not openrouter_reachable in the catalog — do not suggest it.
    assert "OpenRouter" not in by_provider["xai"].reason


def test_a_provider_the_engine_cannot_construct_is_refused_without_asking_for_a_key():
    """Story 1.6 code review: `xai` has a catalog row and may well have a valid
    key, but the pinned CrewAI cannot build an LLM for it. Telling the user to
    add XAI_API_KEY would send them to fix something that is not broken."""
    team = _team([_agent("grokker", "xai")])

    with pytest.raises(MissingCredentialsError) as exc_info:
        check_credentials(team, KeyConfig(keys={"xai": SecretStr("sk-xai-valid")}))

    [unresolved] = exc_info.value.unresolved
    assert unresolved.provider == "xai"
    assert unresolved.expected_key is None
    assert "no native xai provider" in unresolved.reason
    assert "XAI_API_KEY" not in unresolved.reason


def test_an_unsupported_but_gateway_reachable_provider_is_pointed_at_openrouter():
    """google cannot be called directly by the installed engine, but it *is* a
    real OpenRouter vendor — so the fix offered is the gateway, not its own key."""
    team = _team([_agent("researcher", "google")])

    with pytest.raises(MissingCredentialsError) as exc_info:
        check_credentials(team, KeyConfig(keys={"google": SecretStr("sk-google")}))

    [unresolved] = exc_info.value.unresolved
    assert "OPENROUTER_API_KEY" in unresolved.reason
    assert "google-genai" in unresolved.reason

    # ...and with that key present it resolves through the gateway instead.
    resolved = check_credentials(
        team, KeyConfig(keys={"openrouter": SecretStr("sk-or")})
    )
    assert resolved["researcher"].via_openrouter is True
    assert resolved["researcher"].model == "openrouter/google/some-model"


def test_duplicate_agent_roles_are_refused_rather_than_silently_collapsed():
    """Two agents on one role would key the same credential slot: the second
    overwrites the first and its tasks run on the wrong provider's key. That is
    AD-7's exact failure mode, so the run is refused."""
    team = _team([_agent("worker", "anthropic"), _agent("worker", "openai")])
    key_config = KeyConfig(
        keys={"anthropic": SecretStr("sk-ant"), "openai": SecretStr("sk-oai")}
    )

    with pytest.raises(DuplicateAgentRoleError, match="worker"):
        check_credentials(team, key_config)


def test_the_error_survives_a_pickle_round_trip():
    """The exception is advertised to non-CLI callers (the Epic 4 API), where it
    may cross a process boundary. Python rebuilds it as `type(e)(*e.args)`, so
    `args` has to hold what `__init__` accepts."""
    team = _team([_agent("reviewer", "openai")])

    with pytest.raises(MissingCredentialsError) as exc_info:
        check_credentials(team, KeyConfig(keys={}))

    restored = pickle.loads(pickle.dumps(exc_info.value))

    assert str(restored) == str(exc_info.value)
    assert restored.unresolved[0].provider == "openai"


def test_unresolved_provider_is_hashable():
    """`frozen=True` advertises hashability; a `list` field would break it the
    moment a caller did the natural `set(exc.unresolved)` to dedupe."""
    team = _team([_agent("reviewer", "openai"), _agent("editor", "openai")])

    with pytest.raises(MissingCredentialsError) as exc_info:
        check_credentials(team, KeyConfig(keys={}))

    assert len(set(exc_info.value.unresolved)) == 1


def test_a_task_with_no_name_is_refused():
    """Task name is the join key between TaskResult, the transcript, and the
    engine's task map. Blank makes crewai fall back to the description, so the
    two halves of the result stop agreeing."""
    team = generated_team(
        [agent_spec("architect", api_key_env=None)],
        [task_spec("", "architect")],
    )

    with pytest.raises(InvalidTaskNamesError, match="no name"):
        check_credentials(team, KeyConfig(keys={"anthropic": SecretStr("sk-ant")}))


def test_duplicate_task_names_are_refused():
    """Duplicates collapse the engine's crewai_tasks_by_name map, silently
    breaking `context=` wiring for anything that depends on them."""
    team = generated_team(
        [agent_spec("architect", api_key_env=None)],
        [task_spec("design", "architect"), task_spec("design", "architect")],
    )

    with pytest.raises(InvalidTaskNamesError, match="design"):
        check_credentials(team, KeyConfig(keys={"anthropic": SecretStr("sk-ant")}))


def test_invalid_package_errors_share_one_base_so_the_cli_can_catch_them_together():
    assert issubclass(DuplicateAgentRoleError, InvalidPackageError)
    assert issubclass(InvalidTaskNamesError, InvalidPackageError)
