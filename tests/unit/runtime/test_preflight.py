"""Story 1.6 Task 2 — pre-run credential gate (AC 1, 2, 3, 5, 6).

AD-9 requires key-aware resolution to run *before* any work begins and to fail
fast with a plain-language reason. These tests pin the two things that are easy
to get wrong: reporting **every** unusable provider rather than short-circuiting
on the first, and never letting a key value into the message.

Fully offline — no crewai, no network, no filesystem.
"""
from __future__ import annotations

import pickle
from pathlib import Path

import pytest
from pydantic import SecretStr

from team_maker.domain.models import AgentSpec, GeneratedTeam
from team_maker.keyconfig import KeyConfig
from team_maker.runtime.preflight import (
    DuplicateAgentRoleError,
    InvalidPackageError,
    InvalidTaskNamesError,
    MissingCredentialsError,
    UnauthorizedToolError,
    UnavailableToolError,
    UnsafeMountPolicyError,
    check_credentials,
    check_mount_allowlist_safety,
    check_tool_authorization,
    check_tool_availability,
)
from team_maker.tools.authorization import AuthorizationPolicy
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
    # xai IS openrouter_reachable in the catalog (fixed in Story 4.2 Task 5.1)
    assert "OpenRouter" in by_provider["xai"].reason


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


# ---------------------------------------------------------------------------
# Tool authorization at preflight (spec FR-050 to FR-055, FR-058;
# Amendment 1; tasks T106-T108)
# ---------------------------------------------------------------------------


def test_risky_tool_without_operator_enablement_refuses_before_any_agent_runs():
    team = generated_team(
        [agent_spec("architect", tools=["shell"])],
        [task_spec("design", "architect")],
    )
    with pytest.raises(UnauthorizedToolError, match="shell"):
        check_tool_authorization(team, AuthorizationPolicy())


def test_safe_tool_needs_no_operator_enablement():
    team = generated_team(
        [agent_spec("architect", tools=["state_reader"])],
        [task_spec("design", "architect")],
    )
    check_tool_authorization(team, AuthorizationPolicy())  # must not raise


def test_risky_tool_explicitly_enabled_is_authorized():
    team = generated_team(
        [agent_spec("architect", tools=["shell"])],
        [task_spec("design", "architect")],
    )
    check_tool_authorization(team, AuthorizationPolicy(enabled_tools=frozenset({"shell"})))


def test_every_denied_tool_is_named_not_just_the_first():
    team = generated_team(
        [agent_spec("architect", tools=["shell", "docker_runner"])],
        [task_spec("design", "architect")],
    )
    with pytest.raises(UnauthorizedToolError) as exc_info:
        check_tool_authorization(team, AuthorizationPolicy())
    assert set(exc_info.value.denied) == {"shell", "docker_runner"}


def test_unauthorized_tool_error_message_is_actionable():
    team = generated_team(
        [agent_spec("architect", tools=["shell"])],
        [task_spec("design", "architect")],
    )
    with pytest.raises(UnauthorizedToolError) as exc_info:
        check_tool_authorization(team, AuthorizationPolicy())
    assert "operator" in str(exc_info.value).lower()


def test_hand_edited_package_gets_the_identical_gate():
    """FR-080: this check takes only the team and the policy — nothing here
    could special-case a package's provenance even if it wanted to."""
    import inspect

    assert set(inspect.signature(check_tool_authorization).parameters) == {"team", "policy"}


# ---------------------------------------------------------------------------
# Tool availability at preflight (spec FR-030, FR-031, FR-058, FR-067,
# FR-068; tasks T132-T136)
# ---------------------------------------------------------------------------


def _write_package(tmp_path, tools_source: str):
    from team_maker.codegen import render_template

    package_dir = tmp_path / "pkg"
    package_dir.mkdir()
    (package_dir / "tools.py").write_text(tools_source, encoding="utf-8")
    (package_dir / "state_store.py").write_text(
        render_template("state_store.py.j2", use_vector=False, use_file=True), encoding="utf-8"
    )
    return package_dir


