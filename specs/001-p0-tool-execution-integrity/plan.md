# Implementation Plan: P0 Tool Execution Integrity Remediation

**Branch**: `001-p0-tool-execution-integrity` | **Date**: 2026-08-29 | **Spec**: [spec.md](./spec.md)

**Revision**: v3 — regenerated after spec Amendments 1-7 and the `/speckit-analyze` remediation
(D1 red-first coverage, F1 stage scoping, E1 merge gate, U1 defaults table, U2 checklist triage).
Spec is FR-001 to FR-086 / SC-001 to SC-020. Earlier revision note follows.

**Revision**: v2 — regenerated after spec Amendments 1-6 (authorization policy, stage-deterministic
rejection, required-vs-available capabilities, conditional availability, safe error identifiers,
mandatory sandbox controls). Spec is now FR-001 to FR-078 / SC-001 to SC-018. Existing requirement
IDs were amended in place, not renumbered, so all prior references remain valid.

**Input**: Feature specification from `/specs/001-p0-tool-execution-integrity/spec.md`

**Audit source**: `project-docs/qa/independent-quality-audit-verified.md` v2.1 §2.1-2.4, §9

## Summary

Close the four P0 clusters that let a team declare capabilities, run without them, and report
success. The work is one dependency chain, not a set of parallel fixes: establish a test oracle that
can see the defect, make one canonical tool catalog the gate, remove stub shadowing and enforce
execution policy in a single atomic change, build the resolution boundary that carries tools to the
running agent, require execution receipts before a completion claim, and finally make validation and
preflight report on all of it.

The technical shape is set by three facts read from the source:

1. **`GeneratedTeam` carries no package path**, and `executor.run_team_package` calls
   `engine.run(team, credentials, goal)` — so there is no route from `_build_agent` back to the
   package's `tools.py`. A resolution boundary has to be threaded, not merely called.
2. **The receipt recorder is already built and already subscribed.** `transcript_capture.py`
   subscribes to `ToolUsageStartedEvent`/`ToolUsageFinishedEvent`, but both handlers return early
   unless the event is a delegation (`if target is None: return`). Non-delegation tool usage is
   observed and discarded. This is a consumption change, not a new capture path.
3. **The engine's existing test harness already captures the constructed `Crew`** through
   `_install_fake_kickoff`, and a `Crew` holds its `agents`. The Step 0 oracle is reachable today
   through `captured[0].agents[i].tools`.

Approach: a new `team_maker/tools/` domain package owning catalog, validation, authorization,
execution policy, sandbox controls, safe identifiers and operator config; a new `ToolResolver` port
with a package-backed adapter, mirroring the existing `ExecutionEngine` port pattern; a receipts
record and a required-capability completion rule on the runtime; and additive checks in
`validator.py` and `preflight.py`.

## Technical Context

**Language/Version**: Python 3.10+ (`requires-python = ">=3.10"`), `from __future__ import annotations`
throughout

**Primary Dependencies**: pydantic v2 (schema), click (CLI), jinja2 (codegen templates), pyyaml,
rich. Runtime extra: `crewai>=1.14.6,<1.15` — pin is conformance-gated under AD-7 and **is not
touched by this feature**

**Storage**: Generated packages on disk; `data/teams.db` for team records. No schema change required

**Testing**: pytest. Existing structure `tests/{unit,integration,api,conformance,composer,support}`,
with `tests/unit/{adapters,runtime,cli,composer,templates}`. Shared doubles in `tests/support/`

**Target Platform**: Cross-platform Python (Windows dev host, Linux CI). Sandbox execution requires
a container runtime — its absence is a fail-closed condition, not a fallback (FR-013)

**Project Type**: Single Python package (factory + runtime) with a FastAPI seam under `api/` and a
Next.js frontend under `web/`. **This feature touches neither `api/` nor `web/`**

**Performance Goals**: No new performance target. Tool resolution happens once per run at agent
construction; receipt recording rides the existing event bus. Neither is on a hot path

**Constraints**: No change to credential precedence, provider routing, the CrewAI pin, or unrelated
API/CLI surface (FR-045 to FR-049). Sandboxing is mandatory and fail-closed (FR-012, FR-013, FR-081,
FR-082). No permissive fallback anywhere in the gate — six surfaces state this independently and must
be treated as one set: FR-009, FR-013, FR-017, FR-054, FR-059, FR-078. Two deliberate breaking
changes are approved: strict rejection of non-canonical declarations (FR-037) and the network default
flipping from `bridge` to `none` (FR-073)

