# Feature Specification: P0 Tool Execution Integrity Remediation

**Feature Branch**: `fix/01_tool_catalog_and_runtime_wiring`

**Created**: 2026-08-29

**Status**: In implementation — Q1-Q3 resolved, Amendments 1-8 applied 2026-08-29.
Requirements are FR-001 to FR-087 and SC-001 to SC-020.

**Input**: User description: "Remediate only the release-blocking P0 failures documented in
`project-docs/qa/independent-quality-audit-verified.md`. Required outcomes: (1) teams containing
declared tools can execute those tools through the real product runtime; (2) unknown, unresolvable,
unauthorized or unsafe tools are rejected before execution; (3) stub tools cannot shadow real tools
or create a host-execution escape; (4) runtime tool instances are attached through an explicit
controlled boundary; (5) a run cannot report successful completion without verified execution
receipts; (6) validation and preflight detect semantic configuration failures; (7) regression
coverage begins with the non-empty-tools engine test identified as RC-12 / remediation Step 0.
Preserve the dependency sequence in audit §9. Stub-shadowing removal and sandbox enforcement must
remain one atomic delivery unit. Preserve credential precedence, provider routing, existing package
compatibility, and unrelated API/CLI behavior. Exclude P1, P2, P3, QA-file cleanup, and future
product-design decisions. Do not implement anything yet."

**Source of truth**: `project-docs/qa/independent-quality-audit-verified.md` v2.1
(commit under test `b946030`). Audit clusters in scope: P0-1 (§2.1), P0-2 (§2.2), P0-3 (§2.3),
P0-4 (§2.4). Root causes in scope: RC-3, RC-4, RC-5, RC-8, RC-10, RC-11, RC-12.

---

## Problem Statement

A team that declares capabilities runs without them and then reports that it succeeded. The
product's own run path discards every declared tool, no layer checks whether a declared capability
exists, and nothing requires evidence that a capability ran before a task is marked complete. The
user-visible result is a confident `Validation: ✅ PASSED` and `Run complete.` on a run that
fabricated its output. Nine of the fifteen examined generated packages carry tool assignments,
including the shipped starter team, so this is the default experience for research, coding, DevOps
and data teams rather than a corner case.

A second, currently-dormant hazard sits underneath: the real risky-tool implementations are
unreachable dead code today only because generated stubs shadow them. Restoring reachability
without settling execution policy in the same delivery would arm a host-filesystem escape that is
presently unreachable.

---

## User Scenarios & Testing *(mandatory)*

<!--
  Ordering note: these stories are sequenced by the dependency order in audit §9, not by
  independent business value. US1 is a prerequisite oracle; US2-US5 form a dependency chain;
  US3 is a single atomic unit that MUST NOT be split. Each story states what can be verified
  on its own and what it depends on.
-->

### User Story 1 - The test suite can see the defect (Priority: P1, Step 0)

A maintainer needs the regression suite to be capable of observing a tool-dropping runtime before
any remediation lands. Today the shared agent fixture declares an empty tool list, so a runtime
that honours declared tools and a runtime that silently discards them are behaviourally identical
under test (RC-12). Every subsequent step in this remediation would otherwise be built and
verified against a suite that provably cannot detect the class of defect it exists to prevent.

**Why this priority**: Audit §9 designates this Step 0, before all other work. It is the cheapest
regression guard for the entire sequence and the documented reason three P0 clusters shipped.

**Independent Test**: Fully testable on its own with no product change. Construct a team whose
agent declares a non-empty tool list, run it through the existing agent-construction interception
harness, and assert the constructed agent carries a matching tool. The test MUST fail against
current behaviour before any remediation lands.

**Acceptance Scenarios**:

1. **Given** the unremediated runtime, **When** the new regression test runs an agent that declares
   a non-empty tool list, **Then** the test fails, demonstrating the defect is now observable.
2. **Given** the same test after US4 lands, **When** it runs, **Then** it passes.
3. **Given** the shared test fixtures, **When** a maintainer inspects the runtime fixture defaults,
   **Then** at least one fixture path exercises a non-empty declared tool list.

---

### User Story 2 - Declared tools are checked against one canonical catalog (Priority: P1, Step 1)

A team author (human or the authoring model) declares tools for a role. Every declared tool name is
checked against a single canonical catalog at the point the declaration is recorded. Names that are
not in the catalog are rejected at a stage-deterministic point — visibly at compose, at build, and
at pre-run — rather than silently accepted, written into artifacts, and discovered as a fabricated
result at run time.

**Why this priority**: Audit §9 Step 1, and the gate every later step depends on. Three drifted
catalog copies exist today and none of them is a gate (RC-3); the authoring model is additionally
handed a free-form suggestion field the human-authored rules never describe, which is how invented
tool names and invented credential variable names enter shipped artifacts.

**Independent Test**: Testable without runtime changes. Submit a team declaration containing a
known-invented tool name and confirm it is rejected with a message naming the offending tool; submit
one containing only catalog names and confirm it is accepted.

**Acceptance Scenarios**:

1. **Given** a team declaration containing a tool name absent from the canonical catalog,
   **When** the declaration is validated, **Then** it is rejected with a message identifying the
   unknown name and the surface it came from.
2. **Given** a team declaration whose tool names are all canonical, **When** it is validated,
   **Then** it is accepted unchanged.
3. **Given** the previously drifted catalog copies, **When** a maintainer inspects the system,
   **Then** exactly one canonical catalog governs tool identity and the other surfaces derive from
   it rather than restating it.
4. **Given** a free-form tool suggestion supplied by the authoring model, **When** it is processed,
   **Then** neither its name nor any credential variable name it proposes is adopted without
   passing the same canonical check.
5. **Given** the shipped starter team, **When** it is built and validated after this gate exists,
   **Then** it passes, because its declared tool names have been corrected to canonical names.
6. **Given** an existing package declaring non-canonical tool names, **When** the migration report
   is run, **Then** it lists the package, the offending names and their locations, suggests a
   canonical replacement only where the mapping is unambiguous, and leaves the package untouched.

---

### User Story 3 - Stub shadowing is removed and execution policy is enforced, as one atomic change (Priority: P1, Step 2)

A generated team package contains exactly one definition per tool, and every risky tool executes
under a single enforced execution policy. Removing the stubs that currently shadow real
implementations and enforcing sandbox policy are delivered together, in one unit, because delivering
the first without the second converts a currently-unreachable host escape into a reachable one.

**Why this priority**: Audit §9 Step 2 and the audit's single non-negotiable sequencing constraint
(§12). Today generated stubs rebind the real tool functions at module level, so the real
implementations are unreachable dead code and both registry entries point at the stub (RC-4);
meanwhile the sandbox defaults to off, one risky tool bypasses the sandbox helper entirely, and an
agent-supplied mount argument is a host-filesystem escape primitive (RC-10).

