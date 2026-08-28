# team_maker — Independent Quality Audit (source-verified)

**Author:** independent re-audit of the Story 4.8 QA round
**Date:** 2026-08-28
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

**Verdicts used:** `CONFIRMED` (mechanism read in source and/or reproduced in an artifact) · `CONFIRMED / ROOT CAUSE CORRECTED` (defect is real, the report's explanation of *why* is wrong) · `PLAUSIBLE` (symptom evidenced, mechanism not established) · `REJECTED` (finding does not survive source review) · `MIS-SCOPED` (real, but severity or framing is wrong).

---

## 1. Headline verdict

The core multi-agent engine is **sound**. Four independent full E2E transcripts show genuinely distinct, sequentially-dependent per-agent work — not one agent's text repeated. Plain-language refinements (tone, cost tier, role merges) reliably reach the real generated artifacts. That is a real achievement and it is not in question.

Everything wrapped around that engine is not shippable. Specifically:

> **The product cannot presently be trusted to tell the truth about itself.** It reports `Validation: ✅ PASSED` and `Run complete.` for runs in which the requested capability was never loaded, the output was silently cut off mid-sentence, and the shipped documentation states the opposite of the configuration it was generated from.

**Recommendation: do not release.** Three P0s are release blockers on their own, and one of them (§2.1) I found to have a *different and broader* root cause than the audit round identified.

| Severity | Count (my triage) |
|---|---|
| **P0 — release blocker** | 3 |
| **P1 — major** | 7 |
| **P2 — moderate** | 9 |
| **P3 — minor** | 4 |
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

**Verdict:** CONFIRMED / ROOT CAUSE CORRECTED. **P0.**
**Fix:** one line in `_build_agent`. But it cannot land before §2.2, or it will start raising `NotImplementedError` at runtime instead of hallucinating.

---

### 2.2 P0-2 — Invented tool names pass every gate, and codegen makes stubs shadow the real implementations

Tool names in `agents/*.yaml` are free-form LLM output. **Three separate, drifted copies of the allowlist exist. None of them is a gate.**

| Copy | Location | What it actually does |
|---|---|---|
| `AVAILABLE_TOOLS` (13 names) | `team_maker/llm/prompts.py:12-62` | Prompt text only. Rule 7 at `prompts.py:104` says *"Do not invent tool names"* — advisory, unenforced. |
| `_REGISTRY_TOOLS` (14 names) | `team_maker/schema/request.py:378-382` | Filters a **per-role** `suggested_tools` field, and only `if not role.get("tools")`. Never sees the planner's `agent.tools`. Contains `"linter"`, which exists in neither other copy. |
| `TOOL_REGISTRY` (13 names) | `codegen/templates/tools.py.j2:277-306` | Runtime. Consulted after generation, warns to **stdout**. |

Nothing validates the planner's output against any of them. Confirmed invented names in shipped artifacts: `code_reader_tool`, `file_writer_tool`, `shell_tool`, `file_read`, `text_summarizer`, `web_scraper`, `url_reader`, `twitter_search_tool`, `git_account_tool`.

**How the invention happens** — a mechanism the persona round did not identify: `Composer.compose()` calls `provider.complete_structured(response_model=TeamCreationRequest)` (`composer.py:113-117`). That hands the authoring LLM the **entire** `TeamCreationRequest` JSON schema, including `suggested_tools: List[ToolSuggestion]` with free-form `name`, `description`, and `env_vars` (`schema/request.py:100-115, 249-255`). The human-authored `_SCHEMA_RULES` (`composer.py:34-59`) documents only a subset and never mentions `suggested_tools` at all. So the LLM invents tools, invents their env var names, and writes their descriptions — and all three are taken as fact downstream. That is how `SERPAPI_API_KEY` (a name that appears nowhere in the codebase) got into a shipped file.

**Then codegen actively breaks the working tools.** `tools.py.j2` emits every invented name as a stub *after* the real definitions, into the same module namespace and the same dict literal (`:258-270` for the functions, `:290-292` for the registry entries). Reproduced in `generated_teams/devops_team/tools.py`:

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

Two further real defects in the same template, neither reported:

- Registry key mismatch: the real shell tool registers under key `"shell"` (`tools.py.j2:278`), but the prompt catalog and every agent YAML I read use `"shell_command"`. Even without stub shadowing, that lookup misses.
- `ToolSuggestion.description` is rendered verbatim as the stub's **docstring** (`tools.py.j2:262`), which is what CrewAI shows the agent as the tool's contract. So the authoring LLM's own marketing copy becomes a false capability promise *to the agent*. Verified in `generated_teams/fusion_policy_research_team/tools.py:228`: *"This tool fetches current information from the live web — it is NOT limited to training data and WILL surface 2026 content as it is published online."* — attached to a function whose next four lines are `raise NotImplementedError`.

Also confirmed: `AVAILABLE_TOOLS`'s own header comment reads *"Phase 2 will add real implementations; this drives planner awareness now."* Tools were **never intended to work in this release** — but nothing in the product says so to the user.

**Verdict:** CONFIRMED, and broader than reported. **P0.**

---

### 2.3 P0-3 — "Validation: ✅ PASSED" means "the files exist and the YAML parses"

`team_maker/validation/validator.py` is 90 lines and `OutputValidator.validate()` runs exactly four checks (`:41-47`): required top-level files exist; one YAML per agent; one YAML per task; every `.yaml` parses. `team_maker/runtime/preflight.py` adds credential resolution, duplicate-role and task-name checks — and nothing else. I grepped `team_maker/generators/report.py`: it never mentions tools.

So no layer anywhere checks whether a declared capability exists. Verified across four unrelated packages (`fusion_policy_research_team`, `tagline_forge`, `scifi_story_team`, `devops_team`): all four report `**Validation status:** ✅ PASSED` with `_No issues found._` / `_No warnings._`.

On its own this would be a documentation-quality issue. Combined with §2.1 and §2.2 it is the layer that converts two silent internal failures into an explicit, confident, false assurance to the user. That promotion from "broken" to "broken and asserting it isn't" is what makes this P0.

**Verdict:** CONFIRMED. **P0.**

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

**Severity note:** the persona round called this "P1, arguably P0-adjacent" three times. I keep it P1 — it degrades output rather than asserting a capability that does not exist — but I note that its combination with §2.3 (green banner over a truncated artifact) is what does the real damage.

### 3.2 P1-2 — "My Teams" cannot ever be populated

CONFIRMED at source **and** empirically. `POST /api/teams/save` is fully implemented (`api/routers/teams.py:459-520`, SQLite-backed, path-traversal-guarded). The frontend client (`web/lib/api-client/teams.ts`) exposes exactly four calls — `browse`, `rename`, `delete`, `record-run`. **There is no `save` caller.** The UI can list, rename and delete teams that no code path can create.

Empirical confirmation I ran myself: `data/teams.db` → `SELECT * FROM teams` returns `[]`, and `data/saved_teams/` is empty — after **31** teams were built into `generated_teams/`.

Persona 2 called this "P1, arguably borderline P0". I keep P1 (nothing is corrupted or falsely asserted; the empty state is honest-looking), but it is the top P1.

### 3.3 P1-3 — A run cannot be recovered after any navigation or reload; the run lock is global

CONFIRMED. `api/routers/run.py` declares exactly four routes (`:85, 97, 142, 154`): `GET /teams/{slug}`, `POST ""`, `GET /{run_id}`, `GET /{run_id}/transcript`. **There is no list-runs and no current-run endpoint.** The only copy of `run_id` lives in React state (`workspace-surface.tsx:194`). A reload is therefore unrecoverable by construction — the id is gone and no endpoint can rediscover it.

The lock is genuinely process-wide and non-blocking (`api/runs.py:149-152`, `team_maker/runtime/executor.py:52`) — deliberately, and correctly, because the crewai event bus is a process-global singleton (documented at `executor.py:17-33`). The defect is not the serialization; it is that a *global* lock with **no queue, no ETA, and no way to observe the running run** presents to the user as "your Run button is randomly broken."

### 3.4 P1-4 — Every refinement turn is a full LLM re-author, so any request that doesn't restate the routing silently discards it

CONFIRMED, and this explains four separately-reported findings at once.

`ComposerSession.refine()` (`session.py:76-98`) does not mutate state. It serializes the current spec into a prompt and asks for a complete re-emit:

```python
def _build_refinement_intent(self, message: str) -> str:
    ...  f"Current team specification (JSON):\n{current_spec}\n\n"
         f"Requested change: {message}\n\n"
         "Apply ONLY this change and keep everything else … Re-emit the complete, updated …"
```

And `_SCHEMA_RULES` (`composer.py:44-47`) instructs the model:

> `llm` (optional): … Set it **ONLY if the user named a model/provider for this specific role**; otherwise **omit the field entirely** so the system default applies.

So on a turn like *"Choose the best available model for each role"* — which names no model — the LLM correctly follows the rule, omits every `llm`, and **the diversification established one turn earlier is wiped.** Persona 1's F2 "silent revert" is not an anomaly; it is the specified behaviour of a re-author-from-prompt design. The same mechanism drops `gpt-999` (P6-F4) and `groq` (P6-F5), because the prompt's provider list is `anthropic, openai, xai, google, ollama` — `groq` and `openrouter` are not in it, so the model cannot emit them.

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

What I can establish: `unreadable_response` is the catch-all raised at three points in `web/lib/api-client/transport.ts` (`:179` body is not JSON, `:192` `parseSpec` returned `null`, `:212` the payload is not the `{error:{code,message}}` envelope). Because `parseErrorEnvelope` (`api-types/errors.ts:84-93`) requires that envelope, **any** unhandled server 500 — which FastAPI renders as `{"detail": …}` — surfaces to the user with this exact copy. So the message tells us nothing about the cause, which is itself a diagnosability defect.

Two candidate mechanisms, both cheap to discriminate: (a) an unhandled server exception, or (b) `parseSpec` rejecting the spec — it returns `null` if any task lacks `agent_role` or any role lacks a non-empty `name` (`api-types/compose.ts:133-181`). Timing rules out a client timeout (43 s observed vs `COMPOSE_TIMEOUT_MS = 180_000`). **Needs one repro with the raw response body**; I am not willing to assign a root cause without it. Keeping P1 pending that.

---

## 4. P2 — moderate

### 4.1 The conversational layer has no channel through which to say anything (12 reported findings, one cause)

CONFIRMED. The composer can produce exactly two kinds of reply, and neither can carry information:

1. **Spec exists** → `describeProposal()` (`web/components/composer/proposal.ts:126-129, 168-170`) builds the reply from `rolesInPipelineOrder(spec).map(r => r.name)` and nothing else: `` `Updated: ${names.join(" → ")}.` `` + `` `Anything you would change about ${last}…` ``. It never diffs the spec, never reads provider or model, and has no branch for answering anything.
2. **No spec** → `_generate_clarification()` (`api/routers/compose.py:434-436`) is a **constant**: `return "Please describe the team you want to build and what they should do."`

And the classifier only ever runs when there is no spec yet: `refine()` (`session.py:76-86`) calls `classify_input` **only** `if self.current is None`. Once a team exists, every message — including *"Can this actually search the live internet?"* — is routed as a spec edit. There is no third mode.

This single design fact accounts for **twelve** separately-logged findings: F1, F2 (comms half), P2-F3, P4-F1, P6-F1, P6-F2, P6-F3, P8-F4, P9-F1, P9-F3, CX-F1, CX-F3.

I rate the cluster **P2** as a usability defect — with one exception. **P4-F1 is genuinely severe in context**: a researcher asked the exact protective question (*"or does it only know what's in its training data?"*) immediately before building, and the suppression mechanism swallowed it like any other. I count that not as its own P0 (as the persona report did) but as the aggravating factor that turns §2.1 from a bug into a trust failure. The mechanism is the same P2 template.

### 4.2 Every team gets `template: software_delivery_team`, and a better template is unreachable

CONFIRMED. `DEFAULT_TEMPLATE_ID = "software_delivery_team"` (`team_maker/templates/registry.py:18`); `runner.py:106` → `request.template_id or DEFAULT_TEMPLATE_ID`. The composer's `_SCHEMA_RULES` never mentions `template_id`, so the field is always `None` on the conversational path. Verified `template: software_delivery_team` in 4/4 packages spanning weekly planning, marketing taglines, sci-fi fiction and DevOps. The `research_content` template — whose own docstring calls it *"the flagship showcase team mentioned in the PRD addendum"* — is registered and never selected. **P2** (it drives labels and doc boilerplate; roles/tasks are LLM-composed, so generated agent quality is unaffected).

### 4.3 Model substitutions are disclosed only at Build, never in chat — and the reported inconsistency does not exist

**MIS-SCOPED.** P5-F2 claimed disclosure was *inconsistent* — visible for Persona 3's substitution but hidden for Persona 5's. That is wrong. There is exactly one disclosure path and it is uniform: `_substitutions()` (`api/build.py:94-105`) diffs requested vs resolved labels, and `build-result.tsx:118-137` renders *"One model was not available and a near match was used instead"* with a per-role `requested → resolved` list. It fires for both cases.

The real, uniform gap: `normalize_team_routings` (`model_resolver.py:186-200`) reports substitutions **only to stderr**, and nothing surfaces them during compose. `_closest()` (`:29-40`) is a `difflib` fuzzy match with no similarity floor, so `gpt-999` resolves to whatever ranks highest rather than being rejected. **P2.**

### 4.4 The UI shows providers but never models

CONFIRMED. `web/components/composer/key-check.tsx:169` renders `role.provider` only. A power user who asks for `openai/gpt-4o` and `anthropic/claude-sonnet-4-6` sees two provider names and cannot verify the model until after Build. **P2.** (Persona 6 correctly verified via `generated_teams/market_analysis_team/routing_config.yaml` that the models *are* honoured — a genuine positive.)

### 4.5 Invalid model names are dropped at compose time with no signal

**MIS-SCOPED** — real, but P6 rated it P1. It *is* disclosed, at Build, via §4.3. The gap is compose-time silence plus §4.4. **P2, not P1.**

### 4.6 The build directory name is unpredictable before Build

**CONFIRMED / MECHANISM CORRECTED.** P7-F3 called it hidden "name normalization." The actual mechanism: `_adopt_server_output_path` (`api/routers/compose.py:254-268`) derives `output_path` **once, from the first spec's LLM-authored `team_name`**, and pins it for the session's life (`if entry.output_path is None`). The slug (`api/output.py:55-63`) is only ever displayed *after* Build (`build-result.tsx:62`). So the "A directory already exists…" error names a path the user was never shown. P7 also appears to have read the *role* name `github_automation_agent` as the team name — `team_name` is in fact displayed read-only at `spec-editor.tsx:213-217`. **P2.**

### 4.7 Every generated `requirements.txt` is byte-identical, including algorithmic-trading libraries

CONFIRMED, and stronger than reported. `_render_requirements()` (`team_maker/pipeline/runner.py:296-313`) unconditionally prepends a fixed `base` list containing `pandas_ta`, `vectorbt`, `psycopg2-binary`, `qdrant-client`, `PyGithub`. My check: `md5sum generated_teams/*/requirements.txt | uniq -c` → **`31` files, one hash.** A 3-agent zero-tool fiction team ships a backtesting stack. **P2.**

### 4.8 `run_example.py` hardcodes a software-delivery goal in every package

CONFIRMED across all 31: `goal = "Build a production-ready <team_name> following best practices."` — in the exact file `docs/how_to_run.md` instructs the user to run. **P2.**

### 4.9 "New Team" does nothing when you are already composing

CONFIRMED. `web/lib/nav-items.ts:13` → `{ title: "New Team", href: "/", … }`, rendered as a plain `<Link>` with no reset handler. Next.js does not remount a client component when a `<Link>` targets the current route, so composer state (all in `useReducer`, local to `composer-surface.tsx`) survives. Persona 5's repro 1 — an unrelated request appended onto a stale Twitter-scraper role chain — is the predicted outcome. **P2.**

---

## 5. P3 — minor

- **Generic `expected_output` on every task.** `f"All deliverables for '{t.name}' completed and documented."` — hardcoded at `team_maker/llm/planner.py:62` and `team_maker/templates/role_based.py:99`. CrewAI treats `expected_output` as an output-shaping signal. P5-F4's "Defect A" (the `pitch_drafter` reading *"**All** deliverables"* literally and fabricating the not-yet-run VC's teardown) is a credible consequence, though I mark the causal link PLAUSIBLE rather than proven.
- **`agents/architect.yaml`** — a literal string at `team_maker/generators/docs.py:120`, present in 4/4 packages, referencing a role that exists in none of them. Copy-pasting the documented example raises `FileNotFoundError`.
- **`docs/how_to_extend.md`** ships a `security_engineer` / OWASP worked example to every team regardless of domain.
- **Composer textarea `aria-label` never updates.** `composer-input.tsx:83` hardcodes `aria-label="Describe your team"` while the visible placeholder switches to the refine copy at `:84`. Screen-reader users hear the first-turn label for the entire session. Real a11y defect.
- **Rename/merge leaves stale `display_name` and `backstory`** in the generated YAML (F5, P3-F4).

