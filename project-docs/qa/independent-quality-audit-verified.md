# team_maker — Independent Quality Audit (source-verified)

**Version:** v2.1 (revised after external technical review and product-owner review — see §11 changelog)
**Author:** independent re-audit of the Story 4.8 QA round
**Date:** 2026-08-29
**Commit under test:** `b946030` (`b9460305bcc3f61dce51476816ac6bf8a9dc46a9`, branch `story_4_8`)
**Supersedes:** `browser-use-product-quality-audit.md` (deliberately not read; this report is built only from the raw persona finding files, the saved evidence artifacts, and my own reading of the code)

---

## 0. Method, and what "verified" means here

I re-derived every finding from primary sources rather than accepting the persona reports:

| Evidence tier | What I did |
|---|---|
| **Source** | Read the actual implementation for every mechanism a finding claims. Every code citation in this report is one I opened myself. |
| **Artifact** | Read the 31 packages under `generated_teams/` — `tools.py`, `agents/*.yaml`, `docs/*.md`, `requirements.txt`, `run_example.py`, `generation_report.md`. |
| **Transcript** | Read the four saved run transcripts (`evidence/p{2,3,4,5}_transcript_*.txt`, 480 KB total) at the exact line numbers cited. |
| **Live state** | Queried `data/teams.db` directly. |

**Commit hygiene check first:** `b946030` is a docs-only commit, and `git diff --stat b946030 HEAD -- team_maker api web` is **empty**. Every source citation below therefore describes both the commit under test and current HEAD. Nothing has been fixed since.