**Independent Test**: Testable as a unit by generating a package for a team declaring risky tools
and asserting: exactly one definition per tool name, no duplicate registry keys, the registry
resolves to the real implementation, every risky tool routes through the single execution-policy
path, and an attempt to execute outside that path is refused.

**Acceptance Scenarios**:

1. **Given** a generated package for a team declaring a tool that has a real implementation,
   **When** the package's tool registry is resolved for that name, **Then** it resolves to the real
   implementation and no stub definition of that name exists in the module.
2. **Given** a generated package, **When** its tool registry is inspected, **Then** it contains no
   duplicate keys and every registry key matches the canonical catalog name used in agent
   declarations.
3. **Given** any risky tool, **When** it is invoked, **Then** execution routes through the single
   enforced execution-policy path, sandboxed, with no bypass and no opt-out.
4. **Given** the sandbox mechanism is unavailable or cannot be established, **When** a risky tool is
   invoked, **Then** execution is refused and the refusal states the sandbox could not be
   established. Execution never falls back to the host.
5. **Given** an agent supplies a mount that is not in the operator's allowlist, **When** the tool is
   invoked, **Then** the execution is refused, naming the rejected mount. The tool does not run
   without the mount instead.
6. **Given** an allowlisted mount with no explicit writable marking, **When** it is applied,
   **Then** it is mounted read-only.
7. **Given** a mount that resolves to the host root, a home directory, the Docker socket, a device
   path or a system path, **When** it is requested, **Then** it is refused regardless of allowlist
   contents, and the refusal holds when the path is reached via a symlink or relative segments.
8. **Given** a tool declaration for which no real implementation exists, **When** the package is
   generated, **Then** the absent capability is reported as a failure rather than represented by a
   placeholder whose description asserts a capability it does not have.
9. **Given** a RISKY tool with no explicit operator enablement, **When** execution is attempted,
   **Then** it is denied, because absence of enablement is a denial rather than a permission.
10. **Given** any sandboxed execution, **When** it starts, **Then** network egress is denied unless
   operator policy permits it, and an execution timeout plus CPU, memory, process-count,
   output-size and storage limits are all enforced.
11. **Given** agent-supplied input attempting to extend a timeout, widen network access or raise a
   resource limit, **When** it is processed, **Then** it has no effect on the enforced controls.
12. **Given** an execution that exceeds any limit, **When** the limit is hit, **Then** execution is
   terminated and recorded as a failed receipt naming the limit, never reported as success.
13. **Given** a rejected mount surfaced through the API or UI, **When** the error is rendered,
   **Then** it identifies the mount by operator-defined alias or sanitized identifier and contains
   no raw resolved host path.
14. **Given** this story's changes, **When** they are delivered, **Then** stub removal, execution
   policy, sandbox controls and safe error identifiers appear in the same delivery unit; none is
   merged without the others.

---

### User Story 4 - Declared tools reach the running agent through an explicit boundary (Priority: P1, Steps 3-4)

A user builds a team that declares tools, runs it from the product, and the agents actually have
those tools. Resolution from a declared tool name to a usable runtime instance happens at one named,
explicit boundary that also resolves any credentials the tool needs, so that the product's own run
path and the generated standalone package no longer diverge in whether tools exist at all.

**Why this priority**: Audit §9 Steps 3-4, and the headline finding (P0-1). This is the outcome the
user actually asked for; US1-US3 exist to make it safe and observable.

**Independent Test**: Testable by running a team that declares a tool through the product's own run
path and asserting the agent was constructed with a matching tool instance, and that a run which
requires the tool invokes it.

**Acceptance Scenarios**:

1. **Given** a team whose agents declare tools, **When** it is run through the product's own run
   path, **Then** each agent is constructed carrying a resolved instance for every declared tool.
2. **Given** a declared tool that cannot be resolved to an instance, **When** the run is attempted,
   **Then** the run does not start and the failure names the unresolvable tool. It does not proceed
   with the tool silently absent.
3. **Given** a tool requiring credentials, **When** it is resolved, **Then** credentials are
   resolved through the existing precedence rules unchanged, and no credential value appears in
   transcripts, logs, or error messages.
4. **Given** a previously generated package, **When** it is run standalone as before, **Then** its
   existing behaviour is preserved.
5. **Given** provider routing and model selection, **When** tools are attached, **Then**
   per-agent routing behaviour is unchanged.

---

### User Story 5 - A run cannot claim success it cannot evidence (Priority: P1, Step 5)

A user reads a completed run and can trust the completion claim. A task that declares an external
capability is reported successfully complete only when the required tool actually executed and
produced a recorded receipt. When no receipt exists, the run reports an unverified or failed
outcome instead of success.

**Why this priority**: Audit §9 Step 5 and P0-4. Attaching real tools does not make the product
truthful — a model handed a working tool may still decline to call it and assert the work was done.
Without this, every symptom in the audit's transcripts recurs with real tools attached and no layer
notices. The recording infrastructure already exists and is unconsumed (RC-11), making this the
cheapest available guarantee of truthfulness.

**Independent Test**: Testable by running a task that declares a tool in a configuration where the
tool is never invoked, and asserting the run does not report success.

**Acceptance Scenarios**:

1. **Given** a task declaring an external capability, **When** the required tool executes,
   **Then** a receipt is recorded carrying tool name, sanitized input, success or failure,
   timestamp, and a reference to the output.
2. **Given** a task declaring an external capability, **When** no receipt exists for it at
   completion time, **Then** the task is not reported successfully complete and the run result
   states which required capability produced no evidence.
3. **Given** a completed run, **When** the user views its result, **Then** the tool-execution
   record is available as part of that result.
4. **Given** a recorded receipt, **When** it is stored or displayed, **Then** credential values and
   other secrets are redacted.
5. **Given** a task that declares no external capability, **When** it completes, **Then** existing
   completion behaviour is unchanged.
6. **Given** a task with one required capability and two optional tools available, **When** the
   required capability has a receipt and the optional tools were never used, **Then** the task is
   reported successfully complete and no unevidenced-capability finding is raised.
7. **Given** a claimed external action, **When** no **successful** receipt corresponds to it,
   **Then** the claim is not accepted as evidence of that action.

---

### User Story 6 - Validation and preflight detect semantic failures, not just parseable files (Priority: P2, Step 6)

A user who sees a green validation result can rely on it. Build-time validation and pre-run
preflight check that declared capabilities actually exist and are usable — not merely that the
expected files are present and the configuration parses.

**Why this priority**: Audit §9 Step 6 and P0-3. This cluster is what converts silent internal
failures into an explicit, confident, false assurance. It is last in the dependency sequence
because it reports on the guarantees established by US2-US5; it is P2 relative to them only in
ordering, and it remains inside the P0 release-blocking set.

**Independent Test**: Testable by validating a package that declares an unavailable capability and
asserting validation fails with a specific finding rather than reporting passed.

**Acceptance Scenarios**:

