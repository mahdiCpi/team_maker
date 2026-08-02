"""Multi-provider conformance test — required by AD-7 (Story 1.6 AC 6, 7).

> "Each agent is executed with an explicit per-agent LLM instance carrying its
> full credentials/endpoint; routing never relies on global env vars. A
> multi-provider conformance test (a team spanning >=2 providers asserts each
> agent hit its intended provider) is required and **gates every CrewAI version
> change**."  — ARCHITECTURE-SPINE.md, AD-7

**If this fails after a CrewAI upgrade, do not loosen the assertions.** They
describe the product invariant, not CrewAI's current internals. Investigate the
routing, fix it, and only then move the version pin in `pyproject.toml`.

## How the interception works (verified against crewai 1.14.6, not assumed)

`crewai.LLM(...)` is a **factory**, not a class you can patch: it returns a
provider-specific `BaseLLM` subclass (`AnthropicCompletion`, `OpenAICompletion`,
`OpenAICompatibleCompletion`, ...), each with its own `.call`. Patching
`crewai.LLM.call` intercepts nothing and lets a real network request escape —
confirmed the hard way while writing this. So `_install_call_recorder` walks the
whole `BaseLLM` subclass tree and patches every class that defines `call`.

Those provider modules are imported lazily on first `LLM(...)` construction, so
each model string the run will use is constructed once up front ("warm-up"),
purely to make its class exist before the walk. `_warm_up_models` derives that
list by calling `check_credentials` — the same resolution the real run performs
— rather than hardcoding model strings, so a newly-added provider is covered
automatically instead of silently escaping the patch.

`crewai/agents/step_executor.py:295-300` calls
`self.llm.call(messages, callbacks=..., from_task=self.task, from_agent=self.agent)`,
which is what makes a *per-agent* assertion possible: `self` is that agent's own
LLM instance and `from_agent.role` says who is calling. Returning
`"Final Answer: ..."` terminates the ReAct loop in one step (verified).

Two independent safety nets keep this offline: every `BaseLLM.call` is patched,
and `httpx.Client.send` is blocked outright (raising `_NetworkEscaped`, a
`BaseException` so no `except Exception` retry layer can swallow it), so an
unpatched provider fails the test loudly instead of quietly reaching the
internet.

Historical note: AD-7 cites the CrewAI/litellm #5139 failure class, but crewai
1.14.6 ships `crewai-core` and does **not** install litellm. The specific bug no
longer applies; the invariant it motivated — an agent must never fall back to
ambient credentials — is asserted directly below. The same absence is why the
catalog marks `groq`/`xai`/`google` `runtime_supported=False`: with no litellm
fallback the engine simply cannot construct them.
"""
from __future__ import annotations

import os

import pytest

pytest.importorskip("crewai")

from pydantic import SecretStr  # noqa: E402

from team_maker.keyconfig import KeyConfig  # noqa: E402
from team_maker.pipeline.runner import PipelineRunner  # noqa: E402
from team_maker.runtime.executor import run_team_package  # noqa: E402
from team_maker.runtime.preflight import MissingCredentialsError  # noqa: E402
from team_maker.schema.request import (  # noqa: E402
    ProviderConfig,
    RoleDefinition,
    TaskHint,
    TeamCreationRequest,
)

# Interception harness lives in tests/support/crewai_interception.py so the
# transcript conformance test (Story 1.7) reuses this proven implementation
# rather than reinventing it. Assertions below are unchanged.
from tests.support.crewai_interception import LLMCall  # noqa: E402
from tests.support.crewai_interception import block_all_network as _block_all_network
from tests.support.crewai_interception import install_call_recorder as _install_call_recorder
from tests.support.crewai_interception import warm_up_models as _warm_up_models

_ANTHROPIC_SECRET = "sk-ant-conformance"
_OPENAI_SECRET = "sk-oai-conformance"
_OPENROUTER_SECRET = "sk-or-conformance"


# ---------------------------------------------------------------------------
# A real, mixed-provider Team Package on disk
# ---------------------------------------------------------------------------


