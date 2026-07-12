"""Static provider catalog + availability reporting.

Provider differences live here as *data*, never as branching logic elsewhere
(project-context: "never branch on provider name"). Adding a provider is a new
entry in ``PROVIDERS`` — no other code changes (AD-8).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # avoid import cycle; only needed for typing
    from team_maker.keyconfig import KeyConfig

# Availability status values (kept as constants so callers don't hardcode strings).
STATUS_AVAILABLE = "available"
STATUS_KEYLESS_LOCAL = "keyless-local"
STATUS_VIA_OPENROUTER = "via-openrouter"
STATUS_MISSING = "missing"

# Statuses that mean a provider can actually be used to run (only MISSING blocks).
# Downstream pre-run gating (Story 1.6) should use is_usable(), not string checks.
USABLE_STATUSES = frozenset({STATUS_AVAILABLE, STATUS_KEYLESS_LOCAL, STATUS_VIA_OPENROUTER})

# The OpenRouter gateway provider name, referenced when computing reachability.
OPENROUTER = "openrouter"


@dataclass(frozen=True)
class Provider:
    """One known LLM provider. All provider-specific facts are data here."""

    name: str
    env_var: str | None  # env-var-style key name in the Key Config; None if keyless
    keyless_local: bool = False  # runs locally with no API key (e.g. ollama)
    openrouter_reachable: bool = False  # its models can be routed via OpenRouter


# The catalog. Add a row to support a new provider.
PROVIDERS: list[Provider] = [
    Provider("anthropic", "ANTHROPIC_API_KEY", openrouter_reachable=True),
    Provider("openai", "OPENAI_API_KEY", openrouter_reachable=True),
    Provider("google", "GOOGLE_API_KEY", openrouter_reachable=True),
    Provider("groq", "GROQ_API_KEY", openrouter_reachable=True),
    Provider("ollama", None, keyless_local=True),
    Provider(OPENROUTER, "OPENROUTER_API_KEY"),
]


@dataclass(frozen=True)
class ProviderStatus:
    """Reportable status for one provider — presence only, never key values."""

    name: str
    status: str  # one of the STATUS_* constants
    detail: str


def is_usable(status: str) -> bool:
    """True if a provider with this status can run a team (only MISSING blocks)."""
    return status in USABLE_STATUSES


def env_to_provider() -> dict[str, str]:
    """Map every recognized key name (env-var form and provider name) → provider name."""
    mapping: dict[str, str] = {}
    for p in PROVIDERS:
        mapping[p.name.upper()] = p.name
        if p.env_var:
            mapping[p.env_var.upper()] = p.name
    return mapping


def report_availability(config: "KeyConfig") -> list[ProviderStatus]:
    """Compute per-provider availability from a loaded Key Config.

    Contains no secret values — only presence/absence is used.
    """
    openrouter_present = config.has(OPENROUTER)
    report: list[ProviderStatus] = []
    for p in PROVIDERS:
        if p.keyless_local:
            report.append(
                ProviderStatus(p.name, STATUS_KEYLESS_LOCAL, "local - no API key needed")
            )
        elif config.has(p.name):
            report.append(ProviderStatus(p.name, STATUS_AVAILABLE, "key found in Key Config"))
        elif openrouter_present and p.openrouter_reachable:
            report.append(
                ProviderStatus(p.name, STATUS_VIA_OPENROUTER, "reachable via OpenRouter key")
            )
        else:
            report.append(ProviderStatus(p.name, STATUS_MISSING, "no key found"))
    return report
