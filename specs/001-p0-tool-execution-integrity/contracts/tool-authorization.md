# Contract: Tool authorization policy

**Module**: `team_maker/tools/authorization.py` (new)
**Requirements**: FR-050 to FR-055 | **Amendment**: 1 (2026-08-29) | **Closes**: CHK002, CHK003, CHK006
**Steps**: 2 (policy module, inside the atomic unit) and 3-4 (pre-run evaluation)

## Why this exists separately from the mount allowlist

Constitution II requires a tool be "explicitly authorized" before it executes. The original
requirements defined authorization only for *mounts* — what an already-running tool may see — leaving
the prior question, *may this tool run at all*, unowned. A team could grant itself `docker_runner`
simply by declaring it.

This contract owns the prior question. `MountAllowlist` (see
[execution-policy.md](./execution-policy.md)) continues to own the mount question, within an
execution this contract has already permitted (D-10).

## The rule — three necessary conditions

```text
authorized(tool, team) ⟺ tool is assigned to team                    # intent
                          AND tool in TOOL_CATALOG                    # identity
                          AND ( definition.risk is SAFE
                                OR tool in policy.enabled_tools )     # operator permission
```

All three are necessary. None alone is sufficient. In particular:

- **Declaration is not authorization** (FR-051). A team specification expresses intent; permission is
  an operator decision recorded outside that specification, so a team cannot grant itself anything.
- **RISKY is deny-by-default** (FR-052). `docker_runner`, `shell`, `code_writer` and `test_runner`
  execute only where the operator has explicitly enabled them. Absence of an enablement is a denial,
  never a permission.
- **Unreadable policy denies** (FR-054). Absent, empty, malformed or unparseable policy denies every
  RISKY tool. A policy that cannot be read is not a permissive policy.

## Agent isolation (FR-053)

No agent-supplied input may create, modify, extend, relax or bypass authorization policy. This is a
structural property, not a validation rule: the policy is read from an operator-owned source, and no
code path accepts an agent value that reaches it. There is no "requested authorization" field, no
escalation request, and no per-run override.

## Evaluation point (FR-055)

Authorization is evaluated at **pre-run**, before any agent is constructed, so an unauthorized tool
never reaches a running agent. This sits alongside the existing credential preflight and follows its
established conventions:

- **Collect, don't short-circuit.** Report every unauthorized tool in one failure, as
  `preflight.check_credentials` does for credentials.
- **Name the thing, not the secret.** The diagnostic names the tool, the declaring agent and the
  policy source — never policy contents beyond the decision.

## Ordering against the other gates

```text
canonical (FR-002)  →  resolvable (FR-023, FR-067)  →  AUTHORIZED (FR-050)  →  sandboxed (FR-012)
```

Authorization runs after resolvability so a diagnostic can distinguish "this tool is not available
here" from "this tool is not permitted here" (FR-060). Collapsing them would make an unauthorized
tool indistinguishable from a missing one, which is a diagnosability regression.

## Relationship to the RISKY classification

`ToolDefinition.risk` decides whether a tool needs explicit enablement. The classification criterion
must be documented in the catalog (CHK006 raised that it was asserted per-tool with no stated rule).
A tool is RISKY when it can execute code, write outside the sandbox workspace, reach the network on
its own authority, or control the container runtime.

## Test obligations — permanent security regressions (Constitution V)

| Test | Asserts | File |
|---|---|---|
| Declaration is not permission | A team declaring `docker_runner` with no operator enablement is denied | `tests/security/test_tool_authorization.py` |
| RISKY deny-by-default | Every RISKY catalog tool is denied under an empty policy | `tests/security/test_tool_authorization.py` |
| Unreadable policy denies | Absent, empty and malformed policy each deny every RISKY tool | `tests/security/test_tool_authorization.py` |
| Agent cannot escalate | No agent-supplied input changes an authorization outcome | `tests/security/test_tool_authorization.py` |
| SAFE unaffected | SAFE tools remain usable without explicit enablement | `tests/unit/tools/test_authorization.py` |
| Evaluated pre-run | An unauthorized tool never reaches agent construction | `tests/unit/runtime/` |
| Diagnostic distinguishes | Unauthorized and unresolvable produce different, named reason classes | `tests/unit/runtime/` |
