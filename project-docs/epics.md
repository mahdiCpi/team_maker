---
stepsCompleted: ['step-01', 'step-02', 'step-03', 'step-04']
inputDocuments:
  - project-docs/prds/prd-team_maker-2026-07-05/prd.md
  - project-docs/prds/prd-team_maker-2026-07-05/addendum.md
  - project-docs/architecture/architecture-team_maker-2026-07-05/ARCHITECTURE-SPINE.md
  - project-docs/ux-designs/ux-team_maker-2026-07-05/DESIGN.md
  - project-docs/ux-designs/ux-team_maker-2026-07-05/EXPERIENCE.md
---

# team_maker - Epic Breakdown

## Overview

Epic and story breakdown for team_maker v1 (the conversational multi-agent team builder),
decomposing PRD Rev 2 (FR-1…FR-26), the architecture spine (AD-1…AD-13), and the UX spines into
implementable stories. Kept lean and actionable.

## Requirements Inventory

### Functional Requirements

_Composer_
- FR-1: Compose a valid Team Spec from plain-language intent (incl. named agents/models/tasks).
- FR-20: Conversational multi-turn tuning with a "run now" escape.
- FR-2: Validate-and-repair — never surface/build a schema-invalid spec.
- FR-3: Optional review/edit before build (auto-build is default).
- FR-4: Assign provider/model per agent from intent + preferences.

_Factory (existing, reused)_
- FR-5: Generate a self-contained Team Package from a Team Spec.
- FR-6: Per-agent multi-provider routing (anthropic/openai/google/groq/ollama).
- FR-7: Validate the generated package; surface pass/fail with actionable issues.

_Runtime_
- FR-8: Run a team against a goal; execute tasks in dependency order.
- FR-9: Agents collaborate / hand off per the task DAG.
- FR-10: Resolve credentials before running (fail fast on missing keys).
- FR-11: Return final + per-task results (batch in v1).
- FR-27: Expose the full run transcript — every agent's messages, handoffs, and delegations in
  order — not just the final answer.

_Keys & Providers_
- FR-12: Keys only in a separate Key Config file (never in UI, never logged).
- FR-13: Keyless local/free providers usable without a key.
- FR-21: Key-aware model resolution (use available keys / verify named model / prompt if none).
- FR-22: OpenRouter support (one key → many models) + correct key-check messaging.

_UI_
- FR-14: End-to-end flow in the UI (describe → build → workspace: chat/run/results); sidebar nav.
- FR-15: Plain-language errors and warnings.

_Developer API_
- FR-16: Compose-and-create endpoint.
- FR-17: Run endpoint.
- FR-18: Endpoints sufficient to embed a team in third-party software.

_Starter Teams_
- FR-19: Ship runnable starter teams (baseline education + research/content).

_Team Workspace_
- FR-23: Chat with a built team.
- FR-24: Attach documents to a run (transient context).
- FR-25: Save a team and its results.
- FR-26: Recent-teams list (find/reuse built teams).
- FR-28: Name/rename a saved team; delete a team and its saved results.

### NonFunctional Requirements

- NFR1 (multi-provider correctness): a team spanning ≥2 providers routes each agent to its
  intended provider; verified by a conformance test (AD-7).
- NFR2 (local-only / no infra): runs with no external services — SQLite + files only (AD-11).
- NFR3 (secrets): keys read-only from Key Config; never entered in UI, logged, or in output (AD-9).
- NFR4 (accessibility): WCAG 2.2 AA across web + desktop; full keyboard operability; aria-live run progress.
- NFR5 (cross-platform): web + macOS + Windows from a shared codebase (desktop wrapper deferred).
- NFR6 (portability): generated Team Package remains self-contained/runnable independent of the factory (AD-1).
- NFR7 (theming): all color as semantic tokens; light + dark ship together; one-place theme swap.

### Additional Requirements