1. **Given** a package declaring a tool that is not in the canonical catalog or has no available
   implementation, **When** build-time validation runs, **Then** it reports failure naming the tool.
2. **Given** a package declaring a tool whose required credentials are absent, **When** preflight
   runs, **Then** it reports the missing credential before the run starts.
3. **Given** a package whose declared capabilities are all available and credentialed, **When**
   validation and preflight run, **Then** they report passed.
4. **Given** any validation or preflight failure, **When** it is reported, **Then** the generated
   report reflects the failure rather than stating no issues were found.

---

### Edge Cases

- A previously generated package declares an invented tool name and the user re-runs it after this
  remediation. It fails with an actionable message (FR-037) and appears in the migration report
  (FR-039). Nothing is rewritten on the user's behalf.
- A previously generated package declares tools that all resolve safely through the canonical
  catalog. It continues to build, validate and run unchanged, and does not appear in the migration
  report (FR-038, FR-039). Carrying tool assignments is not itself a failure condition.
- A previously generated package declares four safe tools and one invented one. It fails, and the
  message names the single offending declaration rather than implying the whole package is invalid
  (FR-037, FR-038).
- The migration report encounters a non-canonical name with two plausible canonical counterparts, or
  none. It flags the name for a human decision rather than suggesting a replacement (FR-041).
- The sandbox mechanism is installed but unhealthy mid-run. Subsequent risky-tool invocations are
  refused rather than executed on the host (FR-013).
- An operator allowlists a broad path that resolves to a dangerous location, or an allowlisted path
  contains a symlink pointing at one. The dangerous-location exclusion applies after resolution and
  refuses it regardless of the allowlist (FR-016).
- An agent requests a legitimate allowlisted mount but needs write access the operator did not
  grant. The mount is applied read-only; a write attempt fails inside the sandbox rather than
  escalating (FR-015).
- A team declares a tool that is canonical but has no implementation available in the current
  environment (missing optional dependency). Treated as unresolvable: the run does not start.
- A tool executes and fails. A receipt exists recording failure; this is not the same as no receipt.
  A failed tool execution MUST NOT satisfy the completion rule as though it succeeded.
- A tool is invoked more than once for one task, or a tool executes for a task that did not declare
  it. Receipts are recorded per execution; the completion rule keys on the declaring task.
- A run is cancelled or errors mid-flight after some tools executed. Receipts recorded so far are
  retained and the run reports incomplete, not successful.
- Execution policy is unsatisfiable in the runtime environment (for example the sandbox mechanism is
  unavailable). Risky tools are refused, not silently executed unsandboxed.
- The authoring model proposes a credential variable name that exists nowhere in the system. It is
  rejected at the same gate as an invented tool name.
- A team declares `docker_runner` and the operator has not enabled it. Execution is denied at
  pre-run (FR-052, FR-055), regardless of the tool being canonical and assigned.
- Authorization policy exists but is malformed. Every RISKY tool is denied; the unreadable policy is
  not treated as permissive (FR-054).
- A canonical tool's optional dependency is installed at build time but absent at run time. Build
  succeeds and emits the requirement; pre-run hard-fails naming the missing dependency (FR-066 to
  FR-068).
- A legacy task carries no requiredness marking. Every declared capability is treated as optional
  for the completion rule rather than inferred as required (Assumptions).
- A sandboxed execution needs network access the operator has not granted. It is denied by default;
  the tool fails rather than silently running without network (FR-073).
- An agent supplies a longer timeout or a larger memory value in its tool arguments. The values are
  ignored; enforced controls are operator-owned (FR-076).
- A team declares zero tools. All existing behaviour is unchanged and no new failure mode is
  introduced — this is the majority of currently working text-only teams and MUST NOT regress.

---

## Requirements *(mandatory)*

### Functional Requirements

**Canonical tool identity and validation (RC-3, Step 1)**

- **FR-001**: System MUST maintain exactly one canonical catalog that defines tool identity. Every
  other surface that names tools MUST derive from it rather than restate it.
- **FR-002**: System MUST validate every declared tool name against the canonical catalog at the
  point the declaration is recorded, covering all declaration surfaces — including per-agent tool
  lists, which are unchecked today.
- **FR-003**: System MUST reject a declared tool name that is absent from the canonical catalog,
  identifying the offending name and its source surface. Rejection behaviour is stage-deterministic
  and specified in FR-056 to FR-060; there is no discretionary "surface it instead" path. Advisory
  prompt text MUST NOT be relied on as a gate.
- **FR-004**: System MUST apply the same validation to free-form tool suggestions produced by the
  authoring model, including any credential variable names they propose.
- **FR-005**: System MUST NOT adopt an unvalidated model-authored tool description as a statement of
  a tool's contract to an agent.

**Single definition and enforced execution policy (RC-4 + RC-10, Step 2, ATOMIC)**

- **FR-006**: Generated packages MUST contain exactly one definition per tool name **per generated
  module**, with no definition shadowing or rebinding another within that module. Two packages may
  each define the same tool; one module may not define it twice.
- **FR-007**: Generated tool registries MUST contain no duplicate keys. The registry key, the
  agent-facing tool name emitted by the generated code, and the canonical catalog name MUST all be
  the same string, derived from one source, so no two of them can diverge.
- **FR-008**: Every risky tool MUST route through a single enforced execution-policy path. No tool
  may implement its own execution policy or bypass the shared one.
- **FR-009**: When execution policy cannot be satisfied, the system MUST refuse execution and name
  the unmet condition. It MUST NOT fall back to an unrestricted execution path.
- **FR-010**: System MUST NOT emit a placeholder implementation whose description asserts a
  capability the implementation does not provide. A declared capability that has no implementation
  in the canonical catalog MUST be reported as a build failure. This is distinct from a canonical
  tool whose optional dependency or credential is merely absent in the current environment, which is
  governed by FR-065 to FR-069.
- **FR-011**: Documentation emitted with a package MUST accurately describe the execution policy
  actually applied to each tool.
- **FR-012**: Sandboxed execution of risky tools MUST be mandatory. There is no opt-out, and no
  environment variable, configuration value or absent setting may disable it.
- **FR-013**: When the sandbox mechanism is unavailable, unhealthy or cannot be established, the
  system MUST fail closed: the risky tool execution is refused and the refusal states that the
  sandbox could not be established. Unsandboxed host execution MUST NOT occur under any condition.
- **FR-014**: Agents MUST NOT be able to create arbitrary mounts. A mount is permitted only when it
  matches an entry in an operator-configured allowlist. An empty or absent allowlist means no mounts
  are permitted.
- **FR-015**: Allowlisted mounts MUST be read-only by default. A writable mount is permitted only
  when the operator's allowlist entry explicitly marks it writable.
- **FR-016**: The system MUST refuse any mount resolving to a dangerous location regardless of
  allowlist contents, including at minimum the host root, user home directories, the Docker socket,
  device paths, and system paths. This exclusion MUST be enforced after path resolution so that
  symlinks, relative segments and equivalent paths cannot circumvent it.
