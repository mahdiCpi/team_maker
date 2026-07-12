"""Shared helper: fuzzy-match a requested model against a provider's live catalog."""
from __future__ import annotations

import difflib
import sys


def _closest_model(requested: str, available: list[str], fallback: str) -> str:
    """Return the available model closest to `requested`, or `fallback` if list is empty."""
    if not available:
        return fallback
    if requested in available:
        return requested
    ranked = sorted(
        available,
        key=lambda m: difflib.SequenceMatcher(None, requested, m).ratio(),
        reverse=True,
    )
    chosen = ranked[0]
    print(
        f"[team_maker] WARNING: model '{requested}' not available. "
        f"Using closest match: '{chosen}'",
        file=sys.stderr,
    )
    return chosen
