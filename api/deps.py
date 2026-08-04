"""Credentials and the parametric authoring provider (Story 2.0, AC 4 / AC 10).

Why this is not `cli.py`'s code
-------------------------------
`cli.py:177-190`'s `_resolve_authoring_provider` hardcodes `anthropic` and its
`ANTHROPIC_API_KEY`, which is exactly what AC 10 removes; and both it and
`_bridged_credential` are private members of the CLI layer, so importing them
would invert AD-4 and drag `click`, `rich` and `PipelineRunner`'s import chain
into the API process. The ~10 lines are reimplemented here on purpose. The
duplication is declared in the story's Completion Notes.

Why the credential bridge happens once, at startup
--------------------------------------------------
`_bridged_credential` is a context manager that sets `os.environ[env_var]` and
restores the *pre-entry* value on exit. Under AC 3's threadpool concurrency
that is a live race: request A enters (`previous=None`), request B enters
(`previous=A's key`), A finishes and pops the variable, and B — still in flight
— has its adapter read `os.environ.get(...)` -> `None` -> `EnvironmentError`.
"Resolve once per invocation" does not fix it, because the *unset* is what
races. So every credential in the Key Config is bridged once during lifespan
startup and held for the process lifetime (single process per AD-3 / AC 7).
After startup nothing mutates the environment, so there is nothing left to
race. This also means a provider selected per-session already has its
credential in place.

AD-9 holds throughout: no key value is returned, accepted, or logged. Only
provider *names* appear in logs and error copy.
"""
from __future__ import annotations

import logging
import os
from collections.abc import Callable
from dataclasses import dataclass

from api.errors import (
    AUTHORING_UNAVAILABLE,
    COMPOSE_FAILED,
    SPEC_INVALID,
    ApiError,
    FieldError,
    log_and_wrap,
)
from team_maker.adapters.providers import create_provider, supported_providers
from team_maker.adapters.providers.registry import PROVIDERS, Provider, get_provider
from team_maker.keyconfig import KeyConfig
from team_maker.ports.llm_provider import LLMProvider
from team_maker.schema.request import ProviderConfig

logger = logging.getLogger("api.deps")

# The same default the CLI uses (`cli.py:37-38`), so behaviour is unchanged for
# a user who configures nothing. This retires the spine's Deferred entry
# "Composer default model — configurable behind LLMProvider; concrete default
# TBD" (`ARCHITECTURE-SPINE.md:223`) — it is now configurable per session.
DEFAULT_AUTHORING_PROVIDER = "anthropic"
DEFAULT_AUTHORING_MODEL = "claude-sonnet-4-6"

# The seam the tests inject a fake through. Production always passes
# `create_provider`, so AD-8 holds: all LLM access goes through the one port's
# factory and no concrete adapter is ever instantiated directly here.
ProviderFactory = Callable[[ProviderConfig], LLMProvider]


@dataclass(frozen=True)
class AuthoringChoice:
    """A resolved authoring selection: the config to build from, plus its catalog row."""

    config: ProviderConfig
    row: Provider | None

    @property
    def keyless(self) -> bool:
        return self.row is not None and self.row.keyless_local


def resolve_authoring_choice(provider: str | None, model: str | None) -> AuthoringChoice:
    """Turn an optional `{provider, model}` selection into a `ProviderConfig`.

    Selection is data, never a branch (`project-context.md:43`): the catalog row
    supplies `env_var` and `default_base_url`, and an id the catalog does not
    know is passed through unchanged so `create_provider` can raise its own
    `ValueError` for it.
    """
    name = (provider or DEFAULT_AUTHORING_PROVIDER).strip().lower()
    row = get_provider(name)
    config = ProviderConfig(
        provider=name,
        model=(model or DEFAULT_AUTHORING_MODEL),
        api_key_env=row.env_var if row else None,
        base_url=row.default_base_url if row else None,
    )
    return AuthoringChoice(config=config, row=row)


def has_usable_credential(choice: AuthoringChoice, key_config: KeyConfig) -> bool:
    """Whether the chosen provider can be used to author right now.

    Gated on the catalog row, never on "is there a key": `ollama` has
    `env_var=None` and `keyless_local=True` (`registry.py:104`), and a keyless
    provider must never be refused for a missing credential.
    """
    if choice.row is None:
        return False  # unknown id — `create_provider` owns the error
    if choice.row.keyless_local:
        return True
    return bool(choice.row.env_var) and key_config.has(choice.row.name)


def authoring_unavailable(choice: AuthoringChoice, *, detail: str | None = None) -> ApiError:
    """A 503 that names the provider and the Key Config entry that would fix it.

    Never a bare "missing key" (AC 10). Contains no key value.
    """
    name = choice.config.provider
    if detail is not None:
        return ApiError(AUTHORING_UNAVAILABLE, detail)
    entry = choice.row.env_var if choice.row and choice.row.env_var else name.upper()
    return ApiError(
        AUTHORING_UNAVAILABLE,
        f"No usable credential for the authoring provider '{name}'. "
        f"Add a '{entry}' entry to your Key Config file, or choose a different "
        f"authoring provider when starting the conversation.",
    )


