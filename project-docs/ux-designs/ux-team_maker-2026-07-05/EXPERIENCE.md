---
name: team_maker
status: final
sources:
  - project-docs/prds/prd-team_maker-2026-07-05/prd.md
  - project-docs/briefs/brief-team_maker-2026-07-04/brief.md
updated: 2026-07-05
---

# team_maker — Experience Spine

> Conversational multi-agent team builder (Coinpela R&D). Multi-surface: responsive web +
> macOS + Windows desktop, shared codebase. shadcn/ui on Next.js + Tailwind. `DESIGN.md` is the
> visual identity; this spine owns behavior. Spines win on conflict with any mock or import.

## Foundation

Multi-surface: responsive **web** plus **macOS and Windows desktop** builds from one codebase
(desktop wraps the web app). shadcn/ui does most of the visual work; the brand layer is thin
(see `DESIGN.md`). Primary user is **semi-technical**: comfortable obtaining an API key and
editing a config file, not writing agent specs. API keys never live in the UI — they live in a
separate **Key Config** file; the UI reads and reports status only.

The product's spine is a loop: **describe → (optionally tune) → build → run/chat → save**. The
Composer is a *conversation*, not a one-shot form.

## Information Architecture

| Surface | Reached from | Purpose |
|---|---|---|
| **New Team** | App open / sidebar / `g n` | Conversational Composer — describe a team; chat back-and-forth to tune it; or run right away |
| **Starter Teams** | Sidebar / "Browse starters" | Pick a ready-made team (education, research/content) and run it without composing |
| **Review Spec** *(optional)* | "Review before build" on New Team | Inspect/edit roles, tasks, per-agent Provider/model; edits re-validated before build |
| **My Teams** | Sidebar / `g t` | Lightweight **recent-teams** list; open a team to chat with it or re-run it |
| **Team workspace** (chat + docs) | A team in My Teams / Starter Teams | Chat with a built Team; upload documents; run against a goal; read results |
| **Settings** | Sidebar footer | Light/dark theme; Key Config file path + per-Provider key status; **guidance on handling keys safely**; OpenRouter option |

Sidebar collapses to icons on `md`, becomes a `Sheet` on `sm`. Modal depth: one level (a
`Dialog` over a surface, never dialog-over-dialog).

→ Composition reference: `mockups/team-workspace.html` (rendered at finalize). Spine wins on
conflict.

**Surface closure:** every stated need has a home — compose (New Team), start fast (Starter
Teams), tune (Review Spec), find/reuse (My Teams), use (Team workspace), configure keys/theme
(Settings). Developer needs are served headlessly (see Developer Surface), not by a UI screen.

## Voice and Tone

Microcopy. Brand voice/posture live in `DESIGN.md.Brand & Style`.

| Do | Don't |
|---|---|
| "Describe your team." | "Let's build your AI dream team! 🚀" |
| "Which model should the critic use?" | "Configure agent LLM routing parameters." |
| "openai key missing — add it to your Key Config." | "Error: credential not found (401)." |
| "OpenRouter key found — all routed models are available." | "Provider gateway initialized." |
| "Running · 2 of 4 tasks" | "Execution in progress (50%)." |
| "Save this team and its results?" | "Persist artifacts?" |

Plain, confident, helpful. Name providers/models in the user's words (claude, gemini, chatgpt),
map to real Provider IDs behind the scenes.

## Component Patterns

Behavioral. Visual specs live in `DESIGN.md.Components` (or shadcn defaults).

| Component | Use | Behavioral rules |
|---|---|---|
| Composer chat | New Team | Multi-turn. User describes; app proposes a team and asks targeted follow-ups (roles, models, tasks). Always offers a "Run it now" shortcut that skips further tuning. |
| Team card | My Teams, Starter Teams | Shows team name, agent count, and per-agent provider badges. Click → Team workspace. Live teams show the accent pulse. |
| Agent/provider badge | Composer, Review Spec, Team card | Shows an agent's Provider/model; tinted by key-check state (ok / missing / via-OpenRouter — see State Patterns). |
| Review Spec editor | Review Spec | Editable roles, tasks, per-agent Provider/model. Save re-validates; invalid spec blocks build with inline reasons. |
| Team workspace | Team workspace | Chat box to talk to the team + a **document loader** (drag/drop or picker) for transient run context. Run controls; results stream in as task outputs (batch in v1 — see State Patterns). |
| Task list (run) | Team workspace / Run | One row per Task in DAG order; row shows agent, model, and status; active row carries the accent pulse. |
| Key status list | Settings | Per-Provider ok/missing; Key Config file path; copyable guidance on securing keys. |
| Empty state | Anywhere | shadcn empty pattern + one team_maker sentence + a single primary action. |

