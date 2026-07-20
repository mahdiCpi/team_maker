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

## Deferred from: code review of story-0.3 (2026-07-18)

- `get_runtime_engine`'s silent fallback-to-crewai (`team_maker/adapters/runtime_engines/__init__.py:13-14`)
  combined with `_render_requirements`'s raw `framework == "crewai"` string check
  (`team_maker/pipeline/runner.py:304-307`) can diverge for an unrecognized `framework` value: the
  requirements list would omit `litellm>=1.0` even though the engine that actually renders
  `run_example.py` is CrewAI's (via the fallback). Pre-existing since before Story 0.3 — the old
  `get_adapter`/`framework_deps.get(framework, framework_deps["crewai"])` had byte-identical
  behavior. Not fixed in Story 0.3 because its Dev Notes explicitly direct keeping this branch
  "exactly as-is" (behavior-preserving refactor scope). Candidate fix: branch on `adapter.name`
  instead of the raw `framework` string, and/or log a warning on fallback in `get_runtime_engine`.