---

## 6. Findings I reject or re-scope

| Reported | My verdict | Why |
|---|---|---|
| **CX-F14** — "Enter key doesn't submit (P2)" | **REJECTED — harness artifact** | `composer-input.tsx:58-77` implements `handleKeyDown` correctly: IME guard, `⌘/Ctrl+Enter` → run-now, `Shift+Enter` → newline, bare Enter → `preventDefault()` + `onSend()`. The tester set `.value` via JS and dispatched a synthetic `KeyboardEvent`; React's controlled `value` never updated, so `empty` was `true` and the guard correctly declined. Personas 2/3/4 all independently logged this same harness quirk about `fill_input()`. |
| **CX-F9** — "message during in-flight silently dropped (P2)" | **REJECTED as stated** | Not silent and not dropped. `sendBlockedReason` (`composer-surface.tsx:438-442`) returns *"Still working on your last message. You can keep typing; send it when this finishes."*, rendered persistently at `composer-input.tsx:110-116`, with `aria-disabled` on Send. The typed text stays in the textarea. The source comment at `:439-441` documents fixing the *previous* wording precisely because it over-promised a queue. |
| **CX-F12** — "global run lock (Positive)" | **RE-SCOPED → P2** | Serializing is correct and well-justified (`executor.py:17-33`). But a *global* non-blocking lock with no queue, no ETA, and no way to see the running run is the user-facing half of §3.3, not a positive. |
| **P10-F6** — "Page reload preserves state (Positive)" | **REJECTED** | It "preserved" an empty My Teams page. Directly contradicts CX-F5/CX-F6 in the same round, where reload wiped an in-progress conversation. |
| **P5-F2** — "disclosure is inconsistent" | **PARTLY WRONG** | See §4.3 — one uniform disclosure path, fires for both cited cases. The no-op-swap observation itself stands. |
| **P4-F1** — rated **P0** | **RE-SCOPED → P2 mechanism / P0 aggravator** | The suppression is the §4.1 template, a P2 mechanism. Its severity comes entirely from §2.1, where it is already counted. Rating it a separate P0 double-counts. |
| **P7-F5 / P4-F2** root cause | **CORRECTED** | Stubs are real but never reached; §2.1 is the mechanism. Conclusion and P0 severity both stand. |

