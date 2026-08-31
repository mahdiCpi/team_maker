# Quickstart: Validating the P0 Tool Execution Integrity Remediation

**Date**: 2026-08-29 | **Plan**: [plan.md](./plan.md) | **Revision**: v3 (post Amendments 1-7 and analyze remediation)

How to prove each step works, in the order audit §9 requires. Every step is **red-first**: the
validating test must be demonstrated failing before the change, then passing after (Constitution IV,
FR-036). A step whose test never failed has not been validated — it has been asserted.

## Prerequisites

```bash
python -m venv .venv
.venv/Scripts/activate          # Windows;  source .venv/bin/activate on macOS/Linux
pip install -e ".[dev]"         # factory + CrewAI runtime + test tooling
```

A container runtime is needed for the sandbox tests. **Its absence is not a reason to skip them** —
`test_sandbox_fail_closed.py` asserts the refusal, so it is meaningful precisely when no runtime is
present. Skipping it is the weakening Constitution V prohibits.

No API keys are required. Every test below uses the offline interception harness; no real LLM call
and no network request is made.

---

## Red-first is required at every step

Each step below opens with a red task whose failure must be recorded before the fix, and closes with
a green task that diffs against it (FR-036, Constitution IV):

| Step | Red | Green |
|---|---|---|
| 0 | T008 → `evidence/step0-red.txt` | T110 |
| 1 | T011 → `evidence/step1-red.txt` | T042 |
| 2 | T043 → `evidence/step2-red.txt` | T096 |
| 3-4 | T008 (the oracle is this step's reproduction) | T110 |
| 5 | T114 → `evidence/step5-red.txt` | T127 |
| 6 | T128 → `evidence/step6-red.txt` | T139 |

---

## Step 0 — the oracle must fail first (US1, RC-12, FR-034)

The whole sequence rests on this. Run it **before** any other change.

```bash
# Expected: FAIL. The engine drops tools, so the constructed agent carries none.
.venv/Scripts/python.exe -m pytest tests/unit/adapters/test_crewai_execution_engine.py -k tools -v
```

**Expected**: red. An agent declaring `tools=["shell"]` is constructed with no matching tool.

If this passes before Step 3-4 lands, the test is not exercising the defect — fix the test, not the
product. The oracle hooks through `_install_fake_kickoff`, which captures the `Crew`; the agents are
reachable as `captured[0].agents[i].tools`.

> Note: the audit points at `tests/support/crewai_interception.py` for this. That module patches
> `BaseLLM.call` and never touches `Agent` — see research.md C-1.

---

## Step 1 — canonical catalog (US2, RC-3)

```bash
.venv/Scripts/python.exe -m pytest tests/unit/tools/ -v
```

**Validates**: invented names rejected with their source surface named; `suggested_tools` and
proposed credential variable names gated; model-authored descriptions discarded; aliases rejected as
declarations.

**Single-source check** — no hardcoded tool-name list may survive outside the catalog:

```bash
grep -rn "AVAILABLE_TOOLS\|_REGISTRY_TOOLS\|TOOL_REGISTRY" team_maker/ --include=*.py --include=*.j2
```

**Expected**: every hit either lives in `team_maker/tools/catalog.py` or derives from it. `"linter"`
appears nowhere.

**Starter team** — the primary onboarding path must pass its own new gate:

```bash
.venv/Scripts/python.exe -m pytest tests/unit/templates/ -v
```

**Stage determinism — compose and build only** (Amendment 2, FR-056/FR-057/FR-059; F1):

```bash
.venv/Scripts/python.exe -m pytest tests/unit/tools/test_validation.py -k "stage or fallback" -v
```

**Expected**: compose rejects visibly, build refuses to produce a package, each rejection names tool,
agent, stage and one reason class, and neither stage substitutes, stubs, skips or falls back.

> **Preflight is deliberately not verified here.** Preflight enforcement lands in Step 6 (T136), so
> the third leg of stage determinism is verified there by T139. Phase 3 only defines the contract
> preflight consumes.

**Migration report** — read-only, affected packages only:

```bash
# Inspect, change nothing
.venv/Scripts/python.exe -m team_maker.cli tools migration-report generated_teams/

# Prove it wrote nothing
git status --porcelain generated_teams/
```

**Expected**: findings for affected packages only; `git status` clean; all-canonical packages absent
from the output; ambiguous names flagged for human decision with no suggestion.

---

## Step 2 — ATOMIC: stub removal + execution policy (US3, RC-4 + RC-10)

> Ships as **one** unit (FR-018). Do not validate or merge any part of this in isolation. Splitting
> stub removal from policy enforcement arms a host escape.

```bash
.venv/Scripts/python.exe -m pytest tests/security/ -v
```

**Validates, all permanent regressions**:

| Assertion | File |
|---|---|
| One definition per tool; registry resolves to the real implementation; no duplicate keys | `test_no_stub_shadowing.py` |
| Sandbox unavailable → risky tool refused, naming the reason | `test_sandbox_fail_closed.py` |
| No environment variable or config disables sandboxing | `test_sandbox_fail_closed.py` |
| Non-allowlisted mount refused, with no degrade-to-running-without-it | `test_mount_allowlist.py` |
| Allowlisted path resolving to a dangerous location refused — deny beats allow | `test_mount_allowlist.py` |
| Allowlisted symlink to a dangerous location refused after resolution | `test_mount_allowlist.py` |
| Allowlisted mount without explicit `writable` is read-only | `test_mount_allowlist.py` |
| Declaring a RISKY tool without operator enablement is denied | `test_tool_authorization.py` |
| Absent, empty and malformed authorization policy each deny every RISKY tool | `test_tool_authorization.py` |
| No agent-supplied input changes an authorization outcome | `test_tool_authorization.py` |
| Network egress denied unless operator policy permits | `test_sandbox_controls.py` |
| Every execution carries an enforced timeout; agent values cannot extend it | `test_sandbox_controls.py` |
| CPU, memory, process-count, output-size and storage limits all enforced | `test_sandbox_controls.py` |
| Exceeding a limit terminates and records a failed receipt naming the limit | `test_sandbox_controls.py` |
| No raw resolved host path appears in any user-facing surface or receipt | `test_safe_error_identifiers.py` |
| A rejected mount is named by operator alias or sanitized identifier | `test_safe_error_identifiers.py` |

**Manual verification against the reproduction the audit recorded**:

```bash
# Generate a package declaring risky tools, then inspect it
.venv/Scripts/python.exe -m team_maker.cli create examples/<a-request-with-risky-tools>.yaml
grep -n "@tool(" generated_teams/<pkg>/tools.py | sort | uniq -c
grep -n "SANDBOX_ENABLED\|subprocess.run" generated_teams/<pkg>/tools.py
```

**Expected**: each `@tool` name appears exactly once; no `SANDBOX_ENABLED`; no `subprocess.run` outside
the single enforced path. Compare against `generated_teams/devops_team/tools.py`, where
`shell_command`, `test_runner` and `docker_runner` each appear twice today (real at `:67/:111/:123`,
stub at `:229/:235/:241`).

**Amendment 6 check** — the generated package must carry enforced controls, not ad-hoc values:

```bash
grep -n "timeout\|network\|memory\|cpu\|max_output" generated_teams/<pkg>/tools.py
```

**Expected**: one control set rendered from operator policy, matching the authoritative table in
[data-model.md §10](./data-model.md) — process `120s`, container `300s`, HTTP `30s`, network `none`,
CPU `1.0`, memory `512 MiB`, processes `128`, output `1 MiB`, storage `1 GiB`.
Compare against the current template, which carries **five** hardcoded timeouts (`120`, `60`, `300`,
`30`, `15`) and a `network` default of `bridge`.

> **Behaviour change to expect**: network egress flips from `bridge` to `none`. Teams whose tools
> reach the network will fail until the operator permits `bridge`. This is approved (FR-073), not a
> regression.

---

## Step 3-4 — the resolution boundary (US4, RC-5)

```bash
# The Step 0 oracle now passes — this is the moment it flips
.venv/Scripts/python.exe -m pytest tests/unit/adapters/test_crewai_execution_engine.py -k tools -v

# The boundary itself
.venv/Scripts/python.exe -m pytest tests/unit/runtime/ tests/unit/adapters/ -v
```

**Validates**: agents constructed with resolved instances; unresolvable declaration refuses the run
naming the tool; no partial resolution; tool credentials resolved without touching provider routing
or credential precedence; the port imports no crewai.

**Path parity** — the divergence that started this:

```bash
.venv/Scripts/python.exe -m pytest tests/integration/ -k parity -v
```

**Expected**: the same team run through the product and run standalone attaches the same tool names.

**Regression guard on what must not move**:

```bash
.venv/Scripts/python.exe -m pytest tests/conformance/ -v
```

**Expected**: provider routing and the CrewAI pin behave exactly as before. This suite is the AD-7
gate; it must not be modified by this feature.

---

## Step 5 — receipts and the completion rule (US5, RC-11)

```bash
.venv/Scripts/python.exe -m pytest tests/unit/runtime/ -k "receipt or completion" -v
```

**Validates**: a receipt per execution with all required fields; a **required**-but-uninvoked
capability fails the claim; an optional unused tool does **not** block completion (Amendment 3,
FR-063); a recorded failure does not satisfy the success rule and does not support a claimed action
(FR-064); a legacy task with no requiredness marking treats declared capabilities as optional; tasks
requiring no capability are unaffected; existing delegation transcript entries unchanged.

**The truthfulness check** — the scenario the audit's transcripts show:

```bash
.venv/Scripts/python.exe -m pytest tests/integration/ -k evidence -v
```

**Expected**: a task that declares `test_runner`, where the model asserts the tests passed without
invoking it, is **not** reported successfully complete, and `unevidenced_capabilities` names
`test_runner`.

**Secret safety**:

```bash
.venv/Scripts/python.exe -m pytest tests/security/ tests/unit/test_secret_leakage_regression.py -v
```

---

## Step 6 — validation and preflight (US6, RC-8)

```bash
.venv/Scripts/python.exe -m pytest tests/unit/test_validation.py tests/unit/runtime/test_preflight.py -v
```

**Validates**: a package declaring an unavailable capability fails validation naming the tool; missing
tool credentials caught before the run starts; mount configuration re-checked at run time; the
generated report reflects failures instead of `_No issues found._`.

**F1 completion** — the third leg of stage determinism, deferred from Step 1:

```bash
.venv/Scripts/python.exe -m pytest tests/unit/runtime/test_preflight.py -k determinism -v
```

**Expected**: the same invalid declaration rejected at compose and build is hard-failed at preflight
with the identical reason class (T139).

**Amendment 4 check** — the three availability states must stay distinct:

```bash
.venv/Scripts/python.exe -m pytest tests/unit/tools/ tests/unit/runtime/test_preflight.py -k "availab or prerequisite" -v
```

**Expected**: an unknown name is rejected at build; a canonical tool with no implementation fails the
build; a canonical tool whose optional dependency is absent *here* passes build (emitting its
requirement) and hard-fails at pre-run naming the missing prerequisite. None of the three produces a
stub or a fallback.

**Against the four packages the audit caught reporting a false pass**:

```bash
for pkg in fusion_policy_research_team tagline_forge scifi_story_team devops_team; do
  echo "--- $pkg"
  grep -n "Validation status" "generated_teams/$pkg/generation_report.md"
done
```

**Expected**: packages with unavailable capabilities no longer report `✅ PASSED`. All four report
`✅ PASSED` with `_No issues found._` today.

---

## Full suite

```bash
.venv/Scripts/python.exe -m pytest -v
```

**Expected**: green, including the pre-existing suite. Per SC-011, teams declaring no tools show no
behavioural change and existing packages whose tools all resolve safely continue to build, validate
and run unchanged.

## Success criteria coverage

| Criterion | Validated by |
|---|---|
| SC-001 declared tools available | Step 3-4 oracle + parity |
| SC-002 nothing invalid reaches execution | Step 1 + Step 3-4 |
| SC-003 no duplicate/shadowed definitions | Step 2 `test_no_stub_shadowing.py` |
| SC-004 no unsandboxed risky execution | Step 2 `test_sandbox_fail_closed.py` |
| SC-005 mount rules | Step 2 `test_mount_allowlist.py` |
| SC-006 no unevidenced success | Step 5 evidence test |
| SC-007 receipts inspectable | Step 5 integration |
| SC-008 no false validation pass | Step 6 four-package check |
| SC-009 oracle red-then-green | Step 0 then Step 3-4 |
| SC-010 no credential leakage | Step 5 secret safety |
| SC-011 compatibility preserved | Full suite |
| SC-012 report scope | Step 1 migration report |
| SC-013 traceability | Review — FR + RC IDs on every change |
| SC-019 control defaults | Step 2 `tests/unit/tools/test_limits.py` (T090) |
| SC-020 pre-remediation packages | Step 3-4 `tests/security/` (T112) |
| SC-014 authorization | Step 2 `test_tool_authorization.py` |
| SC-015 deterministic rejection | Step 1 stage-determinism run |
| SC-016 required vs optional | Step 5 receipt and completion tests |
| SC-017 no raw path leakage | Step 2 `test_safe_error_identifiers.py` |
| SC-018 sandbox controls | Step 2 `test_sandbox_controls.py` |
