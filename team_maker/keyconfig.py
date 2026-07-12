"""Key Config loader.

Keys live in a separate, user-managed Key Config file — never entered in the UI,
never logged, never in output (AD-9). Values are wrapped in ``pydantic.SecretStr``
so ``repr``/logging redact them automatically; call ``.get_secret_value()`` only
at the point of use (not in this story).

Resolution priority (decision 2026-07-12): the **file is the source of truth**;
process environment variables are a *fallback* used only for providers the file
does not set, so the availability report reflects what will actually run.

File format is ``.env``-style: one ``KEY=VALUE`` per line. ``#`` comment lines and
blank lines are ignored; an inline `` #comment`` after a value is stripped; one
matched pair of surrounding quotes is removed. Keys map to providers via the
provider catalog (env-var form ``ANTHROPIC_API_KEY`` or bare name ``anthropic``).
The file is read as ``utf-8-sig`` so a BOM does not corrupt the first key. The file
should be git-ignored.
"""
from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, SecretStr

from team_maker.providers.registry import PROVIDERS, env_to_provider

KEY_CONFIG_ENV = "TEAM_MAKER_KEYS"
DEFAULT_FILENAME = "team_maker.keys"


def _unwrap_value(raw_value: str) -> str:
    """Strip an inline comment and a single matched pair of surrounding quotes."""
    value = raw_value.strip()
    # Inline comment: whitespace + '#' (standard .env convention). Do not treat a
    # bare '#' inside the value as a comment.
    for marker in (" #", "\t#"):
        idx = value.find(marker)
        if idx != -1:
            value = value[:idx].rstrip()
    # Remove exactly ONE matched pair of surrounding quotes (not arbitrary quote chars).
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        value = value[1:-1]
    return value


class KeyConfig(BaseModel):
    """Loaded API keys (one SecretStr per provider) plus any non-fatal load warnings."""

    keys: dict[str, SecretStr] = {}
    load_warnings: list[str] = []

    def has(self, provider: str) -> bool:
        """True if a (non-empty) key is present for ``provider``."""
        secret = self.keys.get(provider)
        return secret is not None and bool(secret.get_secret_value())

    @staticmethod
    def default_path() -> Path:
        """Resolve the Key Config path: ``$TEAM_MAKER_KEYS`` or ``./team_maker.keys``."""
        override = os.environ.get(KEY_CONFIG_ENV)
        return Path(override) if override else Path.cwd() / DEFAULT_FILENAME

    @classmethod
    def from_file(
        cls, path: Path | str | None = None, *, include_env: bool = True
    ) -> "KeyConfig":
        """Load a Key Config. Never raises: unreadable/undecodable files become a warning.

        ``include_env`` (default True) adds process env-var keys as a *fallback* for
        providers the file does not set (the file always wins).
        """
        target = Path(path) if path is not None else cls.default_path()
        mapping = env_to_provider()
        keys: dict[str, SecretStr] = {}
        warnings: list[str] = []

        if target.exists() and target.is_file():
            try:
                text = target.read_text(encoding="utf-8-sig")
            except (OSError, UnicodeDecodeError) as exc:
                warnings.append(
                    f"Could not read Key Config at {target}: {exc.__class__.__name__}"
                )
                text = ""
            for raw in text.splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                name, _, raw_value = line.partition("=")
                value = _unwrap_value(raw_value)
                if not value:
                    continue
                provider = mapping.get(name.strip().upper())
                if provider is None:
                    warnings.append(
                        f"Unrecognized key name '{name.strip()}' in Key Config (ignored)"
                    )
                    continue
                keys[provider] = SecretStr(value)

        # Env-var fallback — file has priority; only fill providers not set from the file.
        if include_env:
            for p in PROVIDERS:
                if p.env_var and p.name not in keys:
                    env_val = os.environ.get(p.env_var)
                    if env_val:
                        keys[p.name] = SecretStr(env_val)

        return cls(keys=keys, load_warnings=warnings)
