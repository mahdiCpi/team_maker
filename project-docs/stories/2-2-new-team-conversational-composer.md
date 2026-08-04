---
baseline_commit: 725b475
---

# Story 2.2: New Team — conversational Composer with optional review

Status: blocked-on-2.0

## Story

As a user,
I want to describe and tune a team in the UI (or run it now),
so that composing feels like a conversation, not a form.

## Dependency

**This story requires Story 2.0 (the API seam) to have landed.** It builds the Composer UI only — every call to the Python core goes through the endpoints Story 2.0 creates, because AD-4 admits no other path. Story 2.0 is authoritative for the contract; the summary in Dev Notes is a convenience copy, and if the two disagree, 2.0 wins.

Set `Status: ready-for-dev` once 2.0 is merged, and re-read 2.0's Completion Notes first — it may have declared deviations from the contract as written (for example, `model_substitutions` returning an empty list if capturing substitutions cleanly required touching `team_maker/`).

### Hard constraint added by Story 2.0's code review (2026-08-03)

**`output_path` is server-owned and read-only to the browser. This story displays it and nothing more.**

Story 2.0 originally documented the field as "server-owned" while only its *edit body* refused it: the value was authored by the LLM from free-text intent, so a message like *"put the output in /tmp/x"* re-authored it and steered where the build wrote. The review closed that — the server now derives the path as `TEAM_MAKER_OUTPUT_ROOT / <slugified team_name>`, pins it for the session's lifetime, and re-applies it after every turn (`api/output.py`, Story 2.0 **AC 13**).

For this story that means:

- **Display only.** No input, no picker, no "change location" affordance, no editable default. It is an absolute path on the server's filesystem, not the user's.
- **Do not send it.** `PUT /api/compose/sessions/{id}/spec` rejects it with `extra="forbid"`; including it is a 422, not a no-op.
- **Do not let the conversation move it.** If a user asks the Composer to change the output location, the correct response is UI copy explaining that the destination is chosen by the server — not a refinement turn. The server will ignore it regardless, so a turn spent on it is spend with no effect.
- **A user-selectable destination is explicitly a later story** — Settings (2.6) or desktop packaging, where the trust boundary differs. Do not anticipate it here with a disabled control or a placeholder.

## Acceptance Criteria

1. **Given** `EXPERIENCE.md:25` — *"The Composer is a **conversation**, not a one-shot form"* — and `EXPERIENCE.md:70` (*"Multi-turn. User describes; app proposes a team and asks targeted follow-ups"*), **When** the user opens `/` (already the landing route from Story 2.1), **Then** the page is a chat: an initial state headed **`Describe your team.`** (`EXPERIENCE.md:54,181`; `DESIGN.md:90`) with the placeholder `e.g. a team that researches a topic, drafts an article, and critiques it…` (`mockups/color-themes-1.html:87`); submitting calls `POST /api/compose/sessions`; each turn appends a user message and an assistant message; and the assistant's proposal names the roles in pipeline order and asks **one** targeted follow-up, not a checklist (`EXPERIENCE.md:184`; Story 1.3 Dev Notes `:99`). The mockup's single-textarea "Build team" screen is the **first turn of that chat**, not a competing design — `EXPERIENCE.md:14` ("Spines win on conflict with any mock") settles it. (FR-1, FR-20, UX-DR4)

2. **Given** `EXPERIENCE.md:84` — *"shadcn `Skeleton`/typing indicator while the app drafts the spec; **user can keep typing**"* — **When** a turn is in flight, **Then** a neutral-token thinking indicator renders, **the input is not disabled**, and the pending state survives a multi-second call. A turn is 1–4 blocking LLM calls with no streaming and no progress callback, so this is an opaque spinner — **do not fake progress percentages or a token stream.** The indicator must not use `--signal`/`bg-signal` (AC 7). (`EXPERIENCE.md:84`)

3. **Given** UX-DR4 requires *"a persistent 'run now' affordance"* (`epics.md:97`) and `EXPERIENCE.md:97` says *"A 'Run it now' affordance is **always present** so users can skip tuning"*, **When** the Composer renders, **Then** a control labelled **`Run it now`** (spine wording — `EXPERIENCE.md:70,97,167`) is present from the first proposal onward, does not scroll away with the transcript, and **builds immediately, bypassing the review toggle**. It **builds; it does not start a run** — a run needs a goal, and the goal is entered in the Workspace (`EXPERIENCE.md:188`). If it is unavailable, it says why in text — `EXPERIENCE.md:104` bans *"hiding a blocked run behind a silent failure (always say why)"* — rather than rendering as a silent dead control, which was a Story 2.1 review finding. (UX-DR4, FR-20)

