# Contract: Single tool definition and enforced execution policy

**Modules**: `team_maker/tools/policy.py` (new), `team_maker/codegen/templates/tools.py.j2` (modified)
**Requirements**: FR-006 to FR-018, FR-070 to FR-078 | **Root causes**: RC-4 + RC-10 | **Audit**: §2.2(b), §2.2(c)
**Step**: 2 — **ATOMIC, MUST NOT BE SPLIT**

> **Atomicity.** FR-018 binds FR-006 through FR-017, FR-070, FR-071 and FR-073 through FR-078 into
> one delivery unit. Amendment 6 folded the sandbox controls in: network posture, timeouts and
> resource limits are part of the execution policy whose absence is what makes stub removal
> dangerous, so shipping them separately would reproduce the exact split this constraint forbids. Removing stub shadowing
> while leaving execution policy alone converts a currently-unreachable host escape into a reachable
> one. This is the audit's single non-negotiable sequencing constraint (§12). No subset of this
> contract may merge independently.

---

## Part A — one definition per tool (FR-006, FR-007)

### Today

`tools.py.j2` emits every invented name as a stub **after** the real definitions, into the same
module namespace and the same dict literal (`:258-270`, `:290-292`). Python rebinding means the real
implementations are unreachable dead code — worse than the duplicate-key problem originally reported,
because both dict entries already point at the stub.

Reproduced in `generated_teams/devops_team/tools.py`: real `shell_command` at `:67`, stub rebinding it
at `:229`; same for `test_runner` and `docker_runner`.

### Required

1. Exactly one definition per tool name in a generated module (FR-006).
2. No duplicate registry keys, and every key matches the canonical catalog name used in agent
   declarations (FR-007).
3. **No stub emission at all.** A declared capability with no implementation is a build failure, not
   a placeholder (FR-010). Step 1's gate means an unimplemented name cannot reach codegen anyway;
   removing the stub block makes that structural.
4. The module docstring states the policy actually applied (FR-011). Today `:5-6` claims risky tools
   sandbox "when SANDBOX_ENABLED=true" and names `docker_runner`, the one tool that never did.

---

## Part B — one enforced execution path (FR-008, FR-009)

### Today

| Tool | Path | Sandboxed? |
|---|---|---|
| `shell_command` | `_run_sandboxed` | Only if `SANDBOX_ENABLED=true` |
| `code_writer` | `_run_sandboxed` | Only if `SANDBOX_ENABLED=true` |
| `test_runner` | `_run_sandboxed` | Only if `SANDBOX_ENABLED=true` |
| `docker_runner` | **direct `subprocess.run`** (`:130-138`) | **Never** |

`USE_SANDBOX = os.environ.get("SANDBOX_ENABLED", "false")...` (`:45`) — off by default, so the
else-branch runs `subprocess.run(command, shell=True, ...)` on the host (`:66`).

### Required

Every tool whose catalog entry is `RISKY` routes through one enforced path. `docker_runner` included —
it may not implement its own execution policy (FR-008). No bypass, no second path, no tool-local
`subprocess` call.

---

## Part C — mandatory sandbox, fail closed (FR-012, FR-013)

1. **The `SANDBOX_ENABLED` toggle is deleted**, not defaulted to true (D-7). A default can be
   overridden; an absent mechanism cannot. No environment variable, config value or absent setting
   may disable sandboxing.
2. When the sandbox cannot be established — runtime absent, image unavailable, daemon unreachable,
   unhealthy mid-run — execution is **refused**, and the refusal states the sandbox could not be
   established (FR-013).
3. **Host execution never occurs.** There is no else-branch.

---

## Part D — mount allowlist (FR-014 to FR-017)

### Today

`docker_runner_tool(image, command, mounts="")` — all three are LLM-filled arguments. `mounts` is
split on commas and splatted in as `-v host:container`. `mounts="/:/host"` plus an agent-chosen
`command` is full host filesystem access.

### Required — evaluation order is the security property

```text
1. RESOLVE   requested host path fully: symlinks, '..' segments, normalization
2. ALLOW     resolved path at or under an allowlist entry?      no  → REFUSE
3. DENY      resolved path at or under a dangerous location?    yes → REFUSE
                                              (regardless of allowlist — FR-016)
4. MODE      apply read-only unless the matched entry is explicitly writable (FR-015)
5. REFUSAL   never degrades to running the tool without the mount (FR-017)
```

- Agents cannot create, extend or modify the allowlist (FR-014). It is operator-configured.
- An empty or absent allowlist means **no mounts permitted**.
- A tool whose catalog entry has `requires_mounts=False` refuses any supplied mount outright.
- **Deny wins over allow.** An over-broad operator entry cannot re-arm the escape (D-8).
- Resolution precedes both checks specifically so a symlinked allowlist entry cannot launder a
  dangerous path.

### Dangerous-location floor

Extendable, never reducible, never overridable by an allowlist entry:

| Class | Examples |
|---|---|
| Host root | `/`, drive roots |
| Home directories | `/home/*`, `/root`, `/Users/*`, `C:\Users\*` |
| Container control | the Docker socket |
| Devices | `/dev`, `/proc`, `/sys` |
| System paths | `/etc`, `/boot`, `/usr`, `/var/run`, Windows system directories |

