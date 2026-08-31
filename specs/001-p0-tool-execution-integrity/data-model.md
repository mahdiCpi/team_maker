# Phase 1 Data Model: P0 Tool Execution Integrity Remediation

**Date**: 2026-08-29 | **Plan**: [plan.md](./plan.md)

Entities are described by responsibility, fields and rules. Field types use Python notation because
the repo's existing domain layer is plain dataclasses (`domain/models.py`) and pydantic v2 only at
the request-schema boundary (`schema/request.py`); these entities follow the same split.

---

## 1. `ToolDefinition` — `team_maker/tools/catalog.py`

The canonical identity of one tool. Plain frozen dataclass; constant data, no I/O.

| Field | Type | Rule |
|---|---|---|
| `name` | `str` | The canonical name. Unique across the catalog. Serves as registry key **and** as the `@tool(...)` decorator argument in generated code (D-2) |
| `description` | `str` | The agent-facing contract. Authored by maintainers, never by a model (FR-005) |
| `risk` | `RiskClass` | `SAFE` or `RISKY`. `RISKY` forces the enforced execution path (FR-008) |
| `required_credentials` | `tuple[str, ...]` | Credential variable names this tool needs. Empty tuple for none. Checked by preflight (FR-031) |
| `requires_mounts` | `bool` | Whether the tool accepts mount arguments at all. `False` means any supplied mount is refused outright |
| `aliases` | `tuple[str, ...]` | Legacy names recognized **only** by the migration report for suggesting a replacement (FR-041). Never accepted as a valid declaration |

**Catalog rules**

- `TOOL_CATALOG: dict[str, ToolDefinition]` is the single source of tool identity (FR-001).
- Exactly one entry per canonical name; no entry's `name` may appear in another's `aliases`.
- `prompts.AVAILABLE_TOOLS`, `schema/request.py`'s membership test, and the `tools.py.j2` registry are
  all derived views. None may hold its own literal list.

---

## 2. `ToolDeclaration` — validation-time view

A tool named by an agent or role in a team specification. Not persisted as its own record; it is the
unit validation, resolution, receipts and the completion rule all key on.

| Field | Type | Rule |
|---|---|---|
| `name` | `str` | As written in the specification or `agents/*.yaml` |
| `agent_role` | `str` | The declaring agent |
| `source_surface` | `str` | Where the declaration came from — planner output, `suggested_tools`, template, or a loaded package. Reported on rejection (FR-003) |

**Validation rules** (`team_maker/tools/validation.py`)

1. `name` MUST be a key in `TOOL_CATALOG`, else **reject**, naming the offending name and
   `source_surface` (FR-002, FR-003).
2. A name matching only an `alias` is **rejected**, not silently resolved (D-2).
3. Model-authored `suggested_tools` entries are validated identically, including any proposed
   credential variable names, which MUST match `required_credentials` of a catalog entry (FR-004).
4. A model-authored `description` is **discarded**; the catalog description is authoritative (FR-005).
5. Validation applies to per-agent `tools` — the surface today's `_REGISTRY_TOOLS` filter never sees.

**State transitions**

```text
declared ──validate──▶ canonical ──resolve──▶ available ──authorize──▶ permitted ──sandbox──▶ executable
    │                      │                       │                        │                     │
    │                      │                       │                        │                     └── receipt (FR-026)
    │                      │                       │                        └── refuse: policy denies (FR-052/FR-054),
    │                      │                       │                            mount refused (FR-017), sandbox
    │                      │                       │                            unavailable (FR-013), limits
    │                      │                       │                            unenforceable (FR-073..FR-078)
    │                      │                       └── refuse: prerequisite missing (FR-068)
    │                      └── reject: no implementation in catalog (FR-010)
    └── reject: unknown — compose (FR-056) / build (FR-057) / pre-run (FR-058)
```

Every arrow fails closed. There is no path that skips a stage (Constitution II), and no arrow
substitutes, stubs, skips or falls back (FR-059).

**Three availability states** (FR-065, D-13) — do not collapse them:

| State | Meaning | Failure stage |
|---|---|---|
| Unknown | Not in the catalog | Compose / build / pre-run per FR-056 to FR-058 |
| Known, no implementation | Catalog entry exists but nothing implements it | Build (FR-010) |
| Known but unavailable | Canonical; optional dependency or credential absent *here* | Pre-run (FR-067, FR-068) |

---

## 3. `ResolvedTool` — `team_maker/ports/tool_resolver.py`

The usable runtime form of a declaration. Exists only when every prior stage passed.

| Field | Type | Rule |
|---|---|---|
| `name` | `str` | Canonical name it resolved from |
| `instance` | `object` | The framework tool object handed to the agent. Opaque to the port |
| `definition` | `ToolDefinition` | The catalog entry it resolved against |

**Rules**

- Constructing a `ResolvedTool` for a non-canonical name is impossible by contract.
- A declaration that cannot produce one MUST refuse the run before it starts (FR-023). There is no
  partially-resolved run.
- Holds no credential value. Credentials are applied at resolution and never stored on the object
  (FR-022, FR-029).

---

## 4. `ExecutionPolicy` and `MountAllowlist` — `team_maker/tools/policy.py`

| `ExecutionPolicy` field | Type | Rule |
|---|---|---|
| `sandbox_required` | `bool` | Always `True` for `RISKY`. Not configurable — there is no field that can disable it (FR-012) |
| `mount_allowlist` | `MountAllowlist` | Empty by default, meaning no mounts permitted (FR-014) |

| `MountAllowlistEntry` field | Type | Rule |
|---|---|---|
| `host_path` | `str` | Operator-configured source path |
| `writable` | `bool` | Defaults `False`. Read-only unless the operator explicitly sets it (FR-015) |

**Mount evaluation order** — binding, and the order is the security property (D-8):

1. Resolve the requested host path fully: symlinks, `..` segments, normalization.
2. **Allow-check**: the resolved path must be at or under an allowlist entry. No match → refuse.
3. **Deny-check**: the resolved path must not be at or under a dangerous location. Match → refuse,
   **regardless of allowlist contents** (FR-016).
4. Apply read-only unless the matched entry sets `writable`.
5. Refusal never degrades to running without the mount (FR-017).

**Dangerous-location floor** — may be extended, never reduced, never overridden:

| Class | Examples |
|---|---|
| Host root | `/`, drive roots |
| Home directories | `/home/*`, `/root`, `/Users/*`, `C:\Users\*` |
| Container control | the Docker socket |
| Devices | `/dev`, `/proc`, `/sys` |
| System paths | `/etc`, `/boot`, `/usr`, `/var/run`, Windows system directories |

---

## 5. `ToolReceipt` — `team_maker/runtime/results.py`

The record that a tool ran. The sole admissible evidence for the completion rule.

| Field | Type | Rule |
|---|---|---|
| `sequence` | `int` | Monotonic, sparse — matches the `TranscriptEntry` convention already in `results.py` |
| `tool_name` | `str` | Canonical name |
| `agent_role` | `str` | Invoking agent |
| `task_name` | `str` | Declaring task — the key the completion rule joins on |
| `arguments` | `dict[str, str]` | Sanitized. Passes the existing api-key redaction guard (FR-029) |
| `succeeded` | `bool` | Outcome. A recorded failure is evidence of execution, **not** evidence of success (FR-027) |
| `timestamp` | `str` | ISO-8601 |
| `output_ref` | `str` | Reference to the output, not the output itself |

**Rules**

- Holds primitives only. No credential, no engine object — the constraint `TranscriptEntry` already
  documents under AD-9/NFR3.
- One receipt per execution. Repeated invocations produce repeated receipts.
- A receipt for a task that did not declare the tool is still recorded; the completion rule keys on
  the declaring task and ignores it.

---

## 6. `RunResult` additions — `team_maker/runtime/results.py`

Additive only, both defaulted, following the convention the docstring already establishes for
`transcript` (Story 1.7) and `error` (Story 4.4).

| New field | Type | Rule |
|---|---|---|
| `tool_receipts` | `list[ToolReceipt]` | Every receipt recorded during the run (FR-028) |
| `unevidenced_capabilities` | `list[str]` | Declared capabilities with no receipt at completion. Non-empty means the run MUST NOT be reported as successfully complete (FR-027) |