def _mixed_provider_package(tmp_path, *, third_provider: str = "ollama"):
    """Build a genuine Team Package spanning three providers via the Factory.

    Deliberately built by `PipelineRunner`, not hand-assembled, so the test
    covers the whole path a user takes: Factory writes -> loader reads back ->
    preflight resolves -> engine executes.
    """
    third = {
        "ollama": ProviderConfig(provider="ollama", model="llama3.2"),
        "openai": ProviderConfig(
            provider="openai", model="gpt-4o", api_key_env="OPENAI_API_KEY"
        ),
    }[third_provider]

    request = TeamCreationRequest(
        team_name="Conformance Team",
        purpose="A mixed-provider team used to prove per-agent routing correctness.",
        output_path=str(tmp_path / "conformance_team"),
        desired_roles=[
            RoleDefinition(
                name="architect",
                description="Designs the system and makes technical decisions.",
                llm=ProviderConfig(
                    provider="anthropic",
                    model="claude-sonnet-4-6",
                    api_key_env="ANTHROPIC_API_KEY",
                ),
            ),
            RoleDefinition(
                name="reviewer",
                description="Reviews the design for correctness and risk.",
                llm=ProviderConfig(
                    provider="openai", model="gpt-4o", api_key_env="OPENAI_API_KEY"
                ),
            ),
            RoleDefinition(
                name="summarizer",
                description="Summarizes the outcome for a non-technical reader.",
                llm=third,
            ),
        ],
        desired_tasks=[
            TaskHint(
                name="design", description="Design it.", agent_role="architect"
            ),
            TaskHint(
                name="review",
                description="Review it.",
                agent_role="reviewer",
                dependencies=["design"],
            ),
            TaskHint(
                name="summarize",
                description="Summarize it.",
                agent_role="summarizer",
                dependencies=["review"],
            ),
        ],
    )
    return PipelineRunner().run(request).output_path


def _run_with_recorder(monkeypatch, package_path, key_config):
    """Execute a real crew with every LLM call intercepted, and return the log."""
    _block_all_network(monkeypatch)
    calls = _install_call_recorder(monkeypatch, _warm_up_models(package_path, key_config))
    result = run_team_package(package_path, "ship the thing", key_config)
    return calls, result


# ---------------------------------------------------------------------------
# The conformance assertions
# ---------------------------------------------------------------------------


def test_each_agent_calls_its_own_provider_with_its_own_credential(tmp_path, monkeypatch):
    """AD-7's core claim: in a team spanning three providers, every agent's call
    carries that agent's own provider, model and credential."""
    package = _mixed_provider_package(tmp_path)
    key_config = KeyConfig(
        keys={
            "anthropic": SecretStr(_ANTHROPIC_SECRET),
            "openai": SecretStr(_OPENAI_SECRET),
        }
    )

    calls, result = _run_with_recorder(monkeypatch, package, key_config)

    assert calls, "no LLM call was intercepted — the crew did not actually run"
    by_role: dict[str, list[LLMCall]] = {}
    for call in calls:
        by_role.setdefault(call.role, []).append(call)
    assert set(by_role) == {"architect", "reviewer", "summarizer"}

    for call in by_role["architect"]:
        assert call.provider == "anthropic"
        assert call.model == "claude-sonnet-4-6"
        assert call.api_key == _ANTHROPIC_SECRET

    for call in by_role["reviewer"]:
        assert call.provider == "openai"
        assert call.model == "gpt-4o"
        assert call.api_key == _OPENAI_SECRET

    for call in by_role["summarizer"]:
        assert call.provider == "ollama"
        assert call.model == "llama3.2"
        # Keyless-local: reached by endpoint, never with one of our real keys.
        assert call.base_url is not None
        assert "11434" in call.base_url
        assert call.api_key not in (_ANTHROPIC_SECRET, _OPENAI_SECRET)

    assert result.final_output


def test_no_agent_is_ever_called_with_another_agents_credential(tmp_path, monkeypatch):
    """The failure mode AD-7 names: agent A's call going out on agent B's key.

    Asserted per role rather than over the set of providers seen — a swapped
    pair would satisfy a set-level check while being exactly the bug.
    """
    package = _mixed_provider_package(tmp_path)
    key_config = KeyConfig(
        keys={
            "anthropic": SecretStr(_ANTHROPIC_SECRET),
            "openai": SecretStr(_OPENAI_SECRET),
        }
    )
    expected_key = {
        "architect": _ANTHROPIC_SECRET,
        "reviewer": _OPENAI_SECRET,
        "summarizer": None,  # keyless-local
    }

    calls, _ = _run_with_recorder(monkeypatch, package, key_config)

    # Without this the whole test passes vacuously the day interception breaks —
    # an empty `calls` makes the loop below a no-op and reports success.
    assert calls, "no LLM call was intercepted — the crew did not actually run"
    assert {c.role for c in calls} == {"architect", "reviewer", "summarizer"}

    for call in calls:
        wrong_keys = {
            secret
            for role, secret in expected_key.items()
            if role != call.role and secret is not None
        }
        assert call.api_key not in wrong_keys, (
            f"agent '{call.role}' was called with another agent's credential"
        )
        # "not someone else's key" alone would be satisfied by handing every
        # agent api_key=None, so pin the positive case too.
        expected = expected_key[call.role]
        if expected is not None:
            assert call.api_key == expected, (
                f"agent '{call.role}' was not called with its own credential"
            )


