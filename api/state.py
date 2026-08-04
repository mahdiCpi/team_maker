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


def app_state(request: Request) -> AppState:
    return getattr(request.app.state, STATE_ATTR)
