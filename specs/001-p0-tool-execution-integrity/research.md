# Phase 0 Research: P0 Tool Execution Integrity Remediation

**Date**: 2026-08-29 | **Plan**: [plan.md](./plan.md) | **Spec**: [spec.md](./spec.md)

All Technical Context unknowns are resolved. No `NEEDS CLARIFICATION` remains — the three spec-level
questions were answered before planning (spec §Resolved Decisions), and the implementation-level
questions below were settled by reading the source.

---

## Corrections to the audit's implementation detail

The audit's mechanisms are accurate. Two of its pointers are not, and both affect where code lands.
Neither changes the diagnosis or the fix order.

### C-1: The Step 0 oracle does not hook where the audit says

**Audit §3.9 / §9 Step 0**: *"`tests/support/crewai_interception.py` already captures the constructed
`Agent`, so this is a few lines."*

**Verified**: `crewai_interception.py` patches `BaseLLM.call` and blocks `httpx` — it records
`LLMCall` objects. It contains no reference to `Agent` at all.

The constructed agent *is* reachable, but through a different existing seam:
`tests/unit/adapters/test_crewai_execution_engine.py:70` `_install_fake_kickoff` monkeypatches
`Crew.kickoff` and appends the `Crew` to a `captured` list. A `Crew` holds `agents`, so the oracle is
`captured[0].agents[i].tools`.

**Impact**: Step 0 lands in `tests/unit/adapters/test_crewai_execution_engine.py` beside the existing
15 engine tests, reusing `_install_fake_kickoff`. Still a few lines. The audit's "few lines" estimate
survives; its file pointer does not.

### C-2: The `shell` key mismatch is decorator-name versus registry-key

**Audit §2.2(b)**: *"the real shell tool registers under key `"shell"` … but the prompt catalog and
every agent YAML use `"shell_command"`."*

**Verified, with the direction clarified**: `AVAILABLE_TOOLS` (`prompts.py:24`) uses `"shell"` and
`TOOL_REGISTRY` (`tools.py.j2:278`) uses `"shell"` — those two agree. The divergent name is the
`@tool("shell_command")` decorator argument (`tools.py.j2:71`), which is what CrewAI shows the agent
and what invented agent YAMLs picked up.

**Impact**: unification is a three-way reconciliation of catalog key, registry key and decorator
name — decided in D-2 below. Not a two-way rename.

---

## Decisions

### D-1: One canonical catalog as a data structure in `team_maker/tools/catalog.py`

**Decision**: A single `TOOL_CATALOG: dict[str, ToolDefinition]` in a new `team_maker/tools/`
package. `prompts.AVAILABLE_TOOLS` becomes a derived view (name → description). `schema/request.py`'s
`_REGISTRY_TOOLS` set is deleted and its membership test reads the catalog. `tools.py.j2` renders its
registry from the catalog rather than hardcoding keys.

**Rationale**: The audit's meta-pattern is that the correct value already exists in the repo, ten to
a hundred lines from the code that ignores it. Three drifted copies exist precisely because each
surface owns its own literal. A catalog carrying description, credential requirements and policy
class in one entry serves all three consumers, so drift becomes structurally impossible rather than
merely discouraged.

**Alternatives rejected**:
- *Promote one existing copy to canonical.* `AVAILABLE_TOOLS` is the natural candidate but holds only
  descriptions; it cannot express credential requirements or the risky/safe distinction that FR-008
  and FR-031 need.
- *A YAML/JSON catalog file.* Adds a parse-and-validate path and a file that can drift from the code
  that consumes it, for no gain — the catalog is code-adjacent constant data with no user-editing
  requirement in this feature.

### D-2: Canonical name is the registry key; the decorator name is derived from it

**Decision**: The catalog key is the single canonical name. `tools.py.j2` renders both the registry
key and the `@tool(...)` decorator argument from that same key, so they cannot disagree. `shell` is
the canonical name; `shell_command` becomes a recognized legacy alias reported by the migration
report (FR-039), not a second identity.

**Rationale**: C-2 shows the mismatch is a rendering divergence — two literals for one concept in one
template. Deriving both from one key removes the class of defect, not the instance.

**Alternatives rejected**:
- *Rename the canonical name to `shell_command`.* More existing agent YAMLs use `shell_command`, but
  renaming makes the prompt catalog and every non-generated consumer wrong instead, trading one
  mismatch for another.
- *Accept both as canonical.* Two names for one tool is how the drift started.

### D-3: `ToolResolver` as a port, mirroring `ExecutionEngine`

**Decision**: New `team_maker/ports/tool_resolver.py` defining an ABC that maps a validated
declaration to a runtime instance, with `team_maker/adapters/tools/package_tool_resolver.py` as the
package-backed implementation. The engine receives a resolver, not a path.

**Rationale**: The repo already separates `ports/execution_engine.py` from
`adapters/runtime_crewai/` under AD-6, and `ports/runtime_engine.py` shows the codebase deliberately
keeps two non-colliding ports rather than overloading one. Following the established pattern keeps
module loading behind one testable boundary and lets tests substitute a fake resolver with no
package on disk.

**Alternatives rejected**:
- *Add `package_path` to `GeneratedTeam` and import `tools.py` inside `_build_agent`.* Smallest diff,
  but puts arbitrary module loading in the engine with no policy seam — structurally the same mistake
  as RC-10, where a risky tool implemented its own execution policy.
- *Resolve tools in `executor.run_team_package` and pass instances to `engine.run`.* Changes the
  `ExecutionEngine.run` signature, which AD-6 and the port's own docstring treat as stable, and
  couples the executor to CrewAI instance types.

### D-4: Thread the resolver, not the path, and keep `ExecutionEngine.run` stable

**Decision**: `run_team_package` constructs the resolver from `package_path` and passes it to the
engine as an optional constructor argument (`CrewAIExecutionEngine(tool_resolver=...)`), leaving the
`run(team, credentials, goal)` signature untouched.

**Rationale**: The port docstring states the signature deliberately does not change to add
capability, citing AD-13. A constructor argument adds the capability without touching the contract
every existing caller and test depends on, and keeps FR-048 (unrelated behaviour unchanged) cheap to
honour.

**Alternatives rejected**:
- *Add a `tools=` parameter to `run()`.* Breaks the port contract and every existing engine test.
- *Store the resolver on `GeneratedTeam`.* Puts a live, environment-dependent object on a dataclass
  the audit describes as plain data, and it would be serialized into places it must not go.

### D-5: Consume the tool events already captured, rather than adding a capture path

**Decision**: Extend `transcript_capture.py`'s `_on_tool_started` / `_on_tool_finished` to record a
`ToolReceipt` for every tool usage, keeping the existing delegation branch intact. Receipts accumulate
alongside the transcript and land on `RunResult` as a new additive field.

**Rationale**: Both handlers already fire, already normalize arguments via `_as_args_dict`, and
already sit behind the documented api-key redaction guard. Today they `return` early unless the event
is a delegation, discarding everything else. The recorder is built; only consumption is missing —
exactly as RC-11 states. Reusing the redaction guard is also how FR-029 gets satisfied for free.

**Alternatives rejected**:
- *A separate event subscriber for receipts.* A second subscription to the same process-global bus,
  with its own lifecycle to unwind on partial registration — the failure mode `_subscribe` already
  documents and guards against.
- *Derive receipts from the transcript after the run.* The transcript intentionally drops
  non-delegation tool events, so the information is already gone by then.

### D-6: `RunResult` gains receipts additively; the completion rule is a separate module

**Decision**: `RunResult` gets `tool_receipts: list[ToolReceipt] = field(default_factory=list)` and
`unevidenced_capabilities: list[str] = field(default_factory=list)`. The rule that reads them lives
in a new `team_maker/runtime/completion.py`.

**Rationale**: `RunResult`'s docstring establishes the additive-widening convention twice already
(`transcript` in Story 1.7, `error` in Story 4.4), and both defaulted so existing callers were
unaffected. Following it keeps FR-048 honest. The rule is separate because it is policy, not data,
and it must be unit-testable without constructing a run.

**Alternatives rejected**:
- *Set `error` when a capability is unevidenced.* Overloads a field whose docstring defines it as a
  run that failed partway; an unevidenced completion is a distinct outcome and callers need to tell
  them apart.
- *Enforce the rule inside the engine.* Makes it CrewAI-specific and unreachable for any future
  engine, and unverifiable without the whole run path.

### D-7: Mandatory sandbox enforced in the generated template, with the policy defined in-package

**Decision**: `team_maker/tools/policy.py` owns `ExecutionPolicy`, `MountAllowlist` and the
dangerous-path floor. `tools.py.j2` renders a single `_execute_sandboxed` path with the
`SANDBOX_ENABLED` toggle removed entirely, `docker_runner` routed through it like every other risky
tool, and mount arguments validated against the rendered allowlist before any container starts.

**Rationale**: FR-012 forbids an opt-out, so the toggle is deleted rather than defaulted to true — a
default can be overridden, an absent mechanism cannot. Defining the policy in the factory and
rendering it into the package keeps one definition of "dangerous" for both the in-product run path
and the standalone package, which is the divergence (FR-025) this feature exists to close.

**Alternatives rejected**:
- *Default `SANDBOX_ENABLED=true`.* An environment variable that disables sandboxing is precisely the
  permissive fallback FR-009 and Constitution II forbid.
- *Enforce only at the runtime boundary, leaving the template as-is.* The generated package runs
  standalone with no runtime boundary in the loop — the escape stays reachable there.

### D-8: Dangerous-path exclusion evaluated after resolution, as a deny-floor

**Decision**: Mount validation resolves the host path fully (symlinks, relative segments, case and
drive normalization) and then tests it against a deny list that no allowlist entry can override.
Floor: host root, user home directories, the Docker socket, device paths, system paths. Read-only
unless the operator's entry explicitly marks the mount writable.

**Rationale**: FR-016 requires post-resolution evaluation specifically so a symlinked allowlist entry
cannot launder a dangerous path. Ordering matters: allow-check then deny-check, with deny winning,
means an operator cannot widen their way into an escape by mistake.

**Alternatives rejected**:
- *Allowlist only, no deny floor.* One over-broad operator entry re-arms the escape the atomic Step 2
  exists to disarm.
- *Deny floor only, no allowlist.* Cannot express the legitimate case, and FR-014 requires
  allowlist-gated mounts.

### D-9: The migration report is a read-only CLI subcommand

**Decision**: `team_maker/tools/migration.py` implements the scan; it surfaces as a CLI subcommand
that walks a directory of packages, reads `agents/*.yaml`, and prints affected packages only. It
opens no file for writing.

**Rationale**: FR-040 and FR-042 require advisory-only and reproducible-without-side-effects. A
read-only scanner satisfies both by construction rather than by discipline. The CLI already has a
command group, so this adds a subcommand without touching existing command behaviour (FR-048).

**Alternatives rejected**:
- *An auto-fix flag.* Directly prohibited by FR-040.
- *Fold the report into `validate`.* `validate` operates on one package; the report's value is the
  cross-package inventory, and coupling them would make the inventory a side effect of validation.

### D-10: Authorization is a separate concern from the mount allowlist

**Decision**: A new `team_maker/tools/authorization.py` owns `AuthorizationPolicy`, evaluating the
three necessary conditions of FR-050 — assigned to team, canonical, operator-authorized. The mount
allowlist stays in `policy.py` and governs mounts *within* an already-authorized execution.

**Rationale**: The requirements-quality review found authorization defined only for mounts, leaving
Constitution II's "explicitly authorized" condition unowned. Keeping them separate means a RISKY tool
can be denied outright without reasoning about mounts at all, and the deny-by-default posture of
FR-052 has one obvious home.

**Alternatives rejected**:
- *Extend `MountAllowlist` to cover tool authorization.* Conflates "may this tool run" with "what may
  it see", which is how the original gap arose.
- *Authorize inside the resolver.* Resolution answers "can this become an instance"; authorization
  answers "is it permitted to". Merging them makes an unauthorized tool indistinguishable from a
  missing one in diagnostics (FR-060).

### D-11: Stage-deterministic rejection replaces a single validation entry point

**Decision**: Validation is invoked at three named stages with distinct, specified outcomes —
compose (visible user rejection, FR-056), build (package refused, FR-057), pre-run (hard fail,
FR-058) — sharing one `validate_declarations` core so the verdict cannot differ between stages.

**Rationale**: FR-003's original "reject or explicitly surface" permitted two behaviours and named no
stage. A shared core with stage-specific reporting keeps the verdict single-sourced while making each
stage's behaviour deterministic.

**Alternatives rejected**:
- *Validate once at authoring only.* A hand-edited or third-party package never passes through
  compose, so the gate would be skippable.
- *Independent checks per stage.* Three checks drift, which is precisely RC-3.

### D-12: Requiredness is a property of the task, not the tool

**Decision**: `TaskSpec` gains a declaration of which capabilities are *required*. The completion rule
reads only that set. Availability stays a property of the agent.

**Rationale**: FR-027's original wording keyed on "declares an external capability", which read as
every tool on the agent. An agent may reasonably carry a tool it does not need for a given task.
Putting requiredness on the task matches where the obligation actually lives, and FR-064's
"successful receipt" requirement then attaches to a claim rather than to mere availability.

**Alternatives rejected**:
- *Infer requiredness from the task description.* Inferring intent from free text is the class of
  mistake this whole feature exists to remove.
- *Treat every declared tool as required.* Blocks completion on legitimately unused optional tools.

### D-13: Known-but-unavailable is a third state

**Decision**: The catalog distinguishes three states — unknown (not in catalog), known-and-available,
known-but-unavailable (canonical, but an optional dependency or credential is absent here). Build
emits the requirement into the package; pre-run validates it.

**Rationale**: The review found FR-010 and FR-023 both plausibly covering a conditionally-registered
tool, with FR-038 promising such packages stay compatible. Three states resolve the conflict: a
missing implementation is a catalog defect (build failure), a missing prerequisite is an environment
condition (pre-run failure), and neither is silently tolerated.

**Alternatives rejected**:
- *Treat unavailable as unknown.* Would fail packages that are correct, just under-provisioned.
- *Treat unavailable as acceptable.* Reintroduces the silent-absence path that produced the
  fabricated results.

### D-14: Safe identifiers are assigned by the operator alongside the allowlist

**Decision**: Each mount allowlist entry carries an operator-defined alias. User-facing surfaces and
receipts name the alias; where none exists, a stable sanitized identifier is derived. Raw resolved
paths appear only in operator-scoped diagnostics.

**Rationale**: FR-017 requires naming the rejected mount and FR-029 forbids leaking secrets; a raw
host path in an API error sits between them. Binding the alias to the allowlist entry means the
operator who authorizes the path also names it, so no separate mapping can drift.

**Alternatives rejected**:
- *Hash the path.* Stable and safe, but useless to the operator reading the error.
- *Omit the identifier entirely.* Makes the refusal undiagnosable, violating Constitution II's
  observable-refusal requirement.

### D-15: Sandbox controls are rendered into the package, not read from the environment

**Decision**: Network posture, timeout and resource limits are rendered into the generated package
from operator policy at build time, with restrictive defaults when policy is silent. No environment
variable can relax them at run time.

**Rationale**: FR-076 requires agents be unable to relax controls, and FR-078 requires a restrictive
default. An environment-read control is exactly the `SANDBOX_ENABLED` mistake (RC-10) in a new
costume: anything the process environment can set, a sufficiently capable agent path can influence.

**Alternatives rejected**:
- *Read limits from environment at run time.* Same shape as the defect being removed.
- *Hardcode limits with no operator control.* Unworkable across deployments, and FR-078 explicitly
  contemplates operator adjustment within enforced bounds.

---

## Unknowns resolved by source reading

| Question | Answer | Source |
|---|---|---|
| Can the engine reach the package? | No. `GeneratedTeam` has no path field; `engine.run(team, credentials, goal)` carries none | `domain/models.py:111-130`, `runtime/executor.py` |
| Are tool events captured today? | Subscribed and handled, then discarded unless the event is a delegation | `transcript_capture.py:239-240, 402, 419` |
| Where can a test observe the constructed agent? | Via the captured `Crew` from `_install_fake_kickoff` | `tests/unit/adapters/test_crewai_execution_engine.py:70` |
| Which starter-team names are phantom? | `diagram_generator`, `text_analyser`. `code_reader` and `web_search` are canonical | `templates/education/template.py:38,55,74` vs `prompts.py:12-62` |
| Does credential resolution need changing? | No. Tool credentials resolve on a separate path; `preflight.check_credentials` is untouched | `runtime/preflight.py`, `ports/execution_engine.py` docstring |
| Does the CrewAI pin move? | No. Nothing in this feature requires a version change; AD-7's conformance gate is not triggered | `pyproject.toml` runtime extra |

## Amendment impact on the plan (2026-08-29)

Amendments 1-6 add requirements but **do not change the audit §9 dependency order**. Placement:

| Amendment | Lands in | Why there |
|---|---|---|
| 2 stage-deterministic rejection | Step 1 | It is the shape of the catalog gate |
| 4 conditional availability | Step 1 (build side) + Step 6 (pre-run side) | Split follows where each check runs |
| 1 authorization policy | Step 2 (policy module) + Steps 3-4 (pre-run evaluation) | Policy is part of the atomic unit; evaluation needs the resolver |
| 5 safe identifiers | Step 2 | Inside the atomic unit — refusal messages ship with the refusals |
| 6 sandbox controls | Step 2 | Explicitly folded into FR-018's atomic unit |
| 3 required vs available | Step 5 | It is the completion rule's shape |

Net effect on Step 2: it grows. It was already the largest unit and remains unsplittable.

## Open risks carried into `/speckit-tasks`

1. **Step 2 is the largest single unit and cannot be split.** FR-018 is binding. Task generation must
   not decompose it into independently mergeable pieces; internal ordering is fine, partial merge is
   not.
2. **`tests/support/team_factories.py:32` is shared.** Changing the `tools=[]` default (FR-035) may
   perturb tests that assume no tools. Step 0 should introduce a tool-carrying factory variant rather
   than flipping the shared default, then reassess once Step 3-4 lands.
3. **Sandbox availability in CI.** FR-013 makes an unavailable sandbox a refusal. The
   security-regression test for fail-closed must assert the refusal, and CI must not be configured to
   skip it when no container runtime is present — a skipped fail-closed test is the weakening
   Constitution V prohibits.
