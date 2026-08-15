---
baseline_commit: e1337fb5be5fd4faeef030e9bf6855dcc6ea9d1b
---

# Story 2.10: Composer should not fabricate a team from non-team input

Status: backlog

## Story

As a user,
I want the Composer to recognize when what I typed isn't a team description,
so that saying "Hello" doesn't produce a fabricated team and a confusing "Here is a team for
that: greeter" response.

## Background

`team_maker/composer/composer.py:_build_system_prompt` (rules in `_SCHEMA_RULES`, lines 34-58)
unconditionally instructs the authoring LLM to emit a schema-valid `TeamCreationRequest` — at
least one role, a `team_name`, a `purpose` — for *any* input, with no branch for "this doesn't
describe a team." `TeamCreationRequest`'s schema requires `desired_roles` to have at least one
entry, so the model has no valid way to say "I don't have enough to build a spec" within the
current contract; it must invent something. On the frontend,
`web/components/composer/proposal.ts:describeProposal` (lines 106-132) then renders whatever comes
back with "Here is a team for that: {roles}." purely from role count — it has no visibility into
the original message either, so it cannot detect this happened.

Verified end-to-end: a user's first message "Hello" produced a fabricated "greeter" role and the
canned "Here is a team for that: greeter." sentence — technically schema-valid, semantically
nonsense.

## Recommended design (subject to confirmation before implementation — see Open Questions)

Add a cheap classification step before the existing schema-authoring call, and a new turn outcome
that means "nothing changed; ask the user to actually describe a team" instead of forcing a
fabricated spec through the pipeline:

1. **API contract**: `api/schemas.py`'s `SessionView.status` (currently `Literal["complete"]`,
   line 128) gains a second value, e.g. `Literal["complete", "needs_clarification"]`; `spec:
   dict[str, Any]` becomes `dict[str, Any] | None` (`None` only when `status ==
   "needs_clarification"` **and** no valid spec exists yet for this session); a new `clarification:
   str | None` field carries the follow-up question to show. This is additive to the schema, not a
   breaking change to the `"complete"` path.
2. **Composer**: before calling the existing, unmodified `Composer.compose()` (do not duplicate or
   fork its validate-and-repair loop — `ComposerSession`'s own docstring already states this
   principle for the same reason, `team_maker/composer/session.py:1-7`), run one lightweight
   classification call through the same injected `LLMProvider` port asking whether the message
   describes a team to build. If not, skip `compose()` entirely for that turn and return a
   `needs_clarification` outcome with a short, specific follow-up question instead.