def _current_tools_source():
    from team_maker.codegen import render_template
    from team_maker.schema.request import SandboxConfig
    from team_maker.tools.limits import DEFAULT_CONTROLS
    from team_maker.tools.policy import EMPTY_ALLOWLIST

    return render_template(
        "tools.py.j2",
        sandbox=SandboxConfig(),
        suggested_tools=[],
        context_dir=None,
        effective_network="none",
        network_allowed=False,
        controls=DEFAULT_CONTROLS,
        mount_allowlist=EMPTY_ALLOWLIST.entries,
    )


def test_available_canonical_tool_passes_preflight(tmp_path):
    package_dir = _write_package(tmp_path, _current_tools_source())
    team = generated_team(
        [agent_spec("architect", tools=["state_reader"])],
        [task_spec("design", "architect")],
    )
    check_tool_availability(team, package_dir)  # must not raise


def test_unknown_tool_name_is_unavailable(tmp_path):
    package_dir = _write_package(tmp_path, _current_tools_source())
    team = generated_team(
        [agent_spec("architect", tools=["text_summarizer"])],
        [task_spec("design", "architect")],
    )
    with pytest.raises(UnavailableToolError, match="text_summarizer"):
        check_tool_availability(team, package_dir)


def test_missing_required_credential_is_unavailable(tmp_path, monkeypatch):
    """Uses `git_account` (GIT_ACCOUNT_TOKEN), not `web_search` — the
    latter is in CONDITIONALLY_AVAILABLE_TOOL_NAMES and is deliberately
    exempted from this check (see the dedicated test below)."""
    monkeypatch.delenv("GIT_ACCOUNT_TOKEN", raising=False)
    package_dir = _write_package(tmp_path, _current_tools_source())
    team = generated_team(
        [agent_spec("architect", tools=["git_account"])],
        [task_spec("design", "architect")],
    )
    with pytest.raises(UnavailableToolError, match="GIT_ACCOUNT_TOKEN"):
        check_tool_availability(team, package_dir)


