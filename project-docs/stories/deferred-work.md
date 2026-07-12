# Deferred Work

## Deferred from: code review of story-1.1 (2026-07-11)

- **Duplicate key definitions silently resolve last-wins** — if the Key Config has the same provider twice (e.g. `ANTHROPIC_API_KEY=` and `anthropic=`), the later value wins with no warning. Acceptable for now; revisit if it causes confusion.
- **Key supplied for a keyless-local provider is ignored** — `config.has("ollama")` can be True but `report_availability` reports `keyless-local` regardless (keyless branch checked first). Harmless today; reconcile if local providers ever take optional auth.
- **OpenRouter gateway identified by a hardcoded name** — `OPENROUTER = "openrouter"` is used in logic rather than a `is_gateway` data flag on `Provider`. Fine while OpenRouter is the only gateway (AD-8 names it); convert to a data flag if a second gateway provider is added.