- **FR-017**: A refused mount MUST NOT silently downgrade to running the tool without it. The
  execution is refused and the refusal identifies the rejected mount and the rule it violated, using
  the safe identifier required by FR-070 rather than the raw resolved host path.
- **FR-018**: FR-006 through FR-017, together with FR-070, FR-071 and FR-073 to FR-078, MUST be
  delivered as a single atomic unit. No subset may be merged independently. The sandbox control
  requirements are inside this unit because they are part of the execution policy whose absence is
  what makes stub removal dangerous.

**Runtime tool resolution boundary (RC-5, Steps 3-4)**

- **FR-019**: System MUST provide one explicit, named boundary that resolves a declared tool name to
  a runtime instance.
- **FR-020**: The product's own run path MUST attach resolved tool instances to each agent that
  declares them.
- **FR-021**: System MUST make the originating package locatable from the run so the boundary can
  resolve that package's tool definitions. This requirement covers **path threading only** — how
  the package location reaches the boundary. What the boundary is then permitted to load, and
  under what controls, is FR-024.
- **FR-022**: The boundary MUST resolve credentials required by a tool, distinctly from and without
  altering model-provider credential resolution.
- **FR-023**: System MUST refuse to start a run when any declared tool cannot be resolved to an
  instance, naming the unresolvable tool. It MUST NOT proceed with the tool silently absent.
- **FR-024**: Loading a generated package's tool definitions MUST occur through a controlled
  mechanism subject to FR-008 through FR-017.
- **FR-025**: The product's run path and the generated standalone package MUST NOT diverge in
  whether declared tools are attached.

**Execution evidence and completion rule (RC-11, Step 5)**

- **FR-026**: System MUST record a receipt for every tool execution containing tool name, sanitized
  input, success or failure, timestamp, and an output reference. **Sanitized input** means the
  argument mapping after the redaction rules of FR-029 and FR-071 have been applied. The **output
  reference** identifies the corresponding transcript entry; it is not the output text, and its
  target need only remain retrievable for the lifetime of the run result that carries it.
- **FR-027**: System MUST NOT report a task as successfully complete unless every capability the
  task marks as **required** has a receipt recording that the tool executed. The rule keys on
  required capabilities, not on the set of tools available to the agent — see FR-061 to FR-064. A
  recorded failure does not satisfy the rule as a success.
- **FR-028**: Run results MUST carry the tool-execution record and MUST identify any declared
  capability that produced no evidence.
- **FR-029**: Receipts MUST redact credential values, secrets and raw resolved host paths wherever
  stored or displayed (see FR-070 to FR-072).

**Validation and preflight (RC-8, Step 6)**

- **FR-030**: Build-time validation MUST verify that every declared capability exists and has an
  available implementation, in addition to existing structural checks.
- **FR-031**: Preflight MUST verify tool availability and required tool credentials before a run
  starts.
- **FR-032**: Preflight MUST verify that every mount an allowlist would permit for the declared
  tools still satisfies FR-015 and FR-016 at run time.
- **FR-033**: Generated reports MUST reflect validation and preflight failures rather than stating
  no issues were found.

**Regression oracle (RC-12, Step 0)**

- **FR-034**: A regression test MUST construct an agent declaring a non-empty tool list and assert
  the constructed agent carries a matching tool. This test MUST be added before any other change in
  this feature and MUST fail against current behaviour when added.
- **FR-035**: Shared runtime test fixtures MUST NOT make the tool-dropping defect unobservable by
  defaulting every agent to an empty tool list.
- **FR-036**: Each remediation step MUST carry regression coverage that fails before its change and
  passes after.

**Legacy package handling and migration reporting (Q1)**

- **FR-037**: A previously generated package that declares a tool which is unknown, invalid,
  unresolvable, unauthorized or unsafe MUST fail validation, and MUST fail at run time with a
  message naming the offending tool, the agent that declares it, and the package. It MUST NOT run
  with the tool silently absent.
- **FR-038**: Failure under FR-037 MUST be scoped to the offending declarations. A previously
  generated package whose declared tools all resolve safely **in the current environment** — canonical,
  authorized, with dependencies and credentials present — MUST continue to build, validate and run
  exactly as it does today. Merely declaring tools is not a failure condition.
- **FR-039**: System MUST provide a migration report covering only the affected packages — those
  carrying at least one unknown, invalid, unresolvable, unauthorized or unsafe declaration — listing
  the offending tool names and where each is declared. Packages whose tools all resolve safely MUST
  NOT appear in the report.
- **FR-040**: The migration report MUST be advisory only. It MUST NOT modify, rewrite, regenerate or
  otherwise alter any existing package. Remediation of an existing package is a user action.
- **FR-041**: The migration report MUST suggest a canonical replacement only where the mapping is
  unambiguous. Where more than one canonical tool could plausibly correspond, or none does, it MUST
  report the name as requiring a human decision rather than guessing.
- **FR-042**: The migration report MUST be reproducible and read-only with respect to the packages
  it inspects, so it can be run repeatedly without side effects.

**Starter-team correction (P1-8, narrowly scoped within Step 1; extended by Amendment 8)**

- **FR-043**: The shipped starter team's declared tool names MUST be corrected to canonical catalog
  names so that the primary onboarding path passes the gate introduced by FR-002 and FR-030.
- **FR-044**: This correction MUST be limited to tool-name declarations across the built-in
  templates (Amendment 8 extends this from "the starter team" to all three built-in templates — see
  below). No other P1 finding, and no other aspect of any template, is in scope.
- **FR-087**: Every built-in template's per-role default `tools` list MUST declare only canonical
  catalog names. A phantom name MUST be removed or replaced with a canonical name whose catalog
  description is an unambiguous semantic match; a fabricated catalog entry MUST NOT be created to
  preserve a phantom capability.

**Preservation constraints (apply to every requirement above)**

- **FR-045**: Credential precedence MUST be unchanged: the key file wins, process environment
  variables are a per-provider fallback.
- **FR-046**: Provider routing, including per-agent routing and model selection, MUST be unchanged.
- **FR-047**: Previously generated packages that declare no tools, or only tools that resolve
  safely in the current environment per FR-069, MUST remain runnable standalone with unchanged
  behaviour. **Unchanged behaviour** means the package still builds, validates and executes, and
  its agents receive the same tool set — not that model output is byte-identical, which is not a
  property this system has.
- **FR-048**: API and CLI behaviour unrelated to tool declaration, resolution, execution, evidence,
  validation and preflight MUST be unchanged.
- **FR-049**: Teams that declare no tools MUST behave exactly as they do today.

> **Cross-reference — the no-fallback rule.** FR-009, FR-013, FR-017, FR-054, FR-059 and FR-078
> each prohibit a permissive fallback on their own surface: execution policy, sandbox
> establishment, mount refusal, authorization policy, stage rejection, and control defaults. They
> are one principle stated six times, deliberately — each surface needs the prohibition written
> where its implementer will read it. Treat them as a set: weakening any one reopens the gate.

