---
title: 'team_maker — conversational multi-agent team builder'
status: final
created: 2026-07-05
updated: 2026-07-05
---

# PRD: team_maker (conversational multi-agent team builder)

_Working title — confirm._

## 0. Document Purpose

This PRD is for the builder(s) of team_maker and the downstream architecture and epic/story
workflows. It defines **v1 capabilities**, not implementation — technology and mechanism choices
(runtime engine, API contract shapes, persistence) live in `addendum.md` and the technical docs
under `project-docs/`. It builds on the finalized product brief
(`project-docs/briefs/brief-team_maker-2026-07-04/brief.md` + addendum) and now also on the
finalized **UX spines** (`project-docs/ux-designs/ux-team_maker-2026-07-05/DESIGN.md` and
`EXPERIENCE.md`), which own *how it looks/works*; this PRD references them and does not duplicate
them. Vocabulary is Glossary-anchored (§3); features are grouped with globally-numbered FRs
nested; inferences are tagged `[ASSUMPTION]` inline and indexed in §9.

> **Rev 2 (2026-07-05):** updated after the UX pass. Added the conversational Composer (FR-20),
> key-aware resolution + OpenRouter (FR-21/FR-22), and a Team Workspace — chat, documents, save,
> recent-teams (FR-23…FR-26). Closed Open Questions 6–7. New v2 items: team memory/learning,
> always-on teams, managed local-model fleets.

## 1. Vision

team_maker turns a plain-language description into a working **team of AI agents that spans
multiple providers** — a team of different thinkers, so a user never has to ask one model and
paste its answer into another. You describe the team you want in a short back-and-forth; an LLM
writes the valid configuration for you; the system builds the team, and you run it or **chat
with it** while the agents collaborate to produce a result.

It ships free and open-source, aimed first at **semi-technical users** who bring their own
model keys (including free or local models), with developer APIs so teams can be embedded in
other software. It stands on an existing, working **Factory** that already generates
self-contained, multi-provider **Team Packages** from a structured spec; v1 adds the two
missing halves — a conversational **Composer** and a **Runtime** that actually runs teams — plus
a **minimal UI**.

Its honest edge is non-code work: research, content, analysis, critique, and education teams —
not large or complex software-engineering projects.

## 2. Target User

### 2.1 Jobs To Be Done

- "I want several specialized AI 'thinkers' to collaborate on my task, without copy-pasting
  between chatbots or wiring an agent framework myself."
- "I want each teammate to use the best (or cheapest, or local) model for its job, without a
  single-vendor lock-in."
- "As a developer, I want to drop a ready-made team (e.g. content creation) into my own
  software through an API."
- "I want to describe the team in plain language and get something that actually runs."

### 2.2 Non-Users (v1)

- Purely **non-technical** users who won't obtain or configure any API key — served later via
  the hosted/no-keys tier (backlog).
- Teams for **large/complex software engineering** projects.

### 2.3 Key User Journeys

Light journeys (scope dial: lighter); persona context inline.

- **UJ-1. Nadia stands up a research-and-writing team in plain language.**
  Nadia, a content strategist who can get an API key but won't write YAML, opens the minimal
  UI and types "a team that researches a topic, drafts an article, and critiques it." The
  Composer proposes a Team Spec (researcher → writer → editor → critic) with a sensible model
  per role; she skims it, tweaks one role's model to a cheaper option, and clicks build then
  run. The team executes and returns a drafted, critiqued article. Realizes FR-1, FR-3, FR-4,
  FR-8, FR-11.

- **UJ-2. Sam embeds a content team inside his own app.**
  Sam, a developer, calls the compose-and-create API with an intent string, gets back a team
  reference, then calls the run API from his product whenever a user needs content generated —
  never leaving his app. Realizes FR-16, FR-17, FR-18.

- **UJ-3. Omar starts from the built-in education team, then tweaks it.** *(lighter)*
  Omar picks the pre-built **education team** that ships with v1, runs it immediately, and later
  describes changes so the Composer adapts it to how he learns. Realizes FR-19, FR-1, FR-8.

- **UJ-4. Priya assigns a model per agent, in plain language.** *(lighter)*
  Priya types "researcher argues *for* using Claude, a critic argues *against* using Gemini,
  ChatGPT is the judge." The Composer maps each named model to a Provider and runs the key
  check; the judge's openai key is missing, so it says exactly that and offers OpenRouter. She
  accepts, the check clears, and the team builds with her exact routing. Realizes FR-4, FR-21,
  FR-22, FR-10.

