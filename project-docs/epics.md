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
- FR-8, FR-9, FR-10, FR-11 → Epic 1 (Runtime)
- FR-12, FR-13, FR-21, FR-22 → Epic 1 (keys, key-aware resolution, OpenRouter)
- FR-20 → Epic 1 (conversational core) / surfaced in Epic 2
- FR-3, FR-14, FR-15 → Epic 2 (UI: optional review, end-to-end flow, plain-language errors)
- FR-23, FR-24, FR-25, FR-26 → Epic 2 (Team Workspace: chat, docs, save, recent teams)
- FR-19 → Epic 3 (starter teams)
- FR-16, FR-17, FR-18 → Epic 4 (developer API + embed)

## Epic List

### Epic 1: Describe → build → run a team, end to end (headless core)
The walking skeleton, usable from the CLI: a user goes from plain-language intent to a running
team's result. Composer (conversational, validate-and-repair, per-agent routing) → Factory
(reuse) → Runtime (CrewAI behind a port). Includes key-aware resolution, Key Config, OpenRouter,
and the required multi-provider conformance test — the biggest technical risk, retired first.
**FRs covered:** FR-1, FR-2, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9, FR-10, FR-11, FR-12, FR-13, FR-20, FR-21, FR-22

### Epic 2: The app — minimal UI & Team Workspace
A friendly cross-platform app over the core: sidebar IA, conversational Composer with a "run now"
escape and optional review/edit, the Team Workspace (chat with the team, document loader, task
list, results), save + recent-teams, plain-language key-check states, and Settings. Realizes the
UX spines (shadcn + Coinpela brand, teal tokens, light/dark).
**FRs covered:** FR-3, FR-14, FR-15, FR-23, FR-24, FR-25, FR-26  · **UX-DR1–9**

### Epic 3: Start fast — starter teams
Ship runnable starter teams (baseline education + research/content); browse and run one
immediately without composing, or adapt it via the Composer.
**FRs covered:** FR-19

### Epic 4: Developer surface — API & embed
A stable public API (compose-and-create, run) and CLI sufficient to create, run, and embed teams
in third-party software without the UI.
**FRs covered:** FR-16, FR-17, FR-18

## Epic 1: Describe → build → run a team, end to end (headless core)

Deliver the walking skeleton, usable from the CLI: plain-language intent → running team → result.

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

## Epic 2: The app — minimal UI & Team Workspace

A friendly cross-platform app over the core, realizing the UX spines.

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

### Story 2.4: Team Workspace — chat, documents, run, results
As a user, I want to use a built team in one place,
so that I can give it goals, add context, and read outputs together.
**Acceptance Criteria:**
**Given** a built team's Workspace
**When** I chat a goal, optionally drag in a document, and run
**Then** attached documents are used as transient context for that run (not persisted), the task
list shows progress (accent pulse on the active task), and results appear with per-task outputs
expandable. (FR-23, FR-24, FR-14, UX-DR6)

### Story 2.5: Save team + results and recent-teams list
As a user, I want to keep teams and results and find them later,
so that I can reuse a team without recomposing.
**Acceptance Criteria:**
**Given** a completed run
**When** I'm prompted to save
**Then** declining persists nothing beyond the recent-teams entry, and accepting stores the team
and that run's results locally (SQLite + files)
**And** My Teams lists built teams so I can reopen a Workspace or re-run. (FR-25, FR-26, AD-11)

### Story 2.6: Settings — keys and providers
As a user, I want a place to understand my key setup,
so that I can configure providers safely.
**Acceptance Criteria:**
**Given** Settings is open
**When** I view it
**Then** it shows the Key Config file path, per-provider key status, the OpenRouter option, and
plain guidance on keeping keys safe — with no key-entry field in the UI. (UX-DR7, AD-9)

### Story 2.7: Accessibility floor
As any user, I want the app to be keyboard- and screen-reader-usable,
so that it's accessible.
**Acceptance Criteria:**
**Given** any surface
**When** I navigate by keyboard or screen reader
**Then** it meets WCAG 2.2 AA, is fully keyboard-operable, announces run progress via aria-live,
and pairs color with text/labels (never color-only). (UX-DR9, NFR4)

## Epic 3: Start fast — starter teams

### Story 3.1: Ship baseline starter teams
As the product, I want curated starter teams included,
so that users can run something immediately.
**Acceptance Criteria:**
**Given** a fresh install
**When** the user opens Starter Teams
**Then** a baseline education team and a research/content team are present as valid Team
Specs/Packages. (FR-19)

### Story 3.2: Run and adapt a starter team
As a user, I want to run a starter without composing, then tweak it,
so that I get value on day one and can personalize later.
**Acceptance Criteria:**
**Given** a starter team
**When** I select and run it
**Then** it runs via the core (Story 1.5) without going through the Composer
**And** "Adapt with Composer" opens it pre-loaded so I can change roles/models in conversation,
re-validating before rebuild. (FR-19, FR-1, FR-8)

## Epic 4: Developer surface — API & embed

### Story 4.1: Compose-and-create endpoint
As a developer, I want to create a team from intent via API,
so that I can build teams programmatically.
**Acceptance Criteria:**
**Given** the API is running
**When** I POST plain-language intent (and optional preferences)
**Then** I get back a team reference plus a pass/fail validation result. (FR-16)

### Story 4.2: Run endpoint
As a developer, I want to run an existing team via API,
so that I can trigger teams from my own software.
**Acceptance Criteria:**
**Given** a valid team reference
**When** I POST a goal to the run endpoint
**Then** I get final + per-task outputs (batch), or a fast-fail naming a missing provider key. (FR-17, FR-10)

### Story 4.3: Embed a team in third-party software (CLI + docs)
As a developer, I want the endpoints and CLI to be sufficient to embed a team,
so that I can drop, e.g., a content team into my product.
**Acceptance Criteria:**
**Given** only the compose-and-create and run endpoints (plus the CLI)
**When** I create then run a team from an external app
**Then** the full flow works without using the UI, and the contract is documented. (FR-18)
