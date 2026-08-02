"""Offline crewai interception harness shared by the conformance tests.

Extracted in Story 1.7 from `tests/conformance/test_multi_provider_conformance.py`
so the transcript conformance test can reuse the *proven* interception rather
than reinventing it — Story 1.6's record shows a hand-rolled variant let a real
network request escape and come back 401 from Anthropic.

Everything here is a **test double**: no real LLM call and no network request is
ever made by code that uses this module.

Three things travel with the helpers and must not be separated from them:

* the `pytest.importorskip("crewai")` guard, which gates every crewai import
  below it so a plain-system-Python run degrades instead of erroring;
* `LLMCall`, the element type the recorder returns;
* `_NetworkEscaped`, deliberately a `BaseException` so no `except Exception`
  retry layer inside an agent framework can swallow the guard.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pytest

pytest.importorskip("crewai")

import httpx  # noqa: E402
from crewai import LLM  # noqa: E402
from crewai.llms.base_llm import BaseLLM  # noqa: E402

from team_maker.runtime.loader import load_team_package  # noqa: E402
from team_maker.runtime.preflight import (  # noqa: E402
    MissingCredentialsError,
    check_credentials,
)


@dataclass(frozen=True)
class LLMCall:
    """One intercepted LLM invocation, attributed to the agent that made it."""

    role: Optional[str]
    provider: str
    model: str
    api_key: Optional[str]
    base_url: Optional[str]


class _NetworkEscaped(BaseException):
    """Raised when a real HTTP request escapes interception.

    Deliberately a `BaseException` and not an `Exception`: agent frameworks wrap
    provider calls in `except Exception` for retry/fallback, which would swallow
    this guard and turn a hard conformance failure into a soft retry loop. Only
    a BaseException is uncatchable by that application code.
    """


def all_subclasses(cls: type) -> list[type]:
    found: list[type] = []
    for sub in cls.__subclasses__():
        found.append(sub)
        found.extend(all_subclasses(sub))
    return found


def warm_up_models(package_path, key_config) -> list[str]:
    """Derive the warm-up list from the run's *own* resolved credentials.

    Emphatically not a hardcoded literal. Every model string the run will use
    has to have had its provider module imported before the `BaseLLM` subclass
    walk, or that provider's `call` is never patched and its request escapes to
    the network. Deriving the list from `check_credentials` — the same call the
    real run makes — means a provider added to a fixture is covered
    automatically, instead of silently escaping until someone notices.

    Returns `[]` when the gate refuses the run: nothing will execute, so there
    is nothing to warm up.
    """
    team = load_team_package(package_path)
    try:
        credentials = check_credentials(team, key_config)
    except MissingCredentialsError:
        return []
    return [credential.model for credential in credentials.values()]


def install_call_recorder(
    monkeypatch: pytest.MonkeyPatch,
    warm_ups: list[str],
    *,
    responder=None,
    force_react: bool = False,
) -> list[LLMCall]:
    """Patch every LLM implementation's `call` and record who called with what.

    `crewai.LLM` is a *factory*, not a class: it returns a provider-specific
    `BaseLLM` subclass, each with its own `.call`. Patching `crewai.LLM.call`
    intercepts nothing, so the whole subclass tree is walked. Those provider
    modules import lazily on first `LLM(...)` construction, hence the warm-up.

    `responder(role, call_index)` may return a canned reply for a specific
    agent, so a test can drive a multi-step exchange (e.g. a delegation). It
    defaults to a single-step ReAct terminator.

    `force_react=True` also patches `supports_function_calling` to return False.
    **This is required to exercise delegation offline**: the default executor
    takes the native function-calling branch, which never reaches the ReAct
    parser, so a stubbed delegation response is swallowed as a final answer and
    no `ToolUsage*` event is ever emitted. Verified against crewai 1.14.6.
    """
    calls: list[LLMCall] = []

    def _record(
        self,
        messages,
        tools=None,
        callbacks=None,
        available_functions=None,
        from_task=None,
        from_agent=None,
        response_model=None,
    ):
        role = getattr(from_agent, "role", None)
        calls.append(
            LLMCall(
                role=role,
                provider=getattr(self, "provider", None),
                model=getattr(self, "model", None),
                api_key=getattr(self, "api_key", None),
                base_url=getattr(self, "base_url", None),
            )
        )
        if responder is not None:
            reply = responder(role, len(calls))
            if reply is not None:
                return reply
        return "Final Answer: done"

    # Force each provider module to import so its class exists to be patched.
    for model in warm_ups:
        LLM(model=model, api_key="warm-up-not-a-real-key")

    patched = [cls for cls in [BaseLLM, *all_subclasses(BaseLLM)] if "call" in cls.__dict__]
    assert patched, "found no BaseLLM implementation to patch — crewai internals changed"
    for cls in patched:
        monkeypatch.setattr(cls, "call", _record)
        if force_react:
            monkeypatch.setattr(
                cls, "supports_function_calling", lambda self: False, raising=False
            )

    return calls


def block_all_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Belt-and-braces: an unpatched provider must fail loudly, not phone home."""

    def _blocked(self, request, *args, **kwargs):
        raise _NetworkEscaped(
            f"conformance test attempted a real network call to {request.url} — "
            "an LLM implementation escaped interception"
        )

    monkeypatch.setattr(httpx.Client, "send", _blocked)
    monkeypatch.setattr(httpx.AsyncClient, "send", _blocked)
    # crewai's telemetry is opt-out; leaving it on would trip the guard above.
    monkeypatch.setenv("CREWAI_TELEMETRY_OPT_OUT", "true")
    monkeypatch.setenv("OTEL_SDK_DISABLED", "true")
