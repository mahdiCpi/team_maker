---
baseline_commit: 2e89846
---

# Story 2.3: Key-check states and plain-language errors

Status: done

## Story

As a user,
I want clear messages about keys and validation,
so that I know exactly what to fix.

## Dependency

**Stories 2.0 (the API seam) and 2.2 (the Composer) are both `done` and merged into `epic_2`.** This story extends both: it adds the `api/` **key-status group** that `epics.md:334` assigns to it, and it adds the key-check surface to the Composer that 2.2 deliberately left empty.

Read, in this order, before writing code:

1. `project-docs/stories/2-0-api-seam-compose-endpoints.md` — **Review Findings** and **Completion Notes**. The error envelope, the containment rules, and the `AppState`/lifespan design are all authoritative there.
2. `project-docs/stories/2-2-new-team-conversational-composer.md` — **Completion Notes** and **Review Findings**. Its `Dev Notes` list the five copy strings it refused to render *because they are yours*.
3. `project-docs/stories/deferred-work.md` — items 85, 86, 92, 132, 140, 153, 154, 160, 167 all land on this story.

### The seam is genuinely empty — three stories refused to fake it

This matters because it means there is no scaffolding to adapt, and no fabricated data to correct:

- **Story 2.1 AC 13** refused the mockup's `Keys: anthropic ✓ · gemini ✓ · openrouter ✓` footer (`mockups/team-workspace.html:80`) as fabricated data.
- **Story 2.2 AC 9** refused per-provider key status, the key-check states, and all four `EXPERIENCE.md:85-88` banners — *"the seam must be left, the states must **not** be faked"*.
- **Story 2.0 AC 4** states: *"Per-provider key **status** is Story 2.3's surface and must not be invented here."*

A grep of `api/` for key/status routes returns nothing. `web/tests/composer/route.test.tsx:91-98` contains a test named **`it("fakes none of Story 2.3's key-check states")`** whose entire purpose is to hold that seam open until now. **You will invert that test — see AC 10.**

### The core already answers this question. Do not build a second answer.

`team_maker/adapters/providers/registry.py:146-155` — `classify()` — carries this docstring:

> *"The single source of truth for provider-availability precedence. Both the `keys status` report and the Runtime's pre-run credential resolution (`adapters/providers/resolution.py`) derive from this, so what the user is told is usable and what actually gets a credential can never drift apart. Contains no secret values — only presence/absence is used."*

