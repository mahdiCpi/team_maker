# Epic 1 Course Correction — 2026-07-25

**Trigger:** Epic 1 (Stories 1.1, 1.2) was started before Epic 0 was fully finalized. This document
(via `bmad-correct-course`) establishes the real state of Epic 0/Epic 1 branches and artifacts, then
reconciles them. See [epic-0-retro-2026-07-25.md](epic-0-retro-2026-07-25.md) for the retrospective
that flagged this for correction.

## 1. Issue Summary

Three unresolved items carried out of the Epic 0 retrospective:

1. `epic_0` → `develop` merge was intentionally left open as a separate gate.
2. `epic_1`/`story_1_2` sat at commit `7fe6473` — the exact pre-Epic-0 baseline — with **zero unique
   commits**, meaning neither branch contained any of Epic 0's ports-and-adapters work.
3. Story 1.1's implementation has no branch history at all — it arrived via the `guru-explore` merge,
   predating both Epic 0 and the CLAUDE.md branching rules.

Additionally, comparing Story 1.2's task list against the code that actually landed in Epic 0 surfaced
a fourth issue not previously flagged: two of Story 1.2's tasks describe building things Epic 0
already built, with a signature mismatch severe enough to break a naive implementation.

## 2. Investigation Findings (state as found)

| Artifact | State found |
|---|---|
| `develop` | `7fe6473`, tracked to `origin/develop`, strict ancestor of `epic_0` (no divergence) |
| `epic_0` | `87642dc`, tracked to `origin/epic_0`, pushed. 5/5 stories done, all review items resolved (per retro), `story_0_5` merged in |
| `epic_1` | `7fe6473` — identical to old `develop`, zero unique commits |
| `story_1_2` | `7fe6473` — identical to `epic_1`, zero unique commits |
| `story_1_1` | **No branch exists, ever.** Code shipped via `main`/`develop`'s `guru-explore` merge (`3d5828d`), before Epic 0 or the branching rules existed |
| Story 1.1 artifact | `Status: done`. ACs match `epics.md`'s current Epic 1 definition exactly — no drift |
| Story 1.2 artifact | `Status: needs-rescoping (spec-first refactor)`. Tasks 1-2 describe building a `LLMProvider` port and a first LLM adapter — **both already exist post-Epic-0**, with a signature the story didn't anticipate |
| sprint-status.yaml | **Does not exist in this project.** This repo tracks status inline per story file (`Status:` field), not via a central sprint-status file — confirmed by searching the full tree; not an omission |
| `_bmad/` scaffold | Not present in this repo (no `config.yaml`, no `resolve_customization.py`) — this project uses a lighter `project-docs/`-only BMAD convention |

### Why Epic 0 was ready to merge
`git merge-base --is-ancestor develop epic_0` confirmed `develop` is a strict ancestor of `epic_0` —
no divergent commits on either side. The retro documented 5/5 stories done with all code-review
action items resolved. This makes the merge a pure fast-forward with no conflict risk.

### Why Story 1.1 needs no reimplementation
Story 1.1's code (`keyconfig.py`, `providers/registry.py`, `keys status` CLI) has been on
`develop`/`main` since the `guru-explore` merge — well before Epic 0 started. Epic 0's Story 0.4
already refactored it in place (relocated the catalog to `adapters/providers/registry.py`, fixed two
data bugs). Once `epic_0` merged into `develop`, that reconciled version became what `epic_1` inherits
directly. There was never a "wrong foundation" for Story 1.1's *code* — only for the `epic_1`/
`story_1_2` *branches*, which pointed at a stale commit that predated even the original
(pre-Epic-0-refactor) version's final state.