---

## Part E — mandatory sandbox controls (FR-073 to FR-078, Amendment 6)

Previously deferred; now inside the atomic unit. Rendered into the package at build time from
operator policy, never read from the process environment at run time (D-15) — an environment-read
control is the `SANDBOX_ENABLED` mistake in a new costume.

| Control | Default when operator policy is silent | Requirement |
|---|---|---|
| Network egress | **Denied** | FR-073 — only operator policy may permit |
| Execution timeout | Restrictive, defined | FR-074 — no path executes without one |
| CPU | Restrictive, defined | FR-075 |
| Memory | Restrictive, defined | FR-075 |
| Process count | Restrictive, defined | FR-075 |
| Output size | Restrictive, defined | FR-075 |
| Storage | Restrictive, defined | FR-075 |

Rules:

1. **Agent-proof** (FR-076). No agent-supplied argument may disable, relax, raise or opt out of any
   control. Values arriving from tool arguments are ignored, not merged.
2. **Limit breach terminates and is recorded** (FR-077). Exceeding any limit terminates execution and
   records a **failed** receipt naming the limit exceeded. A terminated execution is never success.
3. **Silence is restrictive** (FR-078). Every control has a documented default that applies when
   operator policy says nothing. Silence never yields an unbounded execution.
4. Operator adjustment is permitted only within bounds the system enforces.

Note the existing template already carries a network setting and three different hardcoded timeouts
(`120`, `60`, `300`). This part replaces ad-hoc values with one enforced control set.

## Part F — safe error identifiers (FR-070 to FR-072, Amendment 5)

FR-017 requires a refusal to name the rejected mount; FR-029 forbids leaking secrets. A raw host path
in an API or UI error sits between them.

1. API and UI errors identify a rejected mount by **operator-defined alias** or a stable sanitized
   identifier (FR-070). The alias is bound to the allowlist entry, so the operator who authorizes the
   path also names it and no separate mapping can drift (D-14).
2. Raw resolved host paths and secrets appear in **no** receipt and **no** user-facing error, message,
   transcript or report (FR-071).
3. Full path detail may appear only in operator-scoped diagnostics not exposed through the API, the
   UI or a receipt, and remains subject to secret redaction (FR-072).

## Reachability note — why this is not "currently safe"

Across all 31 packages only `devops_team` assigns `docker_runner`, and there it is stub-shadowed. The
dangerous code is unreachable **today**. That is the argument for atomicity, not a mitigation: the
Part A fix, or the Step 3-4 resolver, makes it reachable. Parts A-D land together or not at all.

## Test obligations — permanent security regressions (Constitution V)

These land inside Step 2 and may never be deleted, skipped or weakened.

| Test | Asserts | File |
|---|---|---|
| No stub shadowing | Generated module has one definition per name; registry resolves to the real implementation; no duplicate keys | `tests/security/test_no_stub_shadowing.py` |
| Sandbox fail-closed | Sandbox unavailable → risky tool refused, naming the reason. **Never skipped when no container runtime is present** — a skipped fail-closed test is the weakening the constitution prohibits | `tests/security/test_sandbox_fail_closed.py` |
| No opt-out exists | No environment variable or config disables sandboxing; `SANDBOX_ENABLED` has no effect | `tests/security/test_sandbox_fail_closed.py` |
| Mount allowlist | Non-allowlisted mount refused; refusal does not degrade to running without it | `tests/security/test_mount_allowlist.py` |
| Deny beats allow | Allowlisted path resolving to a dangerous location is refused | `tests/security/test_mount_allowlist.py` |
| Symlink laundering | Allowlisted symlink pointing at a dangerous location is refused after resolution | `tests/security/test_mount_allowlist.py` |
| Read-only default | Allowlisted mount without explicit `writable` is mounted read-only | `tests/security/test_mount_allowlist.py` |
| Docstring accuracy | Generated module docstring matches the policy actually applied | `tests/unit/templates/` |
| Network denied by default | Sandboxed execution has no egress unless operator policy permits | `tests/security/test_sandbox_controls.py` |
| Timeout always enforced | No execution path runs without a timeout; agent values cannot extend it | `tests/security/test_sandbox_controls.py` |
| Resource limits enforced | CPU, memory, process count, output size and storage limits all applied | `tests/security/test_sandbox_controls.py` |
| Controls are agent-proof | Agent-supplied values never relax any control | `tests/security/test_sandbox_controls.py` |
| Breach terminates | Exceeding a limit terminates and records a failed receipt naming the limit | `tests/security/test_sandbox_controls.py` |
| Silence is restrictive | Silent operator policy yields the documented restrictive default | `tests/unit/tools/test_limits.py` |
| No raw path leaks | No API, UI, receipt, transcript or report surface contains a raw resolved host path | `tests/security/test_safe_error_identifiers.py` |
| Alias naming | A rejected mount is named by operator alias or sanitized identifier | `tests/security/test_safe_error_identifiers.py` |