**Tool authorization policy (Amendment 1 — resolves CHK002, CHK003, CHK006)**

- **FR-050**: A tool MUST execute only when **all three** conditions hold: it is assigned to the
  team, it exists in the canonical catalog, and operator policy authorizes it. All three are
  necessary; none alone is sufficient.
- **FR-051**: A team declaring a tool is **not** authorization. Declaration establishes intent;
  authorization is an operator decision recorded outside the team specification.
- **FR-052**: Tools classified RISKY — including `docker_runner` — MUST be denied by default and
  execute only when the operator has explicitly enabled them. Absence of an explicit enablement is a
  denial, not a permission.
- **FR-053**: Agents MUST NOT be able to create, modify, extend, relax or bypass authorization
  policy. No agent-supplied input may widen what is authorized.
- **FR-054**: When authorization policy is absent, empty, malformed or unreadable, the system MUST
  deny every RISKY tool. A policy that cannot be read is not a permissive policy.
- **FR-055**: Authorization MUST be evaluated before execution begins, as part of the pre-run gate,
  so an unauthorized tool never reaches a running agent.

**Deterministic invalid-tool behaviour by stage (Amendment 2 — resolves CHK007, CHK008, CHK009)**

- **FR-056**: **Compose** MUST visibly reject an invalid tool assignment to the user at the point of
  authoring. The rejection is user-visible, not a log line.
- **FR-057**: **Build** MUST reject unknown or unsafe tool declarations and MUST NOT produce a
  package containing them.
- **FR-058**: **Pre-run** MUST hard-fail when any declared tool is unavailable, unauthorized or
  unresolvable, before the run starts.
- **FR-059**: At no stage may the system silently substitute a different tool, emit a stub, skip the
  declaration, or fall back to a degraded path. Every one of these is prohibited (FR-009, FR-013,
  FR-017 state the same prohibition for their own surfaces).
- **FR-060**: Every stage rejection MUST name the offending tool, the declaring agent, the stage at
  which it was rejected, and exactly one reason class, defined as: **unknown** — not in the
  catalog; **invalid** — in the catalog but the declaration is malformed or self-inconsistent;
  **unresolvable** — canonical, but no instance can be produced here; **unauthorized** — resolvable,
  but operator policy does not permit it; **unsafe** — authorized, but execution policy cannot be
  satisfied. Rejections MUST be aggregated, reporting every offending declaration in one failure,
  following the collect-don't-short-circuit convention of FR-023.

**Required versus available capabilities (Amendment 3 — resolves CHK027, CHK028)**

- **FR-061**: The system MUST distinguish **tools available to an agent** from **capabilities a task
  requires**. These are different sets and the completion rule keys only on the second.
- **FR-062**: Completion MUST require a receipt only for each external capability a task marks as
  required.
- **FR-063**: An optional tool that was available but unused MUST NOT block completion and MUST NOT
  produce an unevidenced-capability finding.
- **FR-064**: Any claimed external action MUST be supported by a corresponding **successful**
  receipt. A receipt recording failure does not support a claim of that action having been performed.

**Conditionally available tools (Amendment 4 — resolves CHK015, CHK016, CHK039)**

- **FR-065**: A canonical tool whose dependency or credential is optional MUST be treated as **known
  but possibly unavailable**. This is a distinct state from unknown, and MUST NOT be conflated with
  an invented name.
- **FR-066**: **Build** MUST validate the tool's catalog definition and emit its dependency and
  credential requirements into the generated package, so the package declares what it needs.
- **FR-067**: **Pre-run** MUST validate actual dependencies, credentials, authorization and
  executability in the current environment.
- **FR-068**: Missing prerequisites MUST cause an actionable hard failure naming what is missing and
  what would satisfy it. A stub, a silent skip or a fallback is prohibited.
- **FR-069**: An existing package remains compatible **only when its tools resolve safely in the
  current environment**. Compatibility is an environment-dependent property, not a property of the
  package alone.

**Safe error identifiers (Amendment 5 — resolves CHK049)**

- **FR-070**: API and UI errors MUST identify a rejected mount by an operator-defined alias or a
  sanitized identifier. The raw resolved host path MUST NOT appear.
- **FR-071**: Raw resolved host paths and secrets MUST NOT appear in receipts or in any user-facing
  error, message, transcript or report.
- **FR-072**: Full path detail MAY appear only in operator-scoped diagnostics that are not exposed
  through the API, the UI or a receipt. Operator diagnostics remain subject to FR-029's secret
  redaction.

**Mandatory sandbox controls (Amendment 6 — resolves CHK021, CHK022, CHK023; inside the FR-018 atomic unit)**

- **FR-073**: Network access from a sandboxed execution MUST be denied by default and MUST be
  permitted only by operator policy. Agents MUST NOT be able to enable or widen network access.
- **FR-074**: Execution timeouts MUST be mandatory and enforced. There MUST be no path that executes
  without a timeout, and no agent-supplied value may extend one.
- **FR-075**: CPU, memory, process-count, output-size and relevant storage limits MUST be mandatory
  and enforced on every sandboxed execution.
- **FR-076**: Agents MUST NOT be able to disable, relax, raise or opt out of any control in FR-073 to
  FR-075. Only operator policy may adjust them, and only within bounds the system enforces.
- **FR-077**: Exceeding any limit MUST terminate the execution and MUST be recorded as a failed
  receipt naming the limit that was exceeded. A terminated execution is never reported as success.
- **FR-078**: Every control in FR-073 to FR-075 MUST have a defined, documented default that applies
  when operator policy is silent. A silent policy yields the restrictive default, never an unbounded
  execution.

**Security and configuration clarifications (Amendment 7 — closes CHK004, CHK011, CHK019, CHK020,
CHK025, CHK040, CHK001, CHK005)**

- **FR-079**: The dangerous-location deny floor MUST take precedence over every allowlist entry, and
  MUST be extendable but never reducible. No configuration, operator action or agent input may remove
  an entry from it. (Previously stated only in a design contract.)
- **FR-080**: A hand-edited or third-party package — one whose declarations never passed through this
  system's compose or build stages — MUST be subject to the identical pre-run gate as a
  factory-produced package. Provenance grants no exemption.
- **FR-081**: Mandatory sandboxing and the controls of FR-073 to FR-078 MUST apply to **both** the
  product's own run path and the generated standalone package. Neither path may execute a RISKY tool
  under weaker controls than the other.
- **FR-082**: "The sandbox cannot be established" MUST be defined as any of: the container runtime is
  absent; the runtime is present but unreachable; the sandbox image is unavailable; container creation
  fails; a declared control from FR-073 to FR-075 cannot be enforced; or the sandbox becomes
  unavailable mid-run. Each condition produces a refusal naming which one occurred.