---

## 7. Evidence quality of the round I audited

Worth recording, because it changes how much of this report rests on my own verification rather than the persona round's:

- **Personas 1–5 are strong.** Raw `Network.getResponseBody` captures, four saved transcripts totalling 480 KB, file-level cross-checks, and self-corrections (P2-F6 retracts a false alarm). Every line number I spot-checked was accurate.
- **Personas 6, 7, 9, 10 and the cross-cutting pass saved no artifacts at all.** `evidence/` contains files for p1–p5 and p8 only. Persona 7 carries **four P0 claims with zero saved evidence** — including the fabricated-Docker-output claim, the single most alarming assertion in the round. I was able to confirm all four *mechanisms* independently at source and artifact level, which is why they survive; but the specific fabricated output remains unverified and should be re-run with a saved transcript before it is quoted externally.
- **Coverage gaps not flagged prominently enough:** Persona 9 completed 3/5 scenarios; CX-F17 (same team in two tabs) was never attempted; ollama was never exercised despite being listed `usable=true` in the environment notes.
- **Duplicate files:** `_findings-persona9.md` and `_findings-persona9-browservalidated.md` are byte-identical. Persona 8 and 10 have near-duplicate pairs differing only in completeness.
- **Two stray artifacts in the repo root** (`p1_s1_before_send`, `p1_s1_composer_landing`) and one path-mangled file (`C:ProjectsCoinPela…p4_run_poll.log`) — cleanup, not a product defect.