_(from Architecture spine)_
- Single open-source repo, modular monolith; distribute via Docker, pip, desktop bundle, web (AD-3).
- Ports-and-adapters: LLMProvider, RuntimeEngine, Storage ports; Memory/Lifecycle as v1 no-op ports (AD-2, AD-12).
- Inward dependency direction: UI → API → core → adapters (AD-4).
- Composer→Factory→Runtime; runtime executes only, never composes (AD-5).
- CrewAI 1.14.6 behind the RuntimeEngine port; explicit per-agent LLM creds, no global env (AD-6, AD-7).
- Stack: Python 3.12+/pydantic v2/FastAPI 0.139.x · Next.js 16.2/React 19/Tailwind v4/shadcn · SQLite.
- Composer output validated against factory Pydantic schema (AD-10).
- Batch results behind a streamable interface (AD-13).
- Multi-provider conformance test required; gates CrewAI version pin.

### UX Design Requirements

- UX-DR1: shadcn/ui base + thin Coinpela brand layer; inherit defaults, override only brand tokens.
- UX-DR2: Fintech-Teal semantic color tokens (primary #0E8C82 / accent #2DD4BF), light + dark; one-place swap.
- UX-DR3: Sidebar IA — New Team, Starter Teams, My Teams, Team Workspace, Settings.
- UX-DR4: Conversational Composer surface (chat) with a persistent "run now" affordance.
- UX-DR5: Key-check states — all-good / missing-key (blocks run) / no-keys / via-OpenRouter — plain-language.
- UX-DR6: Team Workspace layout — chat pane + document loader + task list (accent pulse on active) + results.
- UX-DR7: Settings — Key Config path, per-provider status, OpenRouter option, guidance on securing keys.
- UX-DR8: Robot wordmark + "Coinpela R&D" tag; accent reserved for "live/running" only.
- UX-DR9: Accessibility floor — WCAG 2.2 AA, keyboard-first, aria-live run progress, color+label (not color-only).

### FR Coverage Map

- FR-1, FR-2, FR-4 → Epic 1 (Composer core)
- FR-5, FR-6, FR-7 → Epic 1 (Factory reuse + multi-provider)
- FR-8, FR-9, FR-10, FR-11, FR-27 → Epic 1 (Runtime; FR-27 surfaced in Epic 2 and Epic 5)
- FR-12, FR-13, FR-21, FR-22 → Epic 1 (keys, key-aware resolution, OpenRouter)
- FR-20 → Epic 1 (conversational core) / surfaced in Epic 2
- FR-3, FR-14, FR-15 → Epic 2 (UI: optional review, end-to-end flow, plain-language errors)
- FR-23, FR-24, FR-25, FR-26, FR-28 → Epic 2 (Team Workspace: chat, docs, save, recent teams,
  team naming + deletion)
- FR-19 → Epic 3 (starter teams)
- FR-16, FR-17, FR-18 → Epic 5 (developer API + embed)

## Epic List

### Epic 0: Reconcile existing code to the architecture spine
The project already contains a substantial pre-plan implementation (merged from `guru-explore`):
an LLM-driven planner (`team_maker/llm/`), a Jinja code-generation engine (`team_maker/codegen/`),
framework adapters (`team_maker/frameworks/`), and a real end-to-end `pipeline/runner.py`. This
code predates the architecture spine and **diverges from several binding invariants**. Epic 0
migrates it onto the ports-and-adapters spine so Epics 1–5 build on a conformant base rather than
greenfield. Retire the architectural debt before adding features.
**ADs addressed:** AD-1, AD-2, AD-6, AD-8 · **See:** [reconciliation-notes.md](stories/reconciliation-notes.md)

### Epic 1: Describe → build → run a team, end to end (headless core)
The walking skeleton, usable from the CLI: a user goes from plain-language intent to a running
team's result. Composer (conversational, validate-and-repair, per-agent routing) → Factory
(reuse) → Runtime (CrewAI behind a port). Includes key-aware resolution, Key Config, OpenRouter,
and the required multi-provider conformance test — the biggest technical risk, retired first.
**FRs covered:** FR-1, FR-2, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9, FR-10, FR-11, FR-12, FR-13, FR-20, FR-21, FR-22, FR-27

### Epic 2: The app — minimal UI & Team Workspace
A friendly cross-platform app over the core: the **API seam AD-4 requires** (Story 2.0, an enabler
that unblocks 2.2–2.6), sidebar IA, conversational Composer with a "run now"
escape and optional review/edit, the Team Workspace (chat with the team, document loader, task
list, results incl. the full agent transcript), named teams with save/rename/delete + recent-teams,
plain-language key-check states, and Settings. Realizes the UX spines (shadcn + Coinpela brand,
teal tokens, light/dark). Stories 2.8–2.11 close gaps found by manual QA after 2.0–2.7 shipped: the
My Teams browse/re-run frontend, tolerant key-name recognition, non-team Composer input, and
lightweight onboarding.
**FRs covered:** FR-3, FR-14, FR-15, FR-23, FR-24, FR-25, FR-26, FR-27 (surfaced), FR-28  · **UX-DR1–9**

### Epic 3: Start fast — starter teams
Ship runnable starter teams (baseline education + research/content); browse and run one
immediately without composing, or adapt it via the Composer.
**FRs covered:** FR-19

### Epic 4: Deferred Work Consolidation
Consolidate and resolve all deferred technical debt from Stories 0.3–3.2 before proceeding to Epic 5.
This epic addresses security vulnerabilities, architectural inconsistencies, testing gaps, and
cleanup items that accumulated across previous epics. Addressing these now prevents them from
blocking or complicating Epic 5's API work.
**FRs covered:** None (technical debt) · **Dependencies:** None

#### Story 4.1: Security Hardening
As the codebase, I want all security vulnerabilities addressed before API exposure,
so that external developers can safely consume the package.
**Acceptance Criteria:**
**Given** the deferred security items in deferred-work.md
**When** this story completes
**Then** ANSI/OSC escape sequences in transcripts are sanitized, path traversal risks in starter router are fixed, document text cannot leak to server logs, exception messages cannot echo SDK-embedded secrets, basic authentication exists for teams API endpoints, and run-context delimiters cannot be spoofed.

#### Story 4.2: Credential Architecture Unification
As the codebase, I want a single, consistent credential resolution system,
so that provider/key management is not fragmented across multiple modules.
**Acceptance Criteria:**
**Given** the split-brain between keyconfig.py/providers/registry.py and llm/model_resolver.py
**When** this story completes
**Then** credential loading and availability reporting live in one place behind the provider layer, duplicate key definitions warn instead of silently resolving, keyless-local provider keys are not ignored, OpenRouter gateway uses data flags instead of hardcoded names, dead data fields like ProviderRouting.api_key_env are removed, api/deps.py and cli.py credential logic is consolidated, run goal validation exists, and xai's openrouter_slug/reachable inconsistency is fixed.

#### Story 4.3: Transcript and Run Subsystem Hardening
As the codebase, I want a robust transcript capture system,
so that Story 5.2 (HTTP endpoints) can reliably expose transcripts.
**Acceptance Criteria:**
**Given** the current transcript implementation
**When** this story completes
**Then** partial transcripts are returned on failed runs, concurrent runs in one process no longer corrupt each other's transcripts, the generated crewai_runner.py.j2 template captures transcripts, ANSI/OSC escape sequences are sanitized in display, transcript line format is unambiguous and bounded, and document text cannot spoof run-context delimiters.

#### Story 4.4: API Contract and Error Handling
As the codebase, I want robust error handling and contract compliance,
so that external developers have a reliable API experience.
**Acceptance Criteria:**
**Given** the current API layer
**When** this story completes
**Then** SDK-embedded secrets cannot echo in compose exceptions, per-role provider keys are bridged in compose --build, schema-level validation exists for all request fields, spec round-trip no longer mutates on PUT, empty desired_roles are guarded in build path, second builds in same session no longer fail, and fields[].message contains authored copy not pydantic-derived text.

#### Story 4.5: Template and Starter System Hardening
As the codebase, I want all gaps in the starter template system closed,
so that Epic 3's starter teams are production-ready.
**Acceptance Criteria:**
**Given** the current starter template system
**When** this story completes
**Then** template_id has schema-level validation, starter YAMLs are discovered dynamically not hardcoded, template existence is checked at request time, path traversal risks are fixed, YAML structure and content are validated, duplicate template IDs are prevented, thread safety tests exist for registry, error handling exists for corrupt/empty YAMLs, and YAML filename vs template_id sync is validated.

#### Story 4.6: Testing Infrastructure
As the codebase, I want proper CI and test coverage,
so that regressions are caught automatically.
**Acceptance Criteria:**
**Given** the current test gaps
**When** this story completes
**Then** CI lanes exist for pytest and npm test, pytest.importorskip is replaced with proper required markers, conformance tests use KeyConfig.from_file properly, missing negative tests are added, oversized test files are split, and a browser test lane exists.

### Epic 5: Developer surface — API & embed
A stable public API (compose-and-create, run) and CLI sufficient to create, run, and embed teams
in third-party software without the UI.
**FRs covered:** FR-16, FR-17, FR-18

#### Story 5.1: Compose-and-create endpoint
As a developer, I want to create a team from intent via API,
so that I can build teams programmatically.
**Acceptance Criteria:**
**Given** the API is running
**When** I POST plain-language intent (and optional preferences)
**Then** I get back a team reference plus a pass/fail validation result. (FR-16)

#### Story 5.2: Run endpoint
As a developer, I want to run an existing team via API,
so that I can trigger teams from my own software.
**Acceptance Criteria:**
**Given** a valid team reference
**When** I POST a goal to the run endpoint
**Then** I get final + per-task outputs (batch) — with the full run transcript (Story 1.7)
available on request rather than always inlined — or a fast-fail naming a missing provider key.
(FR-17, FR-10, FR-27)

#### Story 5.3: Embed a team in third-party software (CLI + docs)
As a developer, I want the endpoints and CLI to be sufficient to embed a team,
so that I can drop, e.g., a content team into my product.
**Acceptance Criteria:**
**Given** only the compose-and-create and run endpoints (plus the CLI)
**When** I create then run a team from an external app
**Then** the full flow works without using the UI, and the contract is documented. (FR-18)

## Epic 0: Reconcile existing code to the architecture spine

Migrate the merged pre-plan implementation (`llm/`, `codegen/`, `frameworks/`, `pipeline/`) onto
the ports-and-adapters spine. These stories are refactors of **existing, working, test-covered
code** — not greenfield. Each must keep the unit suite green.

### Story 0.1: Introduce the LLMProvider port and move providers behind adapters
As the codebase, I want a single `LLMProvider` port with concrete adapters,
so that the core never depends on a provider SDK and adding a provider is config, not code.
**Acceptance Criteria:**
**Given** the existing `team_maker/llm/providers.py` (ABC `LLMProvider` with `complete_structured`,
plus `create_provider`)
**When** it is migrated
**Then** a `team_maker/ports/llm_provider.py` Protocol defines the seam, concrete providers move to
`team_maker/adapters/providers/`, and core modules import only the port
**And** the existing provider tests pass unchanged or are updated in place. (AD-2, AD-8)

### Story 0.2: Remove provider-name branching from model mapping
As the codebase, I want provider selection to be data-driven,
so that no module branches on provider name (AD-1/AD-8).
**Acceptance Criteria:**
**Given** `team_maker/llm/mapper.py::_infer_provider` (branches on `gpt-`/`claude-`/`grok-` prefixes)
**When** it is refactored
**Then** provider/model resolution is driven by config/registry data, not name prefixes
**And** mixed-provider mapping tests still pass. (AD-1, AD-8)

### Story 0.3: Put CrewAI behind the RuntimeEngine port
As the codebase, I want CrewAI isolated behind a runtime port,
so that the core stays framework-agnostic and the CrewAI version is gated by the conformance test.
**Acceptance Criteria:**
**Given** the framework adapters in `team_maker/frameworks/` and generated CrewAI runners in `codegen/`
**When** the runtime seam is formalized
**Then** a `team_maker/runtime/` module sits behind a `ports/RuntimeEngine`, `crewai` is not a hard
dependency of the `team_maker` package, and the CrewAI pin follows the conformance test. (AD-6, AD-7)

### Story 0.4: Fold the Key Config feature into the provider layer
As the codebase, I want one key/provider-availability system,
so that the Story 1.1 `keyconfig.py`/`providers/registry.py` no longer duplicates `llm/model_resolver.py`.
**Acceptance Criteria:**
**Given** the retained Story 1.1 modules (`team_maker/keyconfig.py`, `team_maker/providers/registry.py`,
`keys status` CLI) and the existing `team_maker/llm/model_resolver.py`
**When** they are reconciled
**Then** key loading + availability reporting live in one place behind the provider layer, the
`keys status` command still works, and the split-brain is removed. (FR-12, FR-13, FR-21, FR-22, AD-9)

### Story 0.5: Reconcile the request schema with the documented data model
As the codebase, I want the schema and its docs to agree,
so that downstream stories have a trustworthy contract.
**Acceptance Criteria:**
**Given** the actual `team_maker/schema/request.py` (fields incl. `planning_llm`, `framework`,
`state_backend`, `git_account`, `sandbox`, `desired_tasks`, `suggested_tools`, `context_dir`,
`model_registry`, `notifications`) vs. `data-models.md`
**When** they are reconciled
**Then** `data-models.md` documents the real schema and the `planning_llm`↔`default_llm` glossary
mismatch is resolved (rename or documented alias). (AD-10)

## Epic 1: Describe → build → run a team, end to end (headless core)

Deliver the walking skeleton, usable from the CLI: plain-language intent → running team → result.

> **Reconciliation note (spec-first):** overlapping functionality already exists in the merged
> `guru-explore` code but under a pre-plan design. Epic 1 stories now consume/refactor that code
> toward the spine rather than building from scratch. See Epic 0 and
> [reconciliation-notes.md](stories/reconciliation-notes.md).

### Story 1.1: Load keys and report available models
As a user, I want the system to read my Key Config and tell me which providers/models are usable,
so that I know what I can run before composing.
**Acceptance Criteria:**
**Given** a Key Config file with some provider keys (and optionally an OpenRouter key)
**When** the system loads it
**Then** it reports each provider as available or missing, marks OpenRouter-reachable models as
"via OpenRouter", and treats keyless local providers (ollama) as available
**And** keys are never written to logs or output. (FR-12, FR-13, FR-22)

### Story 1.2: Compose a valid Team Spec from a prompt
As a user, I want to describe a team in plain language and get a valid Team Spec,
so that I don't hand-write configuration.
**Acceptance Criteria:**
**Given** a plain-language request (optionally naming agents/models/tasks)
**When** the Composer runs via the LLMProvider port
**Then** it emits a Team Spec that passes the factory Pydantic schema, reflecting any named
models/roles/tasks
**And** on a validation failure it repairs and re-validates within a bounded retry, else returns
a clear error rather than an invalid spec. (FR-1, FR-2, FR-4, AD-8, AD-10)
_Refactor, not greenfield:_ fold the existing `team_maker/llm/planner.py` into `composer/` behind
the `LLMProvider` port (Story 0.1) and reuse the existing `schema/request.py` `_pre_process`
validation instead of re-implementing it.

### Story 1.3: Conversational tuning with a run-now escape
As a user, I want to refine the proposed team over a short back-and-forth or just run it now,
so that I control the trade-off between tuning and speed.
**Acceptance Criteria:**
**Given** a proposed Team Spec from Story 1.2
**When** I send follow-up messages
**Then** each change re-derives a schema-valid spec
**And** at any turn I can choose "run now" to build immediately without further tuning. (FR-20)

### Story 1.4: Build a self-contained Team Package
As a user, I want a valid spec turned into a runnable package,
so that the team exists independently of the builder.
**Acceptance Criteria:**
**Given** a schema-valid Team Spec
**When** the factory builds it
**Then** a self-contained Team Package (agents, tasks, routing, docs) is written and validated
**And** missing/malformed files produce specific, human-readable issues; a clean package reports
pass. (FR-5, FR-7, AD-1)

### Story 1.5: Run a team and return results
As a user, I want to run a built team against a goal and get results,
so that the agents do the work instead of me relaying between chatbots.
**Acceptance Criteria:**
**Given** a built Team Package and a goal
**When** I run it
**Then** the Runtime (CrewAI behind the RuntimeEngine port) executes tasks in dependency order,
downstream agents receive upstream outputs, and I get the final result plus per-task outputs in
batch. (FR-8, FR-9, FR-11, AD-6, AD-13)

### Story 1.6: Per-agent multi-provider routing + conformance test
As a user, I want each agent to run on its own provider reliably,
so that a mixed-provider team actually works.
**Acceptance Criteria:**
**Given** a team whose agents use ≥2 different providers
**When** it runs
**Then** each agent is executed with its own explicit credentials/endpoint (never global env),
and a conformance test asserts each agent hit its intended provider
**And** if a required provider key is missing the run fails fast at start, naming the provider
and how to fix it. (FR-6, FR-10, FR-21, FR-22, AD-7)

### Story 1.7: Capture and return the full agent run transcript
As a user, I want to see everything the agents said and handed off to each other,
so that I can follow and trust how the result was produced instead of only seeing the final answer.
**Acceptance Criteria:**
**Given** a team run (Story 1.5)
**When** it completes
**Then** the RuntimeEngine port returns an ordered transcript alongside the existing final +
per-task results — each entry attributed to a task and an agent, including inter-agent handoffs
and delegations — and the CLI can show or write it on request
**And** the default CLI output is unchanged (transcript is opt-in), the transcript rides the same
batch-behind-a-streamable-interface seam so per-turn streaming can be added later without a
contract change, and no key or secret ever appears in it. (FR-27, FR-11, AD-6, AD-13, NFR3)
_Extends, not replaces:_ Story 1.5 shipped `final + per-task outputs`; this widens that result
object rather than introducing a second run path. Surfaced in the UI by Story 2.4 and over the API
by Story 5.2.

## Epic 2: The app — minimal UI & Team Workspace

A friendly cross-platform app over the core, realizing the UX spines.

### Story 2.0: The API seam — FastAPI app and compose endpoints
As the team building Epic 2, I want the FastAPI layer AD-4 requires with the compose endpoints,
so that every Epic 2 surface has a legal path to the core instead of inventing one.
**Acceptance Criteria:**
**Given** AD-4 admits no exception to "the UI reaches the system only through the API", and no
`api/` layer exists
**When** this story lands
**Then** a FastAPI app exists at repo-root `api/` per the Structural Seed, exposing the compose
session/refine/edit/build endpoints with a single error envelope, an in-process session registry
with a turn cap, and no key value ever crossing to the browser
**And** it ships no UI, and `web/` reaches it through a Next `rewrites` proxy. (AD-3, AD-4, AD-9, AD-10)

> **Enabler, numbered 2.0 deliberately.** No story in this plan created the FastAPI application:
> the architecture spine assumes `api/` throughout, its Structural Seed scopes it to
> "compose/create, run, teams, settings", the Capability Map assigns Epic 2's FR-23–FR-26 to it,
> and Epic 5's Story 5.1 opens *"Given the API is running"* — presupposing it. Story 2.1 deferred
> the decision explicitly ("Epic 2 does not create one until it needs it"). This story is that
> moment. Numbered `2.0` rather than renumbering 2.2–2.7 because 45 cross-references to those
> numbers exist across six files, four of them already-accepted stories. Follows the Epic 0
> precedent for work that must land before features.

#### Ownership of the `api/` surface

The Structural Seed (`ARCHITECTURE-SPINE.md:192`) scopes `api/` to four capability groups. Story
2.0 creates the application and the first group; the rest belong to the story that first needs
them, so no part of `api/` is orphaned again:

| `api/` group | Owned by | Notes |
|---|---|---|
| **the app itself** (`main.py`, `deps.py`, error envelope, dev topology) | **Story 2.0** | created once; every later story extends it |
| **compose/create** | **Story 2.0** | session start/refine/edit/build |
| **key status** (read-only) | **Story 2.3** | first consumer; AD-9 forbids a browser-side read |
| **run** | **Story 2.4** | the Workspace runs a built team (FR-23–FR-26 → `api/` per the Capability Map) |
| **teams** (save / browse / rename / delete / recent) | **Story 2.5** | storage-backed, AD-11 |
| **settings** (provider + Key Config *status*, never values) | **Story 2.6** | AD-9: status only, never a key value |
| **the public, versioned contract** (FR-16–FR-18) | **Epic 5** | 5.1/5.2 wrap the same app object; 2.0's routes are an internal precursor they may rename |

### Story 2.1: App shell, sidebar nav, and theming
As a semi-technical user, I want a clean app with clear navigation,
so that I can use team_maker without the CLI.
**Acceptance Criteria:**
**Given** the app is open
**When** it loads
**Then** a left sidebar exposes New Team, Starter Teams, My Teams, and Settings, with the
Coinpela robot wordmark
**And** the UI uses shadcn defaults + the Coinpela brand layer with semantic Fintech-Teal tokens,
supports light and dark, and the accent is used only for "live/running". (FR-14, UX-DR1, UX-DR2, UX-DR3, UX-DR8, NFR7)

### Story 2.2: New Team — conversational Composer with optional review
As a user, I want to describe and tune a team in the UI (or run it now),
so that composing feels like a conversation, not a form.
**Acceptance Criteria:**
**Given** I'm on New Team
**When** I describe a team
**Then** the Composer proposes one in a chat with a persistent "run now" affordance; if I enable
review, an editable spec view appears and my edits re-validate before build
**And** with review off, a valid spec builds automatically. (FR-3, FR-14, FR-20, UX-DR4)

### Story 2.3: Key-check states and plain-language errors
As a user, I want clear messages about keys and validation,
so that I know exactly what to fix.
**Acceptance Criteria:**
**Given** a team about to run
**When** the key check runs
**Then** the UI shows all-good / missing-key / no-keys / via-OpenRouter states in plain language;
a missing required key blocks the run with a fix hint
**And** validation/run errors render as human-readable messages, never raw stack traces. (FR-15, UX-DR5)


> **Owns the `api/` key-status read.** AD-9 forbids the browser touching keys, so the four
> states come from a read-only endpoint this story adds to the app Story 2.0 created. Status only —
> never a key value. Story 2.0 leaves the seam and deliberately fakes nothing.
### Story 2.4: Team Workspace — chat, documents, run, results
As a user, I want to use a built team in one place,
so that I can give it goals, add context, and read outputs together.
**Acceptance Criteria:**
**Given** a built team's Workspace
**When** I chat a goal, optionally drag in a document, and run
**Then** attached documents are used as transient context for that run (not persisted), the task
list shows progress (accent pulse on the active task), and results appear with per-task outputs
expandable
**And** I can open the full agent transcript for that run (Story 1.7) — every agent message and
handoff in order, attributed to agent and task — not just the final result. (FR-23, FR-24, FR-14,
FR-27, UX-DR6)


> **Owns the `api/` run group.** The Capability Map assigns FR-23–FR-26 to `api/`; this story adds
> the run and document endpoints to the app Story 2.0 created. AD-13 keeps results batch behind a
> streamable interface. Note `deferred-work.md` records that concurrent runs in one process corrupt
> each other's transcripts — the crewai event bus is a process-global singleton — so a run endpoint
> must serialise runs or scope capture per run.
### Story 2.5: Named teams — save, browse, rename, delete
As a user, I want teams to have names I choose and to be able to remove ones I no longer want,
so that My Teams stays meaningful and under my control instead of an append-only pile.
**Acceptance Criteria:**
**Given** a completed run
**When** I'm prompted to save
**Then** declining persists nothing beyond the recent-teams entry, and accepting stores the team
under a human-readable team name — proposed by the Composer, editable at save time, unique within
My Teams — together with that run's results locally (SQLite + files)
**And** My Teams lists built teams by name so I can reopen a Workspace, re-run, or rename a team
**And** I can delete a team: an explicit confirm that names what goes with it (the team and its
saved runs/results), after which it disappears from My Teams and recent teams. (FR-25, FR-26,
FR-28, AD-11)
_Already partly present:_ `TeamCreationRequest.team_name` (`team_maker/schema/request.py`) is
already a required, validated, unique-per-team name — this story surfaces and edits it rather than
introducing it. Rename and delete are the new capabilities.


> **Owns the `api/` teams group.** Save / browse / rename / delete / recent, storage-backed per
> AD-11 (SQLite + files, no external services). Also settles the "stable Team reference" question
> PRD Open Q3 leaves open — Story 2.0's `session_id` is deliberately *not* that.
### Story 2.6: Settings — keys and providers
As a user, I want a place to understand my key setup,
so that I can configure providers safely.
**Acceptance Criteria:**
**Given** Settings is open
**When** I view it
**Then** it shows the Key Config file path, per-provider key status, the OpenRouter option, and
plain guidance on keeping keys safe — with no key-entry field in the UI. (UX-DR7, AD-9)


> **Owns the `api/` settings group.** Provider and Key Config **status** only — AD-9 bans key entry
> in the UI outright, so no endpoint here accepts a key value.
### Story 2.7: Accessibility floor
As any user, I want the app to be keyboard- and screen-reader-usable,
so that it's accessible.
**Acceptance Criteria:**
**Given** any surface
**When** I navigate by keyboard or screen reader
**Then** it meets WCAG 2.2 AA, is fully keyboard-operable, announces run progress via aria-live,
and pairs color with text/labels (never color-only). (UX-DR9, NFR4)

> **Stories 2.8–2.11, numbered deliberately.** Epic 2 was marked done through 2.7, but a manual
> QA pass surfaced four gaps squarely inside Epic 2's own stated scope (My Teams/Team Workspace,
> key-check messaging, the Composer, the app shell) rather than Epic 3 (starter teams) or Epic 5
> (developer API). Following the Story 2.0 precedent — inserted deliberately rather than
> renumbering everything after it — these four continue the existing numbering. See each story
> file under `project-docs/stories/` for full context; none has been implemented yet.

