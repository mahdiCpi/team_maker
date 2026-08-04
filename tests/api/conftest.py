"""Shared fixtures for the API test lane (Story 2.0, AC 9).

Everything here is OFFLINE by construction: no network, no real key, no SDK.
The only LLM in these tests is a stub (`tests.support.fake_llm`). A green run
here is NOT evidence that the real Anthropic/OpenAI/OpenRouter/Ollama paths
work (CLAUDE.md test transparency).

The `isolated_key_config` fixture is autouse and load-bearing, not hygiene:
`KeyConfig.from_file(None)` falls back to `./team_maker.keys`, which exists in
this working tree with live keys, and then falls back again to the process
environment. Without isolation the app under test would load real secrets and
AC 4's "the key never appears in a response" assertion would be comparing
against a production credential — one failure message away from printing it
into a terminal or a CI log.
"""
from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from team_maker.adapters.providers.registry import PROVIDERS
from team_maker.schema.request import ProviderConfig
from tests.support.fake_llm import FakeLLMProvider

# Obviously-not-real credentials, unique enough that a substring search for one
# cannot collide with anything else in a response. One per provider shape the
# AC 10 tests need: direct (anthropic, openai) and gateway (openrouter).
# `ollama` is deliberately absent — it is the keyless shape.
SENTINEL_KEYS: dict[str, str] = {
    "ANTHROPIC_API_KEY": "sk-ant-SENTINEL-DO-NOT-LEAK",
    "OPENAI_API_KEY": "sk-openai-SENTINEL-DO-NOT-LEAK",
    "OPENROUTER_API_KEY": "sk-or-SENTINEL-DO-NOT-LEAK",
}
SENTINEL_VALUES: tuple[str, ...] = tuple(SENTINEL_KEYS.values())


@pytest.fixture(autouse=True)
def isolated_key_config(tmp_path, monkeypatch) -> Iterator[dict[str, str]]:
    """Point the app at a throwaway Key Config holding only sentinels.

    Restores the whole process environment afterwards: the app bridges
    credentials into `os.environ` during lifespan startup (by design — see
    `api/deps.py`), and that write is not made through monkeypatch, so only a
    full snapshot/restore is guaranteed to undo it.
    """
    saved_environ = dict(os.environ)
    key_file = tmp_path / "team_maker.keys"
    key_file.write_text(
        "".join(f"{name}={value}\n" for name, value in SENTINEL_KEYS.items()),
        encoding="utf-8",
    )
    monkeypatch.setenv("TEAM_MAKER_KEYS", str(key_file))
    # The API derives `output_path` itself rather than trusting the composer's
    # (code review D2), so builds land under this root. Pointed at `tmp_path`
    # so the suite never writes into the repo's real `generated_teams/`.
    monkeypatch.setenv("TEAM_MAKER_OUTPUT_ROOT", str(tmp_path))
    # KeyConfig's env fallback fills any provider the file does not set, so a
    # developer's exported keys would otherwise leak into the app under test.
    for provider in PROVIDERS:
        if provider.env_var:
            os.environ.pop(provider.env_var, None)
    try:
        yield dict(SENTINEL_KEYS)
    finally:
        os.environ.clear()
        os.environ.update(saved_environ)


@pytest.fixture
def offline_model_resolver(monkeypatch) -> list[str]:
    """STUB: replace the build's live `models.list()` calls with a fixed catalog.

    `PipelineRunner._build_manifest` calls `normalize_team_routings`, which
    queries each provider's real API (`model_resolver.py:106-111`). With a
    sentinel key present those calls would actually go out over the network and
    fail slowly, and AC 9 requires this lane to be fully offline. The fixed
    catalog also makes model substitution deterministic, which is what lets
    `test_build.py` assert on `model_substitutions` at all.
    """
    catalog = ["claude-sonnet-4-6", "claude-haiku-4-5", "gpt-4o"]

    def fake_fetcher(api_key: str) -> tuple[str, ...]:
        return tuple(catalog)

    from team_maker.llm import model_resolver

    patched = {
        name: (fake_fetcher, fallback)
        for name, (_, fallback) in model_resolver._FETCHER_MAP.items()
    }
    monkeypatch.setattr(model_resolver, "_FETCHER_MAP", patched)
    return catalog


@pytest.fixture
def spec_payload() -> Callable[..., dict[str, Any]]:
    """Factory for a schema-valid `TeamCreationRequest` payload (stub LLM output)."""

    def _make(tmp_path, **overrides: Any) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "team_name": "Docs Team",
            "purpose": "Write and maintain product documentation.",
            "output_path": str(tmp_path / "docs_team"),
            "desired_roles": [{"name": "writer", "description": "Writes documentation."}],
        }
        payload.update(overrides)
        return payload

    return _make


@dataclass
class Harness:
    """One booted app plus the seams the AC 10 assertions read."""

    client: TestClient
    provider: Any
    # Every `ProviderConfig` the app handed to the provider factory. This is
    # how AC 10 proves `create_provider` is *reached with the right data*
    # rather than a provider-name branch being taken somewhere.
    configs: list[ProviderConfig] = field(default_factory=list)


@pytest.fixture
def make_client() -> Iterator[Callable[..., Harness]]:
    """Build a booted `TestClient` whose provider factory is a fake."""
    opened: list[TestClient] = []

    def _make(
        responses: list[Any] | None = None,
        *,
        provider: Any = None,
        factory: Callable[[ProviderConfig], Any] | None = None,
        raise_server_exceptions: bool = True,
    ) -> Harness:
        fake = provider if provider is not None else FakeLLMProvider(list(responses or []))
        harness = Harness(client=None, provider=fake)  # type: ignore[arg-type]

        def recording_factory(config: ProviderConfig) -> Any:
            harness.configs.append(config)
            if factory is not None:
                return factory(config)
            return fake

        client = TestClient(
            create_app(provider_factory=recording_factory),
            raise_server_exceptions=raise_server_exceptions,
        )
        client.__enter__()  # runs the lifespan; torn down below
        opened.append(client)
        harness.client = client
        return harness

    yield _make

    for client in opened:
        client.__exit__(None, None, None)