**Verdicts used:** `CONFIRMED` (mechanism read in source and/or reproduced in an artifact) · `CONFIRMED / ROOT CAUSE CORRECTED` (defect is real, the report's explanation of *why* is wrong) · `PLAUSIBLE` (symptom evidenced, mechanism not established) · `UNVERIFIABLE` (the evidence collected cannot settle the claim in either direction) · `REJECTED` (finding does not survive source review) · `MIS-SCOPED` (real, but severity or framing is wrong).

**Scope limit, stated plainly:** this is a source-and-evidence re-analysis of an existing QA round. It is not a new quality-audit run. Where a claim needs a fresh browser session to settle, I say so rather than inferring.

---

## 1. Headline verdict

**Basic sequential LLM orchestration works well for text-only teams.** Four independent full E2E transcripts show genuinely distinct, sequentially-dependent per-agent work — not one agent's text repeated. Plain-language refinements (tone, cost tier, role merges) reliably reach the real generated artifacts. That is a real achievement and it is not in question.

That claim is deliberately narrow. The same orchestration layer also ignores tools entirely, cannot detect truncation, accepts fabricated completion, treats a downstream agent's invented reconstruction as success, and cannot recover a run after reload. "Sound engine" would overstate it.

Everything wrapped around that orchestration is not shippable:

> **The product cannot presently be trusted to tell the truth about itself.** It reports `Validation: ✅ PASSED` and `Run complete.` for runs in which the requested capability was never loaded, the output was silently cut off mid-sentence, and the shipped documentation states the opposite of the configuration it was generated from.

**Recommendation: do not release.** Four P0 clusters, and they are **sequenced, not parallel** — §2.2 must ship as one change, because fixing its stub-shadowing half in isolation *arms* a currently-unreachable host escape.

| Severity | Count (my triage) |
|---|---|
| **P0 — release blocker** | 4 clusters |
| **P1 — major** | 9 |
| **P2 — moderate** | 9 |
| **P3 — minor** | 6 |
| Unverifiable from the evidence collected | 1 |
| Rejected / mis-scoped from the persona round | 6 |
| Verified positives | 7 |

---

## 2. P0 — release blockers

### 2.1 P0-1 — The product's own Run path never passes tools to CrewAI, so every tool-using team runs with zero tools and fabricates the results

**This is the most important finding in the audit, and the persona round got its root cause wrong.** Personas 4 and 7 correctly observed the *symptom* (agents producing detailed fake research citations and fake Docker pushes) and correctly observed that no tool ever executed. They attributed it to the `NotImplementedError` stubs in the generated `tools.py`. That is not the mechanism. The stubs are never even reached.

`AgentSpec.tools` is parsed off disk and then thrown away:

- `team_maker/runtime/loader.py:93` — `tools=cfg.get("tools", [])`, read from `agents/*.yaml`.
- `team_maker/adapters/runtime_crewai/crewai_execution_engine.py:177-185` — `_build_agent()` constructs `Agent(role=…, goal=…, backstory=…, llm=…, allow_delegation=…)`. **There is no `tools=` argument.** I grepped every adapter and runtime module: the string `tools=` does not appear anywhere in `team_maker/adapters/runtime_crewai/` or `team_maker/runtime/`.

Meanwhile the *generated standalone* package does wire tools correctly — `team_maker/codegen/templates/crewai_runner.py.j2:17,105` (`from tools import get_tools_for` … `tools=get_tools_for(cfg.get("tools", []))`). So there are **two divergent execution paths**, and the one the UI exercises is the one with no tools.

Consequences, all of which the persona reports observed but mis-explained:

- Every "research the web" / "run the tests" / "deploy to staging" team the UI builds and runs executes as a pure text generator, always, regardless of env vars, keys, or stub quality.
- `evidence/p4_transcript_fusion_policy_research_team.txt` (177 KB): zero tool invocations. The final deliverable at line 1631 claims `**Source Base:** … 47 Primary and Secondary Sources (~85,000 words)`. **Verified**: the `web_researcher` stage's own honest disclaimer — *"As my knowledge extends through early 2025…"* — appears at lines 175 and 499 and **nowhere after line 1600**. The one moment of honesty in the whole run is dropped by the downstream summarizer before it reaches the user.
- Persona 7's fabricated Docker registry pushes with SHA256 digests and layer timings are exactly what this mechanism predicts. *Caveat:* that specific run has **no saved artifact** (see §7), so I confirm the mechanism, not the specific output.

**Blast radius is wider than the "obviously tool-shaped" teams.** I counted tool assignments across the built packages. Nine of fifteen examined carry them, including four nobody flagged because their `tools.py` contains no stubs and therefore looked clean:

| Team | Tool assignments | Persona affected |
|---|---|---|
| `code_review_and_testing` | 6 (3 stubbed) | 7 |
| `fusion_policy_research_team` | 6 (3 stubbed) | 4 |
| `devops_team` | 5 (3 stubbed) | 7 |
| `github_automation_team` | 4 (1 stubbed) | 7 |
| `ai_twitter_trends` | 3 (2 stubbed) | 4 |
| `customer_persona_creator` | **8, none stubbed** | 5 |
| `baseline_education_team` | **6, none stubbed** | 10 |
| `competitor_pricing_researcher` | **3, none stubbed** | 2 |
| `thesis_outliner` | **2, none stubbed** | 4 |

**Verdict:** CONFIRMED / ROOT CAUSE CORRECTED. **P0.**

**This is not a one-line fix.** `AgentSpec.tools` is `List[str]`; CrewAI needs tool *instances*. And `GeneratedTeam` (`team_maker/domain/models.py:111-130`) has **no package-path field**, while `executor.run_team_package` calls `engine.run(team, credentials, goal)` — so the engine never receives `package_path` at all. There is no route from `_build_agent` to the package's `tools.py`. What the in-product runtime is missing:

- an authoritative runtime tool resolver (name → instance);
- a safe mechanism for loading a generated package's `tools.py`;
- tool credential resolution (the LLM-provider path exists; the tool path does not);
- sandbox-policy enforcement at the runtime boundary (see §2.2);
- the package path inside `_build_agent`;
- a stable port connecting tool definitions to runtime instances.

The diagnosis is one line. The fix is a runtime tool-resolution boundary.

---

### 2.2 P0-2 — Invented tool names pass every gate; codegen makes stubs shadow the real implementations; and the real implementations bypass the sandbox

**These three must be fixed as one change.** Removing stub shadowing while leaving the sandbox policy alone converts a currently-unreachable host escape into a reachable one. Sequencing matters more than severity here.

#### (a) Tool names are unvalidated LLM output — three drifted allowlist copies, none a gate

| Copy | Location | What it actually does |
|---|---|---|
| `AVAILABLE_TOOLS` (13 names) | `team_maker/llm/prompts.py:12-62` | Prompt text only. Rule 7 at `prompts.py:104` says *"Do not invent tool names"* — advisory, unenforced. |
| `_REGISTRY_TOOLS` (14 names) | `team_maker/schema/request.py:378-382` | Filters a **per-role** `suggested_tools` field, and only `if not role.get("tools")`. Never sees the planner's `agent.tools`. Contains `"linter"`, which exists in neither other copy. |
| `TOOL_REGISTRY` (13 names) | `codegen/templates/tools.py.j2:277-306` | Runtime. Consulted after generation, warns to **stdout**. |

Nothing validates the planner's output against any of them. Confirmed invented names in shipped artifacts: `code_reader_tool`, `file_writer_tool`, `shell_tool`, `file_read`, `text_summarizer`, `web_scraper`, `url_reader`, `twitter_search_tool`, `git_account_tool`, `search_tool`, `file_writer`.

Two invention signatures nobody reported:

- **CrewAI class names leaked into the tools list.** `customer_persona_creator/agents/*.yaml` assigns `FileReadTool`, `FileWriterTool`, `ScrapeWebsiteTool`, `SerperDevTool` — Python class identifiers from `crewai_tools`, not registry keys. I grepped all three allowlists: **zero hits for any of them.**
- **The curated starter template does it too** — see P1-8 (§3.8).

**How the invention happens** — a mechanism the persona round did not identify: `Composer.compose()` calls `provider.complete_structured(response_model=TeamCreationRequest)` (`composer.py:113-117`). That hands the authoring LLM the **entire** `TeamCreationRequest` JSON schema, including `suggested_tools: List[ToolSuggestion]` with free-form `name`, `description`, and `env_vars` (`schema/request.py:100-115, 249-255`). The human-authored `_SCHEMA_RULES` (`composer.py:34-59`) documents only a subset and never mentions `suggested_tools` at all. So the LLM invents tools, invents their env var names, and writes their descriptions — and all three are taken as fact downstream. That is how `SERPAPI_API_KEY` (a name that appears nowhere in the codebase) got into a shipped file.

#### (b) Codegen actively breaks the working tools

`tools.py.j2` emits every invented name as a stub *after* the real definitions, into the same module namespace and the same dict literal (`:258-270` for the functions, `:290-292` for the registry entries). Reproduced in `generated_teams/devops_team/tools.py`:

```python
@tool("shell_command")                       # line 67  — REAL, calls _run_sandboxed
def shell_command_tool(command: str) -> str: ...
@tool("test_runner")                         # line 111 — REAL, runs pytest/npm/go/cargo
def test_runner_tool(path=".", framework="pytest") -> str: ...
@tool("docker_runner")                       # line 123 — REAL, subprocess docker run
def docker_runner_tool(image, command, mounts="") -> str: ...

@tool("shell_command")                       # line 229 — STUB, rebinds the name
def shell_command_tool(input: str) -> str:  raise NotImplementedError(...)
@tool("test_runner")                         # line 235 — STUB, rebinds the name
def test_runner_tool(input: str) -> str:    raise NotImplementedError(...)
@tool("docker_runner")                       # line 241 — STUB, rebinds the name
def docker_runner_tool(input: str) -> str:  raise NotImplementedError(...)

TOOL_REGISTRY: dict[str, Any] = {
    "test_runner":   test_runner_tool,       # already the stub — name was rebound
    "docker_runner": docker_runner_tool,     # already the stub
    ...
    "shell_command": shell_command_tool,     # duplicate key
    "test_runner":   test_runner_tool,       # duplicate key
    "docker_runner": docker_runner_tool,     # duplicate key
}
```

This is **worse than Persona 7 reported.** P7-F4 said the duplicate dict keys let the stub win. In fact the module-level *function rebinding* means both dict entries already point at the stub — the real `shell_command`/`test_runner`/`docker_runner` implementations are **unreachable dead code**, with no way to call them at all.

Two further defects in the same template:

- Registry key mismatch: the real shell tool registers under key `"shell"` (`tools.py.j2:278`), but the prompt catalog and every agent YAML I read use `"shell_command"`. Even without stub shadowing, that lookup misses.
- `ToolSuggestion.description` is rendered verbatim as the stub's **docstring** (`tools.py.j2:262`), which is what CrewAI shows the agent as the tool's contract. So the authoring LLM's own marketing copy becomes a false capability promise *to the agent*. Verified in `generated_teams/fusion_policy_research_team/tools.py:228`: *"This tool fetches current information from the live web — it is NOT limited to training data and WILL surface 2026 content as it is published online."* — attached to a function whose next four lines are `raise NotImplementedError`.

#### (c) The real implementations bypass the sandbox — a landmine that fixing (b) arms

Four verified facts:

1. **The sandbox is off by default.** `USE_SANDBOX = os.environ.get("SANDBOX_ENABLED", "false").lower() == "true"` — `tools.py.j2:45`. So with no env var set, `_run_sandboxed` takes its else-branch: `subprocess.run(command, shell=True, …)` on the **host** (`:66`). `shell_command`, `code_writer` and `test_runner` all route through it.
2. **`docker_runner` ignores the sandbox entirely.** I traced every risky tool. `shell_command`, `code_writer` and `test_runner` call `_run_sandboxed`. `docker_runner` (`:130-138`) calls `subprocess.run(["docker","run","--rm", *mount_flags, image, "sh","-c",command])` **directly**, regardless of `USE_SANDBOX`.
3. **`mounts` is an agent-supplied host-filesystem escape primitive.** `docker_runner_tool(image, command, mounts="")` — all three are tool arguments the LLM fills. `mounts` is split on commas and splatted in as `-v host:container`. `mounts="/:/host"` plus an agent-chosen `command` is full host filesystem access.
4. **The module docstring misstates it.** `tools.py.j2:5-6`: *"Risky tools (shell, code_writer, docker_runner) run inside a Docker sandbox when SANDBOX_ENABLED=true."* It names the one tool that never does.

**Reachability today — and why that is the argument, not a mitigation.** Across all 31 packages, only `devops_team` assigns `docker_runner`, and there it *is* stub-shadowed. So the dangerous code is currently unreachable everywhere. It is **not a live vulnerability. It is a landmine that the (b) fix arms.** A change that removes stub shadowing, or that wires §2.1's resolver, makes `docker_runner` reachable with an agent-controlled `-v` flag on a host where the sandbox defaults to off. That is why (a), (b) and (c) are one blocker and not three.

**Verdict:** CONFIRMED. **P0** (design-blocking: needs an explicit sandbox-policy decision, not just a code change).

---

### 2.3 P0-3 — "Validation: ✅ PASSED" means "the files exist and the YAML parses"

`team_maker/validation/validator.py` is 90 lines and `OutputValidator.validate()` runs exactly four checks (`:41-47`): required top-level files exist; one YAML per agent; one YAML per task; every `.yaml` parses. `team_maker/runtime/preflight.py` adds credential resolution, duplicate-role and task-name checks — and nothing else. I grepped `team_maker/generators/report.py`: it never mentions tools.

So no layer anywhere checks whether a declared capability exists. Verified across four unrelated packages (`fusion_policy_research_team`, `tagline_forge`, `scifi_story_team`, `devops_team`): all four report `**Validation status:** ✅ PASSED` with `_No issues found._` / `_No warnings._`.

On its own this would be a documentation-quality issue. Combined with §2.1 and §2.2 it is the layer that converts silent internal failures into an explicit, confident, false assurance to the user. That promotion from "broken" to "broken and asserting it isn't" is what makes this P0.

**Verdict:** CONFIRMED. **P0.**

---

### 2.4 P0-4 — Nothing requires evidence that a capability actually executed before a task is marked complete

Fixing §2.1 and §2.2 attaches real tools. It does **not** make the product truthful. An LLM handed a working `test_runner` may still decline to call it and assert that the tests passed. Every symptom in §2.1's transcripts would recur with real tools attached, and no layer would notice.

The missing invariant:

> A task that declares an external capability cannot be reported successfully complete unless the required tool executed and produced a recorded receipt — tool name, sanitized input, success/failure, timestamp, output reference.

**Most of the infrastructure already exists.** `team_maker/adapters/runtime_crewai/transcript_capture.py` already subscribes to `ToolUsageStartedEvent` and `ToolUsageFinishedEvent` (`:239-240`), with handlers at `:402` and `:419`, argument normalisation via `_as_args_dict` (`:121`), and a documented api-key redaction guard (`:62`). The receipt recorder is **built**. Two things are missing:

1. Those events never fire, because §2.1 attaches no tools.
2. Nothing consumes them. `RunResult` (`team_maker/runtime/results.py`) carries `final_output`, `task_results`, `transcript`, `error` — no tool-execution record, and no completion rule reads one.

So this is a wiring job on existing infrastructure plus a completion rule, not a from-scratch build. That makes it the cheapest available guarantee of truthfulness, which is why it belongs in the blocker set rather than the backlog.

**Verdict:** CONFIRMED (gap established in source). **P0.**

---

## 3. P1 — major

### 3.1 P1-1 — Nothing detects truncated generation; three runs shipped incomplete deliverables under a green "Complete" banner

CONFIRMED, and I verified the transcripts at the cited lines myself.

- `evidence/p3_transcript_scifi_story_team.txt` lines **289 and 405** — identical cutoff, mid-word: `…and each night M`. Both the live "Message" stream and the "Task completed" restatement, so it is stored content, not a render artifact. Downstream `critical_editor` and `prose_polisher` each silently invented their *own* different ending; the final panel looks flawless.
- `evidence/p5_transcript_pitch_and_critique.txt` — three cutoffs verified at lines **440** (`…isn't 'we`), **912** (`…presumably under 18 months`), **1306** (`…directionally consistent`). The "investor-ready" deliverable never reaches Slide 7 (Team) or Slide 8 (The Ask).
- Persona 1's `weekly_planner` case has screenshots only, no saved text. PLAUSIBLE, same class.

**Root cause, established in source:**

- No `max_tokens` anywhere in the run path. `_build_llm` (`crewai_execution_engine.py:187-206`) passes only `model`, `api_key`, and optional `base_url`. The single `max_tokens=8192` in the repo is on the *authoring* provider (`anthropic_provider.py:60`), which is a different call.
- `finish_reason` appears **nowhere** in project code. (It is available — the installed `crewai/llm.py:302` exposes it.) Truncation is not an exception, so the generated runner's `TOKEN LIMIT` categoriser (`crewai_runner.py.j2:258`) is unreachable for this failure mode.

### 3.2 P1-2 — "My Teams" cannot ever be populated

CONFIRMED at source **and** empirically. `POST /api/teams/save` is fully implemented (`api/routers/teams.py:459-520`, SQLite-backed, path-traversal-guarded). The frontend client (`web/lib/api-client/teams.ts`) exposes exactly four calls — `browse`, `rename`, `delete`, `record-run`. **There is no `save` caller.** The UI can list, rename and delete teams that no code path can create. This is missing wiring, not a missing frontend.

Empirical confirmation I ran myself: `data/teams.db` → `SELECT * FROM teams` returns `[]`, and `data/saved_teams/` is empty — after **31** teams were built into `generated_teams/`.

### 3.3 P1-3 — A run cannot be recovered after any navigation or reload; the run lock is global

CONFIRMED. `api/routers/run.py` declares exactly four routes (`:85, 97, 142, 154`): `GET /teams/{slug}`, `POST ""`, `GET /{run_id}`, `GET /{run_id}/transcript`. **There is no list-runs and no current-run endpoint.** The only copy of `run_id` lives in React state (`workspace-surface.tsx:194`). A reload is therefore unrecoverable by construction — the id is gone and no endpoint can rediscover it.

The lock is genuinely process-wide and non-blocking (`api/runs.py:149-152`, `team_maker/runtime/executor.py:52`) — deliberately, and correctly, because the crewai event bus is a process-global singleton (documented at `executor.py:17-33`). The defect is not the serialization; it is that a *global* lock with **no queue, no ETA, and no way to observe the running run** presents to the user as "your Run button is randomly broken."

### 3.4 P1-4 — Full-spec LLM re-authoring makes prior routing nondeterministic, and has demonstrably discarded it

CONFIRMED, with the strength of the claim corrected from v1.

`ComposerSession.refine()` (`session.py:76-98`) does not mutate state. It serializes the current spec into a prompt and asks for a complete re-emit:

```python
def _build_refinement_intent(self, message: str) -> str:
    ...  f"Current team specification (JSON):\n{current_spec}\n\n"
         f"Requested change: {message}\n\n"
         "Apply ONLY this change and keep everything else … Re-emit the complete, updated …"
```

That prompt *does* instruct preservation. But `_SCHEMA_RULES` (`composer.py:44-47`) simultaneously instructs:

> `llm` (optional): … Set it **ONLY if the user named a model/provider for this specific role**; otherwise **omit the field entirely** so the system default applies.

The two instructions conflict on any turn that names no model. The outcome is therefore **nondeterministic, not guaranteed loss** — and Persona 1's F2 is one confirmed instance of it going wrong: after a successful diversification, the turn *"Choose the best available model for each role"* returned all three roles to `anthropic`, with the chat text byte-identical to a turn that changed nothing.

**Correction from v1:** this root cause covers the observed revert and P5-F2's no-op swap. It does **not** cover `groq` (that is the prompt-filter mechanism — §3.5) or `gpt-999` (unverifiable — §4.5). v1 wrongly attributed both here.

### 3.5 P1-5 — `groq` is rejected in silence, while the system holds a user-ready explanation it never shows

CONFIRMED, and worse than reported. `team_maker/adapters/providers/registry.py:81-128` carries per provider a `runtime_supported` flag and an `unsupported_reason` string that is *exactly* the sentence a user needs:

- `groq` → `"the installed CrewAI has no native groq provider"`
- `xai` → `"the installed CrewAI has no native xai provider"`
- `google` → `"the installed CrewAI needs the 'crewai[google-genai]' extra to call Google directly"`

`Composer._usable_provider_names()` (`composer.py:135-138`) filters these providers *out* of the prompt and discards the reason. Because `groq` therefore never reaches the spec, the build-time `model_substitutions` disclosure (§4.3) has nothing to report either — so a `groq` request is the one case with **genuinely zero disclosure at any stage.** The honest string exists, ten lines from the filter that suppresses it.

### 3.6 P1-6 — Shipped documentation asserts the opposite of the configuration it was generated from

CONFIRMED across 4/4 packages inspected. All are one root cause: `_agent_env_vars` (`team_maker/generators/docs.py:339-352`) treats "no explicit `api_key_env`" as "no key needed":

```python
if not seen:
    return "_No API keys required (local models only)._"
```

But `_SCHEMA_RULES` (`composer.py:57`) tells the authoring LLM *"Never invent an `api_key_env` unless the user explicitly names one"* — so for every normally-composed team the field is `None`, and the doc claims no keys are needed for a team that is 100% routed to keyed cloud providers. The same `or 'N/A'` fallback produces the self-contradictory `| API Key Env Var: N/A |` routing table at `docs.py:229`. In `tagline_forge` this directly contradicts the sibling `README.md` four lines away in the same tree, which correctly says `export ANTHROPIC_API_KEY=…`.

The fix is available in the same repo: `PROVIDERS` (`registry.py:81-128`) holds `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_AI_API_KEY`, etc. per provider. The generator simply never consults it.

### 3.7 P1-7 — Long compose input produces a generic "response this app could not read"

PLAUSIBLE — symptom evidenced, **root cause not established.** The persona report's explanation ("the long input caused the backend to send a response the frontend couldn't parse") is a guess.

What I can establish: `unreadable_response` is the catch-all raised at three points in `web/lib/api-client/transport.ts` (`:179` body is not JSON, `:192` `parseSpec` returned `null`, `:212` the payload is not the `{error:{code,message}}` envelope). Because `parseErrorEnvelope` (`api-types/errors.ts:84-93`) requires that envelope, **any** unhandled server 500 — which FastAPI renders as `{"detail": …}` — surfaces with this exact copy. So the message tells us nothing about the cause, which is itself a diagnosability defect.

Two candidate mechanisms, both cheap to discriminate: (a) an unhandled server exception, or (b) `parseSpec` rejecting the spec — it returns `null` if any task lacks `agent_role` or any role lacks a non-empty `name` (`api-types/compose.ts:133-181`). Timing rules out a client timeout (43 s observed vs `COMPOSE_TIMEOUT_MS = 180_000`). **Needs one repro with the raw response body.**

### 3.8 P1-8 — The shipped starter team references tools that exist in no allowlist (new; not reported by any persona)

`team_maker/templates/education/template.py:38,55,74` **hand-hardcodes** tool assignments including `diagram_generator` and `text_analyser`. I grepped all three allowlists (`AVAILABLE_TOOLS`, `_REGISTRY_TOOLS`, `TOOL_REGISTRY`): **zero hits for either name.** The other two, `code_reader` and `web_search`, are conditionally gated on `OPENAI_API_KEY` / `SERPER_API_KEY` and unavailable in the test environment.

This is not an LLM invention — it is in the curated showcase template a first-time user is steered toward, and it is the exact team Persona 10 used for the brief's required starter-team E2E run. `baseline_education_team` therefore ships six tool assignments, of which two can never resolve under any configuration.

**Verdict:** CONFIRMED. **P1** (separately fixable: edit the template and add the §2.2(a) validation gate that would have caught it).

### 3.9 P1-9 — The test suite cannot observe P0-1, because every runtime fixture sets `tools=[]` (new; answers "why didn't our tests catch this?")

This is the most useful question asked about the audit, and it has an exact answer.

`tests/support/team_factories.py:32` — the shared `AgentSpec` factory every runtime test builds from — sets **`tools=[]`**. With an empty list, an engine that drops the field is *behaviourally identical* to one that honours it. The defect is unobservable by construction.

And the suite is otherwise thorough, which is what makes this a test-oracle problem rather than a coverage problem. `tests/unit/adapters/test_crewai_execution_engine.py` has 15 tests asserting `llm.provider`, `llm.model`, `llm.api_key`, the OpenRouter gateway form, Ollama `base_url` precedence, task-context wiring, hierarchical-process manager selection, absence of interpolation inputs, the goal-injection guard, task-output count mismatch, and kickoff-failure handling. **Not one of them constructs an agent with a tool.**

Non-empty tool lists *do* appear in tests — `test_agent_generator.py:18` (`["code_reader"]`), `test_codegen.py:26,37`, `test_docs_generator.py:17,29`, `test_planner_mapper.py:41`. Every one is a **generator** test: they assert the tool name is correctly *written* into YAML or rendered code. So the suite verifies "the name reaches the file" and never "the tool reaches the agent."

**The untested seam is exactly the codegen→runtime boundary** where P0-1, P0-2 and P0-4 all live. One test — build an `AgentSpec` with `tools=["shell_command"]`, run it through the engine's interception harness (`tests/support/crewai_interception.py`, which already captures the constructed `Agent`), assert the agent has a matching tool — would have failed from the day the engine was written.

**Verdict:** CONFIRMED. **P1** (process finding; it is the reason three P0s shipped, and the cheapest regression guard for the whole §9 fix sequence).

---

## 4. P2 — moderate

### 4.1 The conversational layer has no channel through which to say anything (12 reported findings, one cause)

CONFIRMED. The composer can produce exactly two kinds of reply, and neither can carry information:

1. **Spec exists** → `describeProposal()` (`web/components/composer/proposal.ts:126-129, 168-170`) builds the reply from `rolesInPipelineOrder(spec).map(r => r.name)` and nothing else: `` `Updated: ${names.join(" → ")}.` `` + `` `Anything you would change about ${last}…` ``. It never diffs the spec, never reads provider or model, and has no branch for answering anything.
2. **No spec** → `_generate_clarification()` (`api/routers/compose.py:434-436`) is a **constant**: `return "Please describe the team you want to build and what they should do."`

And the classifier only ever runs when there is no spec yet: `refine()` (`session.py:76-86`) calls `classify_input` **only** `if self.current is None`. Once a team exists, every message — including *"Can this actually search the live internet?"* — is routed as a spec edit. There is no third mode.

This single design fact accounts for **twelve** separately-logged findings: F1, F2 (comms half), P2-F3, P4-F1, P6-F1, P6-F2, P6-F3, P8-F4, P9-F1, P9-F3, CX-F1, CX-F3.

I rate the cluster **P2** as a usability defect — with one exception. **P4-F1 is genuinely severe in context**: a researcher asked the exact protective question (*"or does it only know what's in its training data?"*) immediately before building, and the suppression mechanism swallowed it like any other. I count that not as its own P0 (as the persona report did) but as the aggravating factor that turns §2.1 from a bug into a trust failure.

### 4.2 Every team gets `template: software_delivery_team`, and a better template is unreachable

CONFIRMED. `DEFAULT_TEMPLATE_ID = "software_delivery_team"` (`team_maker/templates/registry.py:18`); `runner.py:106` → `request.template_id or DEFAULT_TEMPLATE_ID`. The composer's `_SCHEMA_RULES` never mentions `template_id`, so the field is always `None` on the conversational path. Verified in 4/4 packages spanning weekly planning, marketing taglines, sci-fi fiction and DevOps. The `research_content` template — whose own docstring calls it *"the flagship showcase team mentioned in the PRD addendum"* — is registered and never selected. **P2** (it drives labels and doc boilerplate; roles/tasks are LLM-composed, so generated agent quality is unaffected).

### 4.3 Model substitutions are disclosed only at Build, never in chat — and the reported inconsistency does not exist

**MIS-SCOPED.** P5-F2 claimed disclosure was *inconsistent* — visible for Persona 3's substitution but hidden for Persona 5's. There is exactly one disclosure path and it is uniform: `_substitutions()` (`api/build.py:94-105`) diffs requested vs resolved labels, and `build-result.tsx:118-137` renders *"One model was not available and a near match was used instead"* with a per-role `requested → resolved` list.

The real, uniform gap: `normalize_team_routings` (`model_resolver.py:186-200`) reports substitutions **only to stderr**, and nothing surfaces them during compose. `_closest()` (`:29-40`) is a `difflib` fuzzy match with no similarity floor. **P2.**

### 4.4 The UI shows providers but never models

CONFIRMED. `web/components/composer/key-check.tsx:169` renders `role.provider` only. A power user who asks for `openai/gpt-4o` and `anthropic/claude-sonnet-4-6` sees two provider names and cannot verify the model until after Build. **P2.** (Persona 6 correctly verified via `generated_teams/market_analysis_team/routing_config.yaml` that the models *are* honoured — a genuine positive.) This defect is also what makes §4.5 unverifiable.

### 4.5 Invalid model names (`gpt-999`) — UNVERIFIABLE in both directions

**Both P6's claim and v1's rebuttal are ungrounded.** The chain:

- `ProviderConfig.model` accepts any string — `normalise_model` (`schema/request.py:49-52`) only calls `.strip()`. So `gpt-999` *could* survive compose into the spec.
- The UI never renders models (§4.4). A chip reading "openai" looks identical whether the model is `gpt-999` or `gpt-4o`. **Persona 6 could not have observed the drop they reported.**
- Persona 6 never built that team, so no `model_substitutions` payload exists — v1's §4.5 asserted Build-time disclosure as a counterfactual it never tested.

**Status:** compose-time behaviour unknown; Build-time disclosure for this exact case unverified. **Settled by one test:** send `gpt-999`, capture the compose response body, Build, capture the build response. Not counted in the P2 tally.

### 4.6 The build directory name is unpredictable before Build

**CONFIRMED / MECHANISM CORRECTED.** P7-F3 called it hidden "name normalization." The actual mechanism: `_adopt_server_output_path` (`api/routers/compose.py:254-268`) derives `output_path` **once, from the first spec's LLM-authored `team_name`**, and pins it for the session's life (`if entry.output_path is None`). The slug (`api/output.py:55-63`) is only ever displayed *after* Build (`build-result.tsx:62`). So the "A directory already exists…" error names a path the user was never shown. P7 also appears to have read the *role* name `github_automation_agent` as the team name — `team_name` is in fact displayed read-only at `spec-editor.tsx:213-217`. **P2.**

### 4.7 Every generated `requirements.txt` is byte-identical, including algorithmic-trading libraries

CONFIRMED, and stronger than reported. `_render_requirements()` (`team_maker/pipeline/runner.py:296-313`) unconditionally prepends a fixed `base` list containing `pandas_ta`, `vectorbt`, `psycopg2-binary`, `qdrant-client`, `PyGithub`. My check: `md5sum generated_teams/*/requirements.txt | uniq -c` → **`31` files, one hash.** A 3-agent zero-tool fiction team ships a backtesting stack. **P2.**

### 4.8 `run_example.py` hardcodes a software-delivery goal in every package

CONFIRMED across all 31: `goal = "Build a production-ready <team_name> following best practices."` — in the exact file `docs/how_to_run.md` instructs the user to run. **P2.**

### 4.9 "New Team" does nothing when you are already composing

CONFIRMED. `web/lib/nav-items.ts:13` → `{ title: "New Team", href: "/", … }`, rendered as a plain `<Link>` with no reset handler. Next.js does not remount a client component when a `<Link>` targets the current route, so composer state (all in `useReducer`, local to `composer-surface.tsx`) survives. Persona 5's repro 1 — an unrelated request appended onto a stale Twitter-scraper role chain — is the predicted outcome. **P2.**

### 4.10 The xAI key in `team_maker.keys` is named `X_AI_API_KEY` and is silently ignored (new; found via product-owner review)

CONFIRMED. Key **names** compared (values never read):

| Source | Name |
|---|---|
| `team_maker.keys` | `X_AI_API_KEY` |
| `registry.py:120` | `XAI_API_KEY` |

`Provider("xai", "XAI_API_KEY", …)` (`registry.py:119-126`) declares **no `env_var_aliases`**. Google has exactly this protection — `env_var_aliases=("GOOGLE_API_KEY",)` at `:107` — which is why the file's `GOOGLE_API_KEY` resolves against the catalog's `GOOGLE_AI_API_KEY`. xAI got no equivalent, so a correctly-obtained xAI key sitting in the config file resolves to nothing, with **no warning that the name is wrong**.

Impact is bounded rather than severe, which is why P2 and not P1: xAI is `openrouter_reachable=True` with `openrouter_model_name_prefixes=("grok",)`, and `OPENROUTER_API_KEY` *is* present, so Grok models remain usable through the gateway and `/api/keys/status` correctly reports `via-openrouter`. Nothing is falsely claimed. But a configured credential is discarded in silence, and the person who configured it had no way to find out — the same "no channel for reporting what happened" pattern as RC-1/RC-3. **P2.**

**Two related claims I checked and did not confirm:**

- *"Groq is wrong, it should be Grok."* **Not a bug.** Groq (groq.com, an inference host) and xAI/Grok (the model vendor) are different companies, and the catalog correctly carries both as separate providers with distinct reasons. No `GROQ_API_KEY` is present in the keys file, so groq is genuinely unconfigured. That the product's own owner conflated them is not a code defect — but it is strong evidence for the P3 below.
- *`LLM(model="xai/grok-4.6", base_url=…)` should work, so `runtime_supported=False` is a false negative.* **Not in this install.** I verified: `litellm` is **not installed** (`ModuleNotFoundError`), against `crewai 1.14.6`. Non-native providers route through LiteLLM, so that call would fail here. The catalog comment at `registry.py:77-80` and the `runtime_supported=False` flag are **accurate**. `_render_requirements` (`runner.py:317-319`) correctly adds `litellm>=1.0` to a *generated package* that needs it — the gap is only that the team_maker process itself has no such fallback, which is a deliberate, documented choice. Direct xAI support is therefore an install decision (`pip install litellm`), not a bug fix.

---

## 5. P3 — minor (6)

1. **Generic `expected_output` on every task.** `f"All deliverables for '{t.name}' completed and documented."` — hardcoded at `team_maker/llm/planner.py:62` and `team_maker/templates/role_based.py:99`. CrewAI treats `expected_output` as an output-shaping signal. P5-F4's "Defect A" (the `pitch_drafter` reading *"**All** deliverables"* literally and fabricating the not-yet-run VC's teardown) is a credible consequence; I mark the causal link PLAUSIBLE, not proven.
2. **`agents/architect.yaml`** — a literal string at `team_maker/generators/docs.py:120`, present in 4/4 packages, referencing a role that exists in none of them. Copy-pasting the documented example raises `FileNotFoundError`.
3. **`docs/how_to_extend.md`** ships a `security_engineer` / OWASP worked example to every team regardless of domain.
4. **Composer textarea `aria-label` never updates.** `composer-input.tsx:83` hardcodes `aria-label="Describe your team"` while the visible placeholder switches to the refine copy at `:84`. Screen-reader users hear the first-turn label for the entire session. Real a11y defect.
5. **Rename/merge leaves stale `display_name` and `backstory`** in the generated YAML (F5, P3-F4).
6. **Providers are surfaced as bare lowercase ids with no display name or vendor.** `Provider` (`registry.py:30-70`) has `name`, `env_var`, `unsupported_reason` — but no human label. So `groq` and `xai` appear side by side in `/api/keys/status`, the Settings panel and the role chips as indistinguishable strings, with nothing indicating that one is an inference host and the other is the vendor of Grok. The product owner conflated them during review of this very report — the strongest possible evidence that end users will. A `display_name` and `vendor` field on `Provider`, surfaced in Settings and the chips, fixes it. Fold into the §3.5 work, which already needs to surface `unsupported_reason` from the same struct.

