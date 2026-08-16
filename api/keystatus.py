"""Key-check derivation (Story 2.3, AC 1 / AC 3 / AC 4).

Everything here is a *projection* of `registry.classify()`, which documents itself
as "the single source of truth for provider-availability precedence" and is shared
with the runtime's credential resolution. No availability rule is restated in this
module, and none may be: that is what keeps "what the user is told is usable" and
"what actually gets a credential" from drifting apart.

Two derivations genuinely do not exist in the core, and both live here:

* **The aggregate states.** `classify()` answers per provider; UX-DR5 asks about a
  whole team.
* **"no keys at all".** Note carefully that this is `any_key_present`, *not* "no
  usable provider". `ollama` is unconditionally `keyless-local` and therefore
  `is_usable()`, so "is anything usable?" is True on a completely empty Key Config
  — a value true by construction, and the trap
  `test_no_keys_is_reported_even_though_ollama_is_always_usable` exists to catch.

No key value passes through this module. Only presence, provider names, and
catalog-derived copy.
"""
from __future__ import annotations

from dataclasses import dataclass

from api.deps import providers_needing_restart, safe_label
from team_maker.adapters.providers.registry import (
    OPENROUTER,
    PROVIDERS,
    STATUS_AVAILABLE,
    STATUS_MISSING,
    STATUS_VIA_OPENROUTER,
    ProviderStatus,
    classify,
    get_provider,
    is_usable,
    report_availability,
)
from team_maker.domain.models import ProviderRouting
from team_maker.keyconfig import KeyConfig
from team_maker.runtime.preflight import describe_unresolved_provider

#: A role pinned to a provider the catalog does not know. Not a `registry.STATUS_*`
#: value — it describes the *spec*, not a catalog row — and declared here because
#: it crosses the wire like one.
STATUS_UNRECOGNIZED = "unrecognized"

# --- Aggregates for the provider-level read -----------------------------------
# Deliberately only two. `all-good` and `missing-key` are judgements about a
# specific team's roles, and this read has no team; `groq` and a keyless `ollama`
# are permanent catalog residents, so any whole-catalog verdict is meaningless.
OVERALL_NO_KEYS = "no-keys"
OVERALL_HAS_KEYS = "has-keys"

# --- Aggregates for the per-team check ----------------------------------------
OVERALL_ALL_GOOD = "all-good"
OVERALL_MISSING_KEY = "missing-key"
# A required provider that no key can fix. AC 4 requires this to be its own state:
# folding it into `missing-key` tells a user who added the correct key that they
# did not (`deferred-work.md:85`). An earlier version of this module folded them
# and the code review caught it.
OVERALL_UNSUPPORTED = "unsupported"
OVERALL_VIA_OPENROUTER = "via-openrouter"
# Reported only when the check could not determine a required provider at all.
OVERALL_UNKNOWN = "unknown"


#: Where a provider's credential actually came from. The documented priority is
#: the Key Config file first, then the provider's environment variable
#: (`keyconfig.py:8-10`), and both are legitimate — so the honest thing is to
#: preserve the fallback and *say which one answered*, rather than to hide a
#: credential that genuinely works or to claim the file supplied one it did not.
SOURCE_KEY_CONFIG = "key-config"
SOURCE_ENVIRONMENT = "environment"
#: In the file at startup, still live in `os.environ` because this process bridged
#: it there, and no longer in the file. Reported distinctly because "key found in
#: Key Config" is false and "found in your environment" is misleading: the value
#: is a leftover this process is holding, and a restart would lose it.
SOURCE_STARTUP_LEFTOVER = "startup-leftover"
SOURCE_NONE = "none"

#: Copy that *replaces* the catalog's status detail when the answering credential
#: did not come from the file, because "key found in Key Config" would then be a
#: false statement. `SOURCE_KEY_CONFIG` deliberately has no entry: the catalog's
#: own wording is correct for it and must not be restated here.
_SOURCE_DETAIL = {
    SOURCE_ENVIRONMENT: "key found in the environment, not in your Key Config",
    SOURCE_STARTUP_LEFTOVER: (
        "no longer in your Key Config — this process is still using the value it "
        "loaded at startup, and a restart will lose it"
    ),
}


@dataclass(frozen=True)
class ProviderReport:
    """One provider's status plus what to do about it. Never a key value."""

    name: str
    status: str
    #: What to tell the user. Source-aware: see `_SOURCE_DETAIL`.
    detail: str
    #: The catalog's own word for the *status*, unmodified. Kept separate so a
    #: consumer can render the status without the credential-source overlay.
    status_detail: str
    usable: bool
    env_var: str | None
    fix_hint: str | None
    #: One of the `SOURCE_*` constants. `none` for a provider with no credential
    #: and for a keyless one, which needs none.
    credential_source: str