### Story 2.8: My Teams — browse, reopen, re-run, rename, delete
As a user, I want to see the teams I've saved and act on them from My Teams,
so that building a team is not a dead end — I can come back to it later.
**Acceptance Criteria:**
**Given** `GET /api/teams/browse` (Story 2.5, already shipped)
**When** a user opens My Teams
**Then** the page lists every saved team by name with its last-run time and run count, and lets
the user reopen its Workspace, re-run it, rename it, or delete it with an explicit confirmation
**And** the reopen path resolves a real technical gap: the Workspace's loader
(`GET /api/runs/teams/{team_slug}`) reads only the build-output root, not Story 2.5's saved-teams
storage — see the story file's "Open technical question" before assuming a simple link works.
(FR-25, FR-26, FR-28, frontend-only — see
[2-8-my-teams-browse-and-rerun.md](stories/2-8-my-teams-browse-and-rerun.md))

### Story 2.9: Recognize common alternate key names without a key-entry UI
As a user, I want a Key Config entry named the way I'd naturally guess (e.g. `GOOGLE_API_KEY`) to
be recognized, so that a reasonable guess isn't silently ignored.
**Acceptance Criteria:**
**Given** the hard-coded provider catalog (`team_maker/adapters/providers/registry.py`) and its
exact-match key lookup
**When** a Key Config entry uses a well-known alternate name (seeded with `GOOGLE_API_KEY` →
`GOOGLE_AI_API_KEY`, the one evidenced case)
**Then** it is recognized as that provider's key instead of producing an "Unrecognized key name"
warning
**And** no key-entry UI is added — this is a parsing-layer change only (AD-9 still holds). (FR-12,
FR-21 — see [2-9-key-name-aliasing.md](stories/2-9-key-name-aliasing.md))

