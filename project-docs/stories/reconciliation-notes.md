# Reconciliation Notes — stale `main` vs. real code on `guru-explore`

_Created 2026-07-12. Records a significant mid-plan course correction._

## What happened

The project on this machine was mistakenly bootstrapped from `main`, which was **stale** at commit
`e5021f3` ("initial code"). On top of that stale base, commit `f39b928` added the BMAD planning docs
(`project-docs/`) **and** Story 1.1's code (`keyconfig.py`, `providers/registry.py`, a `keys status`
CLI command). `develop`, `epic_1`, and `story_1_2` were all branched from this wrong foundation.

The **real, advanced project** lived on `origin/guru-explore` (≡ `origin/input_fix`, both at
`16ab039`): the `team_maker/llm/` layer, the `codegen/` Jinja engine, `frameworks/` adapters
(crewai/langgraph/autogen), a real end-to-end `pipeline/runner.py`, a rich `schema/request.py`,
smoke tests, and the CoinPela v4.3 recipe. `guru-explore` descends from `develop`'s own line
(`2ff9626` is an ancestor), so it is the project's true continuation.

## What was done (git surgery)

1. Merged `guru-explore → main` (`3d5828d`). Only conflict was `.gitignore` (resolved as the union);
   `cli.py` auto-merged into the intended union of commands. Removed stray files `=1.0` and `.codex`.
2. Merged `main → develop` (`ca442b9`).
3. Deleted and recreated `epic_1` (from `develop`) and `story_1_2` (from `epic_1`); pushed all.
4. Verified: CLI runs (`create`, `list-templates`, `keys status`), 172 unit tests pass, all four
   branches descend from `16ab039`.

## Decisions (owner: guru.alampalli@gmail.com)

- **Spec-first.** The BMAD ports-and-adapters spine remains the target architecture. The merged
  pre-plan code is refactored toward it (see Epic 0), not accepted as the target design.
- **Merge, don't reset.** `main` history preserved (no force-push).
- **Keep Story 1.1 code.** `keyconfig.py`/`providers/registry.py`/`keys status` are retained through
  the merge because they provide a genuinely new user-facing feature guru-explore lacks; integration
  into the `llm/` layer is deferred to Story 0.4.

## Architectural divergences to retire (feed Epic 0)

| # | Existing code | Spine invariant it violates | Story |
|---|---------------|-----------------------------|-------|
| 1 | `llm/providers.py` — `LLMProvider` is an ABC with `complete_structured`; providers constructed via `create_provider` factory (no port, no `adapters/`) | AD-2 (ports-and-adapters), AD-8 (single `LLMProvider` port) | 0.1 |
| 2 | `llm/mapper.py::_infer_provider` branches on model-name prefixes (`gpt-`→openai, `claude-`→anthropic, `grok-`→xai) | AD-1 / AD-8 (never branch on provider name) | 0.2 |
| 3 | CrewAI wired directly; `frameworks/crewai_adapter.py` pins `crewai>=0.80.0` inside the package | AD-6 (CrewAI behind `RuntimeEngine`), stack pin CrewAI 1.14.6 | 0.3 |
| 4 | Two parallel provider/key systems: `keyconfig.py`+`providers/registry.py` (Story 1.1) vs `llm/model_resolver.py` (availability/substitution) | duplication; AD-9 key handling should be single-sourced | 0.4 |
| 5 | `schema/request.py` has grown fields (`planning_llm`, `framework`, `state_backend`, `git_account`, `sandbox`, `desired_tasks`, `suggested_tools`, `context_dir`, `model_registry`, `notifications`) not in `data-models.md`; `planning_llm` vs spine glossary `default_llm` | AD-10 (schema is the contract) | 0.5 |

## Status of the pre-plan Stories

- **Story 1.1 (load keys / report models):** implemented and now committed to `main`. Its code is
  the retained `keyconfig.py` + `providers/registry.py` + `keys status`. Integration → Story 0.4.
- **Story 1.2 (compose team spec):** overlapping functionality exists (`llm/planner.py`,
  `schema/request.py` `_pre_process`) but under the pre-plan design. Re-scoped as a refactor
  (see epics.md Story 1.2 note + Story 0.1).

## Cleanup performed

- Removed stray repo-root files carried in from guru-explore: `=1.0` (pip-redirect artifact) and
  `.codex` (empty).
- `.gitignore` now unions both branches' entries (`conversation_history.txt`, `final_state.txt`,
  `to_run/`, plus the Key Config block `team_maker.keys` / `*.keys`).
