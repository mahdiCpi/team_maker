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
from typing import Optional

from fastapi import Request

from api.errors import (
    AUTHORING_UNAVAILABLE,
    AUTHENTICATION_REQUIRED,
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

# Basic authentication for the teams API (Story 4.1 AC 6).
# API key can be provided via:
# - X-API-Key header
# - Authorization: Bearer <token> header
# A query-string `api_key` parameter is deliberately NOT supported: query
# strings routinely land in access/proxy logs, shell history, and Referer
# headers, which would contradict AD-9's "keys must never be logged" (code
# review D2, resolved 2026-08-17).
_API_KEY_ENV_VAR = "TEAM_MAKER_API_KEY"


def _extract_api_key(request: Request) -> Optional[str]:
    """Extract the API key from request headers only."""
    x_api_key = request.headers.get("X-API-Key")
    if x_api_key:
        return x_api_key

    authorization = request.headers.get("Authorization")
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
        if token:
            return token

    return None


def verify_api_key(api_key: Optional[str]) -> bool:
    """Verify the provided API key against the configured key.

    Fails closed (code review D1, resolved 2026-08-17): if `TEAM_MAKER_API_KEY`
    is not configured, every request is rejected. A missing server
    configuration must never make protected endpoints publicly accessible,
    including on localhost.
    """
    expected_key = os.environ.get(_API_KEY_ENV_VAR)
    if not expected_key:
        return False

    if api_key is None:
        return False

    # Constant-time comparison to prevent timing attacks.
    import hmac

    return hmac.compare_digest(api_key, expected_key)


def authenticated_request(request: Request) -> Request:
    """FastAPI dependency that requires API key authentication.

    Use this as a dependency in route handlers to require authentication.

    Example:
        @router.get("/teams")
        def list_teams(request: Request = Depends(authenticated_request)):
            ...
    """
    provided_key = _extract_api_key(request)

    if not verify_api_key(provided_key):
        # `ApiError`, not a raw `HTTPException` -- every authored route signals
        # errors through the one envelope (`api/errors.py`'s docstring), and
        # `AUTHENTICATION_REQUIRED` already existed for exactly this case but
        # was never actually raised anywhere until now (code review discovery
        # made while implementing D1/D2).
        raise ApiError(
            AUTHENTICATION_REQUIRED,
            "Authentication required. Provide a valid API key via the X-API-Key "
            "header or an Authorization: Bearer header. If TEAM_MAKER_API_KEY is "
            "not set on the server, no key can satisfy this check by design.",
        )

    return request

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


def current_key_config() -> KeyConfig:
    """Re-read the Key Config so a post-startup edit is visible. Never raises.

    Lives here rather than in a router because more than one surface needs it
    and they must not drift: the key panel and the Workspace's per-agent badges
    are the same availability rule projected twice, and the Story 2.4 review
    found them disagreeing because the run path read a startup snapshot while
    the key routes re-read. `providers_needing_restart` below is the reason
    this is safe — *authoring* needs a restart to see a new key, running does
    not.
    """
    return KeyConfig.from_file()


def file_only_key_config() -> KeyConfig:
    """The same read without the environment fallback, for source attribution.

    Passing `current_key_config()` in this slot is not a harmless shortcut: it
    makes `keystatus.credential_source` answer `key-config` for every provider
    that has a key from any source, which silently disables both the
    "key found in the environment" note and the startup-leftover warning.
    """
    return KeyConfig.from_file(include_env=False)


def safe_label(value: str, *, limit: int = 64) -> str:
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
    label = safe_label(name)
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
    *,
    require_credential: bool = True,
) -> LLMProvider:
    """Construct the authoring adapter, or raise the right AC 2 error.

    `require_credential=False` skips the "has a usable credential" gate.
    Every concrete adapter's `__init__` only stores its config (`model`,
    `api_key_env`, ...) — the credential itself is read, and can fail, only
    inside `complete_structured()` (the actual LLM call). So constructing a
    provider never needs a usable credential; this parameter exists for a
    caller that wants to defer the *gate* — not the construction — to the
    point an authoring call is actually about to be made (Story 3-2: a
    session seeded from a starter needs no credential merely to exist; see
    `api/routers/compose.py`'s "Provider resolution architecture" note).
    """
    if choice.row is not None:
        # Order matters: "this provider has no authoring adapter" must be
        # reported *before* "this provider has no key", or the user is told to
        # add a credential that cannot help.
        if choice.config.provider not in supported_providers():
            raise authoring_unsupported(choice)
        if require_credential and not has_usable_credential(choice, key_config):
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


def providers_needing_restart(
    key_config: KeyConfig, bridged: tuple[str, ...]
) -> list[str]:
    """Providers the Key Config can satisfy but *this process* cannot, until restart.

    Two cases, and the second is the common one:

    * **Added** — a provider absent at startup, so its variable was never bridged.
    * **Changed** — a provider whose value was corrected, rotated or un-expired in
      place. `config.has(name)` and `name in bridged` are both still true, so a
      membership test cannot see it; only comparing the values can.

    Either way a team *run* picks the new value up (it resolves from the Key Config
    directly), while authoring reads `os.environ` and keeps using what was bridged.

    Lives here rather than in `api/keystatus.py` on purpose: this is the one module
    in `api/` that unwraps a secret, and the comparison must stay inside it.
    Returns provider *names* only — no value is returned, logged or compared into
    any message (AD-9).
    """
    stale: list[str] = []
    for row in PROVIDERS:
        if not row.env_var or not key_config.has(row.name):
            continue
        if row.name not in bridged:
            stale.append(row.name)  # added since startup
            continue
        if os.environ.get(row.env_var) != key_config.keys[row.name].get_secret_value():
            stale.append(row.name)  # changed in place since startup
    return stale


def default_provider_factory() -> ProviderFactory:
    return create_provider