### The genuine gap found in Story 1.2
`team_maker/ports/llm_provider.py` (built by Story 0.1, now on `develop`) defines:
```python
def complete_structured(self, system: str, user: str, response_model: type[T]) -> T: ...
```
Story 1.2's Task 1 planned to create a port with `def complete(self, *, system, prompt, model=None) -> str`.
The port module's own docstring already anticipates this: *"supersedes the `complete() -> str` sketch
in Story 1.2 Task 1."* Task 2 planned to build the repo's first LLM adapter (recommending OpenRouter);
Story 0.1 already built five (`anthropic`, `openai`, `xai`, `google`, `ollama`) behind a data-driven
`create_provider()` factory — no OpenRouter adapter among them. This is a real incompatibility: a
literal implementation of Story 1.2's original Task 1 would create a second, conflicting
`LLMProvider` definition.

## 3. Changes Made

### Git / branch state
1. **`epic_0` → `develop` merged** (fast-forward, `7fe6473..87642dc`). 203 unit tests re-verified green
   post-merge. Pushed to `origin/develop`.
2. **`epic_1` fast-forwarded** from `7fe6473` to `87642dc` (`develop`'s new tip) — zero commits lost,
   confirmed via `git merge-base --is-ancestor` before moving. Pushed to `origin/epic_1`.
3. **`story_1_2` fast-forwarded** from `7fe6473` to `87642dc` (`epic_1`'s new tip), same safety check.
   Pushed to `origin/story_1_2`.
4. **No branch created for Story 1.1.** Decision recorded in the story artifact itself (see below):
   treated as a grandfathered pre-rules exception, not silently re-litigated by inventing a
   pointer-only branch with no real commit history (the retro already flagged that exact pattern as
   a process smell for Stories 0.1-0.4).

### BMAD artifacts
- **`project-docs/stories/1-1-load-keys-report-models.md`** — added a Change Log entry: notes the
  Story 0.4 path move (`providers/registry.py` → `adapters/providers/registry.py`), confirms no
  behavior/AC change, and records the explicit decision not to retroactively create `story_1_1`.
  Status unchanged (`done`).
- **`project-docs/stories/1-2-compose-team-spec.md`** — added a second reconciliation comment block;
  rewrote Task 1 (consume the existing `ports/llm_provider.py` + `complete_structured` signature,
  don't recreate it) and Task 2 (reuse the existing five adapters + `create_provider` factory; scoped
  a new OpenRouter adapter down from "required" to "optional enhancement"); updated stale
  `team_maker/providers/registry.py` path references to `team_maker/adapters/providers/registry.py`;
  resolved the old "naming decision" callout (Story 0.4 answered it). **Status: `needs-rescoping` →
  `ready-for-dev`.** Acceptance Criteria and Tasks 3-5 were left untouched — no gap was found in the
  story's intent, only in two tasks' now-outdated implementation guidance.
- **This document** — new, records the full reconciliation for future reference.

No code was changed. No story was reimplemented. No branch or commit was discarded.

## 4. Resulting State

```
develop   -- 87642dc (Epic 0 merged, pushed)
epic_1    -- 87642dc (== develop, pushed)
story_1_2 -- 87642dc (== epic_1, pushed)
```

Story 1.1: `done`, code live on `develop`/`epic_1`, no outstanding implementation work.
Story 1.2: `ready-for-dev`, task list corrected, no outstanding rescoping work — ready for
`bmad-create-story` to do a full context-engineered refresh (recommended, given how much shifted)
or directly for `bmad-dev-story` if the corrected tasks are considered sufficient context.

## 5. Recommended Next BMAD Workflow

**`bmad-create-story`** for Story 1.2, run from the `story_1_2` branch. Rationale: the task-level fix
applied here is a *correction*, not a full re-derivation — it did not re-run the story's original
"exhaustive artifact analysis" against the now-current codebase the way `create-story` would. Given
how much of Epic 0 landed since Story 1.2 was drafted (5 stories' worth of refactors touching exactly
the modules this story depends on), a fresh context-engineered pass will catch anything this
correction pass didn't (e.g., whether `schema/request.py`'s `_pre_process` validator or
`templates/software_delivery/template.py`'s default-provider chain shifted in ways beyond what Story
0.5 documented). Once that pass confirms (or further corrects) the task list, proceed to
`bmad-dev-story` for implementation.

Story 1.1 requires no workflow — it is `done` with no outstanding gaps.