4. **Given** `EXPERIENCE.md:33` names the entry point *"'Review before build' on New Team"* and FR-3 makes **auto-build the default** (`epics.md:27`), **When** the user enables **`Review before build`** (off by default) and a spec exists, **Then** an editable spec view exposes exactly the three dimensions the spine names — **roles, tasks, and per-agent Provider/model** (`EXPERIENCE.md:33,73`) — and **`Save re-validates`** via `PUT /api/compose/sessions/{id}/spec`; an invalid edit **blocks the build with inline reasons** rendered from the response's `fields[]`, and does not replace the good spec.

   With review **off**, committing builds **without a spec-review step** — "no confirmation" (`epics.md:321`) means no interstitial review/approve screen, **not** the absence of a commit control. The commit control is the verbatim **`Build team`** button (`EXPERIENCE.md:185`; `color-themes-1.html:88`), present from the first proposal. **Auto-build must not fire on its own after a turn**: `epics.md:321` governs what happens *at build time*, not when a build is triggered, and firing it automatically would end the conversation after turn 1 and contradict AC 1. A test must prove a second turn is possible after the first valid spec with review off.

   Modal depth is capped at one (`EXPERIENCE.md:38-39,103` — no dialog-over-dialog), so if the editor is a `Dialog`/`Sheet`, any picker inside it is a `Popover`. The per-agent Provider/model control is a **free-text `model` field plus a `provider` select constrained to the ids the schema accepts** — there is **no model catalogue**. The only live model list comes from `normalize_team_routings`' per-provider network calls at build time, and Story 2.0's AC 2 forbids an extra endpoint. Do **not** hard-code a model list in the frontend; that is fabricated data of the same class Story 2.1 rejected with the mockup's key footer. Because the spec is re-serialised server-side (`_pre_process` rewrites input five ways), **the editor must re-render from the response, never from local state.** (FR-3, AD-10, `EXPERIENCE.md:33,73`)

5. **Given** neither Team Workspace (Story 2.4) nor the My Teams list (Story 2.5) exists yet, **When** a build succeeds, **Then** the Composer surface itself reports the outcome from the build response — team name, output path, counts, validation pass/fail, and any `model_substitutions` — and **must not** navigate to a surface that cannot show it. Surfacing substitutions matters: without it the UI claims it built `gpt-4o` when it built `gpt-4o-mini`. `EXPERIENCE.md:186` ("The team lands in **My Teams**; she's dropped into its **workspace**") describes the end state after 2.4/2.5 land; record in Completion Notes that this story deliberately stops short of it rather than faking the destination. (AC 9; `EXPERIENCE.md:186`)

6. **Given** `EXPERIENCE.md:98` reserves the keys, **When** the Composer is focused, **Then** `Enter` sends, `Shift+Enter` inserts a newline, `⌘/Ctrl+Enter` triggers **Run it now**, and `Esc` exits the review editor. **The input must be a real `<textarea>`/`<input>`**, or a `contenteditable` whose attribute value is exactly `""`, `"true"` or `"plaintext-only"` — `web/components/nav-shortcuts.tsx:23-31` guards only those, so any other editor host means typing "**g**rand total" navigates the user away mid-sentence. Do not rebind `⌘/Ctrl+B` (shadcn's sidebar toggle). Must not fight IME composition. (`EXPERIENCE.md:98`; `nav-shortcuts.tsx:11,23-31,66`)

7. **Given** Story 2.1 shipped `--signal` with an intentionally **empty** consumer whitelist — `web/tests/theme/signal-token.test.ts:141` fails if *any* file under `app/`, `components/` (minus `ui/`), `lib/` or `hooks/` mentions `--signal` or `bg-signal` — and given Story 2.4's live-status component is the designated first consumer, **When** this story lands, **Then** it references `--signal` **zero times** and every colour comes from an existing semantic token, so Guard A and Guard B both stay green **unmodified**. `EXPERIENCE.md:185` confirms the passing key check is *"accent-free, neutral badges"*. (Story 2.1 AC 6/7; UX-DR2)

8. **Given** the API returns the seven error codes Story 2.0's AC 2 defines, **When** any of them arrives, **Then** the UI renders a plain-language message and keeps the conversation usable: a failed turn leaves the transcript and the last good spec intact and allows a retry; `session_not_found` (which a backend `--reload` causes on every Python edit) renders as a recoverable "start a new conversation" state, **not a white screen**; `turn_cap_reached` states the cap plainly; and `authoring_unavailable` explains that composing needs a key without ever offering to take one — `EXPERIENCE.md:103` bans key entry in the UI outright. **No `error.message` is rendered as raw JSON and no stack trace is displayed** — 2.0 guarantees none is sent, and this story must not reintroduce one by dumping a caught exception. Error *copy* refinement is Story 2.3's; usable *behaviour* is this story's. (FR-15, `EXPERIENCE.md:104`)

9. **Given** this story's scope, **When** implementing it, **Then** these are explicitly **out of scope**: per-provider key status, key-check states, and the four `EXPERIENCE.md:85-88` banners (Story 2.3 — the seam must be left, the states must **not** be faked, exactly as Story 2.1 refused the mockup's `Keys: anthropic ✓ …` footer); Team Workspace, task list, run execution, documents, transcripts (2.4); save/rename/delete and the recent-teams list (2.5); Settings beyond what already ships (2.6); the WCAG 2.2 AA audit and `aria-live` **run-progress** announcements (2.7); starter-team content and "Adapt with Composer" (Epic 3); **any new or changed API endpoint** — that is 2.0's surface, so if you need one, stop and escalate; streaming; any desktop wrapper. Also out of scope: **entering an API key anywhere in the UI**. (AD-1, AD-4, AD-13)

