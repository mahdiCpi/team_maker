"""Safe mount identifiers: never expose a raw resolved host path to a
user-facing surface (spec FR-070 to FR-072; D-14).

The operator-defined alias is bound to the allowlist entry itself
(`MountAllowlistEntry.alias`), so the operator who authorizes a path also
names it and no separate mapping can drift out of sync. This module's only
job is producing a stable identifier when no alias applies — it never
resolves or exposes the path itself.
"""
from __future__ import annotations

import hashlib


def sanitized_id(raw_path: str) -> str:
    """A stable, non-reversible identifier for a path that has no operator
    alias. Used only in refusal messages for a mount that was never in the
    allowlist at all (so no alias exists to use) — the identifier lets an
    operator correlate repeated refusals without a raw path ever appearing
    in a user-facing surface or receipt (FR-071)."""
    digest = hashlib.sha256(raw_path.encode("utf-8")).hexdigest()[:12]
    return f"mount-{digest}"