**Scale/Scope**: 31 existing generated packages under `generated_teams/`, 15 examined by the audit,
9 carrying tool assignments. 13-14 canonical tool names across three drifted copies to be unified

## Constitution Check

*GATE: evaluated against `.specify/memory/constitution.md` v1.0.0 before Phase 0, re-checked after
Phase 1.*

| Principle | Gate | Pre-Phase 0 | Post-Phase 1 |
|---|---|---|---|
| **I. Compatibility preserved** | AD-1..AD-13, public API/CLI, provider routing, credential precedence, Team Package compatibility unchanged unless an approved spec changes them | **PASS with one declared deviation** — see Complexity Tracking. Spec FR-037 is the approving spec for a narrow, intentional break | **PASS** — deviation unchanged in scope; design confines it to packages with non-canonical declarations (FR-038) |
| **II. Fail-closed security** | Tool executes only when canonical, semantically valid, resolvable, explicitly authorized, sandboxed | **PASS** — all five conditions have owning requirements | **PASS** — mapped to concrete design elements in the table below |
| **III. Execution evidence** | No success report without verifiable evidence | **PASS** — FR-026 to FR-028 | **PASS** — `ToolReceipt` on `RunResult`, completion rule reads it |
| **IV. Reproduction-first** | Every regression fix starts with a failing reproduction; a finding is verified only by re-running its original reproduction | **PASS** — Step 0 (FR-034) precedes all work; FR-036 requires per-step red-first coverage | **PASS** — `quickstart.md` records the red-first commands per step |
| **V. Traceability and gates** | Requirement + audit finding IDs on every change; unit, integration, security-regression and relevant E2E pass; security regressions permanent | **PASS** — every task will cite FR + RC IDs | **PASS** — security-regression tests named in `quickstart.md` as permanent |

### Principle II — five-condition gate mapped to design

| Condition | Requirement | Design element |
|---|---|---|
| Canonical | FR-001 to FR-003, FR-056 to FR-060 | `team_maker/tools/catalog.py` — one `TOOL_CATALOG`; rejection is stage-deterministic (compose / build / pre-run), never discretionary |
| Semantically valid | FR-004, FR-005 | `team_maker/tools/validation.py` — validates `agent.tools` and `suggested_tools` including proposed env var names |
| Resolvable | FR-019, FR-023, FR-065 to FR-069 | `ToolResolver` port; known-but-unavailable is a distinct state — build emits requirements, pre-run validates them |
| Explicitly authorized | **FR-050 to FR-055**, FR-014 to FR-017 | `AuthorizationPolicy` in `team_maker/tools/authorization.py` — three necessary conditions, RISKY denied by default, unreadable policy denies; `MountAllowlist` governs mounts within that |
| Sandboxed | FR-012, FR-013, **FR-073 to FR-078** | Single enforced path in `tools.py.j2`; no `SANDBOX_ENABLED` opt-out; network denied by default; mandatory timeout and CPU/memory/process/output/storage limits; agent-proof |

**Gate result: PASS.** One declared deviation, recorded below with its approving requirement.

## Project Structure

### Documentation (this feature)