10. **Given** no frontend test lane covers this surface, **When** this story lands, **Then** tests live in **`web/tests/composer/`** (not bolted onto `tests/shell/`); `npm test`, `npm run build` and `npm run lint` are green; the **393 Python tests (7 skipped) are untouched**; and **`web/tests/shell/routes.test.tsx` is migrated** — it currently asserts `/` renders an `EmptyState` with `empty-title === "New Team"`, a **single** `getByRole("link")` to `/starter-teams`, and **no `[disabled]` element on any of the first three routes**, none of which survive this story. State before/after test counts and paste the real command tails rather than asserting a number. Per CLAUDE.md, reorganise the crowded area as part of the story. (CLAUDE.md test organization + transparency)

## Tasks / Subtasks

- [ ] **Task 1 — Install the shadcn components this story needs** (AC: 1, 2, 4)
  - [ ] From inside `web/`: `npm exec -- shadcn add textarea card scroll-area badge dialog popover switch` — use the **locally pinned `shadcn@4.16.1`** from `package.json`, not `npx shadcn@latest`. `deferred-work.md:117` records that 4.16.1's Base UI output is what the existing components were generated from; a different CLI version mixes primitive generations inside a directory that lint, coverage, Guard A and Guard B all ignore, so nothing would catch it. **None of these are installed** — the current set is exactly `button, dropdown-menu, empty, input, separator, sheet, sidebar, skeleton, tooltip`.
  - [ ] **Read the generated files before writing any component against them.** This install is **Base UI**, not Radix: `render={<X />}` not `asChild`, no `forwardRef`, `Root/Trigger/Portal/Positioner/Popup`, `Backdrop` not `Overlay`, `data-open`/`data-closed` not `data-state`. Story 2.1's single largest deviation came from assuming otherwise.
  - [ ] If the CLI drops anything outside `components/ui/` (a new `hooks/*` or `lib/*`), add it to **all three** exclusion lists or Guard A will flag upstream code: `eslint.config.mjs`, `vitest.config.mts`, and `tests/theme/color-scan.ts:103-110`.

- [ ] **Task 2 — The API client** (AC: 1, 4, 5, 8)
  - [ ] `web/lib/api-client.ts` — the **single** place that talks to `/api`. One function per Story 2.0 route, plus a shared error-envelope parser producing a discriminated result the UI branches on by `code`.
  - [ ] Type it with a **narrow view type** covering only the fields the UI renders — `{ session_id, turn, turns_remaining, spec: { team_name, purpose, desired_roles: {name, description, llm?}[], desired_tasks: {name, description, agent_role, dependencies}[] } }` — and read everything else as `unknown`, narrowing at the boundary. **Do not mirror `TeamCreationRequest`**; a second source of truth that then gets tested against is the Story 2.1 defect class (rule 3 below). Pin the shape with a fixture **captured from a real API response**, committed under `web/tests/composer/fixtures/` with a header comment giving the date and the command that produced it.
  - [ ] Long timeouts: a compose turn is 1–4 blocking LLM calls behind one request. Use an explicit `AbortSignal` with a generous ceiling and make sure the pending UI survives it.

