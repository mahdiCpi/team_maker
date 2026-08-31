# Operator Tool Execution Policy

This document covers the operator-owned configuration surface introduced by the P0 tool execution
integrity remediation (`specs/001-p0-tool-execution-integrity/`). It is separate from
`team_maker.keys` (LLM provider credentials) and from a team's own request/template config — none of
these settings can be set or altered by the team author, the LLM planner, or an agent at run time.

## The policy file

**Location**: `$TEAM_MAKER_TOOL_POLICY` if set, otherwise `./team_maker.tools.yaml` (mirroring the
existing `team_maker.keys` precedence: explicit override wins, then a default project-root location).

**Absent, empty, malformed, or unreadable** is not a permissive default — it resolves to: every RISKY
tool denied, no mounts permitted, network denied, and the documented default resource limits. This is
deliberate (fail-closed): a missing or broken policy file can only make a run *more* restrictive, never
less.

```yaml
# team_maker.tools.yaml
enabled_tools:
  - shell
  - test_runner
  # RISKY tools not listed here are denied by default: code_writer, docker_runner

network_allowed: true   # default: false. Permits SandboxConfig.network's own "bridge" setting to
                         # take effect; the request can only narrow this ceiling, never widen it.

mount_allowlist:
  - alias: project_repo          # never a raw path in an error/receipt — see below
    host_path: /home/ops/project
    writable: false               # default: read-only unless set true

controls:                         # optional; every field falls back to the documented default
  cpu_limit: "2.0"
  memory_limit: "1g"
  max_processes: 128
  max_output_bytes: 1048576
  storage_limit: "1g"
  timeout_process_seconds: 120
  timeout_container_seconds: 300
  timeout_http_seconds: 30
```

## Authorization: `enabled_tools`

Every tool falls into one of two risk classes (`team_maker/tools/catalog.py`):

- **SAFE** — never executes a host command, writes only inside the sandbox workspace, opens no
  network connection on its own authority, and never controls the container runtime. Runs whenever an
  agent declares it; no entry in `enabled_tools` needed.
- **RISKY** (`shell`, `code_writer`, `test_runner`, `docker_runner`) — denied unless its name appears in
  `enabled_tools`. A team declaring a RISKY tool is not authorization by itself — only the operator's
  own policy file grants it, and no code path lets an agent, the request schema, or the LLM planner
  add to this list.

## Mount allowlist

`docker_runner`'s mount argument is validated against `mount_allowlist` at every invocation, using this
binding order (never bypassable, and identical in the product's own run path and every standalone
generated package):

1. **Resolve** the requested host path fully — symlinks, `..` segments, normalization.
2. **Allow-check** — the resolved path must be at or under some allowlist entry, or the mount is
   refused.
3. **Deny-check** — the resolved path must not land on the dangerous-location floor (host root, home
   directories, the Docker socket, device paths, system paths), *even if* an allowlist entry matched.
   This floor is extendable but never reducible by any configuration.
4. **Mode** — read-only unless the matched entry explicitly sets `writable: true`.

A refused mount never degrades to running the tool without it.

**No raw host path ever appears** in an error message, a receipt, a transcript, or a report. A rejected
mount is named by its operator-defined `alias`, or — if no allowlist entry matched at all — by a
stable, non-reversible identifier (`mount-<hash>`) an operator can correlate across repeated refusals
without the path itself ever leaving the policy file.

## Sandbox control defaults

Applied to every sandboxed execution when the policy file is silent (`team_maker/tools/limits.py`):

| Control | Default | Notes |
|---|---|---|
| Network egress | `none` | `network_allowed: true` permits the request's own `SandboxConfig.network` |
| Process timeout | 120s | `shell`, `code_writer`, `test_runner` |
| Container timeout | 300s | `docker_runner` |
| HTTP timeout | 30s | `http_client` |
| CPU | `1.0` | |
| Memory | `512m` | |
| Max processes | `128` | |
| Max output | `1048576` bytes (1 MiB) | exceeding this terminates the call, never truncates silently |
| Storage | `1g` | |

No agent-supplied argument can disable, relax, raise, or opt out of any control — every value is a
build-time module constant in the generated package, never read from the process environment at run
time. Exceeding any limit terminates the tool call and is recorded as a **failed** receipt naming the
limit exceeded; a terminated execution is never reported as success.

## Conditionally-available tools

`code_reader`, `web_search`, and `filesystem` additionally depend on the optional `crewai-tools`
package (never a `team_maker` dependency itself — install it, plus any tool-specific credential such
as `OPENAI_API_KEY` or `SERPER_API_KEY`, in the environment that will actually run the package) being
installed in the process that runs the package. A declared-but-unavailable tool in this category is
currently omitted with a warning rather than a hard failure — the pre-run gate's more informative,
actionable treatment of this exact case is planned but not yet implemented.
