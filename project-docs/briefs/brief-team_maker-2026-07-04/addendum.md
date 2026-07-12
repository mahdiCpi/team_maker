# Addendum — the conversational team-builder

_Depth captured during the brief conversation that belongs downstream (architecture / roadmap / PRD) rather than in the 1–2 page brief. Not audit information._

## Product surfaces (interface & API design — for downstream architecture)

Three developer-facing API endpoints plus a UI, as described by the user:

1. **Composer endpoint** — an LLM takes plain-language intent and authors a
   team_maker-compatible input (YAML), guaranteeing it matches team_maker's *current* input
   format, then creates the team. (This is the central new capability; not yet built.)
2. **Run/use endpoint** — invoke or interact with a team *after* it has been created (the
   missing runtime layer; see project-docs/vision-and-target-architecture.md).
3. **Generate-only endpoint** — return a set of YAML files without running anything (thin
   wrapper over today's `team_maker` factory).
4. **Minimal UI (v1)** — for semi-technical users who won't call the API directly. API keys
   are supplied via a **separate config file**, not entered through the UI.

Redistribution angle: technical users can run the tool with **free/local models** and offer
it onward to their own outside/non-technical users.

## Flagship use-case domains (candidates for showcase teams)

- **Research / content team** — e.g. researcher → writer → editor → critic. Proposed primary
  showcase (replaces the software-delivery example as the "hero" demo).
- **Education team** — multiple tutors that adapt to *how* a given learner learns and teach
  accordingly. Named as a distinct flagship domain.
- **Analysis / critique teams** — general "different thinkers" review/critique panels.
- **Software/technical teams** — retained; devs may embed a content-creator (or other) team
  inside their own software via the API. (Note the honest limit: not for large/complex
  coding projects.)

## Backlog / parked roadmap

- **Hosted/managed tier** — users don't provide their own API keys; "they pay us, we take
  care of the rest." Turns the pure non-technical audience from aspirational into servable.
- Education-tutor team as a first-class product surface.
- Developer-embed distribution (team-as-a-component inside third-party software).

## Foundation already built (from project-docs/)

`team_maker` today: YAML request → validated (Pydantic) → template → generators → self-
contained team package (agents/tasks/routing/docs) on disk. Multi-provider routing is already
data-driven (anthropic/openai/ollama/groq/google) with per-agent assignment. It does NOT run
agents and has no conversational front door — those are the two build gaps this product fills.
See project-docs/architecture.md and vision-and-target-architecture.md for the full picture.