- [ ] **Task 3 — The Composer chat surface** (AC: 1, 2, 6, 7)
  - [ ] Replace `web/app/page.tsx`'s `EmptyState` with the Composer. **Keep `metadata` exported from `page.tsx`** (it is a server component today) and push interactivity into a `"use client"` child, or the metadata assertions break.
  - [ ] New files under `web/components/composer/` (per CLAUDE.md's structure rule — do not keep flattening `web/components/`): the transcript list, a message bubble, the input, the thinking indicator.
  - [ ] Message anatomy from `mockups/team-workspace.html:49-58` — role label above the bubble in `muted-foreground`, `card` background, `1px border`, `--radius`; the user turn differentiated by `muted` background only. **Both roles left-aligned, full width. No right-aligned bubbles, no avatars.** Role labels follow the mock's convention: `You` / `team_maker`.
  - [ ] The page renders inside the existing `<main class="flex flex-1 flex-col px-4 pb-4">`; the header is `h-12`. Size the scroll region against `flex-1`, **not `100vh`**. Do not add a second `TooltipProvider` or page chrome.
  - [ ] Reuse `EmptyState` for the pre-conversation state; reuse `useMediaQuery` for any responsive logic (never `useState`+`useEffect` — the lint config rejects `react-hooks/set-state-in-effect`).
  - [ ] Add an `aria-live="polite"` region for incoming assistant turns. No source specifies one, and a chat that appends asynchronously needs it; the spines' only live-region mandate is run progress, which is 2.4/2.7. Declare this as an addition.

- [ ] **Task 4 — Run it now, review toggle, and the editable spec view** (AC: 3, 4, 5)
  - [ ] The persistent `Run it now` control (bypasses review) and the `Build team` commit control (honours review), plus the `Review before build` toggle, default off.
  - [ ] Editable spec view: roles, tasks, per-agent Provider/model only. Save → `PUT .../spec` → **re-render from the response** → inline reasons from `fields[]` on failure, with the previous good spec preserved.
  - [ ] Reject an empty roles list in the editor before submitting — an empty `desired_roles` flips the build into a second LLM call through a different provider config, silently.
  - [ ] `Esc` exits the editor. If it is a `Dialog`/`Sheet`, any picker inside is a `Popover` (one modal level, `EXPERIENCE.md:38-39`).
  - [ ] Build result panel per AC 5 — name, output path, counts, validation, substitutions. No navigation to 2.4/2.5 surfaces.
  - [ ] **Do not render a `disabled` control as the answer to "not ready yet."** Story 2.1's review found exactly that, and `routes.test.tsx:73-78` currently asserts no `[disabled]` exists on this route. Prefer `aria-disabled` plus a stated reason, and update that assertion deliberately if you change it.

- [ ] **Task 5 — Tests** (AC: 6, 7, 8, 10)
  - [ ] `web/tests/composer/` — first turn renders, multi-turn appends, a second turn is still possible after the first valid spec with review off (AC 4), thinking state, input stays enabled during a turn, `Enter` sends / `Shift+Enter` newline, `⌘/Ctrl+Enter` runs, `Esc` exits the editor, the build result panel renders every field including substitutions, and **each of the eight error paths renders a usable state** (AC 8).
  - [ ] The chord test must render `<NavShortcuts />` **alongside** the Composer — it lives in `app/layout.tsx:70`, not in the page — and must mock `next/navigation`'s `useRouter` (`nav-shortcuts.tsx:38`); copy the mock from `web/tests/nav/shortcuts.test.tsx`. Assert `router.push` is called **zero** times after typing `g`,`n` into the focused textarea **and** exactly once for the same keys with focus on `document.body`, so the test cannot pass by the mock simply never firing.
  - [ ] Migrate the `/`-route assertions out of `web/tests/shell/routes.test.tsx` into `web/tests/composer/`; leave the other three routes' assertions in place. Note `routes.test.tsx` does **not** mock `next/navigation` — if the new `/` calls `useRouter`/`usePathname`, that suite fails.
  - [ ] **Delete, do not migrate, `routes.test.tsx`'s `route copy > does not reuse My Teams' empty-state sentence on New Team`.** With no `empty-description` on `/`, it degrades to `expect(undefined).not.toBe(...)` — a silent vacuous pass rather than a failure, which is the defect class this story is trying not to repeat.
  - [ ] `@testing-library/user-event` is installed but **unused by any existing test** — this story is its first real consumer. Prefer it over raw `fireEvent` for typing.
  - [ ] Label every stub in Completion Notes. **A mocked `fetch` is not evidence the API works** — CLAUDE.md forbids reporting it as such. State which tests are unit, which are mocked-integration, and whether any real end-to-end run against a live `api/` was performed.
  - [ ] Confirm Guard A and Guard B pass **unmodified**. If you must touch `color-scan.ts`'s `SCAN_ROOTS`, note that a new top-level `web/` directory (e.g. `web/services/`) would be silently unguarded — the identical defect the 2.1 review found with `lib/`.

- [ ] **Task 6 — Documentation and flags, not silent edits** (AC: 5, 9)
  - [ ] Record in Completion Notes, **do not edit the planning artifacts** (Story 1.4–2.1 precedent):
    - This story deliberately stops short of `EXPERIENCE.md:186`'s "lands in My Teams / dropped into its workspace" because neither surface exists until 2.4/2.5.
    - `EXPERIENCE.md:98` specifies `Enter` sends but says nothing about `Shift+Enter` for a newline, nor any touch-keyboard behaviour below `md` (`:161`). Both are additions this story makes.
    - No source specifies an `aria-live` region for incoming chat messages, autoscroll/scroll-anchoring behaviour, message timestamps, markdown rendering inside a bubble, or a transcript length cap. State which you implemented and which you left out.
    - Story 2.1's Open Question 1 — light `--primary` at **4.12:1**, below AA's 4.5:1 for normal text — becomes **user-visible for the first time here**, on the primary `Run it now` / `Build team` labels. Do not change the token unilaterally; escalate.
    - `web/app/page.tsx:15,17` currently ships invented copy that appears in no spine; this story replaces that page wholesale.
  - [ ] Add to `deferred-work.md`: whatever this story leaves open, and any contract friction found against Story 2.0's endpoints.

## Dev Notes

### The API contract you are consuming

**Story 2.0 is authoritative.** Summary for convenience:

| Route | Body | Success |
|---|---|---|
| `POST /api/compose/sessions` | `{ intent, authoring? }` | **201** `{ session_id, spec, turn, turns_remaining }` |
| `POST /api/compose/sessions/{id}/messages` | `{ message }` | **200** same shape, `turn` incremented |
| `PUT /api/compose/sessions/{id}/spec` | `team_name`, `purpose`, `desired_roles[]`, `desired_tasks[]` **only** | **200** same shape |
| `POST /api/compose/sessions/{id}/build` | — | **200** `{ team_name, output_path, agent_count, task_count, written_file_count, model_substitutions, validation }` |
| `GET /api/health` | — | **200** |

Errors are always `{ "error": { code, message, fields? } }` with `code` one of `session_not_found` (404), `turn_cap_reached` (409), `spec_invalid` (422), `authoring_unavailable` (503), `compose_failed` (502), `output_exists` (409), `build_failed` (500). `fields[]` appears only for `spec_invalid` and carries dotted paths like `desired_roles.0.name` — that is what AC 4's inline reasons render.

**There is no `validation` field on the compose responses**, by design: a returned spec is schema-valid by construction. Validation results exist only after a build.

**The authoring provider is parametric** (Story 2.0 AC 10). `authoring` is an **optional** `{ provider?, model? }` on session-create; omitting it uses the server default (`anthropic`/`claude-sonnet-4-6`). Selectable ids are whatever `create_provider` resolves — `anthropic`, `openai`, `xai`, `google`, `ollama`, and `openrouter`. **Never send a key**: AD-9 means the request may name a provider and the server resolves the credential from the Key Config; a body carrying a key value is rejected.

Story 2.2 is **not** required to build a provider picker — omitting `authoring` is a valid call and the default path is the one the ACs describe. If you do expose a choice, it is a provider/model selection only, never a key field (`EXPERIENCE.md:103` bans key entry outright), and `authoring_unavailable` (503) already names the provider and the Key Config entry that would fix it, so render that message rather than composing your own.

**Things the API cannot do for you:**

- **No chat history server-side.** `ComposerSession` keeps only the original intent and the current spec; intermediate turns are discarded. **The UI owns the transcript.** There is no replay endpoint, and the model does not remember turn 2 when it reaches turn 4.
- **No streaming, no progress.** A turn is 1–4 blocking LLM calls behind one HTTP request. Spinner, not stream.
- **No undo.** `ComposerSession` has no rollback (`deferred-work.md:56`); "revert that" is just another refinement turn.
- **Sessions are in-process and single-worker.** A backend `--reload` drops every session, so `session_not_found` is a *routine* dev-time event, not an exceptional one. AC 8 exists because of this.
- **`output_path` is an absolute server-side path, and it is read-only to you.** Render it as informational text, never a link, never an input, never an input default. See the hard constraint in the Dependency section — this is Story 2.0's AC 13, not a styling preference.

### The frontend you are building into — read this before writing a component

Story 2.1 shipped 49 files, 147 tests, all green. The single highest-value fact:

**This shadcn install is Base UI (`@base-ui/react ^1.6.0`, style `base-nova`), not Radix.** No `forwardRef` anywhere. Composition is `render={<Link href="…" />}`, **not** `asChild`. Popups are `Root → Trigger → Portal → Positioner → Popup`; it is `Backdrop` not `Overlay`, `Popup` not `Content`, `data-open`/`data-closed` not `data-state="open"`. Every part carries `data-slot="…"` — that is what tests query. Story 2.1's largest declared deviation came from assuming otherwise; `deferred-work.md:117` ends with the instruction to read the installed files first.

**Installed:** `button, dropdown-menu, empty, input, separator, sheet, sidebar, skeleton, tooltip`.
**Not installed, and this story needs them:** `textarea, card, scroll-area, badge, dialog, popover, switch`.

Reuse, do not reinvent: `EmptyState` (`components/empty-state.tsx`), `useMediaQuery` (`lib/use-media-query.ts`, uses `useSyncExternalStore` — the lint config rejects `useState`+`useEffect` here), `read-tokens.ts` for any token assertion, `setViewportWidth` from `vitest.setup.ts` for viewport tests, the per-route `metadata` pattern, and `ThemeToggle`'s hydration-placeholder pattern (a stable disabled placeholder, never a mount-guard effect). `components/app-shell-provider.tsx` is the client component owning `SidebarProvider` and the `(min-width: 1024px)` query — the Composer renders inside it; do not add a competing provider.

**Guard A will reject**, anywhere under `app/`, `components/` (minus `ui/`), `lib/`, `hooks/`: any hex; `rgb()/hsl()/hwb()/lab()/lch()/oklab()/oklch()/color()/color-mix()`; `bg-teal-500`-shaped palette classes; **`bg-white`/`text-black`/`border-white`**; arbitrary colour values like `bg-[#fff]`/`text-[red]`; CSS named colours in a JS object (`{ color: "red" }`); and `fill="black"` on an SVG. **Guard B will reject any mention of `--signal`/`bg-signal`** — the whitelist is empty and Story 2.4 owns the first use.

The `!` trap: `cn()` is clsx + tailwind-merge, and tailwind-merge does **not** recognise `text-display` as a font-size or `font-display` as a weight. Overriding a vendored component's own utility in an ambiguous group needs Tailwind v4's **trailing** `!` (`text-display!`, not `!text-display`) — see `empty-state.tsx:23`. Verify computed styles; don't assume the merge worked.

### Previous story intelligence — the defect classes this codebase actually produces

Story 2.1's review returned **27 patches, 4 decisions, 1 deferral** on a story whose own Dev Notes had warned about the exact defects it then shipped. Its commit body says it plainly: *"Writing the warning down was not enough to avoid it."* Treat the following as things that will happen to you, not things to nod at.

1. **The guard that cannot fail.** 2.1's Guard B protected its self-declared highest-risk decision and caught nothing — the most obvious violation left all 19 theme tests green. **Feed every new guard a fixture where the property is violated and watch it go red before trusting a green run.** Analogue here: a test asserting "no stack trace is displayed" must be proven against a response that contains one.
2. **Tests true by construction.** Deleting a `setTimeout` left 8/8 green; asserting a string was *absent* passed on a component returning `null`. **Assert counts, not absences**; assert a collection is non-empty before looping. Analogue: `expect(queryByText(/error/i)).toBeNull()` passes on a crashed render.
3. **Measuring a mirror.** The contrast test read a hand-maintained copy of the tokens, not the shipped CSS, and its docstring falsely claimed a guard kept them synced. **Do not keep a TypeScript copy of `TeamCreationRequest`'s shape and test against the copy** — capture a fixture from the real API and say loudly that it is a captured fixture.
4. **A guard narrower than its claim.** The colour scanner walked only `app/` and `components/`, so `lib/` — where the literals were — went unguarded. Analogue: if you add `web/services/` or `web/lib/api/`, check `color-scan.ts:100`'s `SCAN_ROOTS` reaches it.
5. **A comment is a testable assertion.** An inline comment claimed a selector was exhaustive; it wasn't, and it missed exactly the `plaintext-only` case AC 6 cares about. Don't write "all errors surface to the user" unless a test proves it.
6. **Declared deviations get audited.** 2.1's deviation 2 was withdrawn in review as wrong, and the withdrawn reasoning is retained verbatim in the record. Declare everything; expect the reason to be checked.
7. **Self-reported figures must be measured.** A "correction" to a ruff count confused two scopes and impugned an accurate note. Paste real command tails.
8. **Undeclared stubs change what is tested.** An always-`false` `matchMedia` stub silently pinned every test to the desktop branch — which is *how* a missing AC escaped notice. Name every stub in Completion Notes, and remember that a mocked `fetch` proves nothing about the API.
9. **Dead affordances.** A permanently disabled button as the "single primary action"; a `title` unreachable by keyboard. `EXPERIENCE.md:97` requires "Run it now" to be *always present*, and `:104` bans silent blocking — say why.

### Conflicts between the sources, and how they resolve

`EXPERIENCE.md:14` is the tie-breaker: *"Spines win on conflict with any mock or import."*

| Question | Sources disagree | Resolution |
|---|---|---|
| Chat or one-shot form? | `color-themes-1.html:86-88` renders a single textarea + "Build team"; `EXPERIENCE.md:25,70,96` says conversation | **Chat.** The mock is the first/empty turn of it, drawn before the conversational decision was applied. |
| Affordance label | `EXPERIENCE.md:70,97,167` "Run it now"; `epics.md:97,319` "run now" | Spine → **`Run it now`** |
| What does it *do*? | "skips further tuning" / "escape" / "build immediately"; Flow 1 builds then runs later in the Workspace | **Builds immediately, no review.** A run needs a goal, and the goal is entered in the Workspace (`EXPERIENCE.md:188`). |
| `Build team` vs `Run it now` — one control or two? | `EXPERIENCE.md:185` has her click `Build team`; `:97` requires `Run it now` always present | **Two, with different meanings.** `Build team` commits the current spec **honouring** the review toggle. `Run it now` **bypasses** the toggle and builds immediately even when review is on — that is what "skips further tuning" (`:70`) means. With review off they converge; that is expected, not a duplicate control. |
| Where does a successful build land? | `EXPERIENCE.md:186` says My Teams + Workspace | Neither exists until 2.4/2.5 → **report inline on the Composer** (AC 5); do not fake the destination. |
| Starter-team card on New Team | `color-themes-1.html:89` renders one | **Omit** — Epic 3. At most the `Browse starters` secondary action. |
| "Running · 2 of 4 tasks" pill | `color-themes-1.html:90` | **Omit** — 2.4, and it would trip Guard B. |
| Review Spec: surface or inline? | `EXPERIENCE.md:33` lists it as an IA surface; `epics.md:320` says "view" | Reached **from** New Team, **not** a sidebar item (2.1 shipped exactly four and a test enforces it). Route, one-level `Dialog`, or inline panel all permissible. |
| Secondary action wording | `EXPERIENCE.md:32` "Browse starters" vs mock "Browse starter teams" | Spine → **"Browse starters"**; declare if you deviate. |
| `bg`/`card`/`muted` hexes | `color-themes-1.html` gives a full palette | Already resolved in 2.1: **inherit shadcn**. The mock palette is a rendering aid. |

### Copy that belongs to this surface — and copy that does not

**Reuse verbatim:** `Describe your team.` (heading) · `e.g. a team that researches a topic, drafts an article, and critiques it…` (placeholder) · `Build team` · `Run it now` · `Review before build` · role labels `You` / `team_maker` (convention from `team-workspace.html:101,104`).

**Do not borrow** — Story 2.1's review caught exactly this, where My Teams' first-open string was used on two routes:

| String | Actually belongs to |
|---|---|
| `No teams yet. Describe one, or start from a template.` | My Teams (2.5) |
| `Ask a follow-up or refine the goal…` | Team Workspace chat input (2.4) — dangerously close to a Composer placeholder |
| `Running · 2 of 4 tasks` | Run status (2.4) |
| `Save this team and its results?` | Post-**run** prompt (2.5) — not post-build |
| `All models reachable.` / `openai key missing — …` / `OpenRouter key found — …` | Key check (2.3). These render **on** the Composer but are 2.3's copy and 2.3's data. |
| `Keys: anthropic ✓ · gemini ✓ · openrouter ✓` | Fabricated mock data; already rejected by 2.1 |

Voice (`EXPERIENCE.md:52-62`, `DESIGN.md:67-69`): plain, confident, helpful. No hype, no emoji, no exclamation marks. *"Which model should the critic use?"* not *"Configure agent LLM routing parameters."* Name providers in the user's words (claude, gemini, chatgpt) and map to real provider IDs behind the scenes.

**Note:** `web/app/page.tsx:15,17` currently ships invented copy (*"Describe the team you need, or begin from a starter team."* plus a `New Team` button linking to `/starter-teams`) that appears in no spine. This story replaces that page wholesale.

### Project conventions (must follow)

- **This is a frontend-only story.** No file under `team_maker/`, `api/` or `tests/` changes. If you believe you need an API change, stop and escalate — Story 2.0 owns that surface.
- Node commands via `npm --prefix web` or from inside `web/`. Node ≥20.9 (`web/package.json` engines).
- TypeScript strict; **no `any`** in code you write.
- Per CLAUDE.md: files small and cohesive (~200–400 lines — the largest authored file today is 105 lines, so a 500-line `composer-chat.tsx` would be the first violation); tests grouped by responsibility in directories; **label every mock/stub explicitly and never report a mocked integration as proof the real one works.**
- Commit rhythm: one `feat(story-2.2)` for code+tests, one `docs(story-2.2)` for this file and `deferred-work.md`. Linear history, no merge commits. Long-form bodies explaining *why*, ending `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`.

### Git intelligence

`725b475` docs(story-2.1) · `d4dfa55` feat(story-2.1) · `a489334` Merge epic_1 into develop (the only merge commit).

Cut `story_2_2` from `epic_2` **after Story 2.0 has been merged into `epic_2`**, so the API is present in the branch you build on. `develop` remains at `a489334` — Epic 2 folds into `develop` once, after the whole epic.

There is **no `sprint-status.yaml`** and no `_bmad/` scaffold in this repo; status is tracked inline in this file's `Status:` field.

### Project Structure Notes

```text
web/
  app/page.tsx              # REPLACED — Composer surface (keep the `metadata` export)
  components/composer/      # NEW — transcript, bubble, input, thinking indicator,
                            #       run-now control, review toggle, spec editor,
                            #       build-result panel
  lib/api-client.ts         # NEW — the single place that talks to /api
  tests/composer/           # NEW — incl. fixtures/ (captured from a real response)
  tests/shell/routes.test.tsx  # MODIFIED — `/` assertions migrated out, one test deleted
```

- **Untouched:** all of `team_maker/`, `api/`, `tests/` (Python), `pyproject.toml`, `Makefile`, `web/next.config.ts` (Story 2.0 owns the rewrite), `examples/`, `scripts/`, `assets/`.
- Do not create `web/app/api/` — a filesystem route would shadow Story 2.0's rewrite.

### References

- [Source: project-docs/stories/2-0-api-seam-compose-endpoints.md] **the authoritative API contract** — read it before Task 2
- [Source: project-docs/epics.md:313-321] Story 2.2 statement + AC; [:135-141] Epic 2 scope; [:94-102] UX-DR1–9; [:24-28] FR-1/2/3/4/20; [:50-51] FR-14/15
- [Source: .../ux-.../EXPERIENCE.md:14] spine-wins tie-breaker; [:24-33] loop + IA; [:48-62] voice; [:64-77] component patterns; [:81-92] state patterns; [:94-104] interaction primitives; [:106-117] a11y floor; [:180-215] flows
- [Source: .../ux-.../DESIGN.md:63-69] inherit-shadcn discipline + voice; [:110-127] components; [:130-136] Do/Don't
- [Source: .../mockups/team-workspace.html:47-58,99-111] message/composer anatomy (2.4's content, 2.2's shape); [color-themes-1.html:86-90] New Team panel
- [Source: project-docs/stories/2-1-app-shell-sidebar-theming.md] the shipped frontend, its guards, and its review's defect classes
- [Source: project-docs/stories/1-3-conversational-tuning-run-now.md] the refinement/run-now contracts behind the API
- [Source: project-docs/stories/deferred-work.md:42-58,115-126] inherited Composer and frontend gaps
- [Source: CLAUDE.md] structure, test organization, test transparency, file size
- [Source: web/node_modules/next/dist/docs/] Next 16 — authoritative per `web/AGENTS.md`

### Open questions for the PM / designer (not blocking implementation)

1. **Story 2.1's Open Question 1 becomes user-visible here.** Light-mode `#FFFFFF` on `#0E8C82` is 4.12:1, below AA's 4.5:1 for normal text, and this story puts the first normal-size label on a primary button. Settle it now — `#0D857B` was costed at 4.51:1 — or Story 2.7 inherits a token it cannot re-pick.
2. **`Enter` sends, but `Shift+Enter` is unspecified**, as is any touch-keyboard behaviour below `md`. This story adds both; confirm the choice.
3. **Autoscroll, scroll-anchoring, timestamps, markdown-in-bubble and a transcript cap are specified nowhere.** This story picks defaults and declares them; confirm before they harden across 2.4's chat surface, which will inherit them.
4. **Where does the `Browse starters` secondary action belong?** The mock puts it on the describe screen; Starter Teams is Epic 3. Shipping the button now means a live link to an empty-state page.
5. **What proposes the team name?** `epics.md:355-356` says it is "proposed by the Composer, editable at save time" — save is 2.5, but the name arrives in 2.2's spec. Confirm 2.2 only displays it.

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List

## Change Log

- 2026-08-02 — Story drafted via the create-story context engine on branch `story_2_1` @ `725b475`, with four parallel research agents and an independent validation pass.
- 2026-08-03 — **Split.** The original draft carried both the API seam and the Composer UI, which made it the largest story in the epic and mixed two reviewable concerns. The API seam moved to **Story 2.0** (`2-0-api-seam-compose-endpoints.md`), numbered as an enabler rather than renumbering 2.3–2.7, because 45 cross-references to those numbers exist across 6 files, four of them already-accepted stories. This file is now frontend-only and **depends on 2.0**; its ACs renumbered 1–10 and its tasks 1–6. The API contract moved with 2.0 and is summarised here for convenience only. Retained from the original research: the Composer is a chat (the mock's one-shot box is its first turn); `Run it now` **bypasses** the review toggle while `Build team` honours it; auto-build must not fire on its own after a turn or the conversation ends at turn 1; a successful build reports **inline** because 2.4/2.5's destinations do not exist; the surface references `--signal` zero times so Story 2.1's Guard B stays green; the input must be a real textarea or a recognised `contenteditable` value or the `g` chord fires mid-sentence; and seven shadcn components need installing with the **pinned** CLI, not `@latest`.