def fix_hint_for(provider_name: str, status: str) -> str | None:
    """What the user should do, or `None` when there is nothing to fix.

    Delegates to `describe_unresolved_provider`, the one fix-hint generator, so the
    two statements that must never be made — "add a key" for a provider a key
    cannot help, and "use OpenRouter" for one OpenRouter cannot reach — stay wrong
    in only one place if they are ever wrong at all.
    """
    if is_usable(status):
        return None
    return describe_unresolved_provider(provider_name).reason


def credential_source(
    provider_name: str,
    status: str,
    config: KeyConfig,
    file_config: KeyConfig,
    file_providers: tuple[str, ...],
) -> str:
    """Which of the two documented credential sources actually answered.

    The priority is the Key Config file, then the provider's environment variable
    (`keyconfig.py:8-10`). Both are legitimate, so this preserves the fallback and
    reports which one supplied the credential instead of flattening them.

    `SOURCE_STARTUP_LEFTOVER` is the case worth naming: `bridge_credentials` copies
    every Key Config value into `os.environ` at startup and never removes it
    (`api/deps.py:209-236`), so once a user *deletes* a key from the file, the env
    fallback keeps handing back the value this process bridged. Without this branch
    the removal is invisible and the report claims the file still supplies a key it
    does not.

    The discriminator is `file_providers` — what the *file* defined at startup — not
    `bridged_providers`. The bridge publishes whatever `KeyConfig` loaded, which
    already includes the environment fallback, so a key that only ever came from the
    environment is also "bridged" and would be misreported as a leftover.

    For a provider reached through the gateway, the answering credential is
    OpenRouter's, so the source is OpenRouter's source.
    """
    catalog = get_provider(provider_name)
    if catalog is None or catalog.keyless_local or not catalog.env_var:
        return SOURCE_NONE
    if status == STATUS_VIA_OPENROUTER:
        # Recursion terminates: the gateway row is not itself via-openrouter.
        return credential_source(
            OPENROUTER, STATUS_AVAILABLE, config, file_config, file_providers
        )
    if file_config.has(provider_name):
        return SOURCE_KEY_CONFIG
    if config.has(provider_name):
        return (
            SOURCE_STARTUP_LEFTOVER
            if provider_name in file_providers
            else SOURCE_ENVIRONMENT
        )
    return SOURCE_NONE


def _to_report(
    row: ProviderStatus,
    config: KeyConfig,
    file_config: KeyConfig,
    file_providers: tuple[str, ...],
) -> ProviderReport:
    catalog = get_provider(row.name)
    source = credential_source(row.name, row.status, config, file_config, file_providers)
    return ProviderReport(
        name=row.name,
        status=row.status,
        # The catalog's wording is right only when the file answered; otherwise it
        # would assert something the file did not supply.
        detail=_SOURCE_DETAIL.get(source, row.detail),
        status_detail=row.detail,
        usable=is_usable(row.status),
        env_var=catalog.env_var if catalog else None,
        fix_hint=fix_hint_for(row.name, row.status),
        credential_source=source,
    )


def provider_reports(
    config: KeyConfig,
    file_config: KeyConfig,
    file_providers: tuple[str, ...] = (),
) -> list[ProviderReport]:
    """Every catalog provider's status, in catalog order."""
    return [
        _to_report(row, config, file_config, file_providers)
        for row in report_availability(config)
    ]


def any_key_present(config: KeyConfig) -> bool:
    """Whether the user has configured *any* provider key at all.

    Keyless providers are excluded on purpose — see the module docstring.
    """
    return any(config.has(row.name) for row in PROVIDERS if row.env_var)


def provider_overall(config: KeyConfig) -> str:
    return OVERALL_HAS_KEYS if any_key_present(config) else OVERALL_NO_KEYS


def needs_restart_to_author(
    config: KeyConfig, bridged: tuple[str, ...]
) -> list[str]:
    """Providers the Key Config can satisfy but composing cannot, until restart.

    Measured, not assumed (Story 2.3 AC 3): the authoring adapters read
    `os.environ.get(api_key_env)` and `api/deps.py:bridge_credentials` runs once
    during lifespan startup — deliberately, because a per-request environment
    mutation races (`api/deps.py:12-24`). A team *run* resolves credentials from
    the Key Config directly (`adapters/providers/resolution.py`), so a freshly
    added *or corrected* key is genuinely usable there; composing with it is not,
    until the process restarts.

    Delegates to `api/deps.py`, which owns the value comparison because it owns the
    only secret unwrap in `api/`. An earlier version tested provider-name
    membership alone and so could not see a key that was *changed* in place — the
    most likely real remedy — which left exactly the "green while the Composer
    answers 503" case this exists to prevent.

    Names only, never values.
    """
    return providers_needing_restart(config, bridged)


@dataclass(frozen=True)
class RoleReport:
    """One role's required provider and whether it can be satisfied."""

    role: str
    provider: str
    model: str
    status: str
    detail: str
    usable: bool
    inherited_default: bool
    fix_hint: str | None
    credential_source: str
    #: This role cannot be dropped or reassigned away from — the build needs it.
    #: The planner is the only such role today.
    required: bool