```text
specs/001-p0-tool-execution-integrity/
├── plan.md              # This file
├── research.md          # Phase 0 output — decisions and rejected alternatives
├── data-model.md        # Phase 1 output — entities and validation rules
├── quickstart.md        # Phase 1 output — red-first validation per step
├── contracts/           # Phase 1 output — port and artifact contracts
│   ├── tool-catalog.md
│   ├── tool-authorization.md      # NEW (Amendment 1)
│   ├── tool-resolver-port.md
│   ├── execution-policy.md
│   ├── receipts-and-completion.md
│   └── migration-report.md
├── checklists/
│   ├── requirements.md  # Spec quality checklist (16/16)
│   └── tool-integrity.md  # Requirements-quality review, 52 items — drove Amendments 1-6
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
team_maker/
├── tools/                          # NEW — the canonical tool domain (Step 1, Step 2)
│   ├── __init__.py
│   ├── catalog.py                  # TOOL_CATALOG: the single source of tool identity (FR-001)
│   ├── validation.py               # declaration validation, incl. suggested_tools (FR-002..FR-005)
│   ├── policy.py                   # ExecutionPolicy, MountAllowlist, dangerous-path floor (FR-012..FR-017)
│   ├── authorization.py            # NEW — AuthorizationPolicy: 3 conditions, RISKY deny-by-default (FR-050..FR-055)
│   ├── limits.py                   # NEW — SandboxControls: network, timeout, CPU/mem/proc/output/storage (FR-073..FR-078)
│   ├── identifiers.py              # NEW — safe mount aliases for user-facing surfaces (FR-070..FR-072)
│   └── migration.py                # advisory, read-only legacy scan (FR-039..FR-042)
├── ports/
│   ├── execution_engine.py         # unchanged
│   └── tool_resolver.py            # NEW — name → instance boundary (FR-019)
├── adapters/
│   ├── tools/                      # NEW
│   │   ├── __init__.py
│   │   └── package_tool_resolver.py  # controlled load of a package's tools.py (FR-024)
│   └── runtime_crewai/
│       ├── crewai_execution_engine.py  # MODIFIED — _build_agent gains tools= (FR-020)
│       └── transcript_capture.py       # MODIFIED — stop discarding non-delegation tool events (FR-026)
├── runtime/
│   ├── executor.py                 # MODIFIED — thread package_path / resolver to the engine (FR-021)
│   ├── results.py                  # MODIFIED — RunResult gains tool receipts (FR-028)
│   ├── completion.py               # NEW — completion rule over *required* capabilities (FR-027, FR-061..FR-064)
│   └── preflight.py                # MODIFIED — tool availability, tool credentials, mounts (FR-031, FR-032)
├── validation/
│   └── validator.py                # MODIFIED — declared capability exists (FR-030)
├── llm/prompts.py                  # MODIFIED — AVAILABLE_TOOLS derives from catalog (FR-001)
├── schema/request.py               # MODIFIED — _REGISTRY_TOOLS deleted, validates agent.tools (FR-002)
├── templates/education/template.py # MODIFIED — starter tool names corrected (FR-043, FR-044)
└── codegen/templates/tools.py.j2   # MODIFIED — no stub shadowing, one policy path (FR-006..FR-011)

tests/
├── unit/
│   ├── tools/                      # NEW — catalog, validation, policy, authorization, limits, migration
│   ├── adapters/                   # engine tools= oracle (Step 0), resolver adapter
│   └── runtime/                    # completion rule, receipts, preflight
├── security/                       # NEW — permanent security-regression suite (Constitution V)
│   ├── test_no_stub_shadowing.py
│   ├── test_sandbox_fail_closed.py
│   ├── test_mount_allowlist.py
│   ├── test_tool_authorization.py  # NEW — FR-050..FR-055
│   ├── test_sandbox_controls.py    # NEW — FR-073..FR-078
│   ├── test_safe_error_identifiers.py  # NEW — FR-070..FR-072
│   └── test_safe_tool_boundary.py  # NEW — FR-083
├── integration/                    # end-to-end: declared tool reaches agent and produces a receipt
└── support/
    └── team_factories.py           # MODIFIED — tools no longer defaults to [] everywhere (FR-035)
```

**Structure Decision**: Single Python package, extending the existing hexagonal layering the repo
already uses — `ports/` for the boundary interface, `adapters/` for its implementation, `domain`-ish
pure modules under `team_maker/tools/`. This mirrors `ports/execution_engine.py` +
`adapters/runtime_crewai/`, which is the established pattern for exactly this kind of seam (AD-6).
No new top-level project, no new service. `tests/security/` is introduced because Constitution V
makes security-regression tests permanent and they need a stable, obvious home; the CLAUDE.md test
organization rules justify the directory once three related files exist, which they do.

## Delivery Sequence (audit §9 — binding)

Order is a dependency chain and MUST NOT be reordered or parallelized.

| Step | Story | Delivers | Root cause | Gate to proceed |
|---|---|---|---|---|
| **0** | US1 | Engine oracle: agent declaring a non-empty tool list asserts a matching tool | RC-12 | Test committed and demonstrated **failing** |
| **1** | US2 | Canonical catalog, stage-deterministic validation, starter-team correction, migration report | RC-3 | One catalog; invented names rejected at compose/build/pre-run; starter team passes |
| **2** | US3 | **ATOMIC — FR-006 to FR-018, FR-070, FR-071, FR-073 to FR-078.** Stub shadowing removed, execution policy enforced, sandbox controls mandatory, safe error identifiers | RC-4 + RC-10 | Ships as one unit. No subset merges |
| **3-4** | US4 | `ToolResolver` port, package adapter, package path threaded, `_build_agent` attaches, authorization evaluated at pre-run | RC-5 | Step 0 test now passes; unauthorized tools never reach an agent |
| **5** | US5 | Receipts on `RunResult`, completion rule over *required* capabilities | RC-11 | No success without a receipt for every required capability; claims need a successful one |
| **6** | US6 | Validation and preflight detect semantic failures, including dependency/credential/authorization checks | RC-8 | Green means green |