---

## 6. Findings I reject or re-scope

| Reported | My verdict | Why |
|---|---|---|
| **CX-F14** — "Enter key doesn't submit (P2)" | **REJECTED — harness artifact** | `composer-input.tsx:58-77` implements `handleKeyDown` correctly: IME guard, `⌘/Ctrl+Enter` → run-now, `Shift+Enter` → newline, bare Enter → `preventDefault()` + `onSend()`. The tester set `.value` via JS and dispatched a synthetic `KeyboardEvent`; React's controlled `value` never updated, so `empty` was `true` and the guard correctly declined. Personas 2/3/4 all independently logged this same harness quirk. |
| **CX-F9** — "message during in-flight silently dropped (P2)" | **REJECTED as stated** | Not silent and not dropped. `sendBlockedReason` (`composer-surface.tsx:438-442`) returns *"Still working on your last message. You can keep typing; send it when this finishes."*, rendered persistently at `composer-input.tsx:110-116`, with `aria-disabled` on Send. The typed text stays in the textarea. The source comment at `:439-441` documents fixing the *previous* wording precisely because it over-promised a queue. |
| **CX-F12** — "global run lock (Positive)" | **RE-SCOPED → P2** | Serializing is correct and well-justified (`executor.py:17-33`). But a *global* non-blocking lock with no queue, no ETA, and no way to see the running run is the user-facing half of §3.3, not a positive. |
| **P10-F6** — "Page reload preserves state (Positive)" | **REJECTED** | It "preserved" an empty My Teams page. Contradicts CX-F5/CX-F6 in the same round, where reload wiped an in-progress conversation. |
| **P5-F2** — "disclosure is inconsistent" | **PARTLY WRONG** | See §4.3 — one uniform disclosure path, fires for both cited cases. The no-op-swap observation itself stands. |
| **P4-F1** — rated **P0** | **RE-SCOPED → P2 mechanism / P0 aggravator** | The suppression is the §4.1 template, a P2 mechanism. Its severity comes entirely from §2.1, where it is already counted. Rating it a separate P0 double-counts. |
| **P7-F5 / P4-F2** root cause | **CORRECTED** | Stubs are real but never reached; §2.1 is the mechanism. Conclusion and P0 severity both stand. |
| **P6-F4** (`gpt-999`) | **UNVERIFIABLE** | See §4.5. v1 rejected this too confidently. |