---

## 8. Verified positives (not padding — I checked these)

1. **The multi-agent engine genuinely works.** `evidence/p2_transcript_tagline_forge.txt` (85 KB): 15 distinct tagline candidates → a 5-factor scored critique at 0.5-point granularity → a final selection with its own rationale, ending cleanly with *"Ship it."* Not one agent's text repeated.
2. **Plain-language refinements reach the real artifacts.** "make the critic nicer" → verified in `agents/skeptical_critic.yaml`; "make this cheaper" → verified in `routing_config.yaml`; "make the skeptic harsher" → verified verbatim in `agents/skeptical_vc.yaml`; role merge → 4 roles/tasks correctly collapsed to 3 with dependencies rewired.
3. **Explicit model routing is honoured.** `market_analysis_team/routing_config.yaml` contains exactly the requested `openai/gpt-4o` and `anthropic/claude-sonnet-4-6`.
4. **Imprecise input handling is genuinely good.** Typos, single words ("marketing"), mixed Spanish/English, and contradictory requirements all produced sensible teams. This is a real strength.
5. **Security posture at rest is good.** No key input fields in the UI; keys live in a file; Settings carries an explicit rotation warning; `save_team` contains a real path-traversal guard (`teams.py:485-491`) and `TaskHint.validate_task_name` documents blocking a path-traversal primitive it was written to close.
6. **Non-team first messages are not fabricated into teams.** The Story 2.10 classifier is a deliberate, working piece of restraint.
7. **Error copy discipline is unusually good.** `looksLikeLeakedInternals` (`transport.ts:75-101`) is a real defence-in-depth guard against server internals reaching the screen, tested against a payload that actually contains a traceback.