Every state this story renders is a projection of `classify()`. Building a parallel availability rule in `api/` or in `web/` is the **"measuring a mirror"** defect class this repo has shipped twice (Story 2.1's contrast test read `lib/brand-tokens.ts` instead of the shipped CSS). Do not do it.

## Acceptance Criteria

1. **Given** `epics.md:334` assigns the **key status (read-only)** group to this story and `epics.md:372-374` says *"the four states come from a read-only endpoint this story adds to the app Story 2.0 created. Status only — never a key value"*, **When** this story lands, **Then** `api/routers/keys.py` exposes **`GET /api/keys/status`** returning a `KeyStatusView`, registered in `api/main.py` with `app.include_router(keys_router, prefix="/api")` exactly as `compose_router` is. It reports, per provider: `name`, `status` (a `registry.STATUS_*` value, verbatim), `detail` (`registry._STATUS_DETAIL` copy, verbatim), `usable` (`registry.is_usable(status)` — **not** a string comparison; `registry.py:24-25` says so explicitly), the catalog `env_var`, and a `fix_hint` that is `None` when the provider is usable. It also reports `key_config_path` (`KeyConfig.default_path()`, a non-secret and the thing that makes "add it to your Key Config" actionable — Story 1.6 precedent), `load_warnings`, `any_key_present`, and the `overall` aggregate. **Every value is derived from `registry.report_availability()` / `registry.classify()`.** (AD-9, AD-4, FR-15, `epics.md:334`)

2. **Given** `EXPERIENCE.md:86` requires the *"affected **agent** badge flagged"* and `web/components/composer/spec-draft.ts:9-13` explicitly forbids the frontend from inventing the server's default routing, **When** a compose session has a spec, **Then** **`GET /api/keys/check/{session_id}`** returns a `KeyCheckView` in which the **server** has performed the per-role join: for each role, `role`, `provider`, `model`, `status`, `detail`, `usable`, `fix_hint`, and `inherited_default` (true when the role named no `llm` and the resolution order supplied one). The required-provider set is derived by **running the pure template and reading `agent.routing`** — the pattern `api/build.py:63-89` `_requested_routings()` already establishes, whose docstring gives the rationale: *"the alternative was re-encoding the `role.llm → default_llm → anthropic/claude-sonnet-4-6` resolution order here, which would be a second source of truth for a rule that already exists in one place."* **Factor that template call into one shared helper** consumed by both `build.py`'s substitution reporting and this route; do not copy it. A spec with an empty `desired_roles` (the planner path) yields `roles: []` — see AC 5 for what the UI may claim in that case. Unknown or evicted `session_id` → the existing `session_not_found` (404). (FR-21, FR-10, `EXPERIENCE.md:86`)

3. **Given** `api/main.py:70` loads `KeyConfig.from_file()` **once** in the lifespan and freezes it in a `@dataclass(frozen=True) AppState`, and given the entire point of a fix hint is that the user acts on it and re-checks, **When** either key route is served, **Then** it re-reads the Key Config from disk (`KeyConfig.from_file()`, which never raises) so that **a key added after the server started is reflected without a restart** — otherwise the feature is broken in the exact flow it exists for. Consequences that must all be honoured: the handler does blocking file I/O and is therefore **`def`, not `async def`** (FastAPI threadpool — the convention `api/main.py:44-53` documents for `health()`'s exemption); the fresh config is **not** written back into the frozen `AppState`; and **`bridge_credentials` is not re-run** — `api/deps.py:12-24` documents the exact race that forbids per-request `os.environ` mutation.

   **The status must not lie about usability.** `AppState.bridged_providers` records which credentials were published to `os.environ` at startup. Determine empirically — do not assume — which paths read the frozen snapshot versus a fresh read, and whether a provider present in the file but absent from `bridged_providers` can actually be used. If it cannot, the reported `detail`/`fix_hint` must say so honestly rather than reporting a green "available" that then fails. Record what you measured, with the command, in Completion Notes. **This is the highest-risk unknown in the story; resolve it with evidence, not reasoning.**

4. **Given** UX-DR5 (`epics.md:98`) names **four** states while `registry.classify()` returns **five** statuses, **When** the check renders, **Then** all four spine states render with their spine copy and the fifth status has an explicit, non-lying home:

   | State | Trigger | Copy (`EXPERIENCE.md:85-88`, verbatim) |
   |---|---|---|
   | all-good | every required provider `usable`, none via OpenRouter | `All models reachable.` |
   | via-OpenRouter | any required provider is `via-openrouter` | `OpenRouter key found — routed models available.` + badges read `via OpenRouter` |
   | missing-key | any required provider is `missing` | `openai key missing — add it to your Key Config (Settings), or switch this agent to a model you have.` |
   | no-keys | `any_key_present` is false | `You'll need at least one model key to run. Add one in your Key Config, or add an OpenRouter key to unlock many models.` |

   `overall` precedence is **no-keys → missing-key → via-OpenRouter → all-good**, and the per-provider/per-role detail is returned regardless of the aggregate so badges are always renderable.

   **`STATUS_UNSUPPORTED_BY_RUNTIME` is its own rendered state, not missing-key.** It applies to `google`, `groq`, and `xai`. `classify()` returns `available` only when `runtime_supported and config.has(name)`, so **a user with a perfectly valid `GOOGLE_AI_API_KEY` gets `unsupported-by-runtime`** — `deferred-work.md:85` records that *"adding the correct key broke the run"*. Rendering that as "missing — add the key" is a false statement to the user's face. `team_maker/runtime/preflight.py:190-203` already authors the correct copy for it (*"a key would not help, so do not ask for one"*) and correctly offers the OpenRouter route **only** when `openrouter_reachable` — which `groq` is **not** (`registry.py:89-96`, `deferred-work.md:86`), so *"just use OpenRouter"* is wrong for groq. Reuse that logic; do not re-derive it. `STATUS_KEYLESS_LOCAL` (`ollama`) renders as a neutral, non-blocking badge reading its `detail` (`local - no API key needed`). (UX-DR5, FR-13, FR-22, `deferred-work.md:85-86`)

   **`no-keys` is `not any_key_present`, never "no usable provider".** `ollama` is unconditionally `keyless-local` and therefore `is_usable()`, so *"is any provider usable?"* is **`True` on a completely empty Key Config** — a value true by construction, the exact defect class this repo has shipped repeatedly (`2-1` review, `2-2` review). A test must prove the no-keys state renders with a genuinely empty key file.

5. **Given** UX-DR5 requires missing-key to **block the run** and `EXPERIENCE.md:103-104` bans *"hiding a blocked run behind a silent failure (always say why)"*, **When** a required key is missing or unsupported, **Then** the build controls are blocked with the fix hint stated in text. Implement this as **one more branch in the existing funnel** — `actionBlockedReason(state)` at `web/components/composer/composer-surface.tsx:239-265` already feeds all four build entry points (`Build team`, `Run it now`, the `⌘/Ctrl+Enter` chord, and the in-editor `Build team`). Honour it with the pattern `web/components/composer/composer-actions.tsx:52-110` already ships: **never `disabled`** — `aria-disabled` plus a visible reason wired by `aria-describedby`. `EXPERIENCE.md:117` is binding here: *"Missing-key and validation messages are text (not color-only); badges pair color with a label."*

   **The no-keys banner cannot live inside `ComposerActions`** — that component only renders when a spec exists (`composer-surface.tsx:177-188`), and no-keys must be visible before the user has described anything. Give it its own slot in `composer-surface.tsx`.

   **Scope of the block, stated precisely:** there is no run endpoint — `epics.md:335` assigns the `api/` **run** group to Story 2.4 — so "the run" this story can block is the **build**, and it blocks it **in the UI**. `PipelineRunner.run` has no key check (`2-0-...:312`), so a build currently succeeds with zero keys. Server-side enforcement belongs with the run endpoint in 2.4. A UI-only gate is bypassable by anything that is not this UI; **declare that limitation in Completion Notes and add it to `deferred-work.md` as 2.4's inheritance.** Do not silently widen scope by adding a gate to 2.0's build route.

   **When `roles` is `[]` (the planner path), the UI must not claim per-agent certainty it does not have.** Render the provider-level state and say plainly that the team's models are chosen during the build. Do not render green per-agent badges for roles that do not exist yet.

6. **Given** FR-15's second clause — *"A missing-key or validation condition renders a human-readable message in the UI, not a raw stack trace"* — and given `2-0-...:406` hands this story the user-facing copy for `authoring_unavailable` while `deferred-work.md:153` hands it `output_exists`, **When** this story lands, **Then**:

   - **`output_exists`'s server copy is fixed.** It currently *"tells the user to do the one thing the UI is forbidden to offer"* — choose a different output path — while `api/output.py` makes the path server-owned and read-only to the browser (2.0 AC 13). 2.2 papered over it client-side with a single-code override (`OVERRIDDEN_SERVER_COPY` in `api-client.ts`); fixing the server copy is what lets that override be **narrowed or removed**.
   - **`authoring_unavailable`'s copy is reviewed against the `groq` dead end.** `api/deps.py:127-145` already gets this right (a catalogued provider with no adapter is told a key will not help). Confirm the client fallback (`api-client.ts:60-61`, currently *"Composing needs a model provider that is currently unavailable."*) does not contradict the server's more specific copy.
   - **The whole `FALLBACK_MESSAGE` table gets one review pass** for plain language against `EXPERIENCE.md`'s Voice section (`:50-57`) — that table is the client-side copy surface, and this story owns copy.
   - **No new error code is required.** The key check is a `200` read; the block is client-side state. If you find you need one, note that it is a **four-file change** (`api/errors.py` constant + `STATUS_BY_CODE` row + `SERVER_ERROR_CODES` in `web/lib/api-types.ts` + `FALLBACK_MESSAGE` in `web/lib/api-client.ts`) and that `api/errors.py:23` calls it *"a contract change"* — stop and declare it rather than doing it quietly.

   **Rewording server copy invalidates fixtures. Both kinds.** `web/tests/composer/fixtures/error-output-exists.json` and `error-authoring-unavailable.json` are **verbatim captures from a live server** — reword the server and they are stale, so **recapture them** and update the provenance table in `fixtures/index.ts` (date + exact command). Separately, `deferred-work.md:160` records that `turn_cap_reached`, `compose_failed`, `build_failed` and `session_busy` have **no capture at all** — their tests synthesise the envelope *from the server's own copy strings*, so **if you reword any of those four, the frontend tests keep passing against copy that no longer exists.** Either recapture or explicitly re-sync the synthesised envelopes; a silent pass here is the vacuous-guard defect class.

   **Explicitly out of scope, declared not forgotten:** `fields[].message` is *not* authored copy — it forwards pydantic/`ComposerError` text while `api/errors.py:5-8` claims otherwise (`deferred-work.md:140`). Fixing it needs a pydantic-message→copy catalogue, and the client already scrubs leaks structurally (`looksLikeLeakedInternals` + `scrubFields`). Leave it, and say so.

7. **Given** AD-9 and Story 2.0's containment regime, **When** the new routes exist, **Then** the sentinel key values appear in **no response body, no response header, and no log record** of either route, and the existing sweep genuinely reaches them:

   - `tests/api/test_secret_containment.py:77-101` asserts `authored <= visited` against `/openapi.json`. A new route not added to `_exercise_every_route` **fails** this test — by design. Its `_template()` helper only normalises 5-segment `/api/compose/sessions/{id}/x` paths, so `/api/keys/check/{session_id}` needs that helper extended.
   - `tests/api/test_health.py:14-36` asserts the OpenAPI path set is **exactly** 2.0's five routes. Update it deliberately to seven.
   - `tests/api/containment.py:53` pins `_ENVELOPE_KEYS = {"code","message","fields"}`; **do not extend the error envelope** or every error test fails.
   - Any client-supplied string echoed into a message or a log line goes through `api/deps.py:148-157` `_safe_label()` — a raw newline is log-line forgery (`test_review_patches.py:369-404`).
   - Never read pydantic's `input` member (`api/errors.py:153-166`). Request models, if you add any, carry `model_config = _STRICT` — `api/schemas.py:31-33` calls `extra="forbid"` *"a security control, not tidiness"*.
   - `preflight.check_credentials()` looks like the right status source and **is not**: it unwraps real secrets into `ResolvedCredential.api_key`. A status read stops at `classify()` / `is_usable()`. (AD-9, NFR3, 2.0 AC 4)

8. **Given** Story 2.1 shipped `--signal` with an intentionally **empty** consumer whitelist and Story 2.4 is its designated first consumer, and given `DESIGN.md:85` bans *"custom destructive colors (use shadcn's)"* and a second brand hue, **When** this story lands, **Then** it references `--signal`/`bg-signal` **zero times** — including in comments, which is how the guard caught 2.2 — and adds **no new colour token**. There is no `--warning` and no `--success` token in `web/app/globals.css`, and inventing one contradicts `DESIGN.md:85`. The four states are distinguished by **text and structure**, using `destructive` for missing-key/unsupported and neutral `muted`/`muted-foreground`/`border` otherwise — which `EXPERIENCE.md:185` independently confirms: the passing key check is *"accent-free, neutral badges"*. Guard A (`color-literals.test.ts`) and Guard B (`signal-token.test.ts`) both stay green **unmodified**. Note the mockup tints the via-OpenRouter pill with `primary`, not accent (`team-workspace.html:39-40`). (UX-DR2, UX-DR8, NFR7, Story 2.1 AC 6/7)

9. **Given** this story's scope, **When** implementing it, **Then** these are explicitly **out of scope**: **Settings' key-status list, the Key Config path display, and safe-key guidance** (Story 2.6 — `epics.md:337,415-422`; `web/tests/shell/routes.test.tsx:85-93` asserts Settings contains nothing key-related and **must stay green**); the run endpoint and any server-side run gate (2.4); the `--signal` live-status component (2.4); save/rename/delete (2.5); the WCAG 2.2 AA audit and `aria-live` **run-progress** announcements (2.7); a **provider/model picker** — `EXPERIENCE.md:104`'s *"badges are click-to-change (opens a small model picker)"* collides with 2.2's settled *"modal depth is one"* and the ban on modal-over-modal, and the spec editor's existing free-text `model` field plus constrained `provider` select is the shipped affordance; a **model catalogue** of any kind; and **entering an API key anywhere in the UI** (`EXPERIENCE.md:103` bans it outright; AD-9 binds `ui`).

   **`EXPERIENCE.md:87` says the no-keys banner "Links to Settings guidance" — do not build that link.** Its destination has no key guidance until 2.6, and `EXPERIENCE.md:104`/`:172-174` ban dead affordances and buried failures. Name the **Key Config path** (which AC 1's response returns) in the banner instead: that is truthful, actionable today, and follows the Story 1.6 precedent — *"'add the key to your Key Config' is only actionable if the user knows which file that is."* **Declare this as a deviation with that rationale**; do not edit `EXPERIENCE.md`.

10. **Given** CLAUDE.md's test-organisation and test-transparency rules, **When** this story lands, **Then** Python tests live in **`tests/api/test_key_status.py`** (new file; `tests/api/` is already 13 files — do not add to `test_review_patches.py`, which is 636 lines and already over guideline), frontend tests in **`web/tests/composer/`**, and every one of these existing tests is updated **deliberately, with its intent preserved**:

    | Test | What must change |
    |---|---|
    | `web/tests/composer/route.test.tsx:91-98` `fakes none of Story 2.3's key-check states` | **Invert it.** The states are now real; assert they render from a mocked response, not that they are absent. |
    | `route.test.tsx:68-89`, `:106-153` "borrows no copy" guards | Move 2.3's strings (`All models reachable.`, `via OpenRouter`, `key missing`) out of the ban list and into positive assertions. |
    | `route.test.tsx:29-40` `issues no request on first render` | **Narrow, do not delete.** Its stated intent is *"The Composer waits for the user; it does not open a session on mount"* — that is about **compose sessions**. A `GET /api/keys/status` on mount is legitimate; re-scope the assertion to compose-session requests so the guard keeps its teeth. |
    | `tests/api/test_health.py:14-36` | Five authored routes → seven. |
    | `tests/api/test_secret_containment.py:15-56` | Add both routes to `_exercise_every_route`; extend `_template()` for the 4-segment path. |
    | `web/tests/shell/routes.test.tsx:85-93` | **Must stay green unchanged** — Settings stays key-free (2.6). |
    | `web/tests/theme/signal-token.test.ts:141` | `SIGNAL_CONSUMER_WHITELIST` **stays `[]`**. |

    `make test`, `make test-api`, `make lint`, `npm test`, `npm run lint`, `npx tsc --noEmit` and `npm run build` are all green. **State before/after test counts and paste the real command tails** — the baseline is **525 passed / 7 skipped** (Python) and **19 files / 339 tests** (web). Do not assert a number you did not measure: 2.1 reported ruff's 38 as 9 (two different scopes), 2.2 claimed "17/17 E2E checks" against a harness with 16 `check()` calls, and 2.0's `deferred-work.md` reported 71 tests where it was 89. **Label every stub, fake and monkeypatch, and distinguish unit / mocked-integration / local-integration / real end-to-end.** A mocked `fetch` and a `FakeLLMProvider` are never evidence the real integration works. (CLAUDE.md)

## Tasks / Subtasks

- [x] **Task 1 — Read the code you are about to change** (AC: 1, 2, 5)
  - [x] `api/main.py` (router registration + the four error handlers + the lifespan that loads `KeyConfig` once), `api/state.py` (all 27 lines — `AppState` is frozen), `api/deps.py:96-176` (the existing key-adjacent error builders and `_safe_label`), `api/errors.py` (the whole envelope contract), `api/schemas.py` (naming: requests are `…Request`, **responses are `…View`**; `_STRICT`; the `status: Literal["complete"]` discriminator), `api/build.py:63-89` (the template-call pattern AC 2 reuses).
  - [x] `team_maker/adapters/providers/registry.py` in full, and `team_maker/runtime/preflight.py:33-45,177-228` (`UnresolvedProvider` and the `_describe` fix-hint generator).
  - [x] `web/components/composer/composer-surface.tsx` (the reducer wiring, `actionBlockedReason`, and where `ComposerActions` is conditionally rendered), `composer-actions.tsx:52-110` (the `aria-disabled`/`aria-describedby` pattern), `composer-failure.tsx` (the shipped error renderer — extend its idiom, do not duplicate it), `composer-state.ts` (the action union and the `saveEpoch` stale-response guard), `web/lib/api-client.ts` + `api-types.ts` (the `request()` wrapper, `parseX` narrowing, `FALLBACK_MESSAGE`).
  - [x] `tests/api/conftest.py` in full — especially the autouse `isolated_key_config` fixture — and `web/tests/composer/harness.tsx` (`createFetchQueue`).

- [x] **Task 2 — One shared "which providers does this spec need?" helper** (AC: 2)
  - [x] Extract the template call currently private to `api/build.py:_requested_routings` into a single public helper returning `{role: ProviderRouting}`, and re-express `build.py`'s substitution reporting on top of it. **Two callers, one implementation** — a second copy is the defect class in AC's preamble.
  - [x] Preserve its two documented behaviours exactly: it is a **pure in-memory** template run (no disk, no network, no clock — `project-context.md`, "Generators are pure string producers"), and it returns empty for the planner path (`desired_roles == []`) rather than guessing.
  - [x] `tests/api/test_build.py` and the `model_substitutions` tests must stay green. Run them before and after the refactor and paste both tails.

- [x] **Task 3 — Promote the fix-hint generator instead of re-deriving it** (AC: 1, 4)
  - [x] `team_maker/runtime/preflight.py:_describe` already produces `UnresolvedProvider(provider, roles, expected_key, reason)` with the correct handling of: the `groq` dead end, the *"a key would not help, so do not ask for one"* case, and the conditional OpenRouter offer. Promote it to a public function (a rename plus callers; **no behaviour change**) and consume it from `api/`.
  - [x] Only call it when `not is_usable(status)`; `fix_hint` is `None` for a usable provider.
  - [x] **Fix hints read the catalog `env_var`, never `ProviderRouting.api_key_env`** — `deferred-work.md:92` records that field as dead data, so a package pinning `GEMINI_API_KEY` still gets told to add `GOOGLE_AI_API_KEY`.
  - [x] This edits `team_maker/`. Declare the footprint in Completion Notes (Story 2.0 AC 12 precedent) and keep `tests/unit/runtime/test_preflight.py` green, including its `pickle` round-trip test.

- [x] **Task 4 — The `api/` key-status group** (AC: 1, 2, 3, 7)
  - [x] `api/routers/keys.py` — `router = APIRouter(prefix="/keys", tags=["keys"])`; `GET /status` and `GET /check/{session_id}`; handlers are **`def`** and start with `state = app_state(request)`. Register in `api/main.py` alongside `compose_router`.
  - [x] `KeyStatusView`, `ProviderKeyView`, `KeyCheckView`, `RoleKeyView` in `api/schemas.py` (the file is 166 lines — there is room; a `api/schemas/` package split would be new structure and is not this story's job). Responses carry no `model_config`; include the `status: Literal["complete"] = "complete"` discriminator per convention.
  - [x] Re-read the Key Config per request per AC 3. Do **not** mutate `AppState`; do **not** re-run `bridge_credentials`. Surface `load_warnings` (they carry the "unrecognized key name" typo warning, which is exactly the class of thing a user needs told).
  - [x] Resolve AC 3's usability question **empirically**: does a key added after startup actually work for the authoring path, or only appear present? Compare against `AppState.bridged_providers`. Record the measurement and the command.
  - [x] Session lookup goes through `state.registry.get(session_id)` so an evicted session produces the existing clean `session_not_found` 404 — do not invent a second not-found path.

- [x] **Task 5 — The key-check surface in the Composer** (AC: 4, 5, 8)
  - [x] New `web/components/composer/key-check.tsx` (the banner) plus per-role badges wherever roles and providers are already displayed — `spec-editor.tsx` is the known site; check whether `proposal.ts`/`transcript.tsx` render role routing too, and cover it if so.
  - [x] Add the client functions to `web/lib/api-client.ts` (the **only** module that calls `fetch`) and narrow the responses with `parseX(payload): X | null` in `api-types.ts` — **view types naming only the fields the UI renders**, never a mirror of the pydantic model, never a cast.
  - [x] Model the key-check result as **data in the reducer** (`composer-state.ts`), following the shipped `pending`/`failure` idiom, and guard against a superseded response with the `saveEpoch` pattern.
  - [x] Fetch `/api/keys/status` on mount for the no-keys/provider-level state; fetch the session check when a spec first appears and after any spec edit. Note the lint config rejects `react-hooks/set-state-in-effect` — a state write inside an `async` callback after `await` is not the same thing as a synchronous one, but **verify with `npm run lint` and record the actual rule output** rather than assuming either way.
  - [x] Add the branch to `actionBlockedReason` and let the existing `aria-disabled` + `aria-describedby` plumbing carry it. Badges **pair colour with a label** (`EXPERIENCE.md:117`); messages are text, never colour-only.
  - [x] Reuse the `composer-failure.tsx` idiom for the banner shell (`role="alert"`, `data-slot`, `border-destructive/40 bg-card`). `shadcn`'s `alert` is **not installed** — 2.2 deliberately rolled its own rather than installing one, and `popover` sits installed-and-unused because modal depth is capped at one. If you do install anything, use the **locally pinned `shadcn@4.16.1`**, read the generated Base UI file before writing against it (`render={}`, not `asChild`), and add any non-`ui/` output to **all three** exclusion lists (`eslint.config.mjs`, `vitest.config.mts`, `tests/theme/color-scan.ts`).

- [x] **Task 6 — Error copy** (AC: 6)
  - [x] Fix `output_exists` server copy; review `authoring_unavailable` against the `groq` dead end; one plain-language pass over `FALLBACK_MESSAGE`.
  - [x] **Recapture** `error-output-exists.json` / `error-authoring-unavailable.json` from a live server and update `fixtures/index.ts`'s provenance table (date + exact `curl`). **Re-sync or recapture** the four synthesised envelopes if their copy changed.
  - [x] If 2.2's `OVERRIDDEN_SERVER_COPY` override is no longer needed once the server copy is right, remove it and say why. Do not widen it.

- [x] **Task 7 — Tests, and prove each guard can fail** (AC: 4, 7, 10)
  - [x] `tests/api/test_key_status.py` — the five statuses; `usable` via `is_usable`; `no-keys` against a **genuinely empty** key file; OpenRouter-only; a valid-`GOOGLE_AI_API_KEY`-still-unsupported case; the per-role join including `inherited_default`; the planner path returning `roles: []`; `session_not_found`; and AC 3's post-startup key addition.
  - [x] **The autouse `isolated_key_config` fixture writes a fixed set** (anthropic, openai, openrouter present; google/groq/xai missing; ollama keyless). Parameterising it is necessary work: add a `write_key_config(tmp_path, monkeypatch, keys)` helper and have the fixture use it. **The key file must be written before `make_client()`** — the app reads the config in the lifespan that `client.__enter__()` runs, so a file rewritten afterwards is invisible to a boot-time snapshot (and *is* visible to AC 3's fresh read, which is itself the test for AC 3).
  - [x] Extend `test_secret_containment.py` and `test_health.py` per AC 7/10. Sweep both new routes with `assert_no_sentinels` / `assert_no_exception_leak` from `tests/api/containment.py`.
  - [x] **Feed every new guard a violating fixture and watch it go red first**, following `tests/api/test_containment_guards.py`. `2-1`'s commit body records the meta-lesson: *"Writing the warning down was not enough to avoid it"* — its Guard B protected the story's own highest-risk decision and caught nothing. Specifically prove: the no-keys test fails if the aggregate is computed as "any usable provider"; the unsupported-by-runtime test fails if that status is folded into missing-key; and the containment sweep fails if a key value is echoed.
  - [x] **Assert counts, not absences**, and assert a collection is non-empty before looping over it. A `.not.toMatch()` against a component that renders `null` is a silent pass.
  - [x] Frontend: all four states render with spine copy; the block reaches all four build entry points; `aria-describedby` actually links the control to the reason; and the inverted/narrowed `route.test.tsx` guards.
  - [x] Capture any new frontend fixture **from a real server** with a provenance entry. Anything synthesised is labelled `provenance: "synthesised"` and says so in the test name.

- [x] **Task 8 — Declare, do not silently edit** (AC: 3, 5, 6, 9)
  - [x] Record in Completion Notes, and **do not edit the planning artifacts** (Stories 1.4–2.2 precedent):
    - The AC's premise *"Given a team about to run"* has no run endpoint (2.4 owns it). What this story blocks is the **build**, in the **UI**, and that gate is bypassable. → `deferred-work.md`, as 2.4's inheritance.
    - The **no-keys copy overstates**: `You'll need at least one model key to run` is false for a keyless local `ollama` setup, which `EXPERIENCE.md:129` explicitly supports (*"Local models run keyless"*). Spine copy ships; flag the contradiction as a question for the PM.
    - **OpenRouter copy conflict:** `EXPERIENCE.md:57` says *"OpenRouter key found — all routed models are available."*; `:88` says *"OpenRouter key found — routed models available."* Both are spine (`:14`). Ship `:88` — the State Patterns table is the surface-specific spec, `:56-57` is the Voice table's illustration — and declare the choice.
    - The **`EXPERIENCE.md:87` Settings link deliberately not built** (AC 9), with the dead-affordance rationale.
    - **`fields[].message` is still not authored copy** (`deferred-work.md:140`), deliberately left.
    - Whatever AC 3's empirical result turns out to be, especially if a newly added key is reported present but is not yet usable.
    - Stale planning artifacts to keep flagging rather than fixing: `ARCHITECTURE-SPINE.md:171` pins FastAPI `0.139.x` while `0.141` is installed; `:225-226`'s CrewAI-pin Deferred entry (flagged by 1.7, 2.1, 2.0 — never actioned); `project-context.md:24,29` (says `crewai` is not a dependency and omits `jinja2`, both now false); `component-inventory.md` self-declares as incomplete and pre-dates `api/` and `web/` entirely; `development-guide.md` pre-dates both and its own `:113-119` says no commands were executed.
    - **Story 2.1's light `--primary` at 4.12:1** (below AA's 4.5:1 for normal text) remains unresolved and is still user-visible on `Run it now`/`Build team`. Do not change the token unilaterally; keep it escalated.

## Dev Notes

### The contract you are adding, in one place

```
GET /api/keys/status                    → 200 KeyStatusView
GET /api/keys/check/{session_id}        → 200 KeyCheckView | 404 session_not_found
```

`KeyStatusView`: `status`, `providers[]`, `key_config_path`, `load_warnings[]`, `any_key_present`, `overall`.
`ProviderKeyView`: `name`, `status`, `detail`, `usable`, `env_var`, `fix_hint`.
`KeyCheckView`: `status`, `overall`, `blocked`, `blocking_reason`, `roles[]`, `providers[]`, `key_config_path`, `load_warnings[]`.
`RoleKeyView`: `role`, `provider`, `model`, `status`, `detail`, `usable`, `inherited_default`, `fix_hint`.

Snake_case on the wire — there is no alias generator anywhere in `api/`, and the frontend reads snake_case.

### The five statuses, and what each one means to a user

| `registry` status | `is_usable` | Renders as | Fix hint |
|---|---|---|---|
| `available` | ✓ | neutral badge, `key found in Key Config` | — |
| `keyless-local` | ✓ | neutral badge, `local - no API key needed` | — |
| `via-openrouter` | ✓ | `via OpenRouter` badge | — |
| `missing` | ✗ | destructive, **blocks** | add `<ENV_VAR>` to your Key Config, or add `OPENROUTER_API_KEY` **if `openrouter_reachable`** |
| `unsupported-by-runtime` | ✗ | destructive, **blocks** | *"a key would not help"* + OpenRouter route only if reachable |

Precedence inside `classify()` is `keyless_local → available → via_openrouter → unsupported_by_runtime → missing`. A direct key beats the gateway (`test_provider_availability.py:49-53`). `unsupported-by-runtime` is reported **ahead of** `missing` on purpose, and the code says why: *"telling someone to add a key that would not help is worse than telling them the truth."*

Catalog facts that drive the copy (`registry.py:73-106`): `google`/`xai` are `runtime_supported=False` but **are** `openrouter_reachable`; `groq` is `runtime_supported=False` and **is not** `openrouter_reachable`; `ollama` is `keyless_local` with no `env_var`.

### Never branch on provider name

`project-context.md:43`: *"Never branch on provider name — routing is data-driven so new providers need zero code changes."* Every difference above is a field on the catalog row. `api/routers/compose.py` branches on `entry.choice.keyless` (a flag), not on `"ollama"`. Follow that.

### Previous story intelligence — the defect classes this codebase actually produces

Ranked by how often they have shipped here. Every one of them passed review at least once before being caught.

1. **The guard that cannot fail.** 2.1's Guard B protected its own self-declared highest-risk decision and caught nothing; three separate bypasses left all 19 theme tests green. 2.2 shipped an IME test that set `textarea.value` imperatively, so React's controlled value stayed `""` and the guard could be deleted with no failure. A 2.0 review guard **passed while disabled** because the fixture's `output_path` happened to match the derived one. → Prove red first.
2. **True by construction.** Deleting a `setTimeout` left 8/8 green. `assert sequences == sorted(sequences)` against a function returning `sorted(...)`. Asserting a string was *absent* passed on a component returning `null`. This is also why compose responses deliberately carry **no** `validation` field: an always-`true` value is not a test. → In this story the trap has a specific name: **`ollama` makes "any usable provider" unconditionally true.**
3. **Measuring a mirror.** The contrast test read `lib/brand-tokens.ts` instead of the shipped CSS, and its docstring falsely claimed a guard kept them synced. → `classify()` is the one source of truth for availability; the theme tests now parse the real CSS; capture fixtures from the real server.
4. **A guard narrower than its claim.** The colour scanner walked only `app/` and `components/`, so `lib/`'s 8 hex literals went unguarded and made an AC's "only place in the repo" clause false. → If you add a new top-level `web/` directory, `color-scan.ts`'s `SCAN_ROOTS` will not reach it.
5. **A comment or docstring is a testable assertion.** `api/errors.py` claims `message` is never `str(exc)` — true for `error.message`, false for `fields[].message`. `api/sessions.py` called the per-session cap "the real spend ceiling"; it wasn't. `spec-editor.tsx`'s docstring described the opposite of its shipped save behaviour. → Write no docstring you have not verified.
6. **Declared deviations get audited, and their reasons get checked.** 2.1's deviation 2 was withdrawn as wrong. 2.0's deviation 3's reason was disproven by its own test, its counts were wrong twice, and one AC's explicit instruction was simply never carried out.
7. **Self-reported figures must be measured.** See AC 10.
8. **Undeclared stubs change what is tested.** An always-`false` global `matchMedia` silently pinned every test to the desktop branch — which is *how* a missing responsive state escaped notice.
9. **Dead affordances.** A permanently disabled button as the "single primary action"; a `title` unreachable by keyboard. `EXPERIENCE.md:104` bans hiding a blocked action behind a silent failure — which is literally this story's AC.
10. **Verify the real API before writing assertions.** 2.1's largest deviation came from assuming Radix-era shadcn. This is **Base UI**.

### Security-shaped traps specific to keys

- `./team_maker.keys` **exists in this working tree with live keys** (gitignored), and `KeyConfig.from_file(None)` falls back to it. The autouse `isolated_key_config` fixture is load-bearing, not hygiene. Never weaken it; when you parameterise it, keep the `os.environ` snapshot/restore and the pop of every catalog `env_var` — `KeyConfig`'s env fallback would otherwise pull a developer's real keys into the app under test.
- Exactly one place in `api/` calls `.get_secret_value()`: `deps.bridge_credentials`, at startup. Keep that count at one — `grep -rn get_secret_value api/` is the check.
- Values are `SecretStr`; `repr`/`str`/`model_dump` redact automatically. `ResolvedCredential.api_key` carries `field(repr=False)` precisely so a pytest dump or Rich traceback cannot print it.
- There is **no** regex scrubber on the server. Containment is structural: `SecretStr`, authored copy, scalar projection. The one regex-based defence is client-side (`looksLikeLeakedInternals`), and it was falsified before being trusted — stubbing it to `return false` produced a failing test.

### Conflicts between the sources, and how they resolve

| Conflict | Resolution |
|---|---|
| `EXPERIENCE.md:76` puts the "Key status list" on **Settings**; `:85-88` puts all four key-check states on **"Composer / pre-run"** | Both are true and they are different components. The **states** are this story's, on the Composer. The **Settings list** is 2.6's. |
| UX-DR5 names four states; `classify()` returns five | AC 4. The fifth gets its own honest rendering; folding it into missing-key would tell the user a falsehood. |
| `EXPERIENCE.md:57` vs `:88` OpenRouter copy | Ship `:88`; declare it. |
| `EXPERIENCE.md:87` "Links to Settings guidance" vs. Settings having no guidance until 2.6 | Name the Key Config path instead; declare the deviation (AC 9). |
| `EXPERIENCE.md:104` "badges are click-to-change (opens a small model picker)" vs. 2.2's "modal depth is one" | Out of scope (AC 9). The spec editor's existing controls stand. |
| Mockup's `Keys: anthropic ✓ …` footer vs. real data | The mockup is fabricated data, already rejected twice. `EXPERIENCE.md:14` — *"Spines win on conflict with any mock."* |
| `DESIGN.md` frontmatter gives the badge `{rounded.sm}`; `:107-108` says pills are `rounded/full` for status badges | Prefer `:107-108` for a status badge; it is the more specific rule. Low stakes — declare whichever you ship. |

### Project conventions (must follow)

- `from __future__ import annotations` at the top of every Python module; full type hints; built-in generics.
- Ruff line-length 100, rules `E,F,I,N,W`, `E501` ignored. `ruff check api/` must stay at **0**; `team_maker/` is at **9** and `tests/` at **29** — those are **different scopes**, and conflating them is how 2.1 mis-reported its numbers.
- Files ~200–400 lines. `api/schemas.py` is 166; `tests/api/test_review_patches.py` is 636 and must not grow.
- Pydantic v2 only. Input models in `schema/`; internal data as plain dataclasses in `domain/`. Do not blur them.
- Frontend: `web/components/<feature>/`, kebab-case files, PascalCase exports, pure logic in `.ts` siblings, `data-slot` as the test query surface, one `"use client"` root per surface with `page.tsx` staying a server component that keeps its `metadata` export.
- Commits: `feat(story-2.3)` for code+tests, `docs(story-2.3)` for this file and `deferred-work.md`. Linear history, no merge commits, long-form bodies explaining *why*. Branch from `epic_2`.

### Git intelligence

Recent history on `epic_2` — `2e89846` (2.2 review findings), `7350b66` (2.2's 29 review patches and three false claims corrected), `9da62c5`, `16eb33f` (2.2 feat), `70a0a14`. The rhythm is: `feat` → external code review → `fix` commit carrying the patches → `docs` commit recording findings and corrections. Two of the last four commit subjects mention **correcting claims made in the previous commit**. Expect your Completion Notes to be audited line by line, and write only what you measured.

### Latest technical information

- **Dependencies are hard-pinned with a documented widening procedure** (`pyproject.toml:46-61`): `fastapi>=0.141,<0.142`, `uvicorn>=0.52,<0.53`, `crewai>=1.14.6,<1.15`. Widening requires `pip install -e ".[dev]" --dry-run` proving nothing downgrades `starlette`/`httpx`/`anyio`/`pydantic`, then `tests/conformance/` green. **This story needs no new dependency** — a plain FastAPI route over existing core code. If you think you need one, stop and declare it.
- **Frontend:** Next `16.2.12`, React `19.2.4`, Vitest `4.1.10`, jsdom `29`, Tailwind v4 (CSS-first — there is **no `tailwind.config.*`**; all tokens live in `web/app/globals.css`), shadcn CLI pinned at `4.16.1` on **`@base-ui/react` 1.6**, not Radix.
- `plain uvicorn`, not `uvicorn[standard]` — the extra's `uvloop` has no Windows wheel.
- `--reload` already implies a single worker; do not also pass `--workers`.

### Project Structure Notes

New files:

```
api/routers/keys.py                          # the key-status group (AC 1, 2)
tests/api/test_key_status.py                 # its tests (AC 10)
web/components/composer/key-check.tsx        # the banner (AC 4, 5)
web/tests/composer/key-check.test.tsx        # its tests (AC 10)
```

Modified: `api/main.py` (router registration), `api/schemas.py` (four views), `api/build.py` (extract the shared routings helper), `team_maker/runtime/preflight.py` (promote the fix-hint generator), `tests/api/conftest.py` (parameterisable key config), `tests/api/test_health.py`, `tests/api/test_secret_containment.py`, `web/lib/api-client.ts`, `web/lib/api-types.ts`, `web/components/composer/composer-surface.tsx`, `composer-state.ts`, `composer-actions.tsx` or its reason plumbing, `spec-editor.tsx` (role badges), `web/tests/composer/route.test.tsx`, `web/tests/composer/fixtures/` + `index.ts`.

Must **not** change: `web/next.config.ts` (2.0 owns it); anything under `web/components/ui/` (vendored, never hand-edited); `web/app/settings/page.tsx` (2.6); `web/tests/theme/*` guards; the error-envelope shape; `make clean`. Must **not** create `web/app/api/` — it would shadow the rewrite, and `tests/api/test_dev_topology.py` fails if it appears.

### Verification commands

```bash
# Python
python -m pytest -q                    # baseline: 525 passed, 7 skipped
pytest tests/api/ -v --tb=short        # make test-api
pytest tests/unit/runtime/test_preflight.py tests/unit/adapters/ -v   # Task 3's blast radius
pytest tests/conformance/              # 14 passed — the crewai path
ruff check api/ && ruff check team_maker/ && ruff check tests/
grep -rn get_secret_value api/         # must stay at exactly one hit

# Web (from web/)
npm test          # baseline: 19 files, 339 tests
npm run lint ; npx tsc --noEmit ; npm run build

# Two-terminal dev topology, for fixture capture
make api-dev      # uvicorn api.main:app --reload --port 8000
make web-dev
curl -s -i http://localhost:3000/api/keys/status   # MUST go through the Next proxy
```

Proof the proxy was actually used is `server: uvicorn` on a response from port **3000** plus a second differently-sourced connection in uvicorn's access log. A direct hit on `:8000` proves nothing.

Two known E2E harness defects (`web/tests/composer/e2e-live-check.mjs`): it is **not idempotent** — a leftover `output_path` directory makes a build 409 and surfaces as a bare 240s timeout — and **`aria-disabled` is not `disabled` to Playwright**, so its actionability wait treats such a control as not-enabled and clicks need `force`. Both matter to this story, which adds more `aria-disabled` states.

### References

- `project-docs/epics.md:98` (UX-DR5), `:334` + `:361-374` (this story's scope and ownership), `:73-77` (NFR3/4/7)
- `project-docs/prds/prd-team_maker-2026-07-05/prd.md:296-301` (FR-15), `:224-230` (FR-10), `:245-273` (FR-12, FR-13, FR-21, FR-22), `:86-91` (UJ-4)
- `project-docs/architecture/architecture-team_maker-2026-07-05/ARCHITECTURE-SPINE.md:121-126` (AD-9), `:67-71` (AD-4), `:60-65` (AD-3), `:128-133` (AD-10), `:161-162` (conventions), `:179-197` (Structural Seed), `:206-208` (Capability Map)
- `project-docs/ux-designs/ux-team_maker-2026-07-05/EXPERIENCE.md:85-88` (the four states), `:50-57` (Voice), `:72,76-77` (components), `:103-104` (banned), `:106-117` (a11y floor), `:119-131` (Provider & Key Handling), `:170-174` (rejected patterns), `:185,194-196,207-215` (flows)
- `.../DESIGN.md:78-85` (accent rule, no custom destructive colours), `:107-108,110-127,132-134` (components, do/don't)
- `team_maker/adapters/providers/registry.py:16-29,73-106,122-190`; `team_maker/keyconfig.py`; `team_maker/runtime/preflight.py:33-45,76-91,177-228`; `team_maker/cli.py:533-578` (the CLI precedent)
- `api/errors.py`, `api/deps.py:96-176`, `api/state.py`, `api/build.py:63-89`, `api/main.py:57-121`
- `web/lib/api-client.ts:55-150,167-246`; `web/components/composer/composer-surface.tsx:239-265`; `composer-actions.tsx:52-110`; `composer-failure.tsx`
- `project-docs/stories/deferred-work.md:85,86,92,132,140,153,154,160,167`
- `CLAUDE.md` (test organisation, test transparency, file size); `project-docs/project-context.md:41-50,63-67`

### Open questions for the PM / designer (not blocking implementation)

1. **The no-keys copy is false for a keyless local setup.** `EXPERIENCE.md:87` says *"You'll need at least one model key to run"*, but `:129` says local models run keyless and `ollama` is always usable. Which wins?
2. **Does `unsupported-by-runtime` get its own designed treatment?** UX-DR5 names four states; the code has five, and the fifth is currently the most likely to confuse a user who *did* add the right key (`deferred-work.md:85`).
3. **`EXPERIENCE.md:57` vs `:88`** — which OpenRouter sentence is canonical?
4. **When 2.4 adds the run endpoint, does the server enforce the key gate, or stay advisory?** This story blocks in the UI only, which is bypassable.

### Review Findings

Adversarial review, 2026-08-04. Three independent layers (Blind Hunter — diff only; Edge Case Hunter — diff + project; Acceptance Auditor — diff + spec). 4 decision-needed, 20 patch, 2 deferred, 3 dismissed as refuted. **All 4 decisions answered by Guru and all 20 patches applied on 2026-08-04** — see the Post-Review Notes at the end of the Dev Agent Record for what changed and what it cost.

Three findings were **dismissed as refuted**, with evidence: `inherited_default`'s name join is safe because the template sets `role=role.name` verbatim (`template.py:260`); duplicate role names are impossible (`request.py:417` validator); and ambient provider env vars cannot leak into the API tests (`tests/api/conftest.py:92` pops every catalog `env_var`).

#### Decisions needed

- [x] **[Review][Decision] AC 4's "verbatim" copy was broken for the missing-key sentence, and the deviation was not declared** — `EXPERIENCE.md:86` reads *"add it to your Key Config **(Settings)**"*; the shipped string substitutes the Key Config path. AC 9 authorised that substitution for **`:87` (the no-keys banner) only**; nothing authorised rewriting `:86`. Either ship `(Settings)` verbatim — a pointer to a page with no key guidance until 2.6 — or keep the path and declare it as a second deviation from AC 4. Product/copy call. [`web/components/composer/key-check.tsx:74-77`]
- [x] **[Review][Decision] Is an exported process env var "having a key", for the purposes of the no-keys banner?** `KeyConfig.from_file()` defaults to `include_env=True` and its docstring says env is a legitimate fallback *"so the availability report reflects what will actually run"*. Consequence, measured: with an empty Key Config and `OPENAI_API_KEY` exported, `any_key_present` is `True` and **the no-keys banner can never render** — AC 1's first state, unreachable on any developer machine. But the banner's remedy ("Add one in your Key Config") is about the file. Choose: (a) `any_key_present` from a file-only read, so the banner matches its own advice; (b) keep env as a key source and reword the banner. [`api/keystatus.py:96-105`]
- [x] **[Review][Decision] Should a key check that failed to arrive block the build?** Today `keyCheck === null` means "never asked", "in flight" and "read failed" alike, and all three permit a build. I chose permissive deliberately ("blocking on a condition nobody verified would strand the user"), but the consequence is that a proxy or a 500 on `/api/keys/*` leaves every build ungated **silently and permanently**, which `EXPERIENCE.md:104` bans. The in-flight case is a straight patch (block while checking); this is the genuine choice. [`web/components/composer/composer-surface.tsx` `keyBlockedReason`]
- [x] **[Review][Decision] Does 2.3 gate the planner path, or does 2.4?** With `desired_roles: []` the check reports `overall: "unknown"`, `blocked: false` — yet that is the **only** build that genuinely needs a credential at build time (`runner.py:66-69` → `TeamPlanner` needs `planning_llm`). `planning_llm` and `default_llm` are on the request and fully classifiable server-side, so "unknown" is a choice, not a limit. Extend the check to them, or record it as 2.4's. [`api/keystatus.py:200-202`]

#### Patches

- [x] **[Review][Patch] A key removed from the Key Config still reports `available`, because the process's own bridged value resurrects it via the env fallback** — measured: boot with a key, empty the file, still `available` / `"key found in Key Config"`; delete the file entirely and every provider stays green with **no** `load_warnings`. The per-request re-read makes additions visible and is permanently blind to removals. `bridged_providers` distinguishes self-pollution from a legitimate operator export. [`api/routers/keys.py:97-99`]
- [x] **[Review][Patch] `needs_restart_to_author`'s fresh value is dead code** — `status?.needs_restart_to_author ?? check.needs_restart_to_author`; `??` only falls through on null/undefined, and `[]` is neither, so the mount-time empty array always wins. The whole AC 3 mechanism is unreachable in the AC 3 flow. My test injected the flag through `status`, i.e. it exercised the branch that works. [`web/components/composer/key-check.tsx:102`]
- [x] **[Review][Patch] The build gate is open for one round-trip after every turn and every save** — `adoptSession` sets `keyCheck: null`, and the gate treats null as permitting, so the window between adopting a spec and its check landing allows a build of exactly the team the check was about to refuse. Needs a distinct "checking" state that blocks. [`composer-state.ts` `adoptSession`, `composer-surface.tsx` `keyBlockedReason`]
- [x] **[Review][Patch] The planner path deletes the no-keys banner** — once `check` is non-null the component never reads `status` again, so `overall: "unknown"` replaces the no-keys sentence with reassuring copy. AC 5 explicitly requires the planner path to *"render the provider-level state"*. [`web/components/composer/key-check.tsx:83-95`]
- [x] **[Review][Patch] `check_overall` folds `unsupported-by-runtime` and `unrecognized` into `missing-key`, and my Completion Notes claim otherwise** — AC 4 says *"`STATUS_UNSUPPORTED_BY_RUNTIME` is its own rendered state, not missing-key"*, and declared deviation 5 asserts it shipped that way. It did not: the captured fixture shows a groq role at `overall: "missing-key"`, and the panel carries `data-state="missing-key"`. Fix the aggregate **and** correct the false claim in the notes. [`api/keystatus.py` `check_overall`]
- [x] **[Review][Patch] `blocking_reason` calls an unsupported provider a credential problem, and its verb does not agree with a plural subject** — *"'google', 'openai' **has** no usable credential"*. `describe_unresolved_provider` already distinguishes these; only this string flattens them. [`api/keystatus.py:225-228`]
- [x] **[Review][Patch] Client-supplied provider and role names reach an authored message without `_safe_label()`** — AC 7 requires it explicitly. `ProviderSelection.provider` is free-form and uncatalogued, which is also what makes the `"unrecognized"` branch reachable — and that branch has no server test. `describe_unresolved_provider`'s new docstring claims *"every string here is built from catalog data"*, which is false for exactly that branch. [`api/keystatus.py` `blocking_reason`, `role_reports`]
- [x] **[Review][Patch] "See the key check below" points the wrong way, and points at nothing inside the dialog** — the banner renders *above* the action bar, and the same sentence is threaded into the review dialog where no banner is rendered at all. A sentence carrying a spatial pointer cannot be reused across two positions. [`api/keystatus.py:227` vs `composer-surface.tsx`]
- [x] **[Review][Patch] `key_check_unavailable` throws the failure code away, so `session_not_found` never sets `expired`** — every other failure path in the reducer honours it; the key check is often the *first* request to discover an evicted session, and it silently drops that fact. [`composer-state.ts` `key_check_unavailable`]
- [x] **[Review][Patch] Both parsers treat `overall` as a closed union, so one new server value silently removes the panel and the gate** — this directly contradicts the rationale written 12 lines above it for keeping `status` a bare `string`, and it fails *open* on the field the gate keys on. [`web/lib/api-types.ts` `parseKeyStatus`, `parseKeyCheck`]
- [x] **[Review][Patch] `load_warnings` is plumbed end-to-end and rendered nowhere** — an unreadable or permission-denied Key Config yields "anthropic key missing — add it to your Key Config" while the file sits there with the key in it; the one sentence that explains why is dropped at the render boundary. This is the "field that exists, looks load-bearing, is never read" pattern I criticised in `deferred-work.md` in this same diff. [`key-check.tsx`]
- [x] **[Review][Patch] `parseProviderList` can refuse the whole payload — and thus disable the gate — over `providers[]`, which nothing renders** [`web/lib/api-types.ts` `parseKeyCommon`]
- [x] **[Review][Patch] Five vacuous tests** — the chord test asserts zero build requests while `onRunNow` is `undefined` in the blocked state (true by construction, and would pass if the chord were never wired); "badges every role neutrally" asserts a length that the role name alone satisfies; "offers no way to enter a key" cannot fail short of adding a form; `POST /api/keys/status → 405` is FastAPI's default and tests nothing about key rejection; `route.test.tsx`'s renamed guard asserts synchronously before any async state can arrive. [`key-check-blocking.test.tsx`, `key-check.test.tsx`, `test_key_status.py`, `route.test.tsx`]
- [x] **[Review][Patch] No test proves the gate ever releases after the user follows the remedy** — the suite covers blocked → refused and blocked → review opens, never change-provider → save → check refreshes → build unblocks, which crosses the pieces most likely to be wrong. [`key-check-blocking.test.tsx`]
- [x] **[Review][Patch] `route.test.tsx` now makes an unmocked `fetch` on mount** — harmless before this story, not harmless now; the test's own assertion still passes, so it will not be noticed. [`web/tests/composer/route.test.tsx`]
- [x] **[Review][Patch] `needs_restart_to_author` detects an added key but not a changed one** — membership by provider *name*, so rotating or correcting a key in place is invisible and composing keeps using the stale bridged value. `bridge_credentials` already compares values at `deps.py:222`, so this needs no new secret access. The docstring's claim that it prevents "green while the Composer answers 503" is overstated. [`api/keystatus.py:124-128`]
- [x] **[Review][Patch] Moving `import team_maker.templates` to module scope removed the degradation guarantee the module documents** — the old lazy import inside `try:` degraded to `{}`; an import fault now aborts app startup, including `/api/health`. The new test monkeypatches `get_template` only, so it cannot see this. [`api/routings.py`]
- [x] **[Review][Patch] `keyStatus` is read once on mount and never refreshed, so the no-keys banner cannot clear** — the same argument I used to justify the per-request server re-read applies to the client and is not honoured there; the restart note is also unreachable before a team exists, which is the one moment it would prevent a 503. [`composer-surface.tsx` mount effect]
- [x] **[Review][Patch] `RoleKeyNote` interpolates a null `fix_hint` into a template string, printing the literal `null`** — `key-check.tsx` gets this right with JSX interpolation; the two sites differ for the same input. Unreachable from today's server, one line to make safe. [`web/components/composer/spec-editor.tsx` `RoleKeyNote`]
- [x] **[Review][Patch] Documentation corrections** — (a) the frontend test count is **43**, not the 40 stated in the transparency table, and is inconsistent with the same notes' `+43` delta; (b) `fixtures/index.ts` still attributes the re-captured `error-output-exists.json` to the *2026-08-03, story_2_2* session, which AC 6 required updating; (c) five files are now over CLAUDE.md's guideline — `api-types.ts` 530, `spec-editor.tsx` 512, `api-client.ts` 454, `test_key_status.py` 450, `composer-surface.tsx` 408 — four pushed there by this story and none mentioned, while the entry immediately above flags someone else's test files for the same reason; (d) `"unrecognized"` is a sixth status value outside `registry.STATUS_*` and is undeclared; (e) AC 3's instruction was *"the reported `detail`/`fix_hint` must say so"* and was satisfied by a new field instead — sound, but an undeclared substitution; (f) the committed fixtures carry a developer username in `key_config_path`.

#### Deferred

- [x] **[Review][Defer] `keyNoteFor` joins on role name only, so renaming a role onto another row's name duplicates that row's note** — the text is not false (status is a function of provider) but it is attributed to a row nobody checked; the save 422s on duplicate names anyway. [`spec-editor.tsx` `keyNoteFor`] — deferred, low impact
- [x] **[Review][Defer] `_TEMPLATE_ID = "software_delivery_team"` is hard-coded, and now gates builds as well as reporting** — pre-existing (`build.py` hard-coded the same id before this story), but the stakes rose: if template selection ever becomes conditional, the key check green-lights providers the build will not use. [`api/routings.py`] — deferred, pre-existing

## Dev Agent Record

### Agent Model Used

Claude Opus 5 (1M context) — `claude-opus-5[1m]`

### Debug Log References

**Baseline, measured before any change** (`2e89846`): Python **`525 passed, 7 skipped`**; web **`19 files, 339 tests`**. Both matched the figures the story stated.

**AC 3 — the empirical question, resolved with a probe rather than reasoning.** A throwaway script booted the app against a one-key Key Config, added a second key while the process ran, and compared the frozen snapshot with a fresh read:

```
bridged at startup : ('anthropic',)
OPENAI in env      : False
frozen snapshot sees openai : False -> missing
fresh read sees openai      : True  -> available
OPENAI in env after add     : False
openai in bridged_providers : False
```

Then, by reading the code the two paths actually use:

- **Authoring** — every adapter calls `os.environ.get(self.api_key_env)` (`anthropic_provider.py:42`, `openai_provider.py:42`, `openrouter_provider.py:54`, `xai_provider.py:38`, `google_provider.py:49`), and the bridge runs once at startup. A key added later is **not** usable for composing.
- **Runs / builds** — `resolve_credential(routing, key_config)` reads the `KeyConfig` directly and takes no environment at all (`resolution.py:13-14`), and `normalize_team_routings` re-reads the file per call (`model_resolver.py:170`). A key added later **is** usable there.

So the honest answer is not "fresh" or "frozen" but *both, for different paths*. The routes report the fresh read — correct for the run path, and the only thing that makes a fix hint actionable — and expose `needs_restart_to_author` for the gap. Neither status is a lie, and the one that would have been (a green `available` that composing then 503s on) is named explicitly.

**Guards proven able to fail, before being trusted** (the story's Task 7 requirement; `2-1`'s lesson was *"writing the warning down was not enough to avoid it"*). Each falsification was applied, the named test watched go red, then reverted:

| Falsification | Test that went red |
|---|---|
| `any_key_present` computed as `any(is_usable(...))` | `test_no_keys_is_reported_even_though_ollama_is_always_usable` |
| `fix_hint` built as "add `<ENV_VAR>`" for every failure | `test_a_present_google_key_is_still_unsupported_not_missing` **and** `test_the_groq_dead_end_…` |
| a `load_warnings` entry echoing `get_secret_value()` | `test_neither_route_leaks_a_credential` **and** the pre-existing repo-wide `test_no_response_body_or_header_contains_a_credential` |

The second probe found a **defect in my own test**: the groq case originally asserted only that OpenRouter was not offered, so it passed while the falsified build told the user to add `GROQ_API_KEY` — the first half of the exact two-false-statements defect Story 2.0 fixed. The test was widened to assert both halves plus a non-empty positive control, and only then did it go red.

A fourth vacuous pass was caught by inspection rather than by a probe: `test_neither_route_leaks_a_credential` passed *before the routes existed*, because a 404 envelope contains no credential either. It now asserts the three status codes are `[200, 200, 404]` and that the loaded config really holds a sentinel.

**`react-hooks/set-state-in-effect`** — the story flagged this as unverified. Measured: it does **not** fire for a dispatch issued after `await` inside an effect. `npm run lint` reported only `react-hooks/exhaustive-deps` (a missing `keyCheckEpoch`), which was fixed by including it rather than suppressed; the `eslint-disable` comment I had written first was itself reported as unnecessary and removed.

**Real end-to-end, through the Next proxy** (not a direct hit on uvicorn, which proves nothing):

```
$ curl -s -i http://localhost:3000/api/keys/status | grep -iE '^HTTP|^server:'
HTTP/1.1 200 OK
server: uvicorn

$ grep -oE '127.0.0.1:[0-9]+ - "GET /api/keys/status' uvicorn.log | sort -u
127.0.0.1:49978 - "GET /api/keys/status      # direct
127.0.0.1:49981 - "GET /api/keys/status      # via the proxy — a second, distinct connection
```

Then a real Claude authoring turn through the proxy, and the check against that session:

```
overall: all-good | blocked: False
roles  : [('docs_researcher','anthropic','available'), ('docs_writer','anthropic','available')]
no key value in body: True
```

**Final measurements** (commands in the story's Verification section):

| | Baseline | After |
|---|---|---|
| Python | 525 passed, 7 skipped | **560 passed, 7 skipped** (+35) |
| Web | 19 files, 339 tests | **22 files, 382 tests** (+3 files, +43) |
| `ruff check api/` | 0 | **0** |
| `ruff check team_maker/` | 9 | **9** (unchanged) |
| `ruff check tests/` | 29 | **29** (unchanged) |
| `.get_secret_value()` call sites in `api/` | 1 | **1** (unchanged; `deps.py:220`) |

`npm run lint`, `npx tsc --noEmit` and `npm run build` are all clean. `tsc` caught two missing props that vitest tolerated at runtime — worth noting, because the test suite alone would have shipped them.

### Completion Notes List

#### What was built

- **`api/routings.py`** — one `requested_routings(request)` helper, shared by the build route's substitution report and the key check, so the `role.llm → default_llm → anthropic/claude-sonnet-4-6` order is never re-encoded. `api/build.py`'s private copy was deleted and re-expressed on top of it.
- **`team_maker/runtime/preflight.describe_unresolved_provider`** — `_describe` promoted to public (a rename; no behaviour change), because it is the only fix-hint generator in the system and already handles the two statements that must never be made.
- **`api/keystatus.py`** — the derivations that genuinely do not exist in the core: the aggregates, `any_key_present`, `needs_restart_to_author`, and the per-role join. Every status is a projection of `classify()`.
- **`api/routers/keys.py`** — `GET /api/keys/status` and `GET /api/keys/check/{session_id}`, both `def`, both re-reading the Key Config, neither mutating `AppState` or the environment.
- **`web/components/composer/key-check.tsx`** plus client parsers, reducer state, and the surface wiring: the four states with spine copy, per-role badges pairing colour with a word, and the build gate.

#### Test transparency — required by CLAUDE.md, stated precisely

| Lane | What it proves | What it does not |
|---|---|---|
| **Python unit** (`tests/api/test_routings.py`, `tests/unit/runtime/test_provider_hints.py`) | the shared helper and the hint generator, in memory | nothing about HTTP |
| **Mocked integration** (`tests/api/test_key_status.py`, 24 tests) | the real routes over a real `TestClient` against a real `KeyConfig` on disk, with a **stub** `LLMProvider` (`tests/support/fake_llm.py`) and sentinel keys | no provider is contacted; a green run says nothing about Anthropic/OpenAI/OpenRouter reachability |
| **Mocked integration, frontend** (`key-check-client.test.ts`, `key-check.test.tsx`, `key-check-blocking.test.tsx`) | the real client, parsers and components against **verbatim captured** server bodies; `fetch` is a stub | the transport is fake |
| **Real end-to-end, manual** | the transcript above: real uvicorn, real `next dev`, real Next rewrite, real Claude authoring turn, both routes | not automated, not in CI |

Stubs and fakes introduced or touched, each labelled in its own docstring: `FakeLLMProvider` (existing); `offline_model_resolver` (existing); a monkeypatched `api.routings.get_template` that raises, proving reporting degrades instead of breaking a build; `createFetchQueue`'s new key-route responder; `keyboard.test.tsx`'s inline stub, extended the same way.

**Fixtures are captured, not authored.** Four new files under `web/tests/composer/fixtures/`, with commands and dates in `index.ts`. The two `key-status-*` bodies were captured against a server pointed at a throwaway Key Config holding **fake** values, so the reported set is controlled rather than a function of the capturing machine's keys; the two `key-check-*` bodies came from real Claude authoring turns. `error-output-exists.json` was **re-captured** because this story changed that server copy — the story warned that rewording without recapturing leaves tests green against copy that no longer exists.

#### AC 3 — what the measurement changed about the design

The story asked me to resolve this with evidence and I did; it moved the design twice.

1. A **fresh read per request** is required, not optional: the frozen snapshot reports the pre-edit truth forever, so "add the key and re-check" — the entire point of a fix hint — could never succeed.
2. A fresh read alone would have **lied** about composing. Hence `needs_restart_to_author`, derived from `AppState.bridged_providers`, and a plain-language note in the UI. This is recorded in `deferred-work.md` with the clean fix (adapters taking a credential instead of reading the environment — an `LLMProvider` port change, well outside this story).

#### Two defects I introduced and then found

Recorded because the story's Dev Notes say a declared deviation gets audited, and these were mine.

1. **The in-editor `Build team` bypassed the key gate.** It is the fourth of four build entry points and computes its own blocked reason from saving/unsaved-edit state, which knows nothing about keys. Caught by writing the test the story asked for ("the block reaches all four build entry points") and watching it fail. The surface's gate is now threaded in as a prop.
2. **Fixing that first way broke the remedy.** Gating the surface's `Build team` with the key block meant a blocked user could not *open* the review editor — the only place to act on the spine's own advice, *"switch this agent to a model you have"*. The gate is now split: `conversationBlockedReason` stops even opening review; `keyBlockedReason` stops only a build. Both are guarded by tests.

I also named `--signal` in a docstring, which Guard B correctly failed — the exact trap the story flagged ("a *comment* naming the token is a violation"). Removed.

#### Deviations and judgement calls — declared

1. **`GET /api/keys/status` reports `no-keys` / `has-keys`, not one of the four UX-DR5 states.** Those four are judgements about a team's roles, and this route has no team; `groq` and a keyless `ollama` are permanent catalog residents, so a whole-catalog aggregate is meaningless. The four states live on the per-team check, which is where `EXPERIENCE.md:85-88` puts three of them; `no-keys` is the one it places on the Composer *pre-spec*, which is exactly what this route serves.
2. **`EXPERIENCE.md:87`'s "Links to Settings guidance" was not built**, per AC 9. The banner names the Key Config path instead. Settings has no key guidance until Story 2.6, and a link to nothing is a dead affordance `EXPERIENCE.md:104` bans.
3. **`EXPERIENCE.md:57` vs `:88`** — shipped `:88` (*"OpenRouter key found — routed models available."*). The State Patterns table is the surface-specific spec; `:56-57` is the Voice table's illustration.
4. **The missing-key banner uses the spine sentence only when exactly one role is short a key**, which is the spine's own example. With several broken roles, or with a provider no key can fix, it renders the server's `blocking_reason` — which is already plain language and already correct about which of those two situations applies. Calling an `unsupported-by-runtime` provider a "missing key" is the falsehood `deferred-work.md:85` records a user hitting.
5. **`unsupported-by-runtime` renders as its own state.** ⚠️ **This claim was false when written and is now true.** As first shipped, `check_overall` folded every unusable status into `missing-key`, so the panel carried `data-state="missing-key"` for a groq role and the server called it a credential problem — exactly the falsehood AC 4 forbids, and the captured fixture proved it. The code review caught it. There is now a distinct `unsupported` aggregate, `blocking_reason` describes the two causes separately, and both are covered by tests that were falsified first.
6. **A key check that fails to arrive does not block.** `keyCheck === null` means "not established"; blocking on it would strand the user over a condition nobody verified. UX-DR5 blocks on a *missing key*, which the server has to have said.
7. **`role="status"`, not `role="alert"`, on the banner.** It is standing information about a setup, not an event; the failure alert beside it owns `role="alert"`, and two assertive regions talk over each other. The blocked *reason* is announced with the control via the existing `aria-describedby` wiring.
8. **The spec editor carries the per-row key state**, because the dialog's `z-50` backdrop hides the surface banner — the same reason 2.2 gave the editor its own failures. The note is withheld once a row's provider no longer matches what was checked, rather than showing a stale status for a provider nobody checked.
9. **`OVERRIDDEN_SERVER_COPY` removed**, not widened: the server copy it existed to mask is fixed.
10. **`web/tests/composer/harness.tsx` answers the key routes from its own queue**, and records them in `keyRequests` rather than `requests`. Existing assertions like `requests[1].url` mean "the second *compose* call" and predate these routes; changing what they count would have been a silent redefinition.

#### Scope stopped short, deliberately

- **No server-side enforcement of the key gate.** There is no run endpoint (2.4 owns it) and `POST .../build` does not consult the check. The UI gate is therefore bypassable; recorded in `deferred-work.md` as 2.4's inheritance rather than fixed by widening into 2.0's build route.
- **No Settings surface, no key-status list there** (2.6). `web/tests/shell/routes.test.tsx:85-93` still asserts Settings is key-free and passes **unchanged**.
- **No provider/model picker, no model catalogue, no `--signal` consumer, no key entry anywhere.**
- **`fields[].message` left un-authored**, declared in AC 6 and in `deferred-work.md`.
- **The `xai` catalog row untouched**, despite its `openrouter_slug` being dead data — altering it would change what a *run* resolves, which is not this story's surface. Recorded.

#### Existing tests changed, and why

| Test | Change |
|---|---|
| `tests/api/test_health.py` | five authored routes → seven |
| `tests/api/test_secret_containment.py` | both new routes added to the sweep; `_template()` extended for the 4-segment path (it only normalised 5-segment compose paths, so the new route would have failed the `authored <= visited` assertion — by design) |
| `tests/api/conftest.py` | `write_key_config` / `key_config_path` fixtures added so a test can control which providers have keys; `isolated_key_config` unchanged in behaviour |
| `web/tests/composer/route.test.tsx` | "issues no request on first render" **narrowed** to compose requests, with a positive control so it cannot pass by the API never being called; "fakes none of 2.3's states" **inverted** to "states nothing until the server has said something"; 2.3's copy moved out of both ban lists and asserted positively |
| `web/tests/composer/api-client.test.ts`, `error-paths.test.tsx` | the two `output_exists` override tests re-pointed at the fixed server copy, asserting on the **re-captured fixture** so the point is that the server stopped saying it |
| `web/tests/composer/keyboard.test.tsx` | its inline `fetch` stub given the same key-route separation as the shared harness |
| `web/components/composer/spec-editor.tsx` | two new required props (`keyRoles`, `blockedReason`) |

#### Stale planning artifacts — flagged, not edited

Per the Story 1.4–2.2 precedent:

- `ARCHITECTURE-SPINE.md:171` still pins FastAPI `0.139.x`; `0.141` is installed. Flagged by 2.0 and 2.2, still unactioned.
- `ARCHITECTURE-SPINE.md:225-226`'s CrewAI-pin Deferred entry is stale — flagged by 1.7, 2.1, 2.0, and again here.
- `project-docs/project-context.md:24` says *"`crewai` is NOT a dependency of this repo"* (it is an optional extra, `pyproject.toml:43-45`) and its dependency list omits `jinja2` (`pyproject.toml:17`). Both false.
- `project-docs/component-inventory.md` self-declares as incomplete and predates `api/` and `web/` entirely.
- `project-docs/development-guide.md` predates both and its own `:113-119` says no commands were executed; the authoritative commands are the `Makefile`'s.
- **Story 2.1's light `--primary` at 4.12:1** remains below AA for normal text and is still on `Run it now` / `Build team`. Not changed unilaterally; still escalated.

#### Escalations — not decided here

The four Open Questions above stand. The two that most affect users: the no-keys copy is false for a keyless local setup, and `unsupported-by-runtime` has no designed treatment despite being the state most likely to confuse someone who *did* add the right key.

### File List

**New — `api/`**
- `api/routings.py` — the shared per-role routing resolver
- `api/keystatus.py` — status/aggregate derivations and the fix-hint projection
- `api/routers/keys.py` — the two read-only routes

**Modified — `api/`**
- `api/main.py` — registers `keys_router`; records `file_providers` at boot
- `api/state.py` — `AppState.file_providers`
- `api/deps.py` — `safe_label` promoted from `_safe_label`; `providers_needing_restart`
- `api/routings.py` — template import moved back inside the failure guard
- `api/schemas.py` — `ProviderKeyView`, `RoleKeyView`, `KeyStatusView`, `KeyCheckView`
- `api/build.py` — re-expressed on `api/routings.py`; `output_exists` copy fixed

**Modified — `team_maker/`**
- `team_maker/runtime/preflight.py` — `_describe` → public `describe_unresolved_provider`

**New — Python tests**
- `tests/api/test_key_status.py` — the provider-level read
- `tests/api/test_key_check.py` — the per-team check (split out at review)
- `tests/api/keyroutes.py` — shared readers for the two suites above (not collected)
- `tests/api/test_routings.py`
- `tests/unit/runtime/test_provider_hints.py`

**Modified — Python tests**
- `tests/api/conftest.py`, `tests/api/test_health.py`, `tests/api/test_secret_containment.py`

**New — `web/`**
- `web/components/composer/key-check.tsx`

**Modified — `web/`**
- `web/lib/api-types.ts` — key view types and parsers
- `web/lib/api-client.ts` — `getKeyStatus`, `getKeyCheck`, `KEY_CHECK_TIMEOUT_MS`; override removed; fallback copy pass
- `web/components/composer/composer-surface.tsx` — the two reads, the split gates, `KeyCheck`
- `web/components/composer/composer-state.ts` — `keyStatus`, `keyCheck`, `keyCheckEpoch` and their actions
- `web/components/composer/spec-editor.tsx` — per-row key note, `blockedReason` prop

**New — web tests and fixtures**
- `web/tests/composer/key-check.test.tsx`, `key-check-client.test.ts`, `key-check-blocking.test.tsx`
- `web/tests/composer/fixtures/key-status-has-keys.json`, `key-status-no-keys.json`, `key-check-all-good.json`, `key-check-missing-key.json`

**Modified — web tests**
- `web/tests/composer/harness.tsx`, `route.test.tsx`, `keyboard.test.tsx`, `api-client.test.ts`, `error-paths.test.tsx`, `fixtures/index.ts`, `fixtures/error-output-exists.json` (re-captured)

**Modified — docs**
- `project-docs/stories/deferred-work.md`
- `project-docs/stories/2-3-key-check-states-plain-language-errors.md`

### Post-Review Notes (2026-08-04)

All 4 decisions answered by Guru; all 20 patches applied. What the review actually cost is worth stating plainly: **two of its findings were production defects that my tests passed over**, and one of my declared deviations was simply false.

#### The four decisions, and what each changed

1. **AC 4 verbatim — ship `(Settings)`.** The missing-key sentence is now `EXPERIENCE.md:86` character-for-character, parenthetical included. The Key Config path is still shown, on its own line, so nothing actionable was lost. Better Settings key guidance is now tracked for Story 2.6 in `deferred-work.md`. My substitution had been an undeclared deviation: AC 9 authorised it for `:87` (the no-keys banner) only.
2. **Credential priority stays file → environment, with the source reported.** This was the most productive answer: it fixed the removal bug *honestly* rather than by hiding a credential that genuinely works. Every provider row now carries `credential_source` ∈ {`key-config`, `environment`, `startup-leftover`, `none`}, and `detail` is source-aware — so a key deleted from the file no longer claims "key found in Key Config" but says the process is holding a startup leftover that a restart will lose. Distinguishing "only ever in the environment" from "deleted from the file" needs `AppState.file_providers` (a file-only load at boot); `bridged_providers` cannot do it, because the bridge publishes whatever `KeyConfig` loaded, env fallback included. I got that wrong first and a test caught it.
3. **"Rejected/missing" and "check failed" are now different states, and neither ungates.** `keyCheckState` ∈ {`idle`, `checking`, `failed`, `ready`}. `checking` and `failed` both block, each with its own copy. Previously all three of "never asked", "in flight" and "read failed" collapsed to `keyCheck === null` and every one of them *permitted* a build — so the gate was open for a round-trip after every turn and open forever if `/api/keys/*` started failing. A 404 on the check now also sets `expired`, which every other failure path already honoured.
4. **The planner path is gated.** `GET /api/keys/check/{id}` now reports a synthetic `(the planner)` role resolved from `request.planning_llm`, marked `required: true`. It was the one build that genuinely cannot start without a credential (`runner.py:66-69` → `TeamPlanner` → `create_provider(planning_llm)`) and the only one with no gate. A required role blocks and its copy does not suggest switching away from it, because there is nothing to switch to.

#### Corrections to my earlier Completion Notes

- **Deviation 5 was false.** I wrote that `unsupported-by-runtime` "renders as its own state". It did not: `check_overall` folded every unusable status into `missing-key`, and my own captured fixture proved it. Now corrected in place, with a distinct `unsupported` aggregate and a `blocking_reason` that describes the two causes separately — including subject/verb agreement, which my own new test caught me getting wrong (`'xai' has not supported by…`).
- **The frontend test count was wrong.** I stated 40 for the three key suites; measured, it was **43**, and is now **51**. Exactly the class of unmeasured figure I claimed to have avoided.
- **`.get_secret_value()` in `api/` is now two call sites, not one.** Both are in `api/deps.py` (`bridge_credentials` and `providers_needing_restart`), which remains the only module in `api/` that unwraps a secret. Detecting a *changed* key requires comparing values, and `bridge_credentials` already did exactly that comparison — but the invariant as I stated it no longer holds, so here it is restated correctly.
- **File sizes, stated rather than selectively omitted.** Over CLAUDE.md's ~200–400 guideline: `api-types.ts` **560**, `spec-editor.tsx` **517**, `api-client.ts` **454**, `composer-surface.tsx` **428**. `api/keystatus.py` is **398**. `tests/api/test_key_status.py` reached **728** and was **split** into `test_key_status.py` (**349**, what the machine has) plus `test_key_check.py` (**376**, whether one team can run) with shared readers in `tests/api/keyroutes.py` — the reorganisation CLAUDE.md asks for as part of the story. The four `web/` files remain over and are recorded in `deferred-work.md` rather than split here.
- **Two undeclared deviations, now declared.** AC 3 said the honesty must live in `detail`/`fix_hint`; it lives in `needs_restart_to_author` plus source-aware `detail`. And `"unrecognized"` is a sixth status value that is not a `registry.STATUS_*` constant — it describes the *spec*, not a catalog row.
- **The re-captured `error-output-exists.json` was attributed to the 2.2 capture session.** `fixtures/index.ts` now records its real date and reason. All four `key-*` fixtures were re-captured after the contract changed, against `C:\tm-capture\` rather than a home directory, so no developer username is committed.

#### Guards proven able to fail — again, and this time including one that could not

Each falsification was applied, the named test watched go red, then reverted:

| Falsification | Test that went red |
|---|---|
| gate returns `null` on `keyCheckState === "failed"` | `blocks when the check could not be read` + `does not build when the check failed` |
| `credential_source` discriminates on `bridged` instead of `file_providers` | `test_a_key_deleted_from_the_file_stops_claiming_the_file_supplies_it` |
| `check_overall` folds `unsupported` back into `missing-key` | `test_an_unsupported_required_provider_is_not_aggregated_as_missing_key` |
| planner path returns no routings | both `test_the_planner_path_*` tests |
| `restarting` reverted to `status?.… ?? check.…` | *nothing* — see below |

**The last row is the point.** Reverting the `??` bug did **not** fail the suite, because the existing restart test injected the flag through `status` — the branch that worked. I added `prefers the check's list, which is the only one read per request`, re-applied the falsification, and confirmed it goes red. That is the second time in this story the same mistake surfaced, and it is the reason a falsification pass is not optional.

A separate near-miss worth recording: my first attempt at these falsifications used `perl` with `\n` patterns against CRLF files, so the substitution silently did not apply and the suite "passed". A falsification that fails to apply is indistinguishable from a guard that cannot fail. Every one above was re-done with a verified edit.

#### Final measurements

| | Pre-review | Post-review |
|---|---|---|
| Python | 560 passed, 7 skipped | **572 passed, 7 skipped** |
| Web | 22 files, 382 tests | **22 files, 390 tests** |
| The three key suites | 43 | **51** |
| `ruff check api/` · `team_maker/` · `tests/` | 0 · 9 · 29 | **0 · 9 · 29** |

`npm run lint`, `npx tsc --noEmit` and `npm run build` are clean. `tsc` again caught two prop errors vitest tolerated.

#### Still open after this pass

- The key gate remains **UI-only**. `POST .../build` still does not consult the check, so a non-browser client can build a team it cannot run. Recorded as Story 2.4's inheritance.
- **Continuing with a subset of a partly-credentialed team is not implemented.** Your instruction was that any member removal or provider reassignment must be explicit and confirmed. Reassignment is: the review editor changes a role's provider and Save re-validates. *Removal* is not — the editor cannot remove a role at all (`deferred-work.md`, from 2.2's review), so there is no silent-drop path to guard, and no subset-run affordance either. Building one is new authoring surface and needs your call; it is recorded in `deferred-work.md` rather than invented here.

## Change Log

| Date | Change |
|---|---|
| 2026-08-04 | Story created from `epics.md:361-374`, baseline `2e89846`. Status `ready-for-dev`. |
| 2026-08-04 | Implemented all 8 tasks. Added the `api/` key-status group (two read-only routes), the shared per-role routing resolver, the promoted fix-hint generator, and the Composer's four key-check states with a build gate on all four entry points. Fixed `output_exists` server copy and removed the client override it existed to mask. Python 525 → **560 passed, 7 skipped**; web 339 → **382 tests, 22 files**. Status `review`. |
| 2026-08-04 | Adversarial code review (3 independent layers): 4 decisions, 20 patches, 2 deferred, 3 refuted. Two production defects found that the tests passed over — a removed key still reporting `available`, and the build gate open whenever no check had answered. All decisions answered and all patches applied: credential-source reporting, `checking`/`failed` gate states, planner-path gating on `planning_llm`, a distinct `unsupported` aggregate, AC 4 copy shipped verbatim, and five vacuous tests replaced. Corrected two false claims in my own Completion Notes. All four key fixtures re-captured. `test_key_status.py` split at 728 lines. Python **572 passed, 7 skipped**; web **390 tests, 22 files**. Status `done`. |