`error` keeps its existing meaning — a run that failed partway. An unevidenced completion is a
distinct outcome and callers must be able to tell them apart (D-6).

---

## 7. Completion rule — `team_maker/runtime/completion.py`

Pure function over a `RunResult` and the team's declarations. No I/O, unit-testable without a run.

```text
for each capability the task marks REQUIRED:            # not the available set — FR-061
    if no receipt exists for (task_name, required_capability):
        add required_capability to unevidenced_capabilities

task successfully complete ⟺ it requires no external capability
                              OR every REQUIRED capability has a receipt     # FR-062
run successfully complete  ⟺ error is None
                              AND unevidenced_capabilities is empty

claimed external action supported ⟺ a SUCCESSFUL receipt corresponds to it   # FR-064
```

- Optional tools that were available but unused never block completion and never produce an
  unevidenced-capability finding (FR-063).
- A recorded failure satisfies "a receipt exists" but does **not** support a claim that the action
  was performed (FR-064).
- Tasks requiring no external capability are unaffected (FR-049).
- A legacy task carrying no requiredness marking treats every declared capability as optional, rather
  than inferring requiredness (spec Assumptions).

---

## 8. `MigrationFinding` — `team_maker/tools/migration.py`

| Field | Type | Rule |
|---|---|---|
| `package` | `str` | Affected package |
| `agent_role` | `str` | Declaring agent |
| `declared_name` | `str` | The non-canonical name |
| `suggested_replacement` | `str \| None` | Set **only** when exactly one catalog entry lists `declared_name` as an alias (FR-041) |
| `requires_human_decision` | `bool` | `True` when zero or more than one candidate exists |

**Rules**

- Only affected packages produce findings. A package whose declarations are all canonical yields none
  and MUST NOT appear in the report (FR-039).
- The report opens no file for writing (FR-040) and is reproducible with no side effects (FR-042).

---

## 9. `AuthorizationPolicy` — `team_maker/tools/authorization.py`

Operator-owned. Answers "may this tool run at all", kept distinct from the mount allowlist question
of "what may it see" (D-10).

| Field | Type | Rule |
|---|---|---|
| `enabled_tools` | `frozenset[str]` | Canonical names the operator has explicitly enabled |
| `source` | `str` | Where the policy was read from, for operator diagnostics |

**Authorization rule — all three conditions necessary (FR-050)**

```text
authorized(tool, team) ⟺ tool is assigned to team
                          AND tool in TOOL_CATALOG
                          AND ( definition.risk is SAFE
                                OR tool in policy.enabled_tools )
```

- A team declaring a tool is **not** authorization (FR-051).
- RISKY tools are denied unless explicitly enabled; absence of enablement is denial (FR-052).
- Agents cannot create, modify, extend or bypass the policy (FR-053).
- Absent, empty, malformed or unreadable policy denies every RISKY tool (FR-054).
- Evaluated at pre-run, before any agent is constructed (FR-055).

## 10. `SandboxControls` — `team_maker/tools/limits.py`

Mandatory and non-negotiable. Rendered into the package at build time from operator policy, never
read from the process environment at run time (D-15). This table is the **single authoritative
source** required by FR-086; no call site may restate a value.

### Existing behaviour this table must not silently change

Read from source before setting any default:

| Site | Current value | Applies to |
|---|---|---|
| `tools.py.j2:64` | `timeout=120` | sandboxed `shell`, `code_writer`, `test_runner` |
| `tools.py.j2:66` | `timeout=60` | host fallback — **being deleted by FR-012** |
| `tools.py.j2:137` | `timeout=300` | `docker_runner` |
| `tools.py.j2:114` | `timeout=30` | `http_client` HTTP request |
| `tools.py.j2:218,225` | `timeout=15` | `ci_tool` HTTP requests |
| `SandboxConfig.network` (`schema/request.py:128`) | `"bridge"` | **network is currently permitted by default** |

Two consequences worth stating plainly:

1. There are **five** distinct timeout values today, not the three recorded in task T006. Any single
   mandatory timeout would change behaviour for four of the five.
