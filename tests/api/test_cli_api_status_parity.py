"""Real cross-surface parity: CLI `keys status` vs API `GET /api/keys/status`
(Story 4.2 AC 10).

Code-review addition: the Story 4.2 diff's own `test_cli_api_parity.py` only
called the shared `report_availability()`/`bridge_all_credentials()` functions
directly and compared them to themselves -- that proves the shared function is
internally consistent, not that the two actual surfaces (the `team-maker keys
status` command and the `/api/keys/status` route) agree for the same Key
Config. This module drives both real entry points against the same file and
compares their reported per-provider status.
"""
from __future__ import annotations

from click.testing import CliRunner

from team_maker.adapters.providers.registry import PROVIDERS
from team_maker.cli import main
from tests.api.keyroutes import STATUS_PATH, statuses

_PROVIDER_NAMES = {p.name for p in PROVIDERS}
_STATUS_WORDS = {"available", "keyless-local", "via-openrouter", "missing", "unsupported-by-runtime"}
_BOX_CHARS = "|│┃┆┇┊┋‖¦"


def _cli_status_map(output: str) -> dict[str, str]:
    """Parse the `keys status` Rich table's Provider/Status columns.

    Fragile-looking but bounded: every provider name and every status literal
    is a single whitespace-delimited token with no spaces of its own, so a
    provider name immediately followed by a recognized status token is
    unambiguous regardless of the table's box-drawing characters.
    """
    found: dict[str, str] = {}
    for line in output.splitlines():
        tokens = [tok.strip(_BOX_CHARS) for tok in line.split()]
        tokens = [tok for tok in tokens if tok]
        for i, tok in enumerate(tokens):
            if tok in _PROVIDER_NAMES and i + 1 < len(tokens) and tokens[i + 1] in _STATUS_WORDS:
                found[tok] = tokens[i + 1]
    return found


def test_cli_and_api_report_identical_statuses_for_the_same_key_config(
    write_key_config, key_config_path, make_client
):
    """Same Key Config file, both real surfaces, same classification per provider."""
    write_key_config(
        {
            "ANTHROPIC_API_KEY": "sk-ant-parity-sentinel",
            "OPENROUTER_API_KEY": "sk-or-parity-sentinel",
        }
    )

    harness = make_client()
    api_statuses = statuses(harness.client.get(STATUS_PATH).json())

    cli_result = CliRunner().invoke(main, ["keys", "status", "--file", str(key_config_path)])
    assert cli_result.exit_code == 0, cli_result.output
    cli_statuses = _cli_status_map(cli_result.output)

    assert set(cli_statuses) == _PROVIDER_NAMES, (
        f"CLI table did not report every catalog provider: {sorted(cli_statuses)}"
    )
    assert cli_statuses == api_statuses


def test_cli_and_api_agree_on_an_empty_key_config(write_key_config, key_config_path, make_client):
    """An empty Key Config -- the "no keys at all" case -- must also match."""
    write_key_config({})

    harness = make_client()
    api_statuses = statuses(harness.client.get(STATUS_PATH).json())

    cli_result = CliRunner().invoke(main, ["keys", "status", "--file", str(key_config_path)])
    assert cli_result.exit_code == 0, cli_result.output
    cli_statuses = _cli_status_map(cli_result.output)

    assert cli_statuses == api_statuses