## 3. Glossary

- **Team** — a set of Agents assembled to accomplish a stated purpose.
- **Agent** (a.k.a. team member) — one LLM-backed role with its own Routing and one or more
  Tasks.
- **Provider** — an LLM backend (e.g. anthropic, openai, google, groq, or a local runner such
  as ollama).
- **Routing** — the per-Agent Provider + model assignment.
- **Team Spec** — the structured input (YAML) that fully defines a Team; conforms to the
  Factory's input schema.
- **Composer** — the LLM-driven capability that authors a valid Team Spec from plain-language
  intent.
- **Factory** — the existing generation pipeline that turns a Team Spec into a Team Package.
- **Team Package** — the self-contained set of generated files (agent specs, tasks, routing,
  docs) that defines a runnable Team.
- **Runtime** — the component that executes a Team Package so Agents collaborate and produce a
  result.
- **Run** — one execution of a Team against a user goal.
- **Task** — a unit of work assigned to an Agent, with ordered dependencies (a DAG).
- **Key Config** — the separate file that holds API keys per Provider.
- **OpenRouter** — a Provider gateway: a single OpenRouter key routes many models, so one key can
  satisfy multiple Agents' Routing.
- **Team Workspace** — the surface where a user uses a built Team: a chat with the Team plus a
  document loader and run controls.
- **Document** — a user-supplied file attached to a Run/session as transient context (no
  persistent memory in v1).

## 4. Features

### 4.1 Conversational Team Composer

**Description:** The Composer is a **conversational, multi-turn** capability: the user describes
a Team in plain language, the Composer proposes one and asks targeted follow-ups to tune it, and
at any point the user can just run it. It uses the Factory's current input schema as its
contract and never hands the user an invalid spec. Realizes UJ-1, UJ-3, UJ-4.

**Functional Requirements:**

#### FR-1: Compose a Team Spec from natural language
A user can describe a desired Team in plain language — including naming specific agents, their
models, and their tasks — and receive a Team Spec (roles, tasks, Routing) valid against the
Factory's current input schema.
**Consequences (testable):**
- Given a plain-language request, the system emits a Team Spec that passes Factory schema
  validation without manual editing.
- Named models/roles/tasks in the request are reflected in the emitted spec; role names, task
  structure, and Routing conform to the Glossary and schema constraints (e.g. snake_case unique
  role names).

#### FR-20: Conversational tuning with a run-now escape
The Composer refines the Team over a back-and-forth conversation (asking about roles, models,
tasks) and always offers to build/run immediately without further tuning.
**Consequences (testable):**
- The user can reach a built Team either by answering follow-ups or by choosing "run now" at any
  turn.
- Each conversational change re-derives a schema-valid spec (FR-2).

#### FR-2: Guarantee validity (validate-and-repair)
The Composer validates its draft against the schema and self-corrects before presenting it; no
schema-invalid spec reaches the user or the Factory.
**Consequences (testable):**
- On a validation failure, the system re-derives the spec and re-validates; only a passing spec
  is surfaced.
- If it cannot produce a valid spec after bounded retries, it reports a clear error rather than
  emitting an invalid spec. `[ASSUMPTION]` bounded retry count.

#### FR-3: Optional review and edit before build
By default the Team is built automatically from the composed spec. A user may opt into a review
step to inspect and edit roles, tasks, and per-agent Routing before build.
**Consequences (testable):**
- With no review requested, a valid composed spec builds automatically.
- When review is requested, the proposed spec is shown before build; user edits are
  re-validated (FR-2) and reflected in the built Team.