---

## 9. Root-cause analysis — the question asked directly

**Yes. Emphatically.** ~48 reported findings collapse into **9 root causes**, and those 9 collapse further into **one meta-pattern**.

| RC | Root cause (with the code that is the cause) | Reported findings it explains |
|---|---|---|
| **RC-1** | **The conversation has no channel for information.** `proposal.ts:126-170` derives every reply from role names; `compose.py:434-436` is a constant string; `session.py:76-86` only classifies when `current is None`. No third reply mode exists. | F1, F2(comms), P2-F3, P4-F1, P6-F1/F2/F3, P8-F4, P9-F1/F3, CX-F1, CX-F3 — **12** |
| **RC-2** | **Refinement re-authors instead of mutating.** `session.py:88-98` round-trips the whole spec through a prompt; `composer.py:44-47` instructs the model to *omit* `llm` unless restated. State is only as durable as the last prompt. | F2(revert), P5-F2, P6-F4, P6-F5 — **4** |
| **RC-3** | **Tool names are unvalidated LLM output; three drifted allowlist copies, none a gate.** `prompts.py:12` (prompt only) vs `request.py:378` (wrong field, `"linter"` phantom) vs `tools.py.j2:277` (runtime). Plus the LLM sees `suggested_tools` in the raw schema the human rules never describe. | F9, P4-F2, P4-F3, P4-F4, P7-F1, P7-F2 — **6** |
| **RC-4** | **Codegen emits stubs into the real tools' namespace and dict.** `tools.py.j2:258-270, 290-292`. Python rebinding makes the real implementations unreachable. | P7-F4 (and it worsens P7-F1/F2) |
| **RC-5** | **The product's Run path drops `tools` entirely.** `crewai_execution_engine.py:177-185` has no `tools=`; `loader.py:93` reads the field for nothing. Divergent from `crewai_runner.py.j2:105`, which does it right. | P7-F5, P4-F2 (actual mechanism) |
| **RC-6** | **No length/`finish_reason` awareness.** No `max_tokens` in `_build_llm`; `finish_reason` absent from all project code; truncation is not an exception so the runner's TOKEN LIMIT branch is dead. | F8, P3-F2, P5-F4(B,C) — **3** |
| **RC-7** | **Generated artifacts render from hardcoded literals, not from the team.** `docs.py:339-352` (`api_key_env or "no keys needed"`), `docs.py:229` (`or 'N/A'`), `docs.py:120` (`architect.yaml`), `runner.py:303-313` (fixed deps), `planner.py:62` + `role_based.py:99` (`expected_output`), `registry.py:18` (`DEFAULT_TEMPLATE_ID`), hardcoded `run_example.py` goal. | F3, F4, F5, F7, P2-F4, P3-F1, P3-F3, P3-F4, P5-F4(A) — **9** |
| **RC-8** | **"Validation" means "files exist and parse."** `validator.py:41-47` — 4 checks; `report.py` never mentions tools; `preflight.py` checks credentials only. | Amplifies RC-3/4/5/7 into `✅ PASSED` |
| **RC-9** | **All session/run state is component-local React state; nothing is addressable.** `composer-surface.tsx` `useReducer`; `runId` only at `workspace-surface.tsx:194`; no list-runs route in `run.py`; `nav-items.ts:13` is a same-route `<Link>`; no `save` in `api-client/teams.ts`. | P2-F1, P2-F2, P5-F1, P10-F3, CX-F5, CX-F6 — **6** |