3. **`ComposerSession`**: `start()`/`refine()` currently assume every turn either produces a
   `TeamCreationRequest` or raises (`session.py:25-44`). This story's biggest session-lifecycle
   change: `self.current` must be able to stay `None` across **multiple consecutive** turns if the
   user keeps not describing a team (`refine()` today hard-requires `self.current is not None` and
   raises `RuntimeError` otherwise — `session.py:39-40` — this must change to tolerate "still no
   spec yet" rather than crash).
4. **Frontend**: when a turn's response has `status === "needs_clarification"`, render `clarification`
   as the assistant's message instead of calling `describeProposal`. Because `spec` stays `null`,
   the existing `hasSpec` gate in `web/components/composer/composer-surface.tsx` (lines 270-281)
   already keeps the Build team/Run it now/Review toggle actions bar hidden with **no changes
   needed there** — this composes for free with the existing "nothing to build yet" design from
   Story 2.2.
5. **Turn budget**: a `needs_clarification` turn still consumes one of `turns_remaining` — this is
   what already bounds someone using the Composer purely as a free chat window (Story 1.3's
   `turn_cap_reached` mechanism), so no new abuse-prevention mechanism is needed beyond applying
   the existing cap to this new turn type too.

## Open Questions (must be resolved, not assumed, before implementation)

1. **Classification accuracy/cost tradeoff**: a separate LLM call per turn adds latency and cost.
   Should the classification prompt be folded into a cheaper/faster model call than the authoring
   one, or reuse the same authoring provider/model? Not decided here.
2. **False negatives**: a short, ambiguous message ("marketing team", no verb) must still classify
   as team-shaped. The classification prompt's exact wording and its false-positive/false-negative
   tolerance is an implementation detail to get right and test explicitly, not something this story
   prescribes precisely.
3. **Mid-conversation non-team turns**: if a spec already exists (turn 2+) and the user sends
   something conversational ("thanks!", "what does the writer do?"), should that also produce
   `needs_clarification` (losing the existing spec's visibility temporarily), or should it be
   treated differently from a *first*-turn non-team message? This story's AC below scopes the
   requirement to the first-turn case, which is the concretely observed problem; extending it to
   every turn is a larger product decision left open here rather than assumed.

## Acceptance Criteria

1. **Given** a user's first message in a New Team conversation does not describe a team to build
   (e.g. "Hello", "hi", "what is this app"), **when** the Composer processes it, **then** no
   fabricated `TeamCreationRequest` is produced or shown, and the user instead sees a short,
   specific invitation to describe a team — not a generic error and not a silently-invented team.
2. **Given** the same scenario, **when** the response reaches the frontend, **then** the Build
   team / Run it now controls and the Review before build toggle remain hidden (per the existing
   `hasSpec` gate) exactly as they already are before any proposal exists — this story does not
   change that gating, only what triggers it to stay closed.
3. **Given** a user's first message clearly does describe a team (the existing, working case —
   e.g. "I want a team that researches and writes blog posts"), **when** the Composer processes it,
   **then** behavior is unchanged from today: a real spec is proposed and `describeProposal`'s
   existing sentence renders as it does now. This story must not regress the working path while
   fixing the broken one.
4. **Given** the turn-budget mechanism (`turn_cap_reached`, Story 1.3), **when** a
   `needs_clarification` turn occurs, **then** it counts against the same turn cap as any other
   turn, so repeatedly sending non-team messages still converges to the existing cap rather than
   opening an unbounded free-chat loop.
5. **Given** `AD-10` ("only a spec that passes `TeamCreationRequest` validation is ever returned")
   and `AD-2`/`AD-8` (Composer depends only on the `LLMProvider` port; no provider-name branching),
   **when** this story is implemented, **then** neither invariant is violated: no invalid spec is
   ever surfaced (an absent spec is represented as `null`, never as an invalid one), and the
   classification step is provider-agnostic, reusing the same injected `LLMProvider` the authoring
   call already uses rather than introducing new provider-specific logic.
6. **Given** `CLAUDE.md`'s test-transparency rule, **when** this story lands, **then** `pytest -q`
   and the web test suite (`npm test`) both have real before/after counts recorded in Completion
   Notes, with new tests covering: a clear non-team first message (AC 1, 2), a clear team message
   still working (AC 3), and the turn-cap interaction (AC 4).

## Tasks / Subtasks

- [ ] **Task 1 — Resolve the Open Questions above** with the PM/architect before writing code;
  record the decisions made in Dev Notes.
- [ ] **Task 2 — API contract** (AC: 1, 2)
  - [ ] Extend `SessionView` in `api/schemas.py`: `status: Literal["complete",
    "needs_clarification"]`, `spec: dict[str, Any] | None`, new `clarification: str | None`.
- [ ] **Task 3 — Composer classification step** (AC: 1, 3, 5)
  - [ ] Add the pre-authoring classification call in `team_maker/composer/` (new function or
    method, not folded into `Composer.compose()`'s own validate-and-repair loop).
  - [ ] Wire it into `api/routers/compose.py`'s session-create and message handlers.
- [ ] **Task 4 — `ComposerSession` lifecycle** (AC: 1)
  - [ ] Update `start()`/`refine()` (`team_maker/composer/session.py:25-44`) so `self.current`
    can remain `None` across consecutive non-team turns without raising.
- [ ] **Task 5 — Frontend rendering** (AC: 2, 3)
  - [ ] Handle `status === "needs_clarification"` in `web/components/composer/composer-state.ts`'s
    turn-success reducer; render `clarification` instead of calling `describeProposal`.
  - [ ] Confirm (with a test, not just inspection) that `hasSpec`-gated UI stays hidden.
- [ ] **Task 6 — Tests** (AC: 4, 6)
  - [ ] Unit tests for the classification step's clear-cases (obviously not a team / obviously a
    team) — do not over-fit tests to the exact prompt wording chosen in Task 1.
  - [ ] Frontend test asserting a `needs_clarification` turn renders the clarification and keeps
    the actions bar hidden.
  - [ ] Turn-cap interaction test.
  - [ ] Run and record `pytest -q` and `npm test` before/after counts.

## Dev Notes

### Why this can't be fixed in the frontend alone

`proposal.ts:describeProposal` only ever receives the already-fabricated `SpecView` — it has no
access to the original user message and no signal that the spec is fictional (it's schema-valid).
Any fix that only changes `proposal.ts`'s sentence-generation would still have spent an LLM call
inventing a fake team and would have nothing truthful to say instead of "Here is a team for
that: …" — the fabrication has to be prevented upstream, in the Composer, not disguised
downstream.

### Project conventions (must follow)

- `Composer.compose()` itself is not modified — `ComposerSession`'s docstring states the existing
  principle (`session.py:1-7`): wrap it, never duplicate or fork its repair loop. The
  classification step is a new, separate, smaller call, not a change to `compose()`'s internals.
- AD-8: no provider-name branching anywhere in this story's new code.
- Frontend: this story's UI change is additive to `composer-state.ts`'s existing reducer, not a
  rewrite of it.

### References

- `team_maker/composer/composer.py` (whole file — `_SCHEMA_RULES`, `_build_system_prompt`,
  `Composer.compose`)
- `team_maker/composer/session.py` (whole file — `ComposerSession.start`/`refine`)
- `api/schemas.py:125-133` (`SessionView`)
- `api/routers/compose.py` (session create / message handlers)
- `web/components/composer/proposal.ts` (`describeProposal`, lines 106-132)
- `web/components/composer/composer-state.ts` (turn-success reducer)
- `web/components/composer/composer-surface.tsx:270-281` (`hasSpec` gate — unchanged by this
  story, but load-bearing for AC 2)
- `project-docs/stories/1-2-compose-team-spec.md`, `1-3-conversational-tuning-run-now.md` (the
  validate-and-repair loop and turn-cap mechanisms this story must not duplicate or bypass)
- `project-docs/epics.md` AD-2, AD-8, AD-10
- `CLAUDE.md` (test transparency)

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