#### FR-4: Assign a provider/model per agent from intent + preferences
The Composer assigns Routing per Agent, honoring user preferences (e.g. "use local/cheap
models") and constraints, with sensible defaults otherwise.
**Consequences (testable):**
- Absent a stated preference, each Agent receives a default Provider/model; stated preferences
  (cost, local-only, specific provider) are respected in the emitted Routing.

**Notes:** `[NOTE FOR PM]` The Composer itself needs a Provider/model to run — which model
authors the spec, and where its key comes from, is an Open Question (§8).

### 4.2 Multi-Provider Team Generation (Factory)

**Description:** The Factory turns a Team Spec into a self-contained, multi-provider Team
Package. This capability largely exists today; v1 wraps and reuses it. Realizes UJ-1.

**Functional Requirements:**

#### FR-5: Generate a self-contained Team Package
The system generates a Team Package (agent specs, tasks, Routing, docs) from a Team Spec, with
no runtime dependency on the generator.
**Consequences (testable):**
- The Team Package contains one config per Agent and per Task, a routing config, and runs
  independently of the Factory code.

#### FR-6: Per-agent multi-provider Routing
Each Agent in a Team may use a distinct Provider/model; the system supports at least anthropic,
openai, google, groq, and a local runner (ollama).
**Consequences (testable):**
- A Team with agents on two different Providers builds and each Agent's Routing is preserved in
  its config.
- Adding a new Provider requires configuration only, not code changes to the Factory.

#### FR-7: Validate the generated package
The system validates the Team Package (required files present, configs well-formed) and
surfaces pass/fail with actionable issues.
**Consequences (testable):**
- Missing required files or malformed configs produce specific, human-readable validation
  issues; a clean package reports pass.

### 4.3 Team Runtime (run a team)

**Description:** The Runtime executes a Team Package so Agents collaborate on their Tasks and
produce a result. This is the largest net-new build in v1. Realizes UJ-1, UJ-2, UJ-3.

**Functional Requirements:**

#### FR-8: Run a team against a goal
A user can run a created Team against a goal; the Runtime executes Tasks in dependency order.
**Consequences (testable):**
- Tasks execute respecting their DAG; a Task does not start before its dependencies complete.

#### FR-9: Agents collaborate / hand off
Agents pass work to one another per the Task DAG rather than the user relaying messages between
models.
**Consequences (testable):**
- A downstream Agent receives the relevant upstream Agent output as input to its Task.

#### FR-10: Resolve credentials before running
At run start the Runtime resolves each Agent's Provider/model and loads credentials from the
Key Config; missing keys for required Providers are reported **before** work begins, not
mid-run.
**Consequences (testable):**
- If a required Provider's key is absent, the Run fails fast at start with a message naming the
  Provider and the missing key; keyless (local) Providers run without a key.

#### FR-11: Return results
The Runtime returns the Team's final result and makes intermediate Task outputs available.
**Consequences (testable):**
- A completed Run yields a final result plus per-Task outputs retrievable by the user/API.
- Results are returned in **batch** in v1; live streaming/progress is deferred to v2.

### 4.4 Key & Provider Configuration

**Description:** API keys live in a separate Key Config file, never entered through the UI.
Realizes UJ-1.

**Functional Requirements:**

#### FR-12: Keys in a separate config file
API keys are supplied via a separate Key Config file; the system reads keys from it at run
time and never requires key entry in the UI.
**Consequences (testable):**
- Keys are read from the Key Config; the UI has no key-entry field; keys are never written to
  logs or run output.

#### FR-13: Keyless (local/free) providers
Providers that need no key (e.g. local ollama) are usable without any Key Config entry.
**Consequences (testable):**
- A Team using only local Providers runs with an empty/absent Key Config.

#### FR-21: Key-aware model resolution
The system resolves models against the keys the user actually has: if no models are specified,
it uses models covered by available keys; if a specific model is named, it verifies that model's
key is present; if no keys exist at all, it asks the user to add one before any Run.
**Consequences (testable):**
- With no model specified and ≥1 key present, Agents are routed only to models the user can run.
- A named model whose key is absent is flagged at the key check (not at mid-run), naming the
  Provider and how to fix it.
- With zero keys, the system blocks the Run and prompts for a key before proceeding.

#### FR-22: OpenRouter support
A user can supply a single OpenRouter key; the system routes covered models through OpenRouter
and reflects this in the key check.
**Consequences (testable):**
- With an OpenRouter key present, Agents whose models are OpenRouter-reachable pass the key
  check and are labelled as routed "via OpenRouter".
- OpenRouter is discoverable in Settings as an alternative to per-Provider keys.

### 4.5 Minimal UI

**Description:** A minimal interface so semi-technical users reach the product at launch, not
only via CLI/API. Delivered as a **web app plus macOS and Windows desktop** builds. Realizes
UJ-1.

**Functional Requirements:**

#### FR-14: End-to-end flow in the UI
A user can, from the UI: describe a Team in conversation, (optionally review/edit the proposed
Team Spec,) build it, open its Team Workspace to chat/run/attach documents, see results, and
find past Teams in the recent-teams list. Navigation is a left sidebar (New Team, Starter Teams,
My Teams, Settings).
**Consequences (testable):**
- Each step (describe → build → workspace: chat/run/results, with optional review) is reachable
  in the UI without editing files by hand (except the Key Config).
- The UI ships as a web app and as macOS and Windows desktop builds. `[ASSUMPTION]` shared
  codebase across the three surfaces.
- Settings shows the Key Config path, per-Provider key status, the OpenRouter option, and plain
  guidance on keeping keys safe.

#### FR-15: Plain-language errors and warnings
The UI surfaces validation errors (FR-2/FR-7) and missing-key warnings (FR-10) in plain
language.
**Consequences (testable):**
- A missing-key or validation condition renders a human-readable message in the UI, not a raw
  stack trace.

### 4.6 Developer API

**Description:** Endpoints so developers can create and run Teams programmatically and embed
them in their own software. Realizes UJ-2.

**Functional Requirements:**

#### FR-16: Compose-and-create endpoint
An API endpoint accepts plain-language intent (and optional preferences) and returns a
reference to a created Team plus its validation result.
**Consequences (testable):**
- A valid intent returns a Team reference and a pass/fail validation payload.

#### FR-17: Run endpoint
An API endpoint runs an existing Team by reference against a goal and returns results.
**Consequences (testable):**
- A run request against a valid Team reference returns final + per-Task outputs (or a fast-fail
  per FR-10).

#### FR-18: Embeddable
The compose-and-create and run endpoints are sufficient to embed a Team inside third-party
software without using the UI.
**Consequences (testable):**
- The UJ-2 flow (create then run from an external app) is achievable using only these
  endpoints.

### 4.7 Starter Teams

**Description:** Ready-made Teams users can run without composing anything. v1 ships a small
set of curated starters (including a **baseline education team** and the research/content
showcase); users can still compose their own from scratch. Realizes UJ-3.

**Functional Requirements:**

#### FR-19: Ship runnable starter teams
The product includes at least one baseline **education team** and the flagship **research/
content team** as ready-to-run starters.
**Consequences (testable):**
- A user can select a starter Team and run it (FR-8) without going through the Composer.
- A starter Team is a valid Team Spec/Package like any other, so it can be reviewed/edited
  (FR-3) or adapted via the Composer.

**Notes:** `[NON-GOAL for MVP]` the broader library of ~20 domain team templates is v2 (see
§6.2) — deferred because the input-spec format may change first.

### 4.8 Team Workspace (use a team)

**Description:** After a Team is built, the user uses it in a **Team Workspace**: a chat with the
Team plus a document loader and run controls. Built Teams are findable in a lightweight
recent-teams list. Realizes UJ-1, UJ-3.

**Functional Requirements:**

#### FR-23: Chat with a team
A user can open a built Team and interact with it through a chat surface (give goals, ask
follow-ups); running the Team happens from here.
**Consequences (testable):**
- A user can open a saved Team and start a Run by chatting a goal, without re-composing.

#### FR-24: Attach documents to a run (transient)
A user can attach one or more Documents to a Run/session as context.
**Consequences (testable):**
- Attached Documents are available to the Team for that Run/session; they are **not** retained as
  persistent memory in v1 (see §6.2 for the v2 memory item).

#### FR-25: Save a team and its results
After a Run, the system offers to save the Team and its results.
**Consequences (testable):**
- Declining leaves nothing persisted beyond the recent-teams entry; accepting stores the Team
  and that Run's results for later retrieval.

#### FR-26: Recent teams list
Built Teams appear in a lightweight recent-teams list so users can find and reuse them.
**Consequences (testable):**
- A built Team is retrievable from the list and can be re-run or opened in its Workspace.
- `[NON-GOAL for MVP]` full versioning/history of Teams is v2 (see §6.2).

## 5. Non-Goals (Explicit)

- Not a generator for large/complex software-engineering projects.
- Not a hosted/no-keys service in v1 (users bring their own keys). `[NON-GOAL for MVP]`
- No generate-only API endpoint (return files without running) in v1. `[NON-GOAL for MVP]`
- Not a general-purpose chatbot; the chat surface is scoped to composing and using a built Team.
- No **persistent team memory / learning-while-working** in v1 — documents are transient to a
  Run (§4.8 FR-24); persistent memory is v2. `[NON-GOAL for MVP]`
- No **always-on teams** (teams running as toggleable persistent services) in v1 — Runs are
  on-demand; always-on is v2. `[NON-GOAL for MVP]`
- No **managed/large local-model fleets** in v1 (install/manage or connect an "army" of local
  models) — v2. `[NON-GOAL for MVP]`
- No billing, payments, or user accounts in v1.
- No broad template library in v1 — v1 ships a baseline education team + research/content
  starter (§4.7); the ~20 domain templates are v2. `[NON-GOAL for MVP]`
- No live result streaming in v1 (batch only); streaming is v2.

## 6. MVP Scope

### 6.1 In Scope

- Conversational, multi-turn Composer (§4.1) with validate-and-repair, run-now, and optional review.
- Multi-provider Factory generation (§4.2) — reuse existing code.
- Team Runtime that runs teams and lets agents collaborate (§4.3).
- Key Config file + keyless local providers + **key-aware resolution** + **OpenRouter** (§4.4).
- Minimal UI for the end-to-end flow — web app + macOS + Windows desktop, sidebar nav (§4.5).
- Compose-and-create + run API endpoints (§4.6).
- Starter Teams: a **baseline education team** + the **research/content** showcase (§4.7).
- **Team Workspace** — chat with a team, attach documents (transient), save team + results,
  recent-teams list (§4.8).

### 6.2 Out of Scope for MVP

- **Library of ~20 domain team templates** (education, research, brainstorming, customer-support
  ops, legal-document assistant, content generation, sales & lead generation, etc.) — deferred
  to v2 because the input-spec format may change first. `[NOTE FOR PM]` a v1 differentiator if
  timeline allows.
- Live result **streaming** — v2 (v1 is batch).
- **Persistent team memory / learning-while-working** — v2 (architecturally heavy: persistent
  state, likely a vector store).
- **Always-on teams** (persistent, toggleable team services) — v2.
- **Managed/large local-model fleets** (install/manage or connect many local models) — v2.
- Generate-only API endpoint — low value without running. Deferred to v2.
- Hosted/no-keys tier — opens the non-technical audience; deferred. `[NOTE FOR PM]`
  emotionally load-bearing; revisit once v1 adoption is shown.
- Large/complex code-generation teams — out by design.
- Full **team versioning/history** — v1 keeps only a lightweight recent-teams list; versioning
  is v2.

## 7. Success Metrics

**Primary**
- **SM-1**: Teams created — count of Teams composed-and-built. Target: `[ASSUMPTION]` set at
  launch. Validates FR-1..FR-7.
- **SM-2**: Non-coding adoption — count of non-technical/non-coding users running Teams for
  domains like education and research. Validates FR-1, FR-8, FR-11.

**Secondary**
- **SM-3**: Teams actually run (activation) — share of created Teams that are also run at least
  once. Validates FR-8..FR-11.
- **SM-4**: Released under the startup's R&D department — a delivery success condition (met/not
  met), not a growth metric.

