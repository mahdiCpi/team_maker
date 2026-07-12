# Deferred Work

## Deferred from: reconciliation (2026-07-12)

See [reconciliation-notes.md](reconciliation-notes.md) for full context. The `guru-explore` merge
introduced a temporary **provider/key split-brain**: `team_maker/keyconfig.py` +
`team_maker/providers/registry.py` (Story 1.1) coexist with `team_maker/llm/model_resolver.py`
(availability/substitution). Both retained deliberately; unification is tracked as **Story 0.4** and
the broader spine reconciliation as **Epic 0** (Stories 0.1–0.5). Not deferred indefinitely — this is
the next architectural work item, ahead of new Epic 1 features.

## Deferred from: code review of story-1.1 (2026-07-11)

- **Duplicate key definitions silently resolve last-wins** — if the Key Config has the same provider twice (e.g. `ANTHROPIC_API_KEY=` and `anthropic=`), the later value wins with no warning. Acceptable for now; revisit if it causes confusion.
- **Key supplied for a keyless-local provider is ignored** — `config.has("ollama")` can be True but `report_availability` reports `keyless-local` regardless (keyless branch checked first). Harmless today; reconcile if local providers ever take optional auth.
- **OpenRouter gateway identified by a hardcoded name** — `OPENROUTER = "openrouter"` is used in logic rather than a `is_gateway` data flag on `Provider`. Fine while OpenRouter is the only gateway (AD-8 names it); convert to a data flag if a second gateway provider is added.