**Atomicity enforcement for Step 2**: FR-018 now requires FR-006 to FR-017, FR-070, FR-071 and
FR-073 to FR-078 to land together — Amendment 6 folded the sandbox controls into the unit, because
network egress, timeouts and resource limits are part of the execution policy whose absence is what
makes stub removal dangerous. Splitting
stub removal from policy enforcement converts a currently-unreachable host escape into a reachable
one — the audit's single non-negotiable constraint (§12). `/speckit-tasks` MUST emit Step 2 as one
delivery unit with no independently mergeable subtasks, and the security-regression tests for
shadowing, sandbox fail-closed and mount allowlist land inside it.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| **Constitution I** — intentional compatibility break: existing packages declaring unknown, invalid, unresolvable, unauthorized or unsafe tools now fail validation and fail at run (FR-037) | Required outcome 2 mandates rejection before execution. Those declarations never worked — the runs were already fabricating results. Approved by spec FR-037 (Q1, decided 2026-08-29) | Accepting legacy packages under a permissive mode keeps the fabrication path live for existing teams, which leaves P0-1 open. Scope is confined by FR-038 (safely-resolving packages unaffected) and mitigated by the advisory migration report (FR-039 to FR-042), which rewrites nothing |
| **New `tools/` package + new port + new adapter** for what is described as "a wiring job" | `GeneratedTeam` has no package path and `_build_agent` has no route to the package's `tools.py`. The audit itself concludes "the fix is a runtime tool-resolution boundary" and scopes Steps 3-5 as design work | Passing a raw path into `_build_agent` and importing `tools.py` inline would put arbitrary module loading inside the engine with no policy seam — the exact shape of RC-10. A port keeps loading behind one controlled, testable boundary (FR-024) |
| **New `tests/security/` directory** | Constitution V makes security-regression tests permanent and undeletable; they need a stable home separable from feature tests | Scattering them through `tests/unit/` makes "was this security test weakened?" unanswerable at review time |

## Phase Outputs

- **Phase 0** → [research.md](./research.md): 8 decisions with rejected alternatives, plus two
  corrections to the audit's implementation detail (harness location, `shell` key mismatch).
- **Phase 1** → [data-model.md](./data-model.md), [contracts/](./contracts/),
  [quickstart.md](./quickstart.md).

## Post-Design Constitution Re-Check

Re-evaluated after Phase 1 artifacts were regenerated against the amended spec. **PASS.**

- No new deviation appeared during design or during Amendments 1-6. The Complexity Tracking table is
  unchanged from the pre-Phase 0 evaluation.
- **Principle II strengthened.** Amendment 1 gave the "explicitly authorized" condition an owner it
  previously lacked (FR-050 to FR-055); before the amendment the condition was only satisfied for
  mounts, which was a latent gate hole rather than a design choice.
- **Principle III strengthened, not weakened, by Amendment 3.** Narrowing the completion rule to
  *required* capabilities removes false failures on unused optional tools while adding FR-064, which
  requires a **successful** receipt to support a claim. The prior wording was satisfiable by any
  receipt, including a failed one.
- **Amendment 6 respects FR-018.** Sandbox controls landed inside the atomic unit rather than beside
  it, so the unit still cannot be partially merged.
- **Principle IV now holds per step.** The `/speckit-analyze` D1 finding showed FR-036 was satisfied
  at only two points; tasks.md v3 adds a red task for Steps 1, 2, 5 and 6, and documents that Step
  3-4's red is the Step 0 oracle. All six steps now have a demonstrated red-to-green pair.
- **Principle V strengthened.** FR-018 is now enforced by an objective merge gate (T096) rather than
  by prose, and the four previously untraced tasks now carry citations.
- Principle II's five conditions each have a named owner in `contracts/` and a permanent
  security-regression test in `quickstart.md`.
- Principle IV is satisfied structurally: `quickstart.md` gives the red-first command for every
  step, and Step 0 cannot be skipped without the sequence failing its own gate.
- The CrewAI pin, credential precedence and provider routing are untouched by every artifact
  produced — verified against `contracts/tool-resolver-port.md`, which resolves tool credentials on
  a path deliberately separate from `preflight.check_credentials`.
