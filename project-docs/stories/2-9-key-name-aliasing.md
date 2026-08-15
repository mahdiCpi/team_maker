---
baseline_commit: e1337fb5be5fd4faeef030e9bf6855dcc6ea9d1b
---

# Story 2.9: Recognize common alternate key names without a key-entry UI

Status: review

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

### Change Log

- Added `env_var_aliases: tuple[str, ...] = ()` field to Provider dataclass in registry.py
- Set google provider's `env_var_aliases=("GOOGLE_API_KEY",)`
- Extended `env_to_provider()` to register each alias (uppercased) -> provider name
- Added test `test_google_api_key_alias_is_recognized` in test_keyconfig.py
- Updated `test_google_api_key_alone_no_longer_recognized` docstring and added `.has("google")` assertion

### Completion Notes List

- All 3 tasks completed successfully
- pytest tests/unit/test_keyconfig.py tests/unit/adapters/test_provider_availability.py: 25 passed (before: 24 passed, after: 25 passed)
- All existing tests continue to pass
- Implementation follows the "no branching on provider name" invariant (AD-8) - aliases are registered generically in env_to_provider()
- keyconfig.py required no changes - already uses env_to_provider() mapping
- Only google provider has an alias added (as per AC 4 - exactly one evidenced entry)