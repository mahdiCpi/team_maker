"""Mandatory sandbox controls: the single authoritative defaults table (spec
FR-073 to FR-078, FR-086; Amendment 6). No call site — in this module, in
`codegen/engine.py`, or in the rendered `tools.py.j2` template — may restate
a value; everything reads from `DEFAULT_CONTROLS`.

Confirmed 2026-08-29 (see data-model.md §10 for the full derivation):
process/container/HTTP timeouts and the output cap are new render-time
constants that preserve exact pre-existing behaviour (five hardcoded values
in the old template collapse to three, one per class, not to one global
value — collapsing to one would itself be a behaviour change). CPU, memory,
process-count and storage have no pre-existing counterpart; they were
confirmed as new mandatory limits with no prior value to preserve.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SandboxControls:
    """One immutable set of enforced limits. `network_allowed` is resolved
    from operator policy (FR-073) separately — see `team_maker/tools/config.py`
    — because it is a policy decision, not a resource ceiling."""

    timeout_process_seconds: int
    timeout_container_seconds: int
    timeout_http_seconds: int
    max_output_bytes: int
    cpu_limit: str
    memory_limit: str
    max_processes: int
    storage_limit: str


# The authoritative defaults (data-model.md §10). Applied when operator
# policy is silent (FR-078) — silence yields this restrictive default, never
# an unbounded execution.
DEFAULT_CONTROLS = SandboxControls(
    timeout_process_seconds=120,  # preserves tools.py.j2:64 (shell/code_writer/test_runner)
    timeout_container_seconds=300,  # preserves tools.py.j2:137 (docker_runner)
    timeout_http_seconds=30,  # preserves tools.py.j2:114 (http_client)
    max_output_bytes=1_048_576,  # 1 MiB — new; sized above observed transcript outputs
    cpu_limit="1.0",  # new; confirmed 2026-08-29 — typical CI runner allocation
    memory_limit="512m",  # new; confirmed 2026-08-29 — above python:3.12-slim baseline + headroom
    max_processes=128,  # new; confirmed 2026-08-29 — blocks fork bombs, permits pytest -n
    storage_limit="1g",  # new; confirmed 2026-08-29 — above the largest observed workspace
)