---

## 7. Evidence quality of the round I audited

- **Personas 1–5 are strong.** Raw `Network.getResponseBody` captures, four saved transcripts totalling 480 KB, file-level cross-checks, and self-corrections (P2-F6 retracts a false alarm). Every line number I spot-checked was accurate.
- **Personas 6, 7, 9, 10 and the cross-cutting pass saved no artifacts at all.** `evidence/` contains files for p1–p5 and p8 only. Persona 7 carries **four P0 claims with zero saved evidence** — including the fabricated-Docker-output claim, the single most alarming assertion in the round. I confirmed all four *mechanisms* independently at source and artifact level, which is why they survive; the specific fabricated output remains unverified and should be re-run with a saved transcript before it is quoted externally.
- **Coverage gaps:** Persona 9 completed 3/5 scenarios; CX-F17 (same team in two tabs) never attempted; ollama never exercised despite being listed `usable=true`.
- **Duplicate files:** `_findings-persona9.md` and `_findings-persona9-browservalidated.md` are byte-identical. Personas 8 and 10 have near-duplicate pairs differing only in completeness.
- **Stray artifacts** in the repo root (`p1_s1_before_send`, `p1_s1_composer_landing`) and one path-mangled file (`C:ProjectsCoinPela…p4_run_poll.log`) — gitignored clutter, not a product defect.