## State Patterns

| State | Surface | Treatment |
|---|---|---|
| First open / no teams | My Teams | "No teams yet. Describe one, or start from a template." Buttons: New Team, Starter Teams. |
| Composing (thinking) | New Team | shadcn `Skeleton`/typing indicator while the app drafts the spec; user can keep typing. |
| Key check — all good | Composer / pre-run | Provider badges neutral; "All models reachable." Run enabled. |
| Key check — missing key | Composer / pre-run | Affected agent badge flagged; banner: "openai key missing — add it to your Key Config (Settings), or switch this agent to a model you have." **Run is blocked** until resolved. |
| Key check — no keys at all | Composer | "You'll need at least one model key to run. Add one in your Key Config, or add an OpenRouter key to unlock many models." Links to Settings guidance. |
| Key check — OpenRouter present | Composer / pre-run | Badges show "via OpenRouter"; "OpenRouter key found — routed models available." |
| Running | Team workspace / Run | Accent pulse on team + active task row; task list advances; other input queued. Batch result on completion (v1). |
| Run complete | Team workspace | Final result shown; each task row expandable to its output. Prompt: "Save this team and its results?" |
| Run failed (provider error) | Team workspace | shadcn `Toast` (destructive): plain-language cause + retry. `[ASSUMPTION]` partial-results behavior deferred to architecture (PRD Open Q5). |
| Offline / local-only | Global | Teams using only local models run offline; cloud-provider agents show "needs connection". |

## Interaction Primitives

- **Conversational-first.** The Composer is a chat; tuning happens in dialogue, not deep forms.
  A "Run it now" affordance is always present so users can skip tuning.
- **Keyboard:** `g n` New Team, `g t` My Teams; `Enter` sends a Composer message; `⌘/Ctrl+Enter`
  runs the current team; `Esc` closes dialogs/exits edit.
- **Document intake:** drag-and-drop onto the Team workspace, or a file picker. Transient to the
  run/session in v1 (no persistent memory).
- **Mouse:** click to act; provider badges are click-to-change (opens a small model picker).
- **Banned:** entering API keys anywhere in the UI; modal-over-modal; hiding a blocked run
  behind a silent failure (always say why).

## Accessibility Floor

Behavioral; visual contrast inherits shadcn's WCAG-AA defaults (brand teal verified against
`background` in light and dark).

- WCAG 2.2 AA across web and desktop.
- Full keyboard operability: Composer chat, Review Spec editor, run controls, and Settings.
- Screen reader announces surface on navigation and **run progress** via `aria-live`
  ("Task 2 of 4, writer, running").
- Tab order matches reading order; `Esc` closes the topmost layer; visible focus ring
  (`{ring}`) at AA contrast.
- Missing-key and validation messages are text (not color-only); badges pair color with a label.

## Provider & Key Handling *(product-specific)*

The most error-prone moment for a semi-technical user. Rules:

- Keys live only in the **Key Config** file; the UI reads status, never accepts entry (FR-12).
- **Resolution logic** (surfaced honestly in the key check): if the user names no models, the
  app uses models they *have keys for*; if a user names a specific model, the app verifies its
  key first; if there are no keys at all, the app asks for one before any run (FR-10).
- **OpenRouter**: a single OpenRouter key unlocks many models; when present, agent badges read
  "via OpenRouter" and the check reports models reachable through it.
- **Local models** run keyless; managed/large local-model support ("army" of local models) is
  **v2**.
- Settings always shows the Key Config path and plain guidance on keeping keys safe.

## Team Lifecycle & Memory *(v1 scope + v2 markers)*

- **v1:** teams are built, saved to the recent-teams list, chatted with, and run on demand.
  Documents can be attached **transiently** to a run/session.
- **v2:** persistent **team memory / learning-while-working**; **always-on** teams (toggle
  on/off, run as a service); proper **team versioning**; managed **local-model** fleets. These
  are logged and flagged for the PRD Update and architecture — the UI reserves room for a
  per-team "memory" and "always-on" control but does not implement them in v1.