- **FR-083**: A SAFE-classified tool MUST NOT execute host commands, write outside the sandbox
  workspace, open network connections on its own authority, or control the container runtime. A tool
  requiring any of these is RISKY by definition and MUST be classified accordingly.
- **FR-084**: A package generated before this remediation, whose tool module has the pre-remediation
  shape, MUST be detected and refused with an actionable message rather than loaded. It MUST NOT be
  partially loaded, adapted or executed under assumed controls.
- **FR-085**: Operator configuration — authorization policy, mount allowlist with aliases, and sandbox
  control overrides — MUST live in a single operator-owned source whose location follows the existing
  credential-file convention: an explicit path wins, then a default project location. When that source
  is absent, malformed or unreadable, the system MUST apply the denying defaults of FR-054 and FR-078
  and MUST emit an operator diagnostic naming the unreadable source.
- **FR-086**: Every control in FR-073 to FR-075 MUST have its default value documented in a single
  authoritative table that the implementation reads from, rather than restating values per call site.

### Key Entities

- **Canonical Tool Catalog**: The single authoritative set of tool identities. Each entry carries a
  canonical name, a description used as the agent-facing contract, its credential requirements, and
  its execution-policy class (risky or not).
- **Tool Declaration**: A tool named by an agent or role in a team specification. Validated against
  the catalog; the unit that resolution, evidence and completion rules key on.
- **Resolved Tool Instance**: The usable runtime form of a declaration, produced by the resolution
  boundary. Exists only when the declaration is canonical, resolvable, credentialed and
  policy-permitted.
- **Execution Policy**: The rules governing how a risky tool may execute. Sandboxing is mandatory
  and unconditional; the policy is enforced at one path and fails closed when the sandbox cannot be
  established.
- **Authorization Policy**: The operator-owned record of which catalog tools are permitted to
  execute. RISKY tools are denied unless explicitly enabled. Absent, empty, malformed or unreadable
  policy denies every RISKY tool. Agents cannot read-modify-write it (FR-050 to FR-055).
- **Sandbox Controls**: The mandatory, non-negotiable execution limits — network egress denied by
  default, execution timeout, CPU, memory, process count, output size and storage. Each has a
  restrictive documented default that applies when operator policy is silent. Agents cannot relax
  any of them (FR-073 to FR-078).
- **Capability Requirement**: A task's declaration that a specific external capability is *required*
  for that task, as distinct from a tool merely being available to the agent. The completion rule
  keys on this, not on the available set (FR-061 to FR-064).
- **Safe Mount Identifier**: The operator-defined alias or sanitized identifier used to name a
  rejected mount in any API, UI, receipt or user-facing error, in place of the raw resolved host
  path (FR-070 to FR-072).
- **Mount Allowlist**: The operator-configured set of mounts a risky tool may receive. Each entry
  names a permitted source, is read-only unless the operator explicitly marks it writable, and is
  subject to an unconditional dangerous-location exclusion that no entry can override. Agents cannot
  add to it. Absent or empty means no mounts.
- **Execution Receipt**: The record that a tool ran — tool name, sanitized input, outcome,
  timestamp, output reference. The sole admissible evidence for the completion rule.
- **Validation Finding**: A named, actionable failure or warning from build-time validation or
  preflight, carried into the generated report.
- **Migration Report**: An advisory, read-only inventory of existing packages that declare
  non-canonical tool names, with unambiguous canonical replacements suggested and ambiguous ones
  flagged for a human decision. It never modifies a package.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of teams that declare tools have those tools available to their agents when run
  through the product, verified across the packages the audit identified as carrying tool
  assignments.
- **SC-002**: 0 declared tool names that are unknown, unresolvable, unauthorized or policy-refused
  reach execution.
- **SC-003**: 0 generated packages contain a duplicate tool definition, a shadowed real
  implementation, or a duplicate registry key.
- **SC-004**: 0 risky tool executions occur outside the enforced execution-policy path, and 0 occur
  unsandboxed under any configuration, including when the sandbox is unavailable.
- **SC-005**: 0 mounts are applied that are absent from the operator allowlist, and 0 mounts
  resolving to a dangerous location are applied regardless of allowlist contents. Every allowlisted
  mount not explicitly marked writable is applied read-only.
- **SC-006**: 0 runs report successful completion for a task that declared an external capability
  with no execution receipt.
- **SC-007**: 100% of tool executions produce a receipt that a user can inspect from the run result.
- **SC-008**: 0 occurrences of a passed validation result on a package that declares an unavailable
  capability, verified against the four packages the audit identified as falsely reporting passed.
- **SC-009**: The Step 0 regression test fails against pre-remediation behaviour and passes after
  the resolution boundary lands, demonstrated by running it at both points.
- **SC-010**: 0 credential values appear in receipts, transcripts, logs, reports or error messages.
- **SC-011**: 100% of pre-existing tests unrelated to tools continue to pass; teams declaring no
  tools show no behavioural change; and 100% of existing packages whose declared tools all resolve
  safely through the canonical catalog continue to build, validate and run unchanged.
- **SC-012**: The migration report lists only affected packages. 0 packages whose tools all resolve
  safely appear in it.
- **SC-019**: 100% of sandbox controls execute against the documented default table, and 0 control
  values are restated at a call site.
- **SC-020**: 0 pre-remediation-shape packages are loaded, and 0 hand-edited packages bypass the
  pre-run gate.
- **SC-013**: Every change in this feature cites its requirement and its audit finding or root-cause
  ID, and every behavioural finding closed is closed by re-running its original reproduction.
- **SC-014**: 0 tools execute without satisfying all three authorization conditions, and 0 RISKY
  tools execute without explicit operator enablement.
- **SC-015**: 0 invalid tool declarations are silently substituted, stubbed, skipped or fallen back
  from at any stage; 100% produce a stage-named rejection.
- **SC-016**: 0 tasks are blocked from completion by an optional unused tool, and 0 claimed external
  actions lack a corresponding successful receipt.
- **SC-017**: 0 raw resolved host paths appear in receipts, API responses, UI errors, transcripts or
  reports.
- **SC-018**: 0 sandboxed executions run without an enforced timeout and the full set of mandatory
  resource limits; 0 controls are relaxable by agent-supplied input.

---

## Scope

### In Scope

Audit P0 clusters only: §2.1 (P0-1), §2.2 (P0-2, all three parts), §2.3 (P0-3), §2.4 (P0-4), plus
the RC-12 / Step 0 regression oracle that the audit places before them. Root causes RC-3, RC-4,
RC-5, RC-8, RC-10, RC-11, RC-12.

Two deliberate additions, both decided 2026-08-29:

- **The advisory migration report** (FR-039 to FR-042). Not an audit finding; it exists so that the
  affected subset of existing packages — those declaring unknown, invalid, unresolvable,
  unauthorized or unsafe tools — has a path forward under FR-037. It covers only that subset, is
  read-only by construction, and rewrites nothing. Packages whose tools all resolve safely are not
  listed and need no action.
- **The starter-team tool-name correction** (FR-043, FR-044, FR-087). This is P1-8, which audit §9 places
  inside Step 1. Admitted as a narrowly scoped exception to the P1 exclusion, limited strictly to
  the starter team's tool-name declarations, because the primary onboarding path would otherwise
  fail the gate this feature introduces.

### Out of Scope

- All P1 findings (§3) except the narrowly scoped P1-8 correction admitted above — including
  truncation detection (RC-6), My Teams population, run recovery and the global run lock (RC-9),
  re-authoring nondeterminism (RC-2), silent provider rejection, documentation-versus-configuration
  drift (RC-7) and the long-input failure. No other aspect of the starter team is in scope.
- All P2 findings (§4), including the conversational-channel cluster (RC-1), template selection,
  model disclosure, requirements-file uniformity and the xAI key-name mismatch.
- All P3 findings (§5).
- QA-file cleanup and audit-document maintenance.
- Product-design options recorded in audit §13: delegating software work to a coding agent, the
  stub/mock/fake builder warning, and sidebar team listing.
- The per-team shared-memory gap noted under RC-5. It shares RC-5's mechanism but is not itself a
  P0 cluster; it is recorded here so it is not lost.
- Any implementation. This specification defines outcomes only.

---

## Dependencies and Sequencing

The audit's §9 order is a dependency chain and MUST be preserved:

| Order | Story | Root cause | Gating relationship |
|---|---|---|---|
| Step 0 | US1 | RC-12 | Precedes everything; without it no later step is regression-guarded |
| Step 1 | US2 | RC-3 | Canonical catalog is the contract US3-US6 resolve and validate against. Carries the starter-team correction (FR-043) and the migration report (FR-039) |
| Step 2 | US3 | RC-4 + RC-10 | **Atomic.** Splitting arms a host escape. Execution policy settled: mandatory sandbox, fail-closed, allowlist-only read-only mounts |
| Step 3-4 | US4 | RC-5 | Requires US2's catalog and US3's enforced policy |
| Step 5 | US5 | RC-11 | Requires US4, since receipts cannot exist until tools execute |
| Step 6 | US6 | RC-8 | Reports on the guarantees US2-US5 establish |

External dependencies: the existing tool-usage event recording infrastructure (built, unconsumed);
the existing agent-construction interception harness used by US1; the existing credential resolution
and provider routing behaviour, which this feature consumes without altering.

---

## Resolved Decisions

Recorded 2026-08-29. These closed the three open questions this spec was drafted against.

| ID | Question | Decision | Requirements |
|---|---|---|---|
| Q1 | Existing packages that declare unknown, invalid, unresolvable, unauthorized or unsafe tools | Those packages fail validation and fail at run, plus an advisory migration report scoped to them alone. Existing packages whose tools all resolve safely stay compatible and untouched. The report must not rewrite any package, and suggests replacements only where the mapping is unambiguous | FR-037 to FR-042 |
| Q2 | Sandbox default and agent-supplied mounts | Sandbox mandatory with no opt-out and fail-closed when unavailable. Mounts allowlist-only, read-only by default, with an unconditional dangerous-location exclusion (host root, home directories, Docker socket, devices, system paths) | FR-012 to FR-017 |
| Q3 | Shipped starter team (P1-8) | Include, narrowly scoped to the starter team's tool-name declarations only. No other P1 finding enters this spec | FR-043, FR-044, FR-087 |

### Amendment 1-6 (2026-08-29, post-checklist review)

Raised by the `tool-integrity.md` requirements-quality review and resolved by product decision.
Existing requirement IDs were **amended in place, not renumbered**, so every reference in
`plan.md`, `tasks.md`, `contracts/` and the checklists remains valid. New requirements were appended
from FR-050.

| # | Issue | Resolution | Requirements | Closes |
|---|---|---|---|---|
| 1 | Authorization defined only for mounts; a declaration was treated as permission | Three necessary conditions; RISKY denied by default and operator-enabled only; agents cannot alter policy; unreadable policy denies | FR-050 to FR-055 | CHK002, CHK003, CHK006 |
| 2 | FR-003's "reject **or** surface" was two behaviours | Stage-deterministic: compose rejects visibly, build rejects, pre-run hard-fails; substitution, stubbing, skipping and fallback prohibited everywhere | FR-003 amended, FR-056 to FR-060 | CHK007, CHK008, CHK009, CHK012 |
| 3 | Completion rule read as all-or-nothing over every available tool | Receipts required only for capabilities a task marks *required*; optional unused tools never block; a claim needs a **successful** receipt | FR-027 amended, FR-061 to FR-064 | CHK027, CHK028 |
| 4 | Conditionally available tools were both "no implementation" and "unresolvable" | Known-but-unavailable is a distinct state: build emits requirements, pre-run validates them, missing prerequisites hard-fail | FR-010/FR-038/FR-047 amended, FR-065 to FR-069 | CHK015, CHK016, CHK039 |
| 5 | Naming a rejected mount could leak a host path to the API/UI | Safe alias or sanitized identifier in all user-facing surfaces and receipts; full detail only in operator-scoped diagnostics | FR-017/FR-029 amended, FR-070 to FR-072 | CHK049 |
| 6 | Network, timeout and resource limits were deferred | All mandatory, restrictive by default, operator-only adjustment, agent-proof; folded into the FR-018 atomic unit | FR-018 amended, FR-073 to FR-078 | CHK021, CHK022, CHK023 |

### Amendment 7 (2026-08-29, post-analysis triage)

Raised by `/speckit-analyze` finding U1/U2 and the triage of the 29 open `tool-integrity.md` items.
Existing IDs amended in place; new requirements appended from FR-079.

| Issue | Resolution | Requirements | Closes |
|---|---|---|---|
| Deny floor precedence lived only in a contract | Stated as a requirement, extendable never reducible | FR-079 | CHK004, CHK024 |
| Hand-edited packages had no stated gate | Identical pre-run gate; provenance grants no exemption | FR-080 | CHK011 |
| Sandbox scope ambiguous between run paths | Applies to both product run path and standalone package | FR-081 | CHK019 |
| "Sandbox cannot be established" undefined | Six enumerated conditions, each named in the refusal | FR-082 | CHK020, CHK026 |
| SAFE tool permissions unstated | SAFE excludes host execution, writes outside workspace, own-authority network, runtime control | FR-083 | CHK025 |
| Pre-remediation package shape | Detected and refused, never partially loaded | FR-084 | CHK040 |
| Operator config location unspecified | Single operator-owned source following credential-file precedence; unreadable denies and diagnoses | FR-085 | CHK001, CHK005 |
| Control defaults undocumented | One authoritative table the implementation reads from | FR-086 | U1 |
| Rejection reason classes undifferentiated | Five classes each defined; rejections aggregate | FR-060 amended | CHK010, CHK013 |
| Scope words imprecise | One-definition scoped per module; unchanged-behaviour defined; output reference and sanitized input defined | FR-006, FR-026, FR-047 amended | CHK014, CHK033, CHK035, CHK041 |
| Registry / decorator / catalog name drift | All three are one string from one source | FR-007 amended | CHK017 |
| Path threading vs controlled loading conflated | FR-021 scoped to threading only | FR-021 amended | B2 |