---

## 8. Verified positives

1. **Sequential text-only orchestration genuinely works.** `evidence/p2_transcript_tagline_forge.txt` (85 KB): 15 distinct tagline candidates → a 5-factor scored critique at 0.5-point granularity → a final selection with its own rationale, ending cleanly with *"Ship it."* Not one agent's text repeated.
2. **Plain-language refinements reach the real artifacts.** "make the critic nicer" → verified in `agents/skeptical_critic.yaml`; "make this cheaper" → verified in `routing_config.yaml`; "make the skeptic harsher" → verified verbatim in `agents/skeptical_vc.yaml`; role merge → 4 roles/tasks correctly collapsed to 3 with dependencies rewired.
3. **Explicit model routing is honoured.** `market_analysis_team/routing_config.yaml` contains exactly the requested `openai/gpt-4o` and `anthropic/claude-sonnet-4-6`.
4. **Imprecise input handling is genuinely good.** Typos, single words ("marketing"), mixed Spanish/English, and contradictory requirements all produced sensible teams.
5. **Security posture at rest is good** (distinct from §2.2's execution-time posture, which is not). No key input fields in the UI; keys live in a file; Settings carries an explicit rotation warning; `save_team` has a real path-traversal guard (`teams.py:485-491`) and `TaskHint.validate_task_name` documents blocking a path-traversal primitive it was written to close.
6. **Non-team first messages are not fabricated into teams.** The Story 2.10 classifier is deliberate, working restraint.
7. **Error copy discipline is unusually good.** `looksLikeLeakedInternals` (`transport.ts:75-101`) is real defence-in-depth against server internals reaching the screen, tested against a payload that actually contains a traceback.

---

## 9. Root-cause analysis

**~55 reported and newly-found findings collapse into 12 root causes, and those into one meta-pattern.**

| RC | Root cause (with the code that is the cause) | Findings it explains |
|---|---|---|
| **RC-1** | **The conversation has no channel for information.** `proposal.ts:126-170` derives every reply from role names; `compose.py:434-436` is a constant string; `session.py:76-86` only classifies when `current is None`. | F1, F2(comms), P2-F3, P4-F1, P6-F1/F2/F3, P8-F4, P9-F1/F3, CX-F1, CX-F3 — **12** |
| **RC-2** | **Refinement re-authors instead of mutating, under conflicting prompt rules.** `session.py:88-98` round-trips the whole spec; `composer.py:44-47` says to *omit* `llm` unless restated, while the refine prompt says to preserve. Nondeterministic. | F2(revert), P5-F2 — **2** |
| **RC-3** | **Tool names are unvalidated LLM output; three drifted allowlist copies, none a gate.** `prompts.py:12` vs `request.py:378` (wrong field, `"linter"` phantom) vs `tools.py.j2:277`. Plus the LLM sees `suggested_tools` in the raw schema the human rules never describe. | F9, P4-F2, P4-F3, P4-F4, P7-F1, P7-F2, P1-8, CrewAI-class-name leak — **8** |
| **RC-4** | **Codegen emits stubs into the real tools' namespace and dict.** `tools.py.j2:258-270, 290-292`. Python rebinding makes the real implementations unreachable. | P7-F4 (and it worsens P7-F1/F2) |
| **RC-5** | **The product's Run path drops `tools` entirely.** `crewai_execution_engine.py:177-185` has no `tools=`; `loader.py:93` reads the field for nothing; `GeneratedTeam` carries no package path. Divergent from `crewai_runner.py.j2:105`. **Third instance found via product-owner review: per-team shared memory is unreachable for the same reason** — `state_store` appears only in `codegen/templates/state_store.py.j2`, `tools.py.j2` and `pipeline/runner.py` (which writes the file); it is referenced **nowhere** in `team_maker/runtime/` or the execution engine, and its only access path is the `state_reader`/`state_writer` *tools*, which RC-5 discards. So cross-agent shared state is built, shipped into every package, and dead in the product's own run path. | P7-F5, P4-F2 (actual mechanism), shared-memory gap — **3** |
| **RC-6** | **No length/`finish_reason` awareness.** No `max_tokens` in `_build_llm`; `finish_reason` absent from all project code; truncation is not an exception so the runner's TOKEN LIMIT branch is dead. | F8, P3-F2, P5-F4(B,C) — **3** |
| **RC-7** | **Generated artifacts render from hardcoded literals, not from the team.** `docs.py:339-352`, `docs.py:229`, `docs.py:120`, `runner.py:303-313`, `planner.py:62` + `role_based.py:99`, `registry.py:18`, hardcoded `run_example.py` goal. | F3, F4, F5, F7, P2-F4, P3-F1, P3-F3, P3-F4, P5-F4(A) — **9** |
| **RC-8** | **Build-time "validation" means "files exist and parse."** `validator.py:41-47`; `report.py` never mentions tools; `preflight.py` checks credentials only. | Amplifies RC-3/4/5/7/10 into `✅ PASSED` |
| **RC-9** | **No addressable persistence or resume contract; the client retains no session/run IDs.** `runId` only at `workspace-surface.tsx:194`; no list-runs route in `run.py`; `nav-items.ts:13` is a same-route `<Link>`; no `save` caller in `api-client/teams.ts`. *(The server does hold the composer spec in the in-memory `api/sessions.py` registry — what is missing is addressability and client-side ID retention, not server state.)* | P2-F1, P2-F2, P5-F1, P10-F3, CX-F5, CX-F6 — **6** |
| **RC-10** | **Risky tools implement their own execution policy instead of routing through the one sandbox helper, and the sandbox defaults to off.** `tools.py.j2:45` (`SANDBOX_ENABLED` default `"false"`), `:130-138` (`docker_runner` bypasses `_run_sandboxed`), agent-supplied `mounts` → `-v host:container`, `:5-6` docstring misstates it. | **New — no persona reported this** |
| **RC-11** | **No run-time evidence contract.** `transcript_capture.py:239-240` already records `ToolUsage{Started,Finished}` events; `RunResult` (`runtime/results.py`) carries no tool-execution record and no completion rule reads one. | **New — enables all of §2.1's symptoms to recur after RC-5 is fixed** |
| **RC-12** | **The test suite's default fixture value is the one value that hides the defect.** `tests/support/team_factories.py:32` sets `tools=[]`, so all 15 engine tests are blind to RC-5 by construction; non-empty tool lists exist only in *generator* tests, leaving the codegen→runtime seam — where RC-3, RC-4, RC-5 and RC-11 all live — with no oracle at all. | P1-9. **This is why three P0s shipped.** |

### The meta-pattern

**RC-1, RC-2, RC-3, RC-7 and RC-11 are the same mistake wearing five hats:**

> An LLM's free-form output is adopted as trusted, validated state, and the deterministic layer around it neither constrains what comes in nor reports on what it did with it.

The missing invariant is a single one: *every LLM-authored field crosses a validating boundary on the way in, and every deterministic transformation reports what it changed on the way out.*

- **In:** tool names unchecked against the registry (RC-3); provider names unchecked against `runtime_supported` (RC-2/§3.5); `suggested_tools` and its `env_vars` unchecked against anything (RC-3); agent-supplied `mounts` unchecked against any policy (RC-10).
- **Out:** the doc generator does not read `PROVIDERS[…].env_var` (RC-7); the chat does not diff the spec (RC-1); the model resolver reports to `stderr` (RC-2); the tool registry reports to `stdout` (RC-3); the tool-usage recorder reports to nothing (RC-11).

**In almost every case the correct value already exists in the repo, ten to a hundred lines from the code that ignores it.** `PROVIDERS[…].env_var` for RC-7. `unsupported_reason` for §3.5. `AVAILABLE_TOOLS` for RC-3. The real `shell_command_tool` for RC-4. `crewai_runner.py.j2:105` for RC-5. `crewai/llm.py`'s `finish_reason` for RC-6. `POST /api/teams/save` for RC-9. `_run_sandboxed` for RC-10. The `ToolUsage*` handlers for RC-11. These are built features that are not wired up.

**RC-5, RC-6, RC-8, RC-9, RC-10 and RC-11 share a second pattern:** a working implementation exists on one path and is absent or bypassed on the path users actually take.

### Fix order (executable — corrected from v1)

v1 listed RC-5 first and then said it must not land first. That was self-contradictory. The dependency-respecting order:

1. **Canonical tool catalog + semantic validation.** One shared allowlist; validate at the point `agent.tools` is written; reject or surface unknown names. Fix `education/template.py`'s phantom names (P1-8) here.
2. **Remove collisions and stub shadowing, *with* sandbox and credential policy in the same change.** Splitting these arms RC-10's host escape. Requires an explicit decision on the sandbox default and on whether agent-supplied `mounts` is permitted at all.
3. **Build the runtime tool resolver.** Thread the package path (or a resolver port) to the engine; define name → instance resolution and tool-credential resolution.
4. **Attach resolved instances to CrewAI** (`_build_agent`).
5. **Add the tool-execution evidence contract and completion rule** — wire the existing `ToolUsage{Started,Finished}` handlers into `RunResult` and gate task completion on a receipt.
6. **Expand validation and preflight** to check tool availability and credentials at build and pre-run.

**Step 0, before any of the above — close RC-12.** Add the one engine test that builds an `AgentSpec` with a non-empty `tools` list and asserts the constructed `Agent` carries a matching tool. `tests/support/crewai_interception.py` already captures the `Agent`, so this is a few lines. Without it, every step below is unguarded against regression, and steps 3-5 are being designed against a suite that provably cannot see the class of bug they exist to fix.

Then the non-blocking clusters by leverage: RC-7 (9 findings, mechanical) → RC-1 (12 findings; spec-diff in `describeProposal` is cheap, a true answer mode is a larger design change) → RC-6 → RC-2 → RC-9.

**Effort:** v1 estimated "a handful of days." I withdraw that. Steps 1–2 and 6 are largely mechanical; steps 3–5 are a design task (a runtime tool-resolution boundary, a sandbox policy decision, and a completion invariant), and should be scoped as design work, not as a patch.

---

## 10. Persona ranking

Ranked by verified severity × detection likelihood × whether the bad output leaves the product.

| # | Persona | P0 clusters hit | Worst problem | Detectable by them? |
|---|---|---|---|---|
| **1** | **7 — Software engineer** | **4 of 4** | Fabricated Docker registry pushes with SHA256 digests under a `Complete` banner; and the only persona whose teams reach RC-10's code path | Medium — `docker images` would betray it |
| **2** | **4 — Student / researcher** | **4 of 4** | Citation-formatted literature review, "47 Primary and Secondary Sources", zero web calls, honest disclaimer stripped downstream | **Lowest of any persona** |
| **3** | **10 — Returning user** | 2 (P0-1, P0-3) | The persona's entire premise (My Teams) is dead, *and* the starter team it is steered to ships two tools that resolve nowhere (P1-8) | Yes for My Teams; no for the tools |
| **4** | **5 — Founder / PM** | 2 (P0-1, P0-3) | "Investor-Ready" deck truncated before the Team and Ask slides; `customer_persona_creator` carries 8 silently-dropped tools | Only by reading the full transcript |
| **5** | **2 — Knowledge worker** | 2 (P0-1, P0-3) | My Teams dead + run unrecoverable on reload + false "no API keys required" | Partly |
| **6** | **1 — First-time user** | 0 | Provider diversification silently reverted by the next turn | No |
| **7** | **3 — Creative writer** | 0 | Mid-pipeline truncation *invisible in the final artifact* — two agents invented over it | Almost never |
| **8** | **6 — LLM power user** | 0 | All disclosure defects; **zero incorrect behaviour** — routing is actually correct | Yes, they read `routing_config.yaml` |
| **9** | **9 — Security-conscious** | 0 | One P2. Strong verified positives on key handling at rest — though §2.2(c) is squarely this persona's concern and no scenario probed it | n/a |
| **10** | **8 — Imprecise / non-native** | 0 | 4 positives, 1 P2. Best-served persona in the product. | n/a |

**1 and 2 are effectively tied**; the order flips on which criterion you weight. Persona 7 leads on defect density (all four clusters, 3/3 teams, and the only persona whose requests reach RC-10). Persona 4 leads on undetectability: it asked the exact protective question, got boilerplate, and its bad output propagates *outside* the product into coursework. Either is a release blocker alone.

**Persona 6's low rank is a finding, not an absence of one.** Six findings and a "Trust assessment: FAIL" — yet every underlying behaviour was correct. That persona is 100% RC-1/RC-2/§4.4 communication defects. Cheapest cluster to fix; inflates the raw finding count without inflating risk.

**Persona 9's rank is a coverage gap, not a clean bill.** RC-10 (sandbox bypass, agent-controlled host mounts) is exactly what a security-conscious persona exists to find, and the round's Persona 9 scenarios — all five about API-key handling — never went near it. Any re-run should add execution-time scenarios to this persona.

---

## 11. Changelog

Revised after external technical review. Changes, and why:

| # | Change | Reason |
|---|---|---|
| 1 | **Added §2.2(c) and RC-10 — Docker sandbox bypass.** | v1 omitted a real security defect I had read the code for. Escalated beyond the review's framing: the sandbox also **defaults to off**, `mounts` is an **agent-supplied** host-FS escape primitive, and the module docstring misstates the behaviour. Framed as a landmine the RC-4 fix *arms* rather than a parallel P0 — which is why (a)+(b)+(c) is one change. |
| 2 | **Added §2.4 and RC-11 — tool-execution evidence contract.** | Correct: attaching real tools does not make the product truthful. Noted that `transcript_capture.py:239-240` already records `ToolUsage*` events, so this is wiring plus a completion rule, not a new build — which moves it earlier in the order. |
| 3 | **Removed "the fix is one line."** | Wrong. `AgentSpec.tools` is `List[str]`; `GeneratedTeam` has no package path; `engine.run()` never receives one. Replaced with the six missing pieces and a runtime tool-resolver requirement. |
| 4 | **Corrected the fix order.** | v1 listed RC-5 first then said it must not land first. |
| 5 | **Narrowed "the core multi-agent engine is sound."** | Overstated; contradicted by v1's own §2.1 and §3.1. Now "basic sequential LLM orchestration works well for text-only teams," with the exclusions named. |
| 6 | **Softened §3.4 and removed `groq`/`gpt-999` from RC-2.** | v1 claimed *every* non-restating turn discards routing — too absolute; the refine prompt does instruct preservation, so the accurate claim is nondeterminism plus one demonstrated loss. `groq` belongs to the prompt-filter cause (§3.5), which v1's own §3.5 already said — an internal contradiction. |
| 7 | **§4.5 `gpt-999` → UNVERIFIABLE.** | Went further than the review asked. Because the UI never renders models (§4.4), Persona 6 **could not have observed** the drop; and since they never built, v1's "it is disclosed at Build" was an untested counterfactual. Both claims are ungrounded. |
| 8 | **Withdrew the "handful of days" estimate.** | Steps 3–5 are design work, not a patch. |
| 9 | **Fixed the P3 count (4 → 5); reworded RC-9; removed "tools were never intended to work in this release."** | Off-by-one; the server *does* hold the composer spec in `api/sessions.py`, so the gap is addressability and client ID retention; and the "Phase 2" comment proves design drift, not an approved product decision — the same file contains working `shell_command`, `git_account`, `ci_tool`. |
| 10 | **Added P1-8 (starter template phantom tools), the CrewAI-class-name leak, and the 9-of-15 tool-exposure table.** | Found while verifying the persona ranking; not reported by any persona. Widens RC-3 and P0-1's blast radius to Personas 2, 5 and 10. |
| 11 | **Added §10 persona ranking.** | Requested separately; re-run against the four-cluster model. |

**Unchanged and re-affirmed:** P0-1's corrected root cause (§2.1), the stub-shadowing mechanism (§2.2b), the six rejections in §6, RC-1/3/4/5/6/7/8's evidence, and all seven verified positives.

### v2 → v2.1 (product-owner review)

| # | Change | Reason |
|---|---|---|
| 12 | **Added P1-9 and RC-12 — the test suite cannot observe P0-1.** | Answers "why didn't our tests catch that?" precisely: `team_factories.py:32` sets `tools=[]`, so all 15 engine tests are blind by construction, and non-empty tool lists appear only in *generator* tests. Added as **step 0** of the fix order — it is the regression guard for the entire sequence. |
| 13 | **Added §4.10 — `X_AI_API_KEY` vs `XAI_API_KEY`.** | Real bug found by the owner's instinct (though not their diagnosis): the catalog declares no `env_var_aliases` for xai, so a configured key is silently discarded. Google has exactly this protection; xai does not. |
| 14 | **Recorded two non-bugs under §4.10, with the checks that settled them.** | "Groq should be Grok" — Groq and xAI are different companies; the catalog is correct. And `runtime_supported=False` for xai is **accurate**: I verified `litellm` is not installed against `crewai 1.14.6`, so the suggested `LLM(model="xai/grok-4.6", …)` call would fail here. Direct xAI is an install decision, not a bug fix. |
| 15 | **Added P3 #6 — providers have no display name.** | The owner conflated `groq` and `xai` while reviewing this report. `Provider` carries no human label, so both render as bare lowercase ids. Folded into the §3.5 work, which already needs to surface `unsupported_reason` from the same struct. |
| 16 | **Extended RC-5 — per-team shared memory is a third instance.** | `state_store` appears only in the two codegen templates and `runner.py`; nothing in `team_maker/runtime/` references it, and its access path is the `state_reader`/`state_writer` tools that RC-5 discards. Shared state is built, shipped, and dead in the product's run path — so the owner's "each team should have its own shared memory" is not a feature request. |
| 17 | **Added §13 — design options raised in review.** | Coding-agent-as-team-member, stub/mock warnings, and the two sidebar UX items are product decisions, not audit findings. Recorded with their blocking dependencies rather than silently dropped or promoted to findings. |

---

## 12. Release decision

**Do not release.** The four P0 clusters together mean the product confidently reports success for capabilities it never loaded, with no mechanism that could detect otherwise. This is not a corner case: it fires for every research, coding, DevOps or data team, and it reaches nine of the fifteen built packages examined — including the shipped starter team.

One sequencing constraint is non-negotiable: **§2.2's three parts ship together.** A change that removes stub shadowing, or that wires §2.1's resolver, without settling the sandbox policy converts a currently-unreachable host escape into a reachable one.

The encouraging read stands, with a correction to its cost. Nothing here suggests an architectural rewrite — it suggests a codebase where the last wire on several finished features was never connected. But three of the six blocker steps require a design decision (a runtime tool-resolution boundary, a sandbox policy, a completion invariant), so this should be scoped as design work rather than a bug-fix sprint.

---

## 13. Design options raised in review (not audit findings)

These are product decisions rather than defects. Recorded here with dependencies so they are not lost, and deliberately kept out of the severity counts.

### 13.1 Delegate software work to a real coding agent instead of implementing the tool set

The software-oriented tools (`shell_command`, `code_writer`, `code_reader`, `test_runner`, `docker_runner`) are the exact set implicated in P0-2 — collision-prone, stub-shadowed, sandbox-bypassing, and in `code_reader`'s case dependent on `OPENAI_API_KEY` for a `CodeDocsSearchTool` that is not really a code reader. Rather than hardening all five, a software role could delegate to an existing coding agent (Claude Code, Codex, OpenCode) behind one tool boundary.

Weigh it as an alternative to §9 steps 2-4, not an addition: it replaces five risky in-process tools with one subprocess boundary that already has its own sandboxing and permission model, and it makes RC-10's sandbox policy question mostly moot for the software case. It does **not** remove the need for step 1 (validation), step 5 (RC-11 receipts — arguably more important, since a delegated agent's claims need the same evidence contract) or step 0 (RC-12). It also adds an external dependency and a cost/latency profile the current design does not have. **Recommend: evaluate during §9 step 3, when the resolver boundary is being designed anyway — that is the cheapest moment to choose.**