def test_missing_required_credential_message_never_leaks_a_value(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_ACCOUNT_TOKEN", "")
    package_dir = _write_package(tmp_path, _current_tools_source())
    team = generated_team(
        [agent_spec("architect", tools=["git_account"])],
        [task_spec("design", "architect")],
    )
    with pytest.raises(UnavailableToolError) as exc_info:
        check_tool_availability(team, package_dir)
    assert "GIT_ACCOUNT_TOKEN" in str(exc_info.value)
    assert "not set" in str(exc_info.value)


def test_present_credential_is_available(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_ACCOUNT_TOKEN", "a-real-looking-token")
    package_dir = _write_package(tmp_path, _current_tools_source())
    team = generated_team(
        [agent_spec("architect", tools=["git_account"])],
        [task_spec("design", "architect")],
    )
    check_tool_availability(team, package_dir)  # must not raise


def test_unresolvable_registry_drift_is_unavailable(tmp_path):
    source = _current_tools_source().replace('"state_reader":   state_reader_tool,\n', "")
    package_dir = _write_package(tmp_path, source)
    team = generated_team(
        [agent_spec("architect", tools=["state_reader"])],
        [task_spec("design", "architect")],
    )
    with pytest.raises(UnavailableToolError, match="state_reader"):
        check_tool_availability(team, package_dir)


def test_availability_and_authorization_are_distinct_reason_classes(tmp_path):
    """T107: a diagnostic can tell "not permitted here" from "not
    available here" — a RISKY-but-unauthorized tool raises
    `UnauthorizedToolError`, never `UnavailableToolError`, and a genuinely
    unresolvable SAFE tool raises the other way around."""
    package_dir = _write_package(tmp_path, _current_tools_source())
    team = generated_team(
        [agent_spec("architect", tools=["shell"])],
        [task_spec("design", "architect")],
    )
    with pytest.raises(UnauthorizedToolError):
        check_tool_authorization(team, AuthorizationPolicy())
    check_tool_availability(team, package_dir)  # shell IS resolvable — must not raise


def test_conditionally_available_tool_missing_credential_does_not_hard_fail(tmp_path, monkeypatch):
    """D-IMPL-007's warn-and-omit leniency for `code_reader`/`web_search`/
    `filesystem` must not be re-broken by the credential check added in
    Phase 7 — found via a real regression in `tests/conformance/`
    (`code_reader` declared, no `OPENAI_API_KEY`, this dev environment
    never has `crewai-tools` installed either)."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    package_dir = _write_package(tmp_path, _current_tools_source())
    team = generated_team(
        [agent_spec("architect", tools=["code_reader"])],
        [task_spec("design", "architect")],
    )
    check_tool_availability(team, package_dir)  # must not raise


def test_no_tools_declared_is_unaffected(tmp_path):
    package_dir = _write_package(tmp_path, _current_tools_source())
    team = generated_team([agent_spec("architect")], [task_spec("design", "architect")])
    check_tool_availability(team, package_dir)  # must not raise


def test_preflight_reason_class_matches_compose_and_build(tmp_path):
    """F1, T139: the same invalid declaration rejected at compose (schema/
    request.py, a `TeamCreationRequest` construction-time check) and build
    (structurally guaranteed by the same shared `validate_declarations`
    core, since an invalid `TeamCreationRequest` can never reach
    `PipelineRunner`) is also hard-failed at preflight with the identical
    `RejectionReason` — completing the three-stage determinism claim Phase
    3 deliberately could not verify (F1)."""
    from team_maker.tools.validation import RejectionReason, validate_declarations

    declaration = [("text_summarizer", "architect")]
    compose_outcome = validate_declarations(declaration, stage="compose")
    preflight_outcome = validate_declarations(declaration, stage="preflight")

    assert len(compose_outcome.rejections) == len(preflight_outcome.rejections) == 1
    assert compose_outcome.rejections[0].reason == RejectionReason.UNKNOWN
    assert preflight_outcome.rejections[0].reason == RejectionReason.UNKNOWN

    # And it is actually reachable through check_tool_availability, not just
    # the shared core in isolation.
    package_dir = _write_package(tmp_path, _current_tools_source())
    team = generated_team(
        [agent_spec("architect", tools=["text_summarizer"])],
        [task_spec("design", "architect")],
    )
    with pytest.raises(UnavailableToolError, match="text_summarizer"):
        check_tool_availability(team, package_dir)


# ---------------------------------------------------------------------------
# Mount allowlist safety at preflight (spec FR-032, FR-016, FR-079)
# ---------------------------------------------------------------------------


def test_dangerous_allowlist_entry_refuses():
    from team_maker.tools.config import ToolPolicyConfig
    from team_maker.tools.limits import DEFAULT_CONTROLS
    from team_maker.tools.policy import MountAllowlist, MountAllowlistEntry

    policy = ToolPolicyConfig(
        authorization=AuthorizationPolicy(),
        mount_allowlist=MountAllowlist((MountAllowlistEntry(alias="dangerous-root", host_path="/"),)),
        network_allowed=False,
        controls=DEFAULT_CONTROLS,
        source="test",
    )
    with pytest.raises(UnsafeMountPolicyError, match="dangerous-root"):
        check_mount_allowlist_safety(policy)


def test_safe_allowlist_entry_passes():
    """Uses a scratch dir under the repo's own working tree, not `tmp_path`
    (which sits under the OS user's home tree — see
    tests/unit/tools/test_policy.py's `non_home_workspace` fixture for why
    that would false-positive against the dangerous-location floor)."""
    import shutil
    from team_maker.tools.config import ToolPolicyConfig
    from team_maker.tools.limits import DEFAULT_CONTROLS
    from team_maker.tools.policy import MountAllowlist, MountAllowlistEntry

    root = Path.cwd() / "_test_scratch_preflight_mount_safety"
    workspace = root / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    policy = ToolPolicyConfig(
        authorization=AuthorizationPolicy(),
        mount_allowlist=MountAllowlist((MountAllowlistEntry(alias="ws", host_path=str(workspace)),)),
        network_allowed=False,
        controls=DEFAULT_CONTROLS,
        source="test",
    )
    try:
        check_mount_allowlist_safety(policy)  # must not raise
    finally:
        shutil.rmtree(root, ignore_errors=True)