## Developer Surface *(lightweight — technical users)*

Developers don't need the heavy UI, but get first-class basics:

- **API:** compose-and-create and run endpoints (PRD FR-16..FR-18) to create/run/embed teams
  headlessly; results returned in batch (v1).
- **CLI:** generate and run teams from the terminal (the existing factory CLI, extended to run).
- **Key Config:** the same separate file the UI reads — documented for scripted/CI use;
  OpenRouter supported.
- **Embedding:** a created team is a self-contained package; developers can drop, e.g., a
  content team into their own product via the API.
- No dashboard for developers in v1 beyond the shared UI; docs + API + CLI are the surface.

## Responsive & Platform

| Breakpoint / surface | Behavior |
|---|---|
| `≥ lg` (web) / desktop | Sidebar visible; Team workspace = chat + docs pane side by side. |
| `md` | Sidebar → icons; workspace stacks (chat above, docs/results below). |
| `< md` (`sm`) | Sidebar → `Sheet`; Composer and workspace go single-column full-width. |
| macOS / Windows | Same layout as web (shared codebase); native window chrome only. |

## Inspiration & Anti-patterns

- **Lifted from chat-first tools:** the Composer is a conversation that converges on a spec —
  describe, get asked the right follow-ups, or bail out with "Run it now."
- **Lifted from shadcn:** the whole surface vocabulary; the brand is *what we add*, not a
  from-scratch system.
- **Rejected — key entry in the UI:** keys stay in the Key Config file; the UI only reports and
  guides. Security posture, not a limitation to paper over.
- **Rejected — hype/celebration UI:** no confetti, no "dream team" language; this is a tool.
- **Rejected — burying failures:** a blocked run always states the reason (missing key,
  invalid spec) in plain language.

## Key Flows

### Flow 1 — Nadia builds and runs a research team (default path)

1. Nadia (content strategist; has an API key, won't write YAML) opens the desktop app; lands on
   **New Team**: "Describe your team."
2. She types "a team that researches a topic, drafts an article, and critiques it." The Composer
   proposes researcher → writer → editor → critic and asks one follow-up ("any model
   preferences, or should I pick from the keys you have?"). She replies "use what I have."
3. The key check passes (accent-free, neutral badges). She clicks **Build team** (review left
   off). The team lands in **My Teams**; she's dropped into its **workspace**.
4. She types her goal in the chat — "state of solid-state batteries, ~800 words" — and hits
   `⌘/Ctrl+Enter` to run. She drags in a reference PDF; it's attached to this run.
5. The task list advances researcher → writer → editor → critic, the active row pulsing accent.
6. **Climax:** the finished, critiqued article fills the results pane; she expands the critic's
   row for feedback and the researcher's for sources — one place, no chatbot-hopping. A prompt
   asks: "Save this team and its results?" She saves. Realizes FR-1, FR-4, FR-8..FR-11.

*Edge — missing key:* an agent routed to openai with no key → run blocked before it starts;
banner names the provider and offers "add to Key Config" or "switch this agent." She switches
the judge to a model her OpenRouter key covers; badge flips to "via OpenRouter"; run proceeds.

### Flow 2 — Omar starts from a starter team, then adapts it

1. Omar wants to learn, not configure. Sidebar → **Starter Teams** → **Education**.
2. He opens its workspace and runs it against a topic immediately — no composing.
3. **Climax:** the tutor team returns an explanation tuned to his question; he reads it in the
   workspace. Later he clicks **Adapt with Composer**, which opens the Composer pre-loaded with
   this team so he can tweak roles/models in conversation; changes re-validate before rebuild.
   Realizes FR-19, FR-1, FR-3, FR-8.

### Flow 3 — Priya specifies providers per agent (power path, still no YAML)

1. Priya types "researcher argues *for* using Claude, a critic argues *against* using Gemini,
   and ChatGPT is the judge."
2. The Composer maps each named model to a Provider and runs the key check: Claude ✓, Gemini ✓,
   ChatGPT (openai) — missing. Badge flags the judge.
3. **Climax:** the banner says exactly what's wrong and how to fix it; Priya adds the key to her
   Key Config (or accepts OpenRouter), the check flips green, and the team builds with her exact
   routing intact. Realizes FR-1, FR-4, FR-10.
