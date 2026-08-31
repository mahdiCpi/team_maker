# Release Note — P0 Tool Execution Integrity Remediation

## Summary

Declared tools now actually reach the agents that declare them, run under a mandatory sandbox with
operator-controlled authorization, and a run cannot claim success it cannot evidence. Four
audit-identified root causes are closed: tool declarations were silently dropped at runtime (RC-5),
duplicate stub definitions shadowed real tool implementations (RC-4), an unsandboxed execution path
allowed a host escape via a docker mount argument (RC-10), and validation reported packages as passing
that declared invented, unauthorized, or unsafe tools (RC-8).

## Breaking changes

This release contains **two** breaking changes, both deliberate and both required to close the
security gaps above.

### 1. A package declaring an unknown, invalid, unresolvable, unauthorized or unsafe tool now fails

Before this release, an invented tool name (e.g. `text_summarizer`), a legacy alias
(`shell_command`), or a RISKY tool (`shell`, `code_writer`, `test_runner`, `docker_runner`) declared
without operator authorization would build and validate successfully — the declaration was either
silently dropped (so the agent never actually had the tool) or, in the case of stub-shadowed names,
routed to a dead code path.

**Now**: build rejects an unknown or unsafe declaration outright; validation and the pre-run gate both
reject unknown, invalid, unresolvable, unauthorized or unsafe declarations, naming the tool, the
declaring agent, and the package. **RISKY tools are denied by default** — `shell`, `code_writer`,
`test_runner` and `docker_runner` will not run until the operator explicitly authorizes them.

**Migration**: run `team_maker tools migration-report <packages-dir>` for an advisory report of every
affected package (never modifies anything) — see [Operator configuration](#operator-configuration)
below to create an authorization policy. A package whose tools already resolve safely is unaffected.

### 2. Sandbox network egress flips from `bridge` to `none` by default

Every generated package's sandboxed tool execution previously defaulted to `SandboxConfig.network =
"bridge"` (open network access from inside the sandbox). The mandatory sandbox now **denies network
egress by default** — this will break any team whose tools reach the network (e.g. `http_client`,
`web_search`) unless the operator's policy explicitly permits it.

**Migration**: set `network_allowed: true` in the operator's tool policy file (see below). The
per-request `SandboxConfig.network` field still exists (narrowed to `none`/`bridge`; `host` is removed
entirely — it defeats the sandbox) but only takes effect once the operator's policy permits network at
all; a request can narrow the ceiling, never widen it.

## What is unaffected

- A package whose declared tools are all canonical, authorized (or SAFE), and resolvable in the target
  environment builds, validates, and runs exactly as before.
- A team declaring no tools at all is completely unaffected (FR-049).
- The CrewAI version pin and provider-routing/credential conformance guarantees (AD-7) are unchanged —
  verified by running that suite, unmodified, against every change in this release.
- The generated package's public shape (`tools.py`, `run_example.py`, `state_store.py`, etc.) and the
  standalone run path are unchanged in structure, only in policy: mandatory sandboxing, a mount
  allowlist, and resource limits now apply where an unsandboxed path or an unbounded default existed
  before.

## Operator configuration

See `docs/tool-execution-policy.md` for the full operator configuration surface: the single policy
file location, the authorization allowlist, the mount allowlist with aliases, and the sandbox control
defaults table.
