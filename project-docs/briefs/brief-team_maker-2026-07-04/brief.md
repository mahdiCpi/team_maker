---
title: 'Product Brief: team_maker — the conversational multi-agent team builder'
status: final
created: 2026-07-04
updated: 2026-07-04
---

# Product Brief: team_maker (conversational multi-agent team builder)

_Working title — naming is open._

## Executive Summary

Most people who want real work out of LLMs end up doing it the hard way: a non-developer opens
one chatbot, gets an answer, copies it into another chatbot for a second opinion, and stitches
the pieces together by hand. A developer who wants something better reaches for a framework
like CrewAI — and then has to define every agent, wire them together, and re-do the work each
time they want a different team. Meanwhile most ready-to-use, open-source multi-agent tools
lock the whole team to a **single** LLM provider.

**team_maker** turns a plain-language description into a working **team of AI agents that spans
multiple providers** — a team of different thinkers, so you don't have to ask one model and
copy its answer into another. You describe the team you want; an LLM writes the correct
configuration for you and assembles the team; you run it and get the result. It builds on an
existing, working factory (`team_maker`) that already generates self-contained, multi-provider
team packages from a structured spec.

It ships **free and open-source** as an R&D side product, aimed first at **semi-technical
users** who can bring their own (including free or local) model keys, with developer APIs for
embedding teams into other software — and a path toward a hosted option for people who just
want the outcome.

## The Problem

- **Semi-technical users** can describe what they want but can't hand-author a valid agent
  spec or wire a framework. Today they fall back to copy-pasting between separate chatbots —
  no real collaboration between specialized agents, no repeatability.
- **Developers** *can* build multi-agent teams with CrewAI/AutoGen/LangGraph, but must define
  and wire agents themselves and re-generalize for each new team shape — high effort for
  something they'll want to vary often.
- **Single-provider lock-in:** most ready-to-use OSS multi-agent packages route the entire
  team through one provider, so you can't put the best (or cheapest, or local) model on each
  role.

## The Solution

Describe the team you need in plain language. team_maker:

1. **Composes the spec for you** — an LLM authors a valid team_maker input from your intent,
   guaranteed to match team_maker's current input format (no YAML by hand).
2. **Builds a multi-provider team** — each agent can run on a different provider/model, chosen
   for its job; bring your own keys, including free or local models.
3. **Runs the team and returns results** — a runtime executes the team so the agents
   collaborate on their tasks, rather than you relaying messages between chatbots. (This
   runtime is the main piece still to be built, and it's in v1.)

Delivered through **a minimal UI** for semi-technical users and **developer API endpoints** to
compose-and-create and to run a team, so teams can also be embedded in other software. (A
generate-only endpoint and other surfaces are backlog; see `addendum.md`.)

## What Makes This Different

- **Ready-to-use, not build-it-yourself.** vs. CrewAI et al., you don't define and wire agents
  — you describe intent and get a working team.
- **A team of different thinkers.** Multi-provider by design: the best/cheapest/local model per
  role, no single-vendor lock-in — where most OSS packages are single-provider.
- **Reachable by semi-technical users**, not just engineers — while still giving developers a
  clean API to embed teams.
- **Free and open-source.** No paywall to the core capability.
- **Honest scope:** strongest for **non-code** teams — research/content, analysis, critique,
  education — rather than large/complex software-engineering projects.

## Who This Serves

- **Primary — semi-technical users.** Comfortable getting an API key and using a simple UI, but
  not writing agent specs or wiring frameworks. In v1 they supply their own model keys (via a
  config file).
- **Secondary — developers.** Use the API to generate/run teams and embed them in their own
  software (e.g. dropping a content-creation team into their product).
- **Future — non-technical users** via a hosted/managed option (no keys required). Parked in
  the backlog (see `addendum.md`).

Flagship teams a user would actually spin up: a **research/content team** (researcher → writer
→ editor → critic) as the hero example, and an **education team** of adaptive tutors — replacing
the current software-delivery example as the showcase.

## Success Criteria

It's working when:

- **People create many teams** — teams created and active users are the headline signal.
- **Non-coding users adopt it** — specifically the count of non-technical/non-coding people
  using it for domains like **education** and **research** (not just developers).
- **It ships under the startup's R&D department** — releasing it as an official R&D open-source
  product is itself a success condition, not just a vanity outcome.

Counter-signal (what we're *not* optimizing for): raw GitHub stars without teams actually being
created, and coverage of large/complex software-engineering projects.

## Scope

**In (v1):**

- **Composer** — an LLM authors a valid team_maker spec from plain-language intent and creates
  the team (no hand-written YAML), kept current with team_maker's input format.
- **Run-a-team runtime** — executes the assembled multi-provider team so agents collaborate and
  return results.
- **Minimal UI** — a thin interface so semi-technical users reach the product at launch, not
  just via CLI/API. API keys are supplied through a separate config file, not entered in the UI.
- Built on the **existing factory** (spec → validated → multi-provider team package).

**Out (backlog):**

- Generate-only API endpoint (return files without running).
- Hosted / no-keys tier ("pay us, we handle the keys").
- Education packaged as its own product surface.

## Vision

Where it goes if it succeeds: a place where anyone can stand up a collaborating team of
specialized, multi-provider AI "thinkers" for whatever domain they care about — research,
content, analysis, teaching — without touching code, and where developers embed those teams
into their own products. The hosted, no-keys tier is what eventually opens the door from
semi-technical to genuinely non-technical users.

## Foundation: team_maker as it exists today

A working Python factory that turns a structured YAML request into a **self-contained,
multi-provider team package** (agents, tasks, provider routing, docs) — validated and
ready to hand to an agent runtime. It already supports per-agent provider/model assignment
across anthropic/openai/ollama/groq/google with no code changes. What it does **not** yet do:
author the spec conversationally, or run the team. Those two gaps are exactly what this product
adds. (Full technical picture: `project-docs/architecture.md`,
`project-docs/vision-and-target-architecture.md`.)