def role_reports(
    routings: dict[str, ProviderRouting],
    inherited: dict[str, bool],
    config: KeyConfig,
    file_config: KeyConfig | None = None,
    file_providers: tuple[str, ...] = (),
    required: frozenset[str] = frozenset(),
) -> list[RoleReport]:
    """Resolve each role's routing into a status.

    `routings` comes from `api/routings.requested_routings`, so the
    `role.llm -> default_llm -> default` order is not re-encoded here.

    `required` names roles that cannot be dropped or swapped away from — today the
    synthetic planner role, which the build itself needs a credential for.
    """
    file_config = file_config if file_config is not None else config
    # Hoisted: this walks the whole catalog, and calling it per role made a 10-role
    # team perform 10 full classifications on a route the Composer hits after every
    # adopted spec.
    details = {row.name: row.detail for row in report_availability(config)}
    reports: list[RoleReport] = []
    for role, routing in routings.items():
        provider_name = routing.provider
        model = routing.model
        catalog = get_provider(provider_name)
        if catalog is None:
            # An unrecognised provider is not "missing a key" — no key exists to
            # add. `describe_unresolved_provider` says so and lists the real ones.
            reports.append(
                RoleReport(
                    role=role,
                    provider=provider_name,
                    model=model,
                    status=STATUS_UNRECOGNIZED,
                    detail="not a known provider",
                    usable=False,
                    inherited_default=inherited.get(role, False),
                    fix_hint=describe_unresolved_provider(provider_name).reason,
                    credential_source=SOURCE_NONE,
                    required=role in required,
                )
            )
            continue
        status = classify(catalog, config)
        source = credential_source(provider_name, status, config, file_config, file_providers)
        reports.append(
            RoleReport(
                role=role,
                provider=provider_name,
                model=model,
                status=status,
                detail=_SOURCE_DETAIL.get(source, details.get(catalog.name, status)),
                usable=is_usable(status),
                inherited_default=inherited.get(role, False),
                fix_hint=fix_hint_for(provider_name, status),
                credential_source=source,
                required=role in required,
            )
        )
    return reports


def check_overall(reports: list[RoleReport]) -> str:
    """The team-level verdict.

    `missing` and `unsupported-by-runtime` are kept apart (AC 4): the first is fixed
    by adding a key, the second cannot be fixed by any key, and one word for both
    tells a user who added the right key that they did not.
    """
    if not reports:
        return OVERALL_UNKNOWN
    unusable = [report for report in reports if not report.usable]
    if any(report.status == STATUS_MISSING for report in unusable):
        return OVERALL_MISSING_KEY
    if unusable:
        # Nothing is *missing*; what remains is a provider no key can enable.
        return OVERALL_UNSUPPORTED
    if any(report.status == STATUS_VIA_OPENROUTER for report in reports):
        return OVERALL_VIA_OPENROUTER
    return OVERALL_ALL_GOOD


def blocking_reason(reports: list[RoleReport]) -> str | None:
    """Why this team cannot run yet, in plain language, or `None`.

    `EXPERIENCE.md:104` bans hiding a blocked action behind a silent failure, so a
    blocked check always carries the sentence that says why.

    Three things this deliberately does not do, each a defect the code review found
    in the first version:

    * It does not say "has no usable credential" about a provider no credential can
      fix. Those are described as unsupported instead.
    * It does not carry a spatial pointer ("see the key check below"). The same
      sentence is rendered above the action bar *and* inside the review dialog,
      where no banner exists, so any direction it named was wrong somewhere.
    * It agrees with its own subject in number.

    Client-supplied provider and role names are passed through `safe_label` (AC 7):
    `ProviderSelection.provider` is a free-form bounded string that the catalog does
    not constrain, and role names come from the spec.
    """
    unusable = [report for report in reports if not report.usable]
    if not unusable:
        return None
    roles = ", ".join(safe_label(report.role) for report in unusable)
    missing = sorted({r.provider for r in unusable if r.status == STATUS_MISSING})
    unsupported = sorted({r.provider for r in unusable if r.status != STATUS_MISSING})

    clauses: list[str] = []
    if missing:
        # "has/have no usable credential" — the verb is `to have`.
        clauses.append(
            f"{_subject(missing)} {'has' if len(missing) == 1 else 'have'} "
            "no usable credential"
        )
    if unsupported:
        # "is/are not supported" — the verb is `to be`. Sharing one `_verb` helper
        # across both clauses produced "'xai' has not supported by the installed
        # runtime engine"; the test that asserts subject/verb agreement caught it.
        clauses.append(
            f"{_subject(unsupported)} {'is' if len(unsupported) == 1 else 'are'} "
            "not supported by the installed runtime engine"
        )
    required = [r.role for r in unusable if r.required]
    tail = (
        " This team cannot be built without it."
        if required
        else " Switch the affected agents to a model you can use."
    )
    return f"This team cannot run yet: {' and '.join(clauses)} (affects {roles})." + tail


def _subject(providers: list[str]) -> str:
    return ", ".join(f"'{safe_label(name)}'" for name in providers)