### The meta-pattern

**RC-1, RC-2, RC-3 and RC-7 are the same mistake wearing four hats:**

> An LLM's free-form output is adopted as trusted, validated state, and the deterministic layer around it neither constrains what comes in nor reports on what it did with it.

The invariant the codebase is missing is a single one: *every LLM-authored field crosses a validating boundary on the way in, and every deterministic transformation reports what it changed on the way out.* Concretely, in four places:

- **In:** tool names are not checked against the registry (RC-3); provider names are not checked against the catalog's `runtime_supported` flag (RC-2/§3.5); `suggested_tools` and its `env_vars` are not checked against anything at all (RC-3).
- **Out:** the doc generator does not read `PROVIDERS[…].env_var` (RC-7); the chat does not diff the spec (RC-1); the model resolver reports to `stderr` (RC-2/§4.3); the tool registry reports to `stdout` (RC-3).

The recurring shape of the honest fix is striking: **in almost every case the correct value already exists in the repo, ten to a hundred lines from the code that ignores it.** `PROVIDERS[…].env_var` for RC-7. `unsupported_reason` for §3.5. `AVAILABLE_TOOLS` for RC-3. The real `shell_command_tool` for RC-4. `crewai_runner.py.j2:105` for RC-5. `crewai/llm.py`'s `finish_reason` for RC-6. `POST /api/teams/save` for RC-9. These are not missing features. They are **built features that are not wired up.**