2. `network` defaults to `"bridge"` today. FR-073 flips this to denied — a **deliberate,
   approved behaviour change** (Amendment 6), not an oversight. It will break any existing team whose
   tools reach the network from inside the sandbox.

### Authoritative defaults

| Control | Default | Basis | Requirement |
|---|---|---|---|
| `network` | `none` | **Behaviour change, approved.** Today `bridge`. Operator policy may set `bridge`; `host` is removed as an option — it defeats the sandbox | FR-073 |
| `timeout_process` | `120s` | **Preserves** the existing sandboxed-execution timeout | FR-074 |
| `timeout_container` | `300s` | **Preserves** the existing `docker_runner` timeout | FR-074 |
| `timeout_http` | `30s` | **Preserves** the existing `http_client` timeout | FR-074 |
| `max_output_bytes` | `1_048_576` (1 MiB) | New. Sized above the largest observed tool output in the saved transcripts | FR-075 |
| `cpu` | `1.0` core | **Confirmed 2026-08-29.** New; matches typical CI runner allocation | FR-075 |
| `memory` | `512 MiB` | **Confirmed 2026-08-29.** New; above the `python:3.12-slim` baseline plus headroom | FR-075 |
| `max_processes` | `128` | **Confirmed 2026-08-29.** New; well above any observed tool, blocks fork bombs | FR-075 |
| `storage` | `1 GiB` writable layer | **Confirmed 2026-08-29.** New; above the largest observed workspace | FR-075 |

**Timeouts are per class, not one global value.** Collapsing them to a single number would cut
`docker_runner` from 300s to 120s and `http_client` from 30s to 120s — both material changes to
working behaviour, which the amendment brief prohibits.

**The four new rows had no existing counterpart** — nothing in the codebase sets a CPU, memory,
process or storage limit today. Values confirmed 2026-08-29; the table is now authoritative and
FR-086 binds the implementation to read from it rather than restate values at call sites.

**Watch item for Phase 4.** `test_runner` is the tool most likely to meet the memory and
process ceilings — `pytest` on a large suite, especially under `pytest -n`. If T087 shows a
legitimate suite hitting either limit, raise that control rather than weakening enforcement:
FR-076 permits operator adjustment within enforced bounds, and FR-077 makes a breach a recorded
failure rather than a silent truncation, so the symptom will be visible rather than mysterious.

- Agents cannot disable, relax, raise or opt out of any control (FR-076).
- Exceeding any limit terminates execution and records a **failed** receipt naming the limit
  exceeded; a terminated execution is never reported as success (FR-077).
- Silence in operator policy yields the restrictive default, never an unbounded execution (FR-078).
- The controls apply identically to the product run path and the standalone generated package;
  neither may execute a RISKY tool under weaker controls (FR-081).
- A control that cannot be enforced is a sandbox-establishment failure and refuses execution,
  rather than executing without it (FR-082).

## 11. `SafeMountIdentifier` — `team_maker/tools/identifiers.py`

| Field | Type | Rule |
|---|---|---|
| `alias` | `str` | Operator-defined name bound to the allowlist entry (D-14) |
| `sanitized_id` | `str` | Stable derived identifier used when no alias exists |

- API, UI, receipts and every user-facing error name a mount by `alias` or `sanitized_id` (FR-070).
- Raw resolved host paths and secrets never appear in receipts or user-facing surfaces (FR-071).
- Full path detail may appear only in operator-scoped diagnostics, still subject to secret
  redaction (FR-072).

## Entity relationships

```text
ToolDefinition (catalog) ◀──validates── ToolDeclaration (agent YAML / spec)
       │                                        │
       │                                        ├──unresolved──▶ run refused (FR-023)
       │                                        └──non-canonical──▶ MigrationFinding (FR-039)
       ▼
   ResolvedTool ──authorized by──▶ AuthorizationPolicy ──attached to──▶ Agent
                                          │                                 │
                                   denies RISKY                             │ executes under
                                   by default                               ▼
                                                 ExecutionPolicy + MountAllowlist + SandboxControls
                                                                            │
                                             refusals named by SafeMountIdentifier
                                                                            ▼
                                                                      ToolReceipt
                                                                    │
                                                                    ▼
                                                    completion rule ──▶ RunResult
```
