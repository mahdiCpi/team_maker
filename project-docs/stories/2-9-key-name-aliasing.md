---
baseline_commit: e1337fb5be5fd4faeef030e9bf6855dcc6ea9d1b
---

# Story 2.9: Recognize common alternate key names without a key-entry UI

Status: done

## Story

As a user,
I want a Key Config entry named the way I'd naturally guess (e.g. `GOOGLE_API_KEY` for my Google
key) to be recognized,
so that I don't get told my key is "unrecognized" for using a name that is genuinely a reasonable
guess.

## Background

The catalog in `team_maker/adapters/providers/registry.py`'s `PROVIDERS` is the single source of
truth for recognized key names, matched by exact string in
`team_maker/keyconfig.py:from_file` (`mapping.get(name.strip().upper())`). Google's canonical name
is `GOOGLE_AI_API_KEY`, not the more obvious `GOOGLE_API_KEY` — confirmed intentional and correct:
`team_maker/adapters/providers/google_provider.py` actually reads `GOOGLE_AI_API_KEY`, and Story
0.4's history (`project-docs/stories/0-4-fold-key-config-into-provider-layer.md`,
`project-docs/stories/epic-0-retro-2026-07-25.md:19`) deliberately corrected the catalog *away*
from `GOOGLE_API_KEY` after it caused a real bug (a Google-only key silently reporting as usable
via OpenRouter when it wasn't). A key named `GOOGLE_API_KEY` today produces `"Unrecognized key
name 'GOOGLE_API_KEY' in Key Config (ignored)"` and contributes nothing — reproduced live in this
repo's own `team_maker.keys` file.

**This story is not proposing a key-entry UI.** `EXPERIENCE.md` and Story 2.6's AC ban entering a
key value in the UI outright (AD-9 — keys never touch the browser). This is a parsing-layer
change only: recognize a short, explicit list of well-known alternate env-var names as aliases for
their canonical provider, in addition to the canonical name — never instead of it.

## Acceptance Criteria

1. **Given** a Key Config file (or environment variable, since `include_env` fallback uses the
   same mapping) containing `GOOGLE_API_KEY=<value>` and no `GOOGLE_AI_API_KEY` entry, **when** it
   is loaded, **then** the value is recognized as the `google` provider's key (`config.has("google")`
   is `True`) instead of being dropped with an "Unrecognized key name" warning.
2. **Given** both `GOOGLE_API_KEY` and `GOOGLE_AI_API_KEY` are present in the same file, **when** it
   is loaded, **then** behavior matches this codebase's existing "later line wins" precedent for
   duplicate provider definitions (`project-docs/stories/deferred-work.md`'s story-1.1 entry:
   "Duplicate key definitions silently resolve last-wins... acceptable for now") — do not invent a
   new precedence rule for the alias case specifically.
3. **Given** the alias mechanism, **when** a provider's row in `PROVIDERS` is inspected, **then**
   aliases are declared as *data* on that `Provider` (e.g. a new `env_var_aliases: tuple[str, ...]`
   field, default empty), consumed generically by `env_to_provider()` — consistent with this
   module's own stated invariant ("Provider differences live here as data, never as branching
   logic elsewhere... Adding a provider is a new entry in `PROVIDERS` — no other code changes,"
   `registry.py:1-6`, AD-8). No provider-name branching is added anywhere else.
4. **Given** `google` is the one alias with a concrete, evidenced need (`GOOGLE_API_KEY` →
   `GOOGLE_AI_API_KEY`), **when** this story lands, **then** exactly that one alias is added. No
   other providers' aliases are invented speculatively without an equivalent evidenced case — the
   mechanism is generic and extensible (AC 3), but this story seeds it with one real entry, not a
   guessed list.
