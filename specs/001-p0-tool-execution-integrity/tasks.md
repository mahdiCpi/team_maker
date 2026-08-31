---
description: "Task list for P0 Tool Execution Integrity Remediation"
---

# Tasks: P0 Tool Execution Integrity Remediation

**Revision**: v3 — regenerated 2026-08-29 after `/speckit-analyze` remediation (D1, F1, E1, U1, U2,
E2, I1-I3, B1, B2). Covers FR-001 to FR-086 and SC-001 to SC-020. Supersedes v2 (130 tasks).

**Input**: Design documents from `/specs/001-p0-tool-execution-integrity/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: REQUIRED. Constitution IV mandates a failing reproduction before every fix; FR-034 and
FR-036 make red-first coverage a delivery condition **for every step**, not only Step 0.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel. Used sparingly and deliberately.
- **[Story]**: US1-US6, mapping to spec user stories.
- Every task carries its audit trace and, where applicable, a verification command.

## Terminology (I1)

This document uses **preflight** for the pre-run validation stage throughout, matching the
implementing module `team_maker/runtime/preflight.py`. Where the spec says "pre-run", it means the
same stage. "Pre-run" is not used here as a separate concept.

## ⚠️ Parallelism policy

Security-sensitive and dependency-ordered work is **never** marked `[P]`.

- **Phase 4 contains no `[P]` markers at all** — one atomic unit, entirely security-sensitive.
- `[P]` appears only on disjoint-file work with no shared state and no security surface: 9 tasks.

## Red-first coverage map (D1, FR-036, Constitution IV)

Every §9 step has a task that demonstrates its defect failing **before** the fix.

| Step | Phase | Red task | Green confirmation |
|---|---|---|---|
| 0 — regression oracle | 2 | **T008** (existing) | T110 |
| 1 — canonical catalog | 3 | **T011** (new) | T042 |
| 2 — atomic policy unit | 4 | **T043** (new) | T096 |
| 3-4 — resolution boundary | 5 | **T008** — the oracle *is* this step's reproduction (RC-5); no second red needed | **T110** |
| 5 — receipts and completion | 6 | **T114** (new) | T127 |
| 6 — validation and preflight | 7 | **T128** (new) | T139 |

**Correction to the analysis report**: it said "five tasks, one per phase" while naming only Phases
3, 4, 6 and 7. **Four** were genuinely missing; the count was wrong, the enumeration was right.
Phase 5 needs no new red because T008 already fails on exactly the defect Phase 5 fixes, and T110 is
its green — a red-first pair spanning two phases, which is why it was easy to miscount.

## Audit trace legend

`RC-n` root cause (audit §9) · `P0-n` blocker cluster (audit §2) · `FR-n` spec requirement ·
`SC-n` success criterion · `D-n` research decision · `C-n` research correction · `A-n` spec amendment ·
`CHK-n` requirements-quality checklist item

---

## Phase 1: Baseline Evidence Capture (No Implementation)

**Purpose**: Record the pre-remediation state so every later "fixed" claim can be checked against a
recorded reproduction (Constitution III and IV). No product code changes.

- [X] T001 Capture the full-suite baseline to `specs/001-p0-tool-execution-integrity/evidence/baseline-suite.txt` via `.venv/Scripts/python.exe -m pytest -v`, committing the output verbatim as the comparison basis for T141 (SC-011)
- [X] T002 [P] Record the four false-pass packages (P0-3, RC-8) to `evidence/baseline-false-pass.txt` — for `fusion_policy_research_team`, `tagline_forge`, `scifi_story_team`, `devops_team` run `grep -n "Validation status" generated_teams/<pkg>/generation_report.md` and confirm each reports `✅ PASSED`
- [X] T003 [P] Record the stub-shadowing reproduction (P0-2, RC-4) to `evidence/baseline-stub-shadowing.txt` via `grep -n "@tool(" generated_teams/devops_team/tools.py`, confirming `shell_command`, `test_runner` and `docker_runner` each appear twice (real at `:67/:111/:123`, stub at `:229/:235/:241`)
- [X] T004 [P] Record the unsandboxed-path reproduction (P0-2, RC-10) to `evidence/baseline-sandbox.txt` via `grep -n "SANDBOX_ENABLED\|subprocess.run" team_maker/codegen/templates/tools.py.j2`, confirming the `"false"` default at `:45` and `docker_runner`'s direct `subprocess.run` at `:130-138`
- [X] T005 [P] Inventory non-canonical tool declarations across all 31 packages (RC-3) to `evidence/baseline-invented-names.txt` via `grep -rn "tools:" -A 6 generated_teams/*/agents/*.yaml`, to be diffed against the Phase 3 migration report
- [X] T006 [P] Record the **five** existing timeout values and the current network default (A-6, U1) to `evidence/baseline-controls.txt` via `grep -n "timeout=" team_maker/codegen/templates/tools.py.j2` and `grep -n "network" team_maker/schema/request.py`, confirming `120`/`60`/`300`/`30`/`15` and `network="bridge"`, matching the table in [data-model.md §10](./data-model.md)

**Checkpoint**: Pre-remediation state recorded.

---

## Phase 2: Foundational — Step 0 Regression Oracle (US1, RC-12)

**Purpose**: Make the defect observable before fixing anything. Audit §9 Step 0.

**⚠️ BLOCKING**: No task in Phase 3 or later may begin until T008 has demonstrated red.

- [X] T007 [US1] **FIRST IMPLEMENTATION TASK** — Add the failing non-empty-tools engine oracle `test_agent_declaring_tools_is_constructed_with_them` to `tests/unit/adapters/test_crewai_execution_engine.py`, building an `AgentSpec` with `tools=["shell"]`, reusing `_install_fake_kickoff` at `:70`, asserting `captured[0].agents[0].tools` contains a matching tool (RC-12, FR-034, C-1 — the audit's pointer to `tests/support/crewai_interception.py` is wrong; that module patches `BaseLLM.call` and never touches `Agent`)
- [X] T008 [US1] **RED — Step 0.** Demonstrate T007 failing and record to `evidence/step0-red.txt` via `.venv/Scripts/python.exe -m pytest tests/unit/adapters/test_crewai_execution_engine.py -k tools -v`, confirming FAIL (FR-036, SC-009). If it passes, the test is not exercising the defect — fix the test, not the product
- [X] T009 [US1] Add a tool-carrying agent factory variant to `tests/support/team_factories.py` rather than flipping the shared `tools=[]` default at `:32` (FR-035, research risk 2)
- [X] T010 [US1] Confirm the rest of the suite is unaffected via `.venv/Scripts/python.exe -m pytest -v`, diffing against `evidence/baseline-suite.txt` (SC-011)

**Checkpoint**: The suite can now see RC-5.

---

## Phase 3: User Story 2 — Canonical Catalog and Stage-Deterministic Rejection (Step 1, RC-3)

**Goal**: One catalog governs tool identity; invalid names are rejected deterministically at compose
and build, with no substitution, stub, skip or fallback.

**Independent Test** (F1-corrected): An invented name is rejected at **compose and build** with a
consistent verdict; an all-canonical declaration is accepted unchanged. **Preflight rejection is
verified in Phase 7 (T139), where preflight enforcement is implemented** — this phase only defines
the contract preflight will consume (T022).

**Contract**: [contracts/tool-catalog.md](./contracts/tool-catalog.md)

- [X] T011 [US2] **RED — Step 1.** Add a failing catalog-gate reproduction to `tests/unit/tools/test_validation.py` asserting a known invented name (`text_summarizer`) is rejected at compose and at build; demonstrate FAIL against current behaviour and record to `evidence/step1-red.txt` (FR-036, RC-3, Constitution IV)

### Catalog core

- [X] T012 [US2] Create `team_maker/tools/__init__.py` and `team_maker/tools/catalog.py` defining frozen `ToolDefinition` (name, description, risk, required_credentials, requires_mounts, aliases) and `RiskClass` per [data-model.md §1](./data-model.md) (FR-001, D-1)
- [X] T013 [US2] Populate `TOOL_CATALOG` in `team_maker/tools/catalog.py` from the 13 real entries in `team_maker/llm/prompts.py:12-62`, setting `risk=RISKY` for `shell`, `code_writer`, `test_runner`, `docker_runner` and `requires_mounts=True` only for `docker_runner` (FR-001, FR-008)
- [X] T014 [US2] Document the RISKY classification criterion in `team_maker/tools/catalog.py` and enforce its inverse — a SAFE tool may not execute host commands, write outside the sandbox workspace, open network connections on its own authority, or control the container runtime (FR-083, closes CHK006, CHK025)
- [X] T015 [US2] Register report-only legacy aliases in `team_maker/tools/catalog.py` — `shell_command`→`shell`, `code_reader_tool`→`code_reader` and the remaining single-candidate names in `contracts/tool-catalog.md`; ambiguous names such as `web_scraper` get NO alias (FR-041, D-2)
- [X] T016 [US2] Write catalog unit tests in `tests/unit/tools/test_catalog.py` asserting one entry per canonical name, no name appearing in another entry's aliases, `"linter"` absent, and every RISKY entry satisfying the FR-083 criterion (FR-001, FR-083)

### Validation core and stage determinism (Amendment 2)

- [X] T017 [US2] Implement `validate_declarations` in `team_maker/tools/validation.py` returning a structured outcome naming each offending tool and its source surface; alias-only matches rejected with the canonical name suggested (FR-002, FR-003, D-2)
- [X] T018 [US2] Define the five reason classes in `team_maker/tools/validation.py` with the distinguishing definitions in FR-060 — unknown, invalid, unresolvable, unauthorized, unsafe — as exactly-one-of values (FR-060, closes CHK010)
- [X] T019 [US2] Make rejections aggregate in `team_maker/tools/validation.py`, reporting every offending declaration in one failure per the collect-don't-short-circuit convention of `team_maker/runtime/preflight.py` (FR-060, FR-023, closes CHK013)
- [X] T020 [US2] Wire compose-stage validation in `team_maker/composer/` so an invalid assignment is **visibly rejected to the user**, not logged, at the point the spec is accepted (FR-056, A-2)
- [X] T021 [US2] Wire build-stage validation in `team_maker/pipeline/runner.py` so no package containing an unknown or unsafe declaration is produced (FR-057, A-2)
- [X] T022 [US2] Define the preflight-stage rejection contract in `team_maker/tools/validation.py` for consumption by `team_maker/runtime/preflight.py` in Phase 7, covering unavailable, unauthorized and unresolvable. **Contract only — enforcement and its verification are T136 and T139** (FR-058, A-2, F1)
- [X] T023 [US2] Ensure no stage substitutes, stubs, skips or falls back on an invalid declaration, in `team_maker/tools/validation.py` and every call site (FR-059, A-2)
- [X] T024 [US2] Ensure every rejection names the offending tool, the declaring agent, the stage and exactly one reason class, in `team_maker/tools/validation.py` (FR-060, closes CHK012)
- [X] T025 [US2] Write stage-determinism tests in `tests/unit/tools/test_validation.py` asserting the same invalid declaration yields a consistent verdict at **compose and build**, and that no fallback path exists at either (FR-056, FR-057, FR-059, SC-015, F1)
- [X] T026 [US2] Write validation unit tests in `tests/unit/tools/test_validation.py` covering every confirmed invented name in `contracts/tool-catalog.md` — `code_reader_tool`, `file_writer_tool`, `shell_tool`, `file_read`, `text_summarizer`, `web_scraper`, `url_reader`, `twitter_search_tool`, `git_account_tool`, `search_tool`, `file_writer` — plus the CrewAI class-name leak `FileReadTool`, `FileWriterTool`, `ScrapeWebsiteTool`, `SerperDevTool` (RC-3, FR-002)

### Conditional availability — build side (Amendment 4)

- [X] T027 [US2] Model the three availability states in `team_maker/tools/catalog.py` — unknown, known-with-no-implementation, known-but-unavailable — as distinct and non-collapsible (FR-065, D-13)
- [X] T028 [US2] Make build validate the catalog definition and emit each tool's dependency and credential requirements into the generated package, in `team_maker/codegen/engine.py` (FR-066, A-4)
- [X] T029 [US2] Write availability-state tests in `tests/unit/tools/test_catalog.py` asserting a canonical tool with a missing optional dependency is never treated as unknown and never fails the build (FR-065, FR-066)

### Converting the drifted copies into derived views

- [X] T030 [US2] Replace the `AVAILABLE_TOOLS` literal at `team_maker/llm/prompts.py:12-62` with a derived `{name: description}` view over `TOOL_CATALOG`, leaving `build_system_prompt` and the Rule 7 text at `:104` intact as guidance only (FR-001, FR-003)
- [X] T031 [US2] Delete the `_REGISTRY_TOOLS` set at `team_maker/schema/request.py:378-382`, including the phantom `"linter"`, and route its membership test through the catalog (FR-001)
- [X] T032 [US2] Extend validation in `team_maker/schema/request.py` to cover per-agent `tools` — the surface the old filter never saw, since it ran only `if not role.get("tools")` (FR-002)
- [X] T033 [US2] Gate model-authored `suggested_tools` names AND their proposed `env_vars` against the catalog in `team_maker/schema/request.py`, closing the path that put `SERPAPI_API_KEY` into a shipped package (FR-004, RC-3)
- [X] T034 [US2] Discard model-authored tool descriptions in `team_maker/schema/request.py` so the catalog description is the sole agent-facing contract (FR-005)
- [X] T035 [US2] Add the single-source regression test to `tests/unit/tools/test_catalog.py` asserting no hardcoded tool-name list exists outside `team_maker/tools/catalog.py`, and that registry key, agent-facing name and catalog name are one string from one source; verify via `grep -rn "AVAILABLE_TOOLS\|_REGISTRY_TOOLS\|TOOL_REGISTRY" team_maker/ --include=*.py --include=*.j2` (FR-001, FR-007, closes CHK017, E2)

### Starter-team correction (narrowly scoped P1-8)

- [X] T036 [US2] Correct the two phantom tool names in `team_maker/templates/education/template.py` — `diagram_generator` at `:38` and `text_analyser` at `:74`; `code_reader` (`:38,55,74`) and `web_search` (`:55`) are canonical and unchanged (FR-043)
- [X] T036a [US2] **Amendment 8 (discovered during implementation).** Correct the same class of phantom name in `team_maker/templates/software_delivery/template.py` (`DEFAULT_TEMPLATE_ID`) and `team_maker/templates/research_content/template.py`, whose per-role defaults bypass compose-stage validation entirely via `role_based.py:68`. See `implementation-decision-log.md` D-IMPL-002 for the full before/after table and reasoning (FR-044 amended, FR-087)
- [X] T037 [US2] Add `tests/unit/templates/test_template_tool_conformance.py` asserting every built-in template — education, research_content, software_delivery — declares only canonical tool names, parametrized and regression-permanent. **Scope fence unchanged**: tool-name declarations only; no other P1 finding enters here (FR-044, FR-087)

### Migration report

- [X] T038 [P] [US2] Implement the read-only scan in `team_maker/tools/migration.py` producing `MigrationFinding` records per [data-model.md §8](./data-model.md), opening no file for writing (FR-039, FR-040, FR-042, D-9)
- [X] T039 [US2] In `team_maker/tools/migration.py`, set `suggested_replacement` only when exactly one catalog entry lists the declared name as an alias; zero or multiple candidates set `requires_human_decision=True` with no suggestion (FR-041)
- [X] T040 [US2] Exclude all-canonical packages from the report in `team_maker/tools/migration.py` — carrying tool assignments is not a finding (FR-038, FR-039, SC-012)
- [X] T041 [P] [US2] Add the `tools migration-report` subcommand to `team_maker/cli.py` under the existing group, leaving existing command behaviour unchanged (FR-048)
- [X] T042 [US2] **GREEN — Step 1.** Run `.venv/Scripts/python.exe -m pytest tests/unit/tools/ tests/unit/templates/ -v`, confirm T011 now passes, diff against `evidence/step1-red.txt`, then verify the migration report writes nothing via `.venv/Scripts/python.exe -m team_maker.cli tools migration-report generated_teams/` followed by `git status --porcelain generated_teams/` (FR-036, FR-040, FR-042, SC-015)

**Checkpoint**: One catalog is the gate; compose and build reject deterministically.

---

## Phase 4: User Story 3 — Stub Removal, Authorization, Execution Policy and Sandbox Controls (Step 2, RC-4 + RC-10)

> ## 🔒 ATOMIC DELIVERY UNIT — DO NOT SPLIT
>
> **FR-018 binds T043-T096 into one merge**, enforced by the explicit gate at **T096** (E1).
> Removing stub shadowing while leaving policy alone converts a currently-unreachable host escape
> into a reachable one — audit §12's single non-negotiable sequencing constraint.
>
> **Internal review checkpoints (T093-T095) exist so a 54-task unit is reviewable.** They are
> *review* boundaries, not *merge* boundaries. Nothing merges until T096 passes.
>
> **No task in this phase is marked `[P]`.** Every task here is security-sensitive.

**Contract**: [contracts/execution-policy.md](./contracts/execution-policy.md),
[contracts/tool-authorization.md](./contracts/tool-authorization.md)

- [X] T043 [US3] **RED — Step 2.** Add failing reproductions to `tests/security/` asserting (a) the real `shell_command` is reachable and not stub-shadowed, (b) a RISKY tool is refused when the sandbox is unavailable, (c) `mounts="/:/host"` is refused; demonstrate all three FAIL against current behaviour and record to `evidence/step2-red.txt` (FR-036, RC-4, RC-10, Constitution IV)

### Part A — one definition per tool (FR-006, FR-007, FR-010, FR-011)

- [X] T044 [US3] Delete the `{% if suggested_tools %}` stub-emission block at `team_maker/codegen/templates/tools.py.j2:252-270`, which rebinds real tool functions at module level (RC-4, FR-006, FR-010)
- [X] T045 [US3] Remove the `{% for t in suggested_tools %}` registry entries at `team_maker/codegen/templates/tools.py.j2:290-292` that produce duplicate keys already pointing at the stub (RC-4, FR-007)
- [X] T046 [US3] Render `TOOL_REGISTRY` keys AND `@tool(...)` decorator arguments in `team_maker/codegen/templates/tools.py.j2` from the same catalog key, so the `shell` / `shell_command` divergence at `:71` vs `:278` cannot recur (FR-007, D-2, C-2)
- [X] T047 [US3] Make a declared capability with no catalog implementation a build failure in `team_maker/codegen/engine.py`; no stub may be emitted (FR-010)
- [X] T048 [US3] Rewrite the module docstring at `team_maker/codegen/templates/tools.py.j2:5-6` to state the policy actually applied; it currently claims sandboxing "when SANDBOX_ENABLED=true" and names `docker_runner`, the one tool that never did (FR-011)

### Part B — authorization policy (FR-050 to FR-055, FR-085, Amendment 1)

- [X] T049 [US3] Create `team_maker/tools/authorization.py` defining `AuthorizationPolicy` (enabled_tools, source) per [data-model.md §9](./data-model.md) (FR-050, D-10)
- [X] T050 [US3] Implement the three-necessary-conditions rule in `team_maker/tools/authorization.py` — assigned to team AND in catalog AND (SAFE OR operator-enabled) (FR-050, FR-051)
- [X] T051 [US3] Implement RISKY deny-by-default in `team_maker/tools/authorization.py` so absence of explicit operator enablement is a denial, never a permission (FR-052)
- [X] T052 [US3] In `team_maker/tools/authorization.py`, deny every RISKY tool when policy is absent, empty, malformed or unreadable, and emit an operator diagnostic naming the unreadable source (FR-054, FR-085, closes CHK005)
- [X] T053 [US3] Ensure no code path in `team_maker/tools/authorization.py` accepts agent-supplied input that reaches policy; no escalation request, no per-run override (FR-053)
- [X] T054 [US3] Implement the single operator configuration source in `team_maker/tools/config.py` — authorization policy, mount allowlist with aliases and control overrides — resolving an explicit path first then a default project location, mirroring the `team_maker.keys` convention (FR-085, closes CHK001)

### Part C — one enforced execution path (FR-008, FR-009)

- [X] T055 [US3] Create `team_maker/tools/policy.py` defining `ExecutionPolicy`, `MountAllowlist`, `MountAllowlistEntry` and the dangerous-location floor per [data-model.md §4](./data-model.md) (FR-012 to FR-017, D-7, D-8)
- [X] T056 [US3] Route `docker_runner_tool` at `team_maker/codegen/templates/tools.py.j2:130-138` through the single enforced path, removing its direct `subprocess.run` (RC-10, FR-008)
- [X] T057 [US3] Ensure in `team_maker/codegen/templates/tools.py.j2` that every RISKY catalog entry routes through the one path, with no second path and no tool-local `subprocess` call (FR-008, FR-009)

### Part D — mandatory sandbox, fail closed (FR-012, FR-013, FR-081, FR-082)

- [X] T058 [US3] Delete the `USE_SANDBOX` / `SANDBOX_ENABLED` toggle at `team_maker/codegen/templates/tools.py.j2:45` rather than defaulting it to true — a default can be overridden, an absent mechanism cannot (FR-012, D-7)
- [X] T059 [US3] Remove the unsandboxed else-branch at `team_maker/codegen/templates/tools.py.j2:66` (`subprocess.run(command, shell=True, ...)` on the host) (FR-012)
- [X] T060 [US3] In `team_maker/tools/policy.py`, refuse execution when the sandbox cannot be established, stating which condition occurred (FR-013)
- [X] T061 [US3] Enumerate the six sandbox-unavailable conditions in `team_maker/tools/policy.py` — runtime absent, runtime unreachable, image unavailable, container creation failed, a declared control unenforceable, unavailable mid-run — each producing a distinctly named refusal (FR-082, closes CHK020, CHK026)
- [X] T062 [US3] Ensure the enforced path in `team_maker/tools/policy.py` and `team_maker/codegen/templates/tools.py.j2` applies identically to the product run path and the standalone generated package, so neither executes a RISKY tool under weaker controls (FR-081, closes CHK019)

### Part E — mount allowlist (FR-014 to FR-017, FR-079)

- [X] T063 [US3] Implement mount evaluation in `team_maker/tools/policy.py` in the binding order: resolve fully (symlinks, `..`, normalization) → allow-check → deny-check → apply mode (FR-014 to FR-016, D-8)
- [X] T064 [US3] In `team_maker/tools/policy.py`, enforce that agents cannot create, extend or modify the allowlist, that empty or absent permits no mounts, and that a `requires_mounts=False` tool refuses any supplied mount (FR-014)
- [X] T065 [US3] In `team_maker/tools/policy.py`, apply read-only unless the matched operator entry explicitly sets `writable` (FR-015)
- [X] T066 [US3] In `team_maker/tools/policy.py`, enforce deny-wins-over-allow against the dangerous-location floor so an over-broad operator entry cannot re-arm the escape (FR-016)
- [X] T067 [US3] Make the deny floor extendable but never reducible in `team_maker/tools/policy.py` — no configuration, operator action or agent input may remove an entry (FR-079, closes CHK004, CHK024)
- [X] T068 [US3] In `team_maker/tools/policy.py`, ensure a refused mount never degrades to running the tool without it (FR-017)
- [X] T069 [US3] Replace the agent-supplied `mounts` splat in `team_maker/codegen/templates/tools.py.j2` — currently `mounts.split(",")` → `-v host:container`, where `mounts="/:/host"` is full host access — with allowlist-validated mounts only (RC-10, FR-014)

### Part F — safe error identifiers (FR-070 to FR-072, Amendment 5)

- [X] T070 [US3] Create `team_maker/tools/identifiers.py` defining `SafeMountIdentifier` (alias, sanitized_id) per [data-model.md §11](./data-model.md) (FR-070, D-14)
- [X] T071 [US3] Bind the operator-defined alias to each `MountAllowlistEntry` in `team_maker/tools/policy.py`, so the operator who authorizes a path also names it and no separate mapping can drift (FR-070, D-14)
- [X] T072 [US3] Ensure raw resolved host paths appear in no receipt and no user-facing error, message, transcript or report, across `team_maker/tools/policy.py` and `team_maker/tools/identifiers.py` (FR-071)
- [X] T073 [US3] Confine full path detail to operator-scoped diagnostics not exposed through API, UI or receipts, in `team_maker/tools/identifiers.py`; if no such channel exists, drop the detail rather than expose it (FR-072, spec Assumptions)

### Part G — mandatory sandbox controls (FR-073 to FR-078, FR-086, Amendment 6)

- [X] T074 [US3] Create `team_maker/tools/limits.py` defining `SandboxControls` and transcribe the authoritative defaults table from [data-model.md §10](./data-model.md) as the single source no call site may restate (FR-075, FR-078, FR-086)
- [X] T075 [US3] In `team_maker/tools/limits.py`, deny network egress by default (`none`), permitting `bridge` only by operator policy and removing `host` as an option entirely — it defeats the sandbox. **This flips the current `SandboxConfig.network` default of `"bridge"` and will break teams whose tools reach the network** (FR-073, U1)
- [X] T076 [US3] In `team_maker/tools/limits.py` and `team_maker/codegen/templates/tools.py.j2`, enforce the three per-class timeouts from the defaults table — process `120s`, container `300s`, HTTP `30s` — preserving existing behaviour rather than collapsing to one value (FR-074, U1)
- [X] T077 [US3] In `team_maker/tools/limits.py`, enforce the confirmed limits from the [data-model.md §10](./data-model.md) table on every sandboxed execution — CPU `1.0`, memory `512 MiB`, processes `128`, output `1 MiB`, storage `1 GiB` (FR-075, values confirmed 2026-08-29)
- [X] T078 [US3] In `team_maker/tools/limits.py`, ignore rather than merge any agent-supplied value for a control, so no agent input can disable, relax, raise or opt out (FR-076)
- [X] T079 [US3] In `team_maker/tools/limits.py`, terminate execution on any limit breach and record a **failed** receipt naming the limit exceeded; a terminated execution is never success (FR-077)
- [X] T080 [US3] Render the control set into the package at build time from operator policy in `team_maker/codegen/templates/tools.py.j2`, never reading it from the process environment at run time — an environment-read control is `SANDBOX_ENABLED` in a new costume (FR-076, D-15)
- [X] T081 [US3] Treat an unenforceable control in `team_maker/tools/limits.py` as a sandbox-establishment failure that refuses execution, rather than executing without it (FR-082)
- [X] T082 [US3] Detect and refuse a pre-remediation-shape tool module in `team_maker/adapters/tools/package_tool_resolver.py`, with an actionable message and no partial load (FR-084, closes CHK040)

### Permanent security regressions (Constitution V)

- [X] T083 [US3] Create `tests/security/test_no_stub_shadowing.py` asserting one definition per tool name per module, registry resolving to the real implementation, no duplicate keys; verify against `evidence/baseline-stub-shadowing.txt` (RC-4, FR-006, SC-003)
- [X] T084 [US3] Create `tests/security/test_tool_authorization.py` asserting: declaring a RISKY tool without operator enablement is denied; every RISKY tool denied under empty policy; absent/empty/malformed policy each deny; no agent-supplied input changes an outcome (FR-050 to FR-054, SC-014)
- [X] T085 [US3] Create `tests/security/test_sandbox_fail_closed.py` asserting a risky tool is refused for each of the six FR-082 conditions and that no environment variable or config disables sandboxing. **MUST NOT be skipped when no container runtime is present** — it is meaningful precisely then, and a skipped fail-closed test is the weakening Constitution V prohibits (FR-012, FR-013, FR-082, SC-004)
- [X] T086 [US3] Create `tests/security/test_mount_allowlist.py` asserting: non-allowlisted mount refused; allowlisted path resolving to a dangerous location refused (deny beats allow); allowlisted symlink to a dangerous location refused after resolution; deny floor not reducible by configuration; mount without explicit `writable` read-only; refusal never degrades (FR-014 to FR-017, FR-079, SC-005)
- [X] T087 [US3] Create `tests/security/test_sandbox_controls.py` asserting: network denied by default; each per-class timeout enforced and not extendable by agent input; CPU, memory, process, output and storage limits enforced; limit breach terminates and records a failed receipt naming the limit (FR-073 to FR-077, SC-018)
- [X] T088 [US3] Create `tests/security/test_safe_error_identifiers.py` asserting no raw resolved host path appears in any API response, UI error, receipt, transcript or report, and that a rejected mount is named by alias or sanitized identifier (FR-070, FR-071, SC-017)
- [X] T089 [US3] Create `tests/security/test_safe_tool_boundary.py` asserting no SAFE-classified tool executes host commands, writes outside the workspace, opens its own network connections, or controls the container runtime (FR-083, closes CHK025)
- [X] T090 [US3] Write control-default tests in `tests/unit/tools/test_limits.py` asserting a silent operator policy yields the documented default from the table, that no call site restates a value, and that the three per-class timeouts match the preserved existing values (FR-078, FR-086, SC-019)
- [X] T091 [US3] Write authorization unit tests in `tests/unit/tools/test_authorization.py` asserting SAFE tools remain usable without explicit enablement and that the three conditions are each individually necessary (FR-050, FR-052)
- [X] T092 [US3] Add a generated-docstring accuracy test to `tests/unit/templates/` asserting the module docstring matches the policy actually applied (FR-011)

### Internal review checkpoints — review boundaries, NOT merge boundaries

- [X] T093 [US3] **Review checkpoint 1 of 3** — review T044-T054 together in `team_maker/codegen/templates/tools.py.j2`, `team_maker/tools/authorization.py` and `team_maker/tools/config.py`: stub removal and authorization policy. Confirm no stub emission path survives and no agent input reaches policy. **Do not merge** (FR-018)
- [X] T094 [US3] **Review checkpoint 2 of 3** — review T055-T073 together in `team_maker/tools/policy.py` and `team_maker/tools/identifiers.py`: single execution path, mandatory sandbox, mount allowlist, safe identifiers. Confirm no second execution path and no raw path in a user-facing surface. **Do not merge** (FR-018)
- [X] T095 [US3] **Review checkpoint 3 of 3** — review T074-T092 together in `team_maker/tools/limits.py` and `tests/security/`: sandbox controls and the permanent security suite. Confirm every control reads the defaults table and no security test is skippable. **Do not merge** (FR-018)

### Atomic merge gate

- [X] T096 [US3] **GREEN + FR-018 MERGE GATE — Step 2.** Confirm T043 now passes, diff against `evidence/step2-red.txt`, run `.venv/Scripts/python.exe -m pytest tests/security/ tests/unit/tools/ -v`, then verify the delivered change contains **all** of T044-T092 in one merge via `git diff --name-only main...HEAD` — the diff MUST include `team_maker/codegen/templates/tools.py.j2`, `policy.py`, `authorization.py`, `limits.py`, `identifiers.py`, `config.py` and `tests/security/`. **If any is absent, the merge is refused**: partial delivery arms the host escape (FR-018, FR-036, SC-003, SC-004, SC-005, SC-014, SC-017, SC-018, closes CHK051, E1)

**Checkpoint**: Stubs cannot shadow; unauthorized tools cannot run; the host escape is disarmed
before it becomes reachable. **T044-T092 merge together or not at all.**

---

## Phase 5: User Story 4 — Runtime Tool Resolution Boundary (Steps 3-4, RC-5, P0-1)

**Goal**: Declared, authorized tools reach the running agent through one explicit boundary.

**Red-first**: this step's reproduction is **T008** (the Step 0 oracle), which fails on exactly the
defect this phase fixes. T110 is its green.

**Contract**: [contracts/tool-resolver-port.md](./contracts/tool-resolver-port.md)

- [X] T097 [US4] Create `team_maker/ports/tool_resolver.py` defining the `ToolResolver` ABC with `resolve` and `resolve_all`, plus `UnknownToolError`, `UnresolvableToolError` and `ToolPolicyError`, mirroring `ports/execution_engine.py` (FR-019, D-3)
- [X] T098 [US4] Define `ResolvedTool` in `team_maker/ports/tool_resolver.py` per [data-model.md §3](./data-model.md), holding no credential value (FR-022, FR-029)
- [X] T099 [US4] Implement `resolve_all` in `team_maker/ports/tool_resolver.py` with collect-don't-short-circuit semantics matching `runtime/preflight.py` (FR-023)
- [X] T100 [US4] Create `team_maker/adapters/tools/package_tool_resolver.py` as the only code that loads a generated package's tool module, subject to the Phase 4 execution policy (FR-024, D-3)
- [X] T101 [US4] Resolve tool credentials in `team_maker/adapters/tools/package_tool_resolver.py` on a path separate from `preflight.check_credentials`, leaving credential precedence unchanged (FR-022, FR-045)
- [X] T102 [US4] Thread the package path from `team_maker/runtime/executor.py:run_team_package` to the resolver — path threading only; what may then be loaded is governed by FR-024 (FR-021, B2)
- [X] T103 [US4] Add an optional `tool_resolver=None` constructor argument to `CrewAIExecutionEngine` in `team_maker/adapters/runtime_crewai/crewai_execution_engine.py` so all 15 existing engine tests and every existing caller are unaffected (FR-048, D-4)
- [X] T104 [US4] Attach resolved instances in `_build_agent` at `team_maker/adapters/runtime_crewai/crewai_execution_engine.py:177-185` — add the `tools=` argument that has never existed there (RC-5, FR-020)
- [X] T105 [US4] In `team_maker/runtime/executor.py`, refuse to start a run when any declared tool cannot be resolved, naming it, with no partially-resolved run (FR-023)
- [X] T106 [US4] Evaluate authorization at preflight in `team_maker/runtime/preflight.py`, before any agent is constructed, using collect-don't-short-circuit reporting (FR-055, A-1)
- [X] T107 [US4] Ensure unauthorized and unresolvable produce distinct, named reason classes in `team_maker/runtime/preflight.py`, so a diagnostic can tell "not permitted here" from "not available here" (FR-060)
- [X] T108 [US4] Apply the identical preflight gate to hand-edited and third-party packages in `team_maker/runtime/preflight.py` — provenance grants no exemption (FR-080, closes CHK011)
- [X] T109 [US4] Add a port-boundary test in `tests/unit/runtime/` asserting `team_maker/ports/tool_resolver.py` imports no crewai, following the existing engine-agnostic enforcement used for `preflight.py` (FR-019, E2)
- [X] T110 [US4] **GREEN — Steps 3-4.** Run `.venv/Scripts/python.exe -m pytest tests/unit/adapters/test_crewai_execution_engine.py -k tools -v`, confirm the T008 oracle now PASSES, and diff against `evidence/step0-red.txt` to prove the red-to-green transition (FR-036, SC-001, SC-009, Constitution IV)
- [X] T111 [US4] Add a path-parity integration test in `tests/integration/` asserting the same team run through the product and standalone attaches the same tool names, and that a previously generated package whose tools resolve safely still runs standalone with unchanged behaviour per FR-047's definition (FR-025, FR-047)
- [X] T112 [US4] Add a pre-remediation-package test in `tests/security/` asserting an old-shape tool module is refused with an actionable message and never partially loaded (FR-084, SC-020)
- [X] T113 [US4] Verify provider routing and the CrewAI pin are untouched via `.venv/Scripts/python.exe -m pytest tests/conformance/ -v`. This is the AD-7 gate and MUST NOT be modified (FR-046)

**Checkpoint**: Tool-using teams have their tools. P0-1 closed.

---

## Phase 6: User Story 5 — Receipts and the Required-Capability Completion Rule (Step 5, RC-11, P0-4)

**Goal**: A run cannot claim success it cannot evidence — without failing runs over unused optional
tools.

**Contract**: [contracts/receipts-and-completion.md](./contracts/receipts-and-completion.md)

- [X] T114 [US5] **RED — Step 5.** Add a failing reproduction to `tests/unit/runtime/` asserting a task that requires `test_runner` but never invokes it is NOT reported successfully complete; demonstrate FAIL against current behaviour and record to `evidence/step5-red.txt` (FR-036, RC-11, Constitution IV)
- [X] T115 [US5] Define `ToolReceipt` in `team_maker/runtime/results.py` per [data-model.md §5](./data-model.md), holding primitives only, with `output_ref` identifying the corresponding transcript entry rather than carrying output text (FR-026, closes CHK033, AD-9/NFR3)
- [X] T116 [US5] Record a receipt in `_on_tool_started` at `team_maker/adapters/runtime_crewai/transcript_capture.py:402` **before** the `if target is None: return` delegation branch (RC-11, FR-026)
- [X] T117 [US5] Record the outcome in `_on_tool_finished` at `team_maker/adapters/runtime_crewai/transcript_capture.py:419` on the same pattern, preserving existing delegation behaviour exactly (RC-11, FR-026)
- [X] T118 [US5] Route receipt arguments through the existing api-key redaction guard at `team_maker/adapters/runtime_crewai/transcript_capture.py:62`, extended to strip raw host paths (FR-029, FR-071, closes CHK035, D-5)
- [X] T119 [US5] Add `tool_receipts` and `unevidenced_capabilities` to `RunResult` in `team_maker/runtime/results.py`, both defaulted, following the additive-widening convention its docstring already establishes (FR-028, D-6)
- [X] T120 [US5] Add a required-capability declaration to `TaskSpec` in `team_maker/domain/models.py`, distinguishing capabilities a task **requires** from tools merely available to the agent (FR-061, D-12, A-3)
- [X] T121 [US5] Implement the completion rule as a pure function in `team_maker/runtime/completion.py` keying only on required capabilities, per [data-model.md §7](./data-model.md) (FR-027, FR-062, D-6)
- [X] T122 [US5] In `team_maker/runtime/completion.py`, ensure an optional tool that was available but unused never blocks completion and never raises an unevidenced-capability finding (FR-063, A-3)
- [X] T123 [US5] In `team_maker/runtime/completion.py`, require a **successful** receipt to support a claimed external action; a failed receipt satisfies "executed" but not "performed" (FR-064, A-3)
- [X] T124 [US5] In `team_maker/runtime/completion.py`, treat a legacy task carrying no requiredness marking as declaring only optional capabilities, and ignore receipts belonging to a task that did not declare the tool (spec Assumptions, closes CHK031, E2)
- [X] T125 [US5] Write receipt and completion unit tests in `tests/unit/runtime/` covering: receipt per execution with all fields; delegation entries unchanged; required-but-uninvoked capability fails the claim; optional unused tool does not block; failure ≠ success; legacy task defaults to optional; receipt ordering follows the sparse-sequence convention (FR-026 to FR-028, FR-061 to FR-064, SC-016, closes CHK037)
- [X] T126 [US5] Add a permanent redaction regression to `tests/security/` asserting no credential value and no raw host path appears in any receipt; verify via `.venv/Scripts/python.exe -m pytest tests/security/ tests/unit/test_secret_leakage_regression.py -v` (FR-029, FR-071, SC-010, SC-017)
- [X] T127 [US5] **GREEN — Step 5.** Confirm T114 now passes and diff against `evidence/step5-red.txt`, then run the truthfulness integration test in `tests/integration/` — a task **requiring** `test_runner` where the model asserts the tests passed without invoking it is NOT reported successfully complete, `unevidenced_capabilities` names `test_runner`, and the tool-execution record is inspectable from the run result. This is the scenario in `evidence/p4_transcript_fusion_policy_research_team.txt` (FR-036, P0-4, SC-006, SC-007)

**Checkpoint**: Success claims are evidence-backed. P0-4 closed.

---

## Phase 7: User Story 6 — Validation and Preflight (Step 6, RC-8, P0-3)

**Goal**: A green validation result means declared capabilities exist, are authorized and are usable
in this environment.

- [X] T128 [US6] **RED — Step 6.** Add a failing reproduction to `tests/unit/test_validation.py` asserting a package declaring an unavailable capability does NOT report validation passed; demonstrate FAIL against current behaviour and record to `evidence/step6-red.txt` (FR-036, RC-8, Constitution IV)
- [X] T129 [US6] Extend `OutputValidator.validate` in `team_maker/validation/validator.py:41-47` with a declared-capability check alongside the existing four structural checks (RC-8, FR-030)
- [X] T130 [US6] In `team_maker/validation/validator.py`, fail validation for a package declaring a tool that is unknown, invalid, unresolvable, unauthorized or unsafe, naming the tool, the declaring agent and the package (FR-037)
- [X] T131 [US6] In `team_maker/validation/validator.py`, scope that failure to the offending declarations — four safe tools plus one invented one names only the offending declaration, and an all-canonical package is unaffected (FR-038, SC-011)
- [X] T132 [US6] Add tool availability and required-credential checks to `team_maker/runtime/preflight.py`, following its collect-don't-short-circuit and name-the-variable-never-the-value rules (FR-031)
- [X] T133 [US6] In `team_maker/runtime/preflight.py`, validate actual dependencies, credentials, authorization and executability in the current environment, consuming the requirements emitted at build by T028 (FR-067, A-4)
- [X] T134 [US6] In `team_maker/runtime/preflight.py`, make missing prerequisites an actionable hard failure naming what is missing and what would satisfy it, never a stub, skip or fallback (FR-068, A-4)
- [X] T135 [US6] In `team_maker/runtime/preflight.py`, verify every mount the allowlist would permit for the declared tools still satisfies FR-015, FR-016 and FR-079 at run time (FR-032)
- [X] T136 [US6] Wire the preflight-stage rejection contract defined in T022 into `team_maker/runtime/preflight.py`, hard-failing on unavailable, unauthorized and unresolvable declarations (FR-058, F1)
- [X] T137 [US6] Make `team_maker/generators/report.py` reflect validation and preflight failures instead of emitting `_No issues found._` over a broken package (RC-8, FR-033)
- [X] T138 [US6] Write validation and preflight tests in `tests/unit/test_validation.py` and `tests/unit/runtime/test_preflight.py` for all of the above, including the three-availability-state distinction (FR-030 to FR-033, FR-065 to FR-069)
- [X] T139 [US6] **GREEN — Step 6, and the F1 stage-determinism completion.** Confirm T128 now passes and diff against `evidence/step6-red.txt`; then assert in `tests/unit/runtime/test_preflight.py` that the same invalid declaration rejected at compose (T020) and build (T021) is also hard-failed at preflight with the identical reason class — completing the three-stage determinism claim Phase 3 deliberately could not verify (FR-036, FR-056 to FR-058, SC-015, F1)
- [X] T140 [US6] Verify against the recorded false-pass reproduction — rebuild `fusion_policy_research_team`, `tagline_forge`, `scifi_story_team` and `devops_team`, run `grep -n "Validation status" generated_teams/<pkg>/generation_report.md` for each, and diff against `evidence/baseline-false-pass.txt` (P0-3, SC-008)

**Checkpoint**: Green means green. All four P0 clusters remediated.

---

## Phase 8: Polish and Release Readiness

- [X] T141 Run the full suite via `.venv/Scripts/python.exe -m pytest -v` and diff against `evidence/baseline-suite.txt`, confirming no pre-existing test regressed, that teams declaring no tools behave exactly as today (FR-049), and that no unknown, unresolvable, unauthorized or policy-refused tool reached execution (SC-002, SC-011)
- [X] T142 Verify every P0 reproduction recorded under `specs/001-p0-tool-execution-integrity/evidence/` is closed by re-running its original command, not by inspection — a behavioural finding cannot be marked verified unless its original reproduction was exercised (Constitution IV, SC-013)
- [X] T143 Confirm every requirement FR-050 to FR-086 introduced by Amendments 1-7 has at least one implementing task and one test, by cross-checking `specs/001-p0-tool-execution-integrity/tasks.md` against `spec.md` (SC-013 to SC-020)
- [ ] T144 [P] Confirm via `git log --oneline main..HEAD` that every commit cites its FR and RC/P0 audit IDs (Constitution V, SC-013)
- [X] T145 [P] Update `ARCHITECTURE.md` with the `ToolResolver` port, the authorization boundary and the sandbox control set, noting the CrewAI pin and AD-7's conformance gate are unchanged
- [X] T146 Draft the release note in `specs/001-p0-tool-execution-integrity/release-note.md` covering **two** breaking changes: packages declaring unknown, invalid, unresolvable, unauthorized or unsafe tools now fail (FR-037); and sandbox network egress flips from `bridge` to `none`, breaking teams whose tools reach the network (FR-073, U1). Packages whose tools resolve safely are unaffected; the migration report is advisory (FR-037 to FR-042)
- [X] T147 Document the operator configuration surface in `docs/` — the single config source, authorization policy, mount allowlist with aliases, and the sandbox control defaults table — since all four are new operator responsibilities (FR-050, FR-070, FR-078, FR-085, FR-086)
- [X] T148 Confirm the security suite is permanent and unskippable via `.venv/Scripts/python.exe -m pytest tests/security/ -v`, verifying no test is marked skip, xfail or conditionally disabled (Constitution V)

---

## Dependencies

```text
Phase 1 (baseline evidence)
    ↓
Phase 2 — US1 Step 0 oracle  ◀── BLOCKING: T008 must be red before anything else
    ↓
Phase 3 — US2 Step 1 catalog (T011 red → T042 green)
    ↓
Phase 4 — US3 Step 2 ATOMIC (T043 red → T096 merge gate)
    ↓
Phase 5 — US4 Steps 3-4 resolver  ◀── T110 is the green for T008
    ↓
Phase 6 — US5 Step 5 receipts (T114 red → T127 green)
    ↓
Phase 7 — US6 Step 6 validation + preflight (T128 red → T139 green, completes F1)
    ↓
Phase 8 — polish and release readiness
```

**Binding**: this is audit §9 and MUST NOT be reordered or parallelized across phases.

| Edge | Why it cannot be reversed |
|---|---|
| Phase 2 → 3 | Without the oracle, every later step is unguarded against regression (RC-12) |
| Phase 3 → 4 | The catalog is the contract codegen renders its registry from (D-2) |
| Phase 4 → 5 | Wiring the resolver before policy and authorization land arms the host escape (audit §12) |
| Phase 5 → 6 | `ToolUsage` events never fire until tools are attached (RC-11) |
| Phase 6 → 7 | Preflight and validation report on guarantees that must already exist |

**Amendment placement**: A-2 → Phase 3 · A-4 → Phase 3 build side + Phase 7 run side ·
A-1 → Phase 4 module + Phase 5 evaluation · A-5 → Phase 4 · A-6 → Phase 4 · A-3 → Phase 6 ·
A-7 → Phase 3 (FR-083), Phase 4 (FR-079, FR-081, FR-082, FR-085, FR-086), Phase 5 (FR-080, FR-084).

## Parallel Execution

Only 9 of 148 tasks carry `[P]`, all non-security with disjoint files:

- **Phase 1**: T002, T003, T004, T005, T006 — read-only evidence capture, no product code
- **Phase 3**: T038 and T041 — migration module and CLI subcommand, different files, no shared state
- **Phase 8**: T144 and T145 — commit-hygiene review and documentation

**Explicitly NOT parallel**: all of Phase 4 (T043-T096); all resolver, authorization, credential and
receipt work (T097-T126); every task in `tests/security/`.

## Implementation Strategy

**There is no MVP subset.** All four P0 clusters must close before release.

| After | You have | Releasable? |
|---|---|---|
| Phase 2 | A suite that can see the defect | No — nothing is fixed |
| Phase 3 | Invalid names cannot enter at compose or build | No — declared tools still never execute |
| Phase 4 | No shadowing, no unauthorized execution, no host escape, enforced limits | No — tools still not attached |
| Phase 5 | Tool-using teams actually work (P0-1 closed) | No — success claims still unverified |
| Phase 6 | Truthful completion (P0-4 closed) | No — validation still lies |
| Phase 7 | All four P0 clusters closed | **Yes**, subject to Phase 8 |

**Reviewing Phase 4**: use the three internal checkpoints (T093-T095) to review 54 tasks in three
readable passes. They are review boundaries only — T096 refuses the merge unless every part is
present in one diff.

## Task Summary

| Phase | Story | Tasks | Count |
|---|---|---|---|
| 1 Baseline | — | T001-T006 | 6 |
| 2 Step 0 oracle | US1 | T007-T010 | 4 |
| 3 Catalog + stage determinism | US2 | T011-T042 | 32 |
| 4 **Atomic** policy unit | US3 | T043-T096 | 54 |
| 5 Resolver + authorization | US4 | T097-T113 | 17 |
| 6 Receipts + completion | US5 | T114-T127 | 14 |
| 7 Validation + preflight | US6 | T128-T140 | 13 |
| 8 Polish | — | T141-T148 | 8 |
| **Total** | | | **148** |

**Change from v2**: 130 → 148. Added 4 red-first tasks (D1), 1 merge gate (E1), 3 review checkpoints
(T093-T095), 8 Amendment 7 tasks, 1 preflight determinism task (F1) and 1 pre-remediation package
test. Phase 4 grew 43 → 54 and remains unsplittable.
