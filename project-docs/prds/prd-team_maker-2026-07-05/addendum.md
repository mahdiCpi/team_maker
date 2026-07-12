# Addendum — team_maker PRD (mechanism & downstream detail)

_Technical-how and mechanism decisions that back the PRD's capability-level FRs. Feeds
architecture/UX; not audit information. See also `project-docs/architecture.md`,
`project-docs/vision-and-target-architecture.md`, `project-docs/data-models.md`._

## Runtime engine (backs FR-8..FR-11; Open Question 1)

Leading recommendation from the vision analysis: build the Runtime on **CrewAI**, because the
Factory already emits a CrewAI-shaped `run_example.py`, and CrewAI honors per-agent
multi-provider Routing (FR-6) — which a Claude-Code-subagent-only runtime would not, without
extra provider bridges. Claude Code remains a strong **orchestrator/composer** layer (L2) that
calls the Factory (via subprocess or MCP) and supervises runs. Decision deferred to
architecture; the PRD stays capability-level.

## Developer API surface (backs FR-16..FR-18)

Capability-level endpoints for v1 (shapes to be finalized in architecture):
- **compose-and-create** — intent (+ optional preferences) → Team reference + validation result.
- **run** — Team reference + goal → final result + per-Task outputs (or fast-fail on missing
  keys per FR-10).
- Deferred (v2): **generate-only** — Team Spec → Team Package files, no run.

## Provider support (backs FR-6)

Already data-driven in the Factory: anthropic, openai, google, groq, ollama (local). Adding a
Provider is configuration, not code. The Runtime must map each Provider to a concrete client
and honor `api_key_env`/Key Config; local Providers are keyless (FR-13).

## Composer model (Open Question 2)

The Composer is itself an LLM call. Undecided: which Provider/model authors the Team Spec and
whether its key is a dedicated entry in the Key Config. Default candidate: a capable general
model; must be swappable.

## Team persistence / identity (Open Question 3)

The compose step produces a Team Package on disk today. v1 needs a stable **Team reference** so
run can find it. Minimal approach: reference by output path / generated id. Versioning and a
team library are out of MVP (§6.2).

## Template library (v2 — backs §6.2)

~20 ready-made team-template Team Specs across domains (education, research, brainstorming,
customer-support ops, legal-document assistant, content generation, sales & lead generation,
and more) so users start from a working team. Deliberately deferred to v2 because the Factory's
input-spec format may change first — building 20 templates against a spec that then changes is
waste. v1 proves the shape with two curated starters (baseline education + research/content,
FR-19); the library follows once the spec is stable.

## Conversational Composer (backs FR-1/FR-20 — Rev 2)

Multi-turn LLM session that proposes a Team Spec and asks targeted follow-ups, always offering a
"run now" escape. Mechanism (session state, which model runs the Composer, prompt/tooling to emit
schema-valid specs) is for architecture; Open Q2/Q7. The Composer must emit specs valid against
the Factory schema and re-validate on every conversational edit.

## Key-aware resolution & OpenRouter (backs FR-21/FR-22 — Rev 2)

Resolution order: named model → verify its key; no model named → pick from models with available
keys; no keys → prompt. OpenRouter is a **gateway Provider**: one key maps to many models; the
key check reports OpenRouter-reachable models as available and labels their Agents "via
OpenRouter". Architecture decides how model→Provider→gateway mapping and reachability lookup work.

## Team Workspace, documents, memory (backs FR-23…FR-26 — Rev 2)

v1: chat-with-team surface, transient Document attachment for a Run/session, save team+results,
lightweight recent-teams list. Open Q6: how Documents reach Agents (in-context vs. retrieval) and
their limits. **v2 (architecturally heavy, flagged for design):** persistent team **memory /
learning-while-working** (persistent state, likely a vector store), **always-on** teams (teams as
long-running toggleable services rather than one-shot Runs), managed **local-model fleets**, and
full team **versioning**. Architecture should scope v1 so these v2 layers can attach later without
a rewrite.

## Foundation reuse

FR-5/FR-6/FR-7 are largely satisfied by the existing Factory (spec → validated multi-provider
Team Package). Net-new work concentrates in the Composer (§4.1), the Runtime (§4.3), the Key
Config wiring (§4.4), the minimal UI (§4.5), and the API (§4.6).