### Story 2.10: Composer should not fabricate a team from non-team input
As a user, I want the Composer to recognize when what I typed isn't a team description, so that a
bare greeting doesn't produce a fabricated team.
**Acceptance Criteria:**
**Given** the Composer's system prompt today unconditionally authors a full spec for any input
**When** a user's first message does not describe a team (e.g. "Hello")
**Then** no fabricated spec is produced or shown, and the user sees a short, specific invitation to
describe a team instead
**And** the working path (a real team description) is unchanged, and the existing turn-cap
mechanism still bounds the conversation. (FR-1, FR-2, FR-20 — see
[2-10-composer-non-team-input.md](stories/2-10-composer-non-team-input.md))

### Story 2.11: Lightweight orientation and wayfinding for new or lost users
As a user who has never used team_maker before, or who is looking for a specific feature, I want
some minimal, discoverable guidance, so that I'm not left guessing.
**Acceptance Criteria:**
**Given** no orientation or wayfinding exists today beyond one-sentence empty states
**When** a first-time user lands on New Team, or any user looks for a core concept or feature
**Then** a one-time, dismissible, plain-language orientation and a small persistent help
affordance are available
**And** neither introduces hype/celebration copy (`EXPERIENCE.md:172`, already rejected) or
duplicates existing inline copy (e.g. `composer-actions.tsx`'s Build team/Run it now sentence).
(FR-14, FR-15 — see [2-11-onboarding-guidance.md](stories/2-11-onboarding-guidance.md))


