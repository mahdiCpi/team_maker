"""Per-application state, resolved once at startup and read by every route."""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request

from api.deps import ProviderFactory
from api.sessions import SessionRegistry
from team_maker.keyconfig import KeyConfig

# Attribute name on `app.state`. Namespaced so it cannot collide with anything
# Starlette or a future middleware puts there.
STATE_ATTR = "team_maker_api"


@dataclass(frozen=True)
class AppState:
    key_config: KeyConfig
    registry: SessionRegistry
    provider_factory: ProviderFactory
    # Provider *names* whose credential was bridged at startup. Never values.
    bridged_providers: tuple[str, ...]
    # Provider names the Key Config *file* itself defined at startup, excluding the
    # environment fallback. Needed to tell "this key only ever came from the
    # environment" apart from "the file used to define this and no longer does" —
    # `bridged_providers` cannot, because the bridge publishes whatever `KeyConfig`
    # loaded, env-sourced entries included. Names only, never values.
    file_providers: tuple[str, ...] = ()


def app_state(request: Request) -> AppState:
    return getattr(request.app.state, STATE_ATTR)
