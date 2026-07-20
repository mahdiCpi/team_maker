# Deferred Work

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