def authoring_unsupported(choice: AuthoringChoice) -> ApiError:
    """A 503 for a catalog provider that has no authoring adapter.

    `groq` is the only such row today: the key catalog knows it, so the old code
    checked for `GROQ_API_KEY`, found none, and returned "add a `GROQ_API_KEY`
    entry" — advice that cannot work, because `create_provider` has no groq
    adapter. A user who followed it then got "'groq' is not a known provider",
    which is also false. Say the true thing instead, and reuse the explanation
    the catalog row already carries.
    """
    name = choice.config.provider
    reason = choice.row.unsupported_reason if choice.row else None
    detail = f" ({reason})" if reason else ""
    usable = ", ".join(sorted(supported_providers()))
    return ApiError(
        AUTHORING_UNAVAILABLE,
        f"The provider '{name}' cannot be used to author a team specification"
        f"{detail}. Adding a key will not enable it. Choose one of: {usable}.",
    )


def _safe_label(value: str, *, limit: int = 64) -> str:
    """A client-supplied string that is safe to put in a log line or a message.

    Control characters are stripped and the length is bounded. Without this, a
    provider id containing a newline forges a log record — the value is echoed
    into both a `logger.warning` and the response body — and an unbounded one
    puts megabytes of client text through the log and back over the wire.
    """
    cleaned = "".join(ch for ch in value if ch.isprintable())
    return cleaned[:limit] if len(cleaned) <= limit else cleaned[:limit] + "…"


def unknown_authoring_provider(name: str, exc: ValueError) -> ApiError:
    """A 422 for an id `create_provider` cannot resolve.

    Deliberately not a 503: `authoring_unavailable` means "this provider has no
    usable credential", which is a server-configuration fact. An id the factory
    does not know is a malformed request, and `spec_invalid` is the only code in
    AC 2's table that carries `fields`. The message is authored copy — the
    provider name is echoed because it is the client's own input, never
    `str(exc)`.
    """
    label = _safe_label(name)
    logger.warning("unknown authoring provider requested: %r (%s)", label, exc.__class__.__name__)
    return ApiError(
        SPEC_INVALID,
        f"Unknown authoring provider '{label}'.",
        fields=[FieldError("authoring.provider", f"'{label}' is not a known provider.")],
    )


def build_authoring_provider(
    choice: AuthoringChoice,
    key_config: KeyConfig,
    factory: ProviderFactory,
) -> LLMProvider:
    """Construct the authoring adapter, or raise the right AC 2 error."""
    if choice.row is not None:
        # Order matters: "this provider has no authoring adapter" must be
        # reported *before* "this provider has no key", or the user is told to
        # add a credential that cannot help.
        if choice.config.provider not in supported_providers():
            raise authoring_unsupported(choice)
        if not has_usable_credential(choice, key_config):
            raise authoring_unavailable(choice)
    try:
        return factory(choice.config)
    except ValueError as exc:
        raise unknown_authoring_provider(choice.config.provider, exc) from exc
    except Exception as exc:
        # AC 2's table: "any other exception from the provider adapter" is
        # `compose_failed`. Every adapter's constructor is trivial today, so
        # this is latent — but without it a future adapter that imports its SDK
        # in `__init__` would escape the table into a bare 500.
        raise log_and_wrap(
            COMPOSE_FAILED,
            "The authoring provider could not be prepared. Please try again.",
            exc,
        ) from exc


def bridge_credentials(key_config: KeyConfig) -> list[str]:
    """Publish every Key Config credential into its env var, once, at startup.

    The Story 0.1 adapters read credentials via `os.environ.get(...)`
    internally, so this is the point where `.get_secret_value()` is called
    (AD-9). Returns the provider *names* bridged — never the values — so the
    caller can log what is available without logging a secret.
    """
    bridged: list[str] = []
    for row in PROVIDERS:
        if row.env_var and key_config.has(row.name):
            secret = key_config.keys[row.name].get_secret_value()
            existing = os.environ.get(row.env_var)
            if existing is not None and existing != secret:
                # The CLI's `_bridged_credential` restored the prior value on
                # exit; this holds for the process lifetime and never restores,
                # so an operator who exported a different key deserves to be
                # told it stopped being used. Names only, never values (AD-9).
                logger.warning(
                    "%s was already set to a different value in the environment and has "
                    "been replaced by the Key Config entry for '%s' for the lifetime of "
                    "this process",
                    row.env_var,
                    row.name,
                )
            os.environ[row.env_var] = secret
            bridged.append(row.name)
    return bridged


def default_provider_factory() -> ProviderFactory:
    return create_provider