**RC-5, RC-6, RC-8 and RC-9 share a second, narrower pattern:** a working implementation exists on one path and is absent on the path users actually take (generated runner vs in-product engine; save endpoint vs frontend client; token-limit categoriser vs the non-exception failure it cannot see).

### Fix order, by leverage

1. **RC-5** — one line, `tools=` in `_build_agent`. **Must not land before RC-3/RC-4**, or the product starts raising `NotImplementedError` where it currently hallucinates.
2. **RC-3 + RC-4 together** — one shared allowlist, validated at the point `agent.tools` is written; stop rendering stubs that shadow real names. Clears 7 findings and unblocks RC-5.
3. **RC-8** — make the validator check tool availability. This is what converts the remaining long-tail from "silently broken" to "declared broken," and it is cheap.
4. **RC-7** — read `PROVIDERS[…].env_var` in `_agent_env_vars`; derive the doc examples from `team.agents`. Clears 9 findings, mostly mechanically.
5. **RC-1** — give `describeProposal` the previous spec and let it state the diff. Clears 12 findings. A separate answer mode (RC-1's real fix) is a larger design change and can follow.
6. **RC-6** — thread `finish_reason` into `RunResult` and surface it. Small, high trust value.
7. **RC-2** — apply refinements as a patch, or make the re-author prompt carry forward existing `llm` assignments explicitly.
8. **RC-9** — wire the save call; persist `run_id` (URL or storage) and add a current-run lookup.

---

## 10. Release decision

**Do not release.** RC-5, RC-3/RC-4 and RC-8 together mean the product will confidently report success for capabilities it never loaded, and this is not a corner case — it fires for every research, coding, DevOps or data team, which is most of the product's stated purpose.

The encouraging read: the engine underneath is genuinely good, and the fix list is short and mostly mechanical. Items 1–4 above are a handful of days of work and clear 25 of the ~48 findings, including all three P0s. Nothing here suggests an architectural rewrite — it suggests a codebase where the last wire on several finished features was never connected.