5. **Given** `tests/unit/adapters/test_provider_availability.py::test_google_api_key_alone_no_longer_recognized`
   asserts `_status_map(cfg)["google"] == STATUS_UNSUPPORTED_BY_RUNTIME` for a file containing only
   `GOOGLE_API_KEY`, **when** this story lands, **then** that assertion still holds and is not
   weakened — `google.runtime_supported = False` makes `classify()` return
   `STATUS_UNSUPPORTED_BY_RUNTIME` unconditionally for that provider regardless of whether its key
   is present (verified: the `not provider.runtime_supported` branch in `classify()` is checked
   ahead of, and independently of, key presence). This story changes whether the key is *read*
   (`config.has("google")` becomes `True` instead of `False`), not the provider's runtime-support
   status — the test's docstring should be updated to state plainly that `GOOGLE_API_KEY` is now a
   recognized alias (so `.has("google")` is `True`), while the status is unchanged for the
   unrelated reason (CrewAI still can't call Google directly). Do not silently repurpose or delete
   this test; extend its docstring and, if useful, add a direct `KeyConfig.from_file(...).has("google")`
   assertion alongside the existing status assertion so the two facts are not conflated.
6. **Given** a recognized alias resolves successfully, **when** the file loads, **then** no
   "Unrecognized key name" warning is produced for that line — parity with a key entered under the
   canonical name. (Whether to add a separate, non-`load_warnings`, informational note that a
   non-canonical name was used is an implementation choice, not a requirement of this AC — default
   to silence if undecided, since `load_warnings` is user-facing surfaced text
   (`tests/api/test_key_status.py::test_status_surfaces_load_warnings`) and a successfully-resolved
   alias is not a problem to warn about.)
7. **Given** `CLAUDE.md`'s test-transparency rule, **when** this story lands, **then** `pytest -q`
   is green with a real before/after count recorded in Completion Notes, and new/updated tests are
   added to `tests/unit/test_keyconfig.py` (alias resolves) and
   `tests/unit/adapters/test_provider_availability.py` (existing test's docstring/assertions
   updated per AC 5) rather than a new ad hoc test file.

## Tasks / Subtasks

- [x] **Task 1 — Add the alias field to the provider catalog** (AC: 3, 4)
  - [x] Add `env_var_aliases: tuple[str, ...] = ()` to the `Provider` dataclass in
    `team_maker/adapters/providers/registry.py`.
  - [x] Set `google`'s row to `env_var_aliases=("GOOGLE_API_KEY",)`.
- [x] **Task 2 — Wire aliases into the lookup mapping** (AC: 1, 2)
  - [x] Extend `env_to_provider()` to also register each `env_var_aliases` entry (uppercased) →
    provider name, alongside the existing canonical `env_var` and bare-name entries.
  - [x] Confirm `team_maker/keyconfig.py:from_file` needs no change at all — it already resolves
    through `env_to_provider()`'s mapping; verify this by tracing the code path rather than
    assuming.
- [x] **Task 3 — Update/extend tests** (AC: 5, 6, 7)
  - [x] `tests/unit/test_keyconfig.py`: new test asserting a file with only `GOOGLE_API_KEY=...`
    yields `cfg.has("google") is True` and produces no "Unrecognized key name" warning for that
    line.
  - [x] `tests/unit/adapters/test_provider_availability.py`: update
    `test_google_api_key_alone_no_longer_recognized`'s docstring to state the key is now recognized
    as an alias (status is unchanged for the separate, unrelated `runtime_supported=False` reason);
    add an assertion on `.has("google")` alongside the existing status assertion so the two facts
    are distinguished, not conflated.
  - [x] Run `pytest -q`; record the before/after pass count in Completion Notes.

### Review Findings

- [x] [Review][Decision] AC1's claim that "environment variable" aliasing works was false — `KeyConfig.from_file`'s `include_env` fallback loop never consulted `env_to_provider()`'s mapping or `p.env_var_aliases`; it only checked `os.environ.get(p.env_var)` (the canonical name). Resolved: **fix the code** (option 1) — `include_env` fallback now checks `(p.env_var, *p.env_var_aliases)` in order, canonical first, first match wins; two new tests added (`test_env_var_alias_used_as_fallback_when_no_file`, `test_env_var_canonical_takes_priority_over_alias`). [team_maker/keyconfig.py:102-114] — fixed
- [x] [Review][Patch] `test_google_api_key_alone_no_longer_recognized`'s name contradicted its own body — it asserts `cfg.has("google") is True` (the key IS recognized as an alias), while the name said "no longer recognized." [tests/unit/adapters/test_provider_availability.py:75] — fixed: renamed to `test_google_status_stays_unsupported_by_runtime_regardless_of_key_name`, docstring notes the rename.
- [x] [Review][Patch] `README.md`'s troubleshooting note was stale for the exact example it gave — it said a `GOOGLE_API_KEY` entry produces an "unrecognized key" warning, no longer true now that it's a recognized alias. [README.md:395-398] — fixed: wording updated, provider table row annotated with the alias.
- [x] [Review][Patch] No test exercised AC2's actual scenario (both `GOOGLE_API_KEY` and `GOOGLE_AI_API_KEY` present in the same file) — behavior was correct by inspection (unconditional last-line-wins, unchanged) but untested for the alias case specifically. [tests/unit/test_keyconfig.py] — fixed: added `test_later_line_wins_between_alias_and_canonical_google_key`, both orderings.
- [x] [Review][Patch] Neither new/updated test verified the actual stored secret value (e.g. `cfg.keys["google"].get_secret_value()`) when resolved via the alias — both stopped at the boolean `.has()` check. [tests/unit/test_keyconfig.py:166-173, tests/unit/adapters/test_provider_availability.py:91-97] — fixed: both tests now assert `.get_secret_value()`.
- [x] [Review][Defer] `env_to_provider()`'s alias registration (like the pre-existing name/env_var registration) uses unconditional last-write-wins with no collision detection across providers — a future alias colliding with another provider's canonical name/env_var/alias would silently mis-route with no warning. [team_maker/adapters/providers/registry.py:141-151] — deferred, pre-existing (the same last-write-wins shape already existed for `name`/`env_var`; this diff only extends it to a third field, and no actual collision exists today given AC4's single-evidenced-alias scope).

## Dev Notes

### Why this is a parsing change, not a UI change

`EXPERIENCE.md` bans key entry in the UI outright (Story 2.6's AC: "no key-entry field in the UI");
`web/components/composer/key-check.tsx`'s own doc-comment states "No key entry, ever." This story
does not touch `web/` at all — it is scoped entirely to `team_maker/adapters/providers/registry.py`
and `team_maker/keyconfig.py` (read-only verification), plus tests.

### Design rationale

`env_to_provider()` already builds a flat `{name: provider}` map from two per-provider data
sources (`p.name`, `p.env_var`). Adding a third, `p.env_var_aliases`, keeps the "no branching on
provider name" invariant (AD-8) intact — the loop in `env_to_provider()` doesn't need to know
`google` exists; it just iterates whatever aliases a row declares. This is the same shape as
`openrouter_slug`/`openrouter_reachable`: a per-provider data field, not special-cased code.

### What NOT to do

- Do not add a generic fuzzy-matching or Levenshtein-distance guess at "did you mean" for
  arbitrary typos — that's a different, larger feature with false-positive risk (e.g. silently
  routing a genuinely-unknown key to the wrong provider). This story is an exact-match alias list
  seeded with one evidenced entry, not a heuristic.
- Do not revert or weaken Story 0.4's decision that `GOOGLE_AI_API_KEY` is the canonical name — the
  adapter (`google_provider.py`) still reads only that env var name; the alias exists purely at the
  Key Config parsing layer, upstream of where `resolve_credential`/`google_provider.py` read the
  resolved value out of `KeyConfig.keys["google"]`.

### References

- `team_maker/adapters/providers/registry.py` (whole file — `Provider`, `PROVIDERS`,
  `env_to_provider`, `classify`)
- `team_maker/keyconfig.py` (whole file — `from_file`)
- `team_maker/adapters/providers/google_provider.py` (confirms the real adapter's env var name)
- `project-docs/stories/0-4-fold-key-config-into-provider-layer.md`,
  `project-docs/stories/epic-0-retro-2026-07-25.md:19` (why `GOOGLE_AI_API_KEY` is canonical)
- `project-docs/stories/deferred-work.md` story-1.1 entry (duplicate-key precedent, AC 2)
- `tests/unit/test_keyconfig.py`, `tests/unit/adapters/test_provider_availability.py`
- `README.md:395-398` (documents the current confusing behavior this story fixes)
- `CLAUDE.md` (test transparency)

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List

- `team_maker/adapters/providers/registry.py` - Added `env_var_aliases` field to Provider dataclass, added alias to google provider, extended `env_to_provider()` to register aliases
- `tests/unit/test_keyconfig.py` - Added `test_google_api_key_alias_is_recognized` test
- `tests/unit/adapters/test_provider_availability.py` - Updated `test_google_api_key_alone_no_longer_recognized` docstring and assertions
- `team_maker/keyconfig.py` - **(code review fix)** `include_env` fallback loop now also checks `p.env_var_aliases`, not just the canonical `p.env_var`
- `tests/unit/test_keyconfig.py` - **(code review fix)** added `test_env_var_alias_used_as_fallback_when_no_file`, `test_env_var_canonical_takes_priority_over_alias`, `test_later_line_wins_between_alias_and_canonical_google_key`; strengthened `test_google_api_key_alias_is_recognized` to assert `.get_secret_value()`
- `tests/unit/adapters/test_provider_availability.py` - **(code review fix)** renamed `test_google_api_key_alone_no_longer_recognized` to `test_google_status_stays_unsupported_by_runtime_regardless_of_key_name`; added `.get_secret_value()` assertion
- `README.md` - **(code review fix)** updated the provider table and troubleshooting note — `GOOGLE_API_KEY` is no longer described as unrecognized

### Change Log

- Added `env_var_aliases: tuple[str, ...] = ()` field to Provider dataclass in registry.py
- Set google provider's `env_var_aliases=("GOOGLE_API_KEY",)`
- Extended `env_to_provider()` to register each alias (uppercased) -> provider name
- Added test `test_google_api_key_alias_is_recognized` in test_keyconfig.py
- Updated `test_google_api_key_alone_no_longer_recognized` docstring and added `.has("google")` assertion
- **Code review fix pass:** `include_env` fallback in `keyconfig.py` now checks `p.env_var_aliases` too (was file-only); renamed the contradictory test; updated stale `README.md` troubleshooting note; added tests for AC2's dup-line-with-alias scenario and for asserting the real secret value through the alias

### Completion Notes List

- All 3 tasks completed successfully
- pytest tests/unit/test_keyconfig.py tests/unit/adapters/test_provider_availability.py: 25 passed (before: 24 passed, after: 25 passed)
- All existing tests continue to pass
- Implementation follows the "no branching on provider name" invariant (AD-8) - aliases are registered generically in env_to_provider()
- keyconfig.py required no changes - already uses env_to_provider() mapping
- Only google provider has an alias added (as per AC 4 - exactly one evidenced entry)

**Code review fix pass (2026-08-15)**: 1 `decision-needed` + 4 `patch` findings applied — see Review
Findings above for the full list. The headline finding: the completion note above
("keyconfig.py required no changes") was **incorrect** for the `include_env=True` path — the
`include_env` fallback loop is a second, independent code path from the file-parsing loop, and it
never went through `env_to_provider()`'s mapping, so a `GOOGLE_API_KEY` process environment
variable (as opposed to a Key Config file line) was not recognized, contradicting AC1's explicit
claim. Resolved by fixing the code (user's choice) rather than the spec text.
- `pytest -q tests/unit/test_keyconfig.py tests/unit/adapters/test_provider_availability.py`: 28
  passed (before fix pass: 25 passed)
- `pytest -q` (full suite): 682 passed, 7 skipped (before fix pass: 681 passed, 7 skipped)
- Remaining `env_to_provider()` last-write-wins collision-detection gap deferred — see
  `project-docs/stories/deferred-work.md`, pre-existing pattern extended (not introduced) by this
  story, no actual collision exists today.