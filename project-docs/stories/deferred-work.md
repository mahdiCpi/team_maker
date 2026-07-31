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

## Deferred from: code review of story-1.3 (2026-07-27)

- **Only `ComposerError` is caught around `session.refine()` in the interactive loop** — any other exception (network/transient/parse failure) is uncaught there and crashes the whole conversation (exit 1) instead of letting the user retry that turn. Consistent with Story 1.2's own established precedent that retries are scoped to schema-validation failures only, not general resilience.
- **No cap on conversation turns or consecutive failed-refinement attempts** in `compose --interactive` — a confused user or scripted stdin can drive unbounded LLM spend with zero guardrail.
- **No `KeyboardInterrupt` handling in the interactive loop** — Ctrl+C while blocked on `input()` produces a raw traceback; no existing convention for this elsewhere in the CLI either.
- **`ComposerSession` has no undo/rollback** beyond asking the LLM to revert a change in a further turn. AD-11 only requires in-memory current state for v1; no history/versioning requirement in Story 1.3's ACs.
- **Prompt/token cost grows with spec size on every refinement turn** — the full current spec is re-embedded on each `refine()` call with no truncation, diffing, or summarization strategy. A real scalability concern for larger specs or longer conversations, not required by this story.
- **"Apply only this change" is prompt-only guidance, never code-verified** — nothing diffs the LLM's output against the prior spec to catch silent drift in fields the user didn't ask to change. Matches Story 1.2's precedent that prompt-level LLM guidance is acceptable and only schema-level issues are code-enforced via the repair loop.

## Deferred from: code review of story-1.4 (2026-07-27)

- **No `--quiet` coverage in `tests/unit/test_cli_create.py`** (alone or combined with a failing validation result) — valid coverage gap, but not one of Story 1.4 Task 2's explicitly enumerated scenarios.
- **No coverage of the `create` command's override flags** (`--output`/`-o`, `--framework`, `--state-backend`, `--planner-model`, `--no-planner`) in the new CLI tests — real gap, out of Task 2's explicit scope.
- **No negative test for a config file that fails to *parse* as YAML** (distinct from a schema-invalid-but-parseable file) — a different code path (`load_yaml`'s exception handler, `team_maker/cli.py:105-109`) than the schema-invalid test Task 2 asked for.
- **All four `test_cli_create.py` tests share a payload with non-empty `desired_roles`**, so the LLM-planner code path is never exercised by that file; a future edit to the shared `_valid_payload` helper that drops `desired_roles` could accidentally route a test through a real LLM call. Speculative future-hardening, not a current defect.
- **No test for a clean build (exit 0) with warnings but zero issues** (e.g. the "No tasks were generated" warning on its own) in `test_cli_create.py` — valid coverage idea, not one of Task 2's explicitly enumerated scenarios.

## Deferred from: story-1.5 implementation (2026-07-31)

- **The generated `run_example.py` template (`team_maker/codegen/templates/crewai_runner.py.j2:156-163`) builds a broken hierarchical `Crew` for any team with an orchestrator agent** — it passes the manager agent in both `agents=` and `manager_agent=`, which real CrewAI (confirmed on 1.14.5, installed for the first time in this repo as part of Story 1.5) rejects outright: `pydantic_core.ValidationError: Manager agent should not be included in agents list`. This means the standalone `python run_example.py` path has always been broken for any orchestrator/hierarchical team — undiscovered until now because CrewAI was never actually installed anywhere in this repo before Story 1.5. Story 1.5's own new in-process `CrewAIExecutionEngine` (`team_maker/adapters/runtime_crewai/`) works around this correctly (excludes the manager from `agents`), but the template itself is untouched — fixing generated-package code is outside Story 1.5's scope (it doesn't touch the Factory/codegen layer). Candidate fix: in `crewai_runner.py.j2`, exclude `ORCHESTRATOR_ROLE` from the `agents=list(agents.values())` passed to `Crew(...)` when `process=Process.hierarchical`.

## Deferred from: code review of story-1.5 (2026-07-31)

- **Multiple `is_orchestrator=True` agents in a package are not detected** — `CrewAIExecutionEngine._build_crew` picks the first via `next(...)`; a second orchestrator silently becomes a non-manager worker with `allow_delegation=True`, with no error or warning that the team's data was ambiguous. Genuinely uncertain whether the Factory can produce this today; no AC dictates the "correct" behavior (error vs. warn vs. current silent-first).
- **`pyproject.toml`'s `crewai>=0.80.0` (in the `runtime`/`all`/`dev` groups) has no upper version bound** — matches the pre-existing codegen adapter's own unbounded pin, and Story 1.6 already owns finalizing/gating the CrewAI version pin via its multi-provider conformance test.
- **An unrecognized/misspelled LLM provider name in `_build_llm` degrades silently** to `api_key=None` instead of flagging that the provider name itself is likely wrong.
- **No validation that `run`'s `goal` argument is non-empty** before being passed to `crew.kickoff(inputs={"goal": goal})` — CrewAI will simply process an empty goal rather than crash, so this is a UX nicety, not a correctness bug.
- **`team-maker run`'s `--key-file` resolved path is never echoed back in its output**, unlike `keys status`, which explicitly prints which Key Config path it resolved.