def test_a_poisoned_process_environment_never_reaches_an_agent(tmp_path, monkeypatch):
    """The AD-7 invariant in its sharpest form: ambient provider env vars must
    not influence routing. The Key Config is the only credential source."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "POISONED-ENV-ANTHROPIC")
    monkeypatch.setenv("OPENAI_API_KEY", "POISONED-ENV-OPENAI")
    package = _mixed_provider_package(tmp_path)
    # Constructed directly rather than via from_file(): this pins the *engine*
    # side of the invariant — given a KeyConfig, ambient env must not override
    # it. (KeyConfig.from_file's own documented file-wins-over-env precedence is
    # covered separately in tests/unit/test_keyconfig.py.)
    key_config = KeyConfig(
        keys={
            "anthropic": SecretStr(_ANTHROPIC_SECRET),
            "openai": SecretStr(_OPENAI_SECRET),
        }
    )

    calls, _ = _run_with_recorder(monkeypatch, package, key_config)

    assert calls, "no LLM call was intercepted — the crew did not actually run"
    for call in calls:
        assert call.api_key != "POISONED-ENV-ANTHROPIC"
        assert call.api_key != "POISONED-ENV-OPENAI"
    assert {c.api_key for c in calls if c.role == "architect"} == {_ANTHROPIC_SECRET}
    assert {c.api_key for c in calls if c.role == "reviewer"} == {_OPENAI_SECRET}


def test_a_run_never_mutates_the_process_environment(tmp_path, monkeypatch):
    """Credentials are passed per-agent, so nothing needs to be exported. This
    is what stops a future `os.environ.setdefault` shortcut from creeping in.

    The baseline is captured *before* the recorder is installed, because the
    recorder's warm-up constructs a real `LLM` per model — exactly what the run
    does. Snapshotting afterwards would bake any construction-time env write
    into the baseline and make the run's own write an undetectable no-op.
    `_block_all_network` runs first and deliberately outside the snapshot: its
    telemetry opt-out vars are test-harness setup, not run behaviour.
    """
    package = _mixed_provider_package(tmp_path)
    key_config = KeyConfig(
        keys={
            "anthropic": SecretStr(_ANTHROPIC_SECRET),
            "openai": SecretStr(_OPENAI_SECRET),
        }
    )
    _block_all_network(monkeypatch)
    before = dict(os.environ)

    calls = _install_call_recorder(monkeypatch, _warm_up_models(package, key_config))
    run_team_package(package, "ship the thing", key_config)

    assert calls, "no LLM call was intercepted — the crew did not actually run"
    assert dict(os.environ) == before


def test_an_openrouter_reachable_agent_actually_calls_through_the_gateway(
    tmp_path, monkeypatch
):
    """AC 4: admitting an agent as usable `via-openrouter` and then running it
    without a credential would fail mid-flight. It must genuinely go through
    the gateway, on the OpenRouter key."""
    package = _mixed_provider_package(tmp_path, third_provider="openai")
    key_config = KeyConfig(
        keys={
            "anthropic": SecretStr(_ANTHROPIC_SECRET),
            "openrouter": SecretStr(_OPENROUTER_SECRET),
        }
    )

    calls, _ = _run_with_recorder(monkeypatch, package, key_config)

    assert calls, "no LLM call was intercepted — the crew did not actually run"
    openai_calls = [c for c in calls if c.role in {"reviewer", "summarizer"}]
    assert openai_calls
    for call in openai_calls:
        assert call.provider == "openrouter"
        assert call.model == "openai/gpt-4o"
        assert call.api_key == _OPENROUTER_SECRET
        assert call.base_url is not None and "openrouter.ai" in call.base_url

    # The agent with its own key is unaffected by the gateway being in play.
    for call in (c for c in calls if c.role == "architect"):
        assert call.provider == "anthropic"
        assert call.api_key == _ANTHROPIC_SECRET


def test_a_missing_provider_key_aborts_before_any_llm_call(tmp_path, monkeypatch):
    """FR-10 end-to-end: the whole point of the gate is that nothing runs. Not
    one agent, not one call — and the message names the provider and its key."""
    package = _mixed_provider_package(tmp_path)
    key_config = KeyConfig(keys={"anthropic": SecretStr(_ANTHROPIC_SECRET)})
    _block_all_network(monkeypatch)
    # The gate refuses this run, so `_warm_up_models` returns [] — patch whatever
    # BaseLLM subclasses are already imported and assert nothing gets called.
    calls = _install_call_recorder(monkeypatch, _warm_up_models(package, key_config))

    with pytest.raises(MissingCredentialsError) as exc_info:
        run_team_package(package, "ship the thing", key_config)

    assert calls == []
    message = str(exc_info.value)
    assert "openai" in message
    assert "OPENAI_API_KEY" in message
    assert _ANTHROPIC_SECRET not in message