### 13.2 Warn the builder/admin whenever a stub, mock or fake is present

This is a concrete, cheap implementation of what P0-3 (§2.3) is missing, and it is the single highest-value item on this list. The validator already walks the package; detecting a rendered `NotImplementedError` stub, or a tool name absent from the canonical registry, is a few lines — and it converts "silently broken" into "declared broken," which is the difference between the current release-blocking behaviour and an honest one.

Two distinct surfaces, both needed:

- **Build time** — `generation_report.md` and the build-result card must list every tool that is stubbed, unregistered, or missing a credential, and `Validation` must not read `✅ PASSED` when any exist. Fold into §9 step 6.
- **Test time** — the owner's stronger point: a test suite that leans on stubs can pass while the product is broken, which is precisely RC-12. Worth an explicit convention that mocked seams are named and enumerated, so "these 15 engine tests all use `tools=[]`" is visible rather than buried in a fixture default.

### 13.3 List teams in the left sidebar, with each team's conversations nested beneath it

Good UX direction, and it makes the right thing structurally obvious. But it is **blocked on RC-9**, not merely adjacent to it. A sidebar team list needs a populated team store — which is exactly P1-2's missing `POST /api/teams/save` call — and nested conversation history needs addressable, resumable sessions, which is the addressability half of RC-9 (`api/sessions.py` holds the spec in memory today, with no client-retained id and no resume contract).

So the dependency runs: wire the save call → give sessions and runs stable, retrievable ids → then the sidebar is mostly a rendering job. Attempting the UI first would produce a nav item as empty as today's "My Teams". Worth treating as the **acceptance criterion** for RC-9 rather than as separate work — it is a good forcing function, because a sidebar that stays empty is an immediately visible failure in a way that a missing API call is not.

---