### Amendment 8 (2026-08-29, discovered during Phase 3 implementation)

Raised during `/speckit-implement` Phase 3 (T036-T037): the approved P1-8 correction named only
`education/template.py`. Implementation discovered that `templates/software_delivery/template.py` —
`DEFAULT_TEMPLATE_ID`, used by every team that supplies `desired_roles` without an explicit
`template_id` — and `templates/research_content/template.py` also declare phantom tool names as
per-role defaults injected by `templates/role_based.py:68` *after* compose-stage schema validation
has already run, so the Phase 3 gate never saw them. Left uncorrected, this would have broken the
majority of default-path teams once Phase 4 (build failure on no implementation) and Phase 7
(validation) landed — a far larger compatibility break than FR-037/FR-038 anticipated.

Resolved by extending the identical mechanical correction (remove phantom, keep canonical, substitute
only on unambiguous semantic match, never fabricate a new catalog entry) to all three built-in
templates. Recorded in full, including the before/after table for every corrected role, in
`specs/001-p0-tool-execution-integrity/implementation-decision-log.md` D-IMPL-002. Verified by
`tests/unit/templates/test_template_tool_conformance.py`, which asserts — as a regression-permanent
property — that every built-in template declares only canonical names.

| Issue | Resolution | Requirements | Verification |
|---|---|---|---|
| Phantom names in the *default* template bypass compose-stage validation via per-role defaults | Extend the P1-8 correction pattern to all three built-in templates | FR-044 amended, FR-087 | `test_template_tool_conformance.py` |

---

## Assumptions

- The audit at `project-docs/qa/independent-quality-audit-verified.md` v2.1 is accurate as to
  mechanism. Its source citations were independently re-derived by its author, and a commit-hygiene
  check in §0 establishes nothing has been fixed since the commit under test.
- "Unsafe" in required outcome 2 means a tool whose execution policy cannot be satisfied — the
  sandbox cannot be established, or a requested mount is not allowlisted or resolves to a dangerous
  location. It is not a content-level judgement about a tool's purpose.
- The dangerous-location exclusion list (host root, home directories, Docker socket, device paths,
  system paths) is a floor, not a complete enumeration. Planning may add to it; nothing may remove
  from it, and no allowlist entry may override it.
- The operator configuring the mount allowlist is trusted and distinct from the agent. Agents have
  no path to add, widen or mark an entry writable.
- Mount refusal is evaluated after full path resolution, so symlinks, relative segments and
  equivalent paths cannot circumvent the exclusion.
- "Operator" means the person or process configuring the deployment, distinct from both the team
  author and the agent. Operator policy lives outside the team specification so a team cannot grant
  itself permission (FR-051).
- Operator-scoped diagnostics (FR-072) are assumed to exist as a channel separate from the API, UI
  and receipts. If no such channel exists, full path detail is dropped rather than exposed.
- A task's *required* capabilities (FR-061) are expressed in the task specification. Where a legacy
  package carries no requiredness marking, every declared capability is treated as optional for the
  completion rule, since inferring requiredness would reintroduce the guessing this feature removes.
- The mandatory limits in FR-075 have restrictive defaults; tuning them is an operator action within
  system-enforced bounds, not a per-team or per-agent setting.
- Receipts live for the lifetime of the run result that carries them. Durable persistence is an
  API and storage concern outside this feature (CHK034, deferred).
- Concurrent runs cannot interleave receipts, because the existing process-wide run lock serializes
  every run in one process (CHK036).
- Receipt `sequence` follows the existing `TranscriptEntry` convention — monotonic, sparse, ordered
  by data rather than list position — so receipts and transcript entries share one ordering basis
  (CHK037).
- The migration report is a read-only inspection tool. Deciding what an ambiguous legacy tool name
  should become is a human judgement the report surfaces but never makes.
- "Verified execution receipts" means receipts recorded by the runtime from observed tool-execution
  events, not model self-report.
- The completion rule keys on tasks that declare an external capability. Text-only tasks are
  unaffected.
- The audit's own effort note applies: Steps 1, 2 and 6 are largely mechanical while Steps 3-5 are
  design work — a resolution boundary, an execution-policy decision, and a completion invariant.
  This spec therefore defines outcomes and defers mechanism to planning.
- No user-facing feature is added. Every outcome here restores a capability the product already
  claims to have.
- The `state_store` shared-memory gap shares RC-5's mechanism, but fixing RC-5 does not
  automatically restore it, since its access path is via tools that must first become canonical and
  resolvable. It is out of scope and recorded as a known follow-on.

---

## Constitutional Alignment

Checked against `.specify/memory/constitution.md` v1.0.0:

- **I. Compatibility preserved**: FR-045 through FR-049 carry the credential-precedence,
  provider-routing, package-compatibility and API/CLI constraints. Existing packages whose declared
  tools all resolve safely through the canonical catalog remain fully compatible and are unaffected
  by this feature (FR-047). The Q1 resolution accepts a narrow, deliberate compatibility break
  limited to the subset of existing packages that declare unknown, invalid, unresolvable,
  unauthorized or unsafe tools (FR-037) — declarations that never worked, since those runs were
  already producing fabricated results. It is mitigated by the advisory migration report (FR-039 to
  FR-042), which likewise applies only to that affected subset. This is the one intentional
  deviation from Principle I in this feature and is recorded as such.
- **II. Fail-closed security**: the five-condition gate maps to FR-002/003 and FR-056 to FR-060
  (canonical, semantically valid, stage-deterministic rejection), FR-019/023 and FR-065 to FR-069
  (resolvable, including environment-dependent availability), FR-050 to FR-055 (explicitly
  authorized — three necessary conditions, RISKY denied by default, unreadable policy denies), and
  FR-012/013 with FR-073 to FR-078 (sandboxed, mandatory, fail-closed, with network denied by
  default and mandatory timeouts and resource limits). FR-009, FR-013, FR-017, FR-054, FR-059 and
  FR-078 each forbid a permissive fallback.
- **III. Execution evidence**: FR-026 through FR-028, FR-061 to FR-064 and SC-006. Amendment 3
  narrows the rule to *required* capabilities, which strengthens it rather than weakening it: a
  claimed external action now needs a **successful** receipt (FR-064), where the prior wording was
  satisfied by any receipt.
- **IV. Reproduction-first**: FR-034 and FR-036; SC-009 requires the Step 0 test to be demonstrated
  failing before it passes.
- **V. Traceability and gates**: every requirement traces to an audit cluster and root-cause ID;
  SC-013 carries the tracing and closure obligation.