**Counter-metrics (do not optimize)**
- **SM-C1**: GitHub stars/forks without a rising SM-1 — vanity signal; counterbalances SM-1.
- **SM-C2**: Coverage/complexity of software-engineering teams — explicitly not a goal;
  counterbalances any pull toward the coding use case.

## 8. Open Questions

1. **Runtime engine** — build the Runtime on CrewAI (matches today's generated `run_example.py`
   and preserves multi-provider Routing), on Claude Code subagents, or custom? (See
   `project-docs/vision-and-target-architecture.md`; mechanism detail in `addendum.md`.)
2. **Composer's own model** — which Provider/model authors the Team Spec, and where does its key
   come from (part of Key Config)?
3. **Team persistence/identity** — how are Teams stored and referenced between compose and run
   (Team reference format, storage)?
4. **Results delivery** — batch vs. streaming; how is Run progress shown in the UI? (v1 batch;
   streaming v2 — remaining question is how progress is surfaced.)
5. **Failure/retry policy** — what happens when a Provider errors mid-run; are partial results
   returned?
6. **Document handling** — how are attached Documents passed to Agents for a Run (in-context vs.
   retrieval), and what are the size/type limits? (New in Rev 2 with FR-24.)
7. **Conversational Composer model** — same as Open Q2 (which model runs the Composer chat, and
   its key source).

_Resolved in Rev 2:_ UI form factor = web + macOS + Windows desktop (was Q6); spec review is
optional, auto-build is the default (was Q7).

## 9. Assumptions Index

- §4.1 FR-2 — the validate-and-repair loop has a bounded retry count.
- §4.5 FR-14 — the web / macOS / Windows UI is built from a shared codebase.
- §4.8 FR-24 — attached Documents are transient to a Run/session in v1 (no persistent memory).
- §4.8 FR-26 — v1 keeps a lightweight recent-teams list, not full versioning.
- §7 SM-1 — concrete targets are set at launch.
