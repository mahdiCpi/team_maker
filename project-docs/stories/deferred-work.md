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

## Deferred from: code review of story-0.4 (2026-07-25)

- The four model-list fetchers' `lru_cache`s (`_anthropic_models`, `_openai_models`, `_xai_models`,
  `_google_models` in `team_maker/llm/model_resolver.py:39-97`) now key on the raw resolved secret
  value instead of the env-var name, so plaintext API keys are retained indefinitely in process
  memory for the lifetime of the process (no eviction, no rotation-awareness). This is a deliberate,
  spec-mandated design from Story 0.4's Task 3 ("the `@lru_cache` still works: it now caches per
  key-value instead of per-env-var-name, which is equivalent or better") — not fixed in the story's
  code review because overriding an explicit story decision mid-review would exceed the review's
  scope. Candidate fix: cache by a hash (e.g. `hashlib.sha256`) of the key instead of the raw value,
  or swap `lru_cache` for a cache the caller can explicitly evict on key rotation.

## Deferred from: code review of story-1.2 (2026-07-26)

- **`compose --build` doesn't bridge per-role provider keys** — only the authoring provider's key is bridged into `os.environ` before `composer.compose()` runs; if the composed spec routes roles to `openai`/`google`/`xai` (per the Composer's own word→provider alias table), nothing bridges those keys before `PipelineRunner().run()` executes. Harmless today — `model_resolver`'s live-model-substitution already degrades gracefully with "API unreachable — trust the YAML" when a key is absent — and run-time key gating for non-authoring providers is explicitly Story 1.6/FR-10 scope.
- **Generic exception printing in `compose` could echo SDK-embedded secrets** — `except Exception as exc: ... escape(str(exc))` around `composer.compose(intent)` prints the raw exception string, which could in theory contain credential fragments from an underlying SDK error. Matches the existing `create` command's identical pattern elsewhere in `team_maker/cli.py`; not a new regression, and there's no established scrubbing convention in the codebase to extend.
- **`_PROVIDER_ALIASES` is prompt-only, not code-enforced** — a malformed provider word from the authoring LLM costs one extra validate-and-repair round-trip rather than being silently corrected in code. Already covered by the existing AC3 repair loop; an efficiency nit, not a correctness gap.
- **No retry on non-`ValidationError` failures in `Composer.compose`'s repair loop** — transient/network/parsing failures propagate immediately with zero retry. AC3 explicitly scopes the retry budget to schema-validation failures, not general resilience; revisit if flaky LLM calls become a real-world problem.
- **No repair-attempt progress feedback in `compose`'s non-quiet output** — a UX nicety (e.g. "repair attempt 2/3"), not required by any AC.
- **`compose --model` cannot override the authoring provider, only the model string** — matches Task 4's literal spec (only `--model` was requested); revisit if a `--provider` override becomes a real user need.
