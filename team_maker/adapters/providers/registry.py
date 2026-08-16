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
# The catalog knows this provider and a key may well be present, but the runtime
# engine cannot construct an LLM for it (see `Provider.runtime_supported`).
STATUS_UNSUPPORTED_BY_RUNTIME = "unsupported-by-runtime"

# Statuses that mean a provider can actually be used to run.
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
    # Endpoint to use when the routing entry does not pin one (keyless/local
    # providers need this; hosted providers use their SDK's own default).
    default_base_url: str | None = None
    # Vendor prefix OpenRouter uses for this provider's models, when it differs
    # from `name`. Falls back to `name` — see `openrouter_model_prefix()`.
    #
    # IMPORTANT: an OpenRouter model id is `<model-creator>/<model>` — the
    # organisation that made the weights (openai, anthropic, google, x-ai,
    # meta-llama), NOT the company serving them. A provider that is purely an
    # inference *host* (e.g. groq) has no vendor namespace of its own and
    # therefore cannot be reached by prefixing its name; such rows must leave
    # `openrouter_reachable=False`.
    openrouter_slug: str | None = None
    # False when the catalog knows this provider but the pinned runtime engine
    # cannot build an LLM for it. Such a provider is rejected by the pre-run
    # gate with an explanation, instead of passing the gate and then dying with
    # an ImportError at LLM-construction time (Story 1.6 code review).
    runtime_supported: bool = True
    # Why the runtime cannot reach it, shown to the user. Only meaningful when
    # `runtime_supported` is False.
    unsupported_reason: str | None = None
    # Additional environment variable names that should be recognized as aliases
    # for this provider's canonical env_var. Used by env_to_provider() to build
    # the lookup mapping (Story 2.9).
    env_var_aliases: tuple[str, ...] = ()

    def openrouter_model_prefix(self) -> str:
        """The vendor segment of an ``openrouter/<vendor>/<model>`` model string."""
        return self.openrouter_slug or self.name


# The catalog. Add a row to support a new provider.
#
# `runtime_supported=False` rows are catalogued (PRD FR-6 names them) but the
# pinned crewai cannot construct an LLM for them: crewai 1.14.6's native
# provider list has no `groq` and no `xai`, and this repo does not install the
# litellm fallback. Verified empirically against the installed engine.
PROVIDERS: list[Provider] = [
    Provider("anthropic", "ANTHROPIC_API_KEY", openrouter_reachable=True),
    Provider("openai", "OPENAI_API_KEY", openrouter_reachable=True),
    # Reachable only through OpenRouter: crewai's native google provider needs
    # the `crewai[google-genai]` extra, which this repo does not install.
    # (`google-generativeai` in the `all` extra is a different package.)
    Provider(
        "google",
        "GOOGLE_AI_API_KEY",
        openrouter_reachable=True,
        runtime_supported=False,
        unsupported_reason=(
            "the installed CrewAI needs the 'crewai[google-genai]' extra to call Google "
            "directly"
        ),
        env_var_aliases=("GOOGLE_API_KEY",),
    ),
    # groq is an inference host, not a model vendor, so there is no `groq/`
    # namespace on OpenRouter — it is NOT openrouter_reachable.
    Provider(
        "groq",
        "GROQ_API_KEY",
        runtime_supported=False,
        unsupported_reason="the installed CrewAI has no native groq provider",
    ),
    Provider(
        "xai",
        "XAI_API_KEY",
        openrouter_slug="x-ai",
        runtime_supported=False,
        unsupported_reason="the installed CrewAI has no native xai provider",
    ),
    Provider("ollama", None, keyless_local=True, default_base_url="http://localhost:11434"),
    Provider(OPENROUTER, "OPENROUTER_API_KEY"),
]


def get_provider(name: str) -> Provider | None:
    """Look up a catalog row by provider name; ``None`` if unrecognized."""
    for p in PROVIDERS:
        if p.name == name:
            return p
    return None


def provider_names() -> list[str]:
    """Every recognized provider name, in catalog order (for error messages)."""
    return [p.name for p in PROVIDERS]


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
        # Register each alias (uppercased) -> provider name (Story 2.9)
        for alias in p.env_var_aliases:
            mapping[alias.upper()] = p.name
    return mapping


def classify(provider: Provider, config: "KeyConfig") -> str:
    """The single source of truth for provider-availability precedence.

    Both the ``keys status`` report and the Runtime's pre-run credential
    resolution (`adapters/providers/resolution.py`) derive from this, so what
    the user is told is usable and what actually gets a credential can never
    drift apart.

    Contains no secret values — only presence/absence is used.
    """
    if provider.keyless_local:
        return STATUS_KEYLESS_LOCAL
    # A provider the engine cannot construct directly is not "available" just
    # because its key is present — the gateway is its only route.
    if provider.runtime_supported and config.has(provider.name):
        return STATUS_AVAILABLE
    if provider.openrouter_reachable and config.has(OPENROUTER):
        return STATUS_VIA_OPENROUTER
    if not provider.runtime_supported:
        # Reported ahead of MISSING on purpose: telling someone to add a key
        # that would not help is worse than telling them the truth.
        return STATUS_UNSUPPORTED_BY_RUNTIME
    return STATUS_MISSING


_STATUS_DETAIL = {
    STATUS_KEYLESS_LOCAL: "local - no API key needed",
    STATUS_AVAILABLE: "key found in Key Config",
    STATUS_VIA_OPENROUTER: "reachable via OpenRouter key",
    STATUS_MISSING: "no key found",
    STATUS_UNSUPPORTED_BY_RUNTIME: "not supported by the installed runtime engine",
}


def report_availability(config: "KeyConfig") -> list[ProviderStatus]:
    """Compute per-provider availability from a loaded Key Config."""
    report: list[ProviderStatus] = []
    for provider in PROVIDERS:
        status = classify(provider, config)
        # `.get` rather than `[...]`: a status added to `classify` without a
        # matching detail row should degrade, not raise inside `keys status`.
        report.append(
            ProviderStatus(provider.name, status, _STATUS_DETAIL.get(status, status))
        )
    return report
