---
baseline_commit: 725b475
---

# Story 2.0: The API seam — FastAPI app and compose endpoints

Status: ready-for-dev

## Story

As the team building Epic 2,
I want the FastAPI layer AD-4 requires, with the compose endpoints the Composer needs,
so that every Epic 2 surface has a legal path to the Python core instead of inventing one.

## Why this story exists (read this before anything else)

**No story anywhere in the plan creates the FastAPI application, and four Epic 2 stories are blocked on it.**

- **AD-4** (`ARCHITECTURE-SPINE.md:67-71`) is a `Binds: all` invariant with no exception clause: *"dependencies point inward only: `UI → API → core (ports) → adapters`. The UI reaches the system **only** through the API."*
- There is **no `api/` directory, no FastAPI dependency, and no HTTP layer** anywhere in this repo today. Verified.
- The **Structural Seed** (`:192`) scopes `api/` to *"compose/create, run, teams, settings"* — four groups. `teams` and `settings` are Epic 2 surfaces, not Epic 4 ones.
- The **Capability Map** (`:210`) explicitly assigns Epic 2's FR-23–FR-26 to `api/`.
- **Epic 4 does not create it.** Story 4.1's AC opens *"Given the API is running"* — it presupposes the app. Grepping every planning document turns up no story whose AC produces `api/main.py`.
- **Story 2.1 deferred the decision on purpose:** *"There is no `api/` directory in this repo and Epic 2 does not create one **until it needs it**"* (`2-1-...:160`).

This story is that moment, and it is deliberately an **enabler**, numbered `2.0` in the same spirit as Epic 0 (*"Retire the architectural debt before adding features"*). It ships **no UI**. What it unblocks:

| Story | Needs from `api/` |
|---|---|
| **2.2** Composer | the four compose endpoints below |
| **2.3** Key-check states | a key-**status** read; AD-9 forbids the browser touching keys |
| **2.4** Team Workspace | FR-23–FR-26, assigned to `api/` by the Capability Map |
| **2.5** Named teams | save/browse/recent via `api/` + storage |
| **2.6** Settings | the Structural Seed's `settings` group |

**Rejected alternatives** — do not relitigate these mid-implementation:

| Option | Verdict |
|---|---|
| Next.js route handler shelling out to the `team-maker` CLI | **Violates AD-4 and AD-3** (it makes the UI the API), and is technically unworkable: `compose` prints Rich-formatted YAML to stdout interleaved with panels (`cli.py:329,586`), errors are Rich markup + `sys.exit`, and refinement is an `input()` loop (`cli.py:279-304`) that cannot be driven over HTTP without a pty per session. `project-context.md:67` already forbids it: *"Rich console output is cosmetic; never let it carry program logic or data the caller needs."* |
| Route handlers + custom IPC (socket / JSON-RPC / MCP) | Same AD-4/AD-3 violation with more machinery — an API without the OpenAPI, typing or versioning. |
| Ship the Composer against mocked data | Forbidden by Story 2.1's precedent (*"Do not stub a client, do not mock a fetch, do not invent an endpoint shape"*, `:160`) and by `EXPERIENCE.md:103-104`. |

## Acceptance Criteria

1. **Given** AD-4 and the Structural Seed, **When** this story lands, **Then** a FastAPI application exists at repo-root **`api/`** — a sibling of `team_maker/` and `web/`, exactly where `ARCHITECTURE-SPINE.md:192` places it — and it is the only path from `web/` to the Python core. Do **not** create a top-level `core/`: the spine's layer sketch (`:31-43`) mentions one, but the Structural Seed (`:181-197`) puts `composer/`, `runtime/`, `ports/` and `adapters/` inside `team_maker/`, and the repo followed the Seed. (AD-4, AD-3, `ARCHITECTURE-SPINE.md:192,210`)

2. **Given** the Composer is multi-turn, **When** the API is defined, **Then** `api/main.py` includes the compose router under `APIRouter(prefix="/api")` and exposes exactly these authored routes and no more:

   - `POST /api/compose/sessions` → `{ "intent": str, "authoring": { "provider": str, "model": str } | null }` → **201** `{ "session_id": str, "spec": <SpecView>, "turn": 1, "turns_remaining": int }`
     **There is deliberately no `validation` field.** AD-10 and `composer.py:110-126` mean a returned spec is schema-valid *by construction* — `compose()` either returns a valid `TeamCreationRequest` or raises. The only `ValidationResult` in the system (`{passed, issues, warnings}`) is produced by `OutputValidator` **after a build**. An always-`passed: true` field here would be a value true by construction — the defect class Dev Notes rule 2 warns about.
   - `POST /api/compose/sessions/{id}/messages` → `{ "message": str }` → **200**, same body shape, `turn` incremented. On `ComposerError` → **422** with the error envelope below, `session.current` unchanged (the Story 1.3 AC 6 contract).
   - `PUT /api/compose/sessions/{id}/spec` → **an edit body carrying only the three dimensions Story 2.2's review mode edits** — never a `TeamCreationRequest`:
     ```json
     { "team_name": "str", "purpose": "str",
       "desired_roles": [{ "name": "str", "description": "str",
                           "llm": { "provider": "str", "model": "str" } }],
       "desired_tasks": [{ "name": "str", "description": "str",
                           "agent_role": "str", "dependencies": ["str"] }] }
     ```
     The server merges these onto `session.current` and re-validates by constructing `TeamCreationRequest(**merged)`. `output_path`, `overwrite`, `api_key_env`, `planning_llm`, `framework`, `state_backend` and `sandbox` are **server-owned** — carried from `session.current`, never read from the body. `output_path` is schema-required (`request.py:178`) so a partial body cannot validate alone; and a browser-settable `overwrite` would turn `FileExistsError` — the only guard against clobbering an existing directory — into a browser-controlled switch. Valid → **200**, `session.current` replaced. Invalid → **422**, `session.current` **unchanged**.
   - `POST /api/compose/sessions/{id}/build` → runs `PipelineRunner().run(...)` → **200**:
     ```json
     { "team_name": "str", "output_path": "str", "agent_count": 0, "task_count": 0,
       "written_file_count": 0, "model_substitutions": [],
       "validation": { "passed": true, "issues": [], "warnings": [] } }
     ```
     mapped from `PipelineResult` (`runner.py:38-43`). `model_substitutions` exists because `normalize_team_routings` may silently swap a chosen model for a fuzzy nearest match and reports it only to **stderr** (`model_resolver.py:156-185`) — without it the UI will claim it built `gpt-4o` when it built `gpt-4o-mini`.
   - `GET /api/health`

   **The error envelope.** Every non-2xx response has exactly this body and no other:
   ```json
   { "error": { "code": "slug", "message": "plain language, user-facing",
                "fields": [ { "path": "desired_roles.0.name", "message": "…" } ] } }
   ```
   `fields` appears only for `spec_invalid`. `message` is authored copy, **never `str(exc)`** — `deferred-work.md:45` warns that string can echo SDK-embedded secrets. Log the exception server-side; never serialise it.

   | code | status | raised by |
   |---|---|---|
   | `session_not_found` | 404 | unknown or evicted `session_id` (AC 7) |
   | `turn_cap_reached` | 409 | the AC 7 turn cap |
   | `spec_invalid` | 422 | `ComposerError` on refine; a failed `PUT .../spec` |
   | `authoring_unavailable` | 503 | no usable authoring credential (Open Question 2) |
   | `compose_failed` | 502 | any other exception from the provider adapter |
   | `output_exists` | 409 | `FileExistsError` from `PipelineRunner.run` |
   | `build_failed` | 500 | any other exception from `PipelineRunner.run` |

   These routes are an **internal precursor, not the public contract**; Epic 4's FR-16/FR-17 own the versioned public surface and may rename them. "No more routes" governs *authored* routes — FastAPI's built-in `/docs`, `/redoc` and `/openapi.json` stay enabled, since that generated schema is what Epic 4 will version. (`ARCHITECTURE-SPINE.md:192`; `epics.md:402-428`)

3. **Given** `Composer.compose()` performs up to **four sequential blocking LLM round-trips** (`composer.py:106-126`) and nothing in the core is async, **When** the path operations are written, **Then** they are declared **`def`, not `async def`** (FastAPI runs sync handlers in a threadpool), or explicitly wrapped in `anyio.to_thread.run_sync`. A blocking call inside `async def` stalls the event loop for the whole request and the API stops serving anything else, including `/api/health`.

   A test must prove the server answers `GET /api/health` while a compose call is in flight, **and must be shown to go red against an `async def` handler**. Concretely: inject a fake `LLMProvider` whose `complete_structured` blocks on a `threading.Event`; start the compose request on a `ThreadPoolExecutor`; from the main thread assert `GET /api/health` returns 200 within a short timeout; then set the event and assert compose completes. `TestClient.get()` is synchronous and a fake provider that returns instantly passes whether the handler is `def` or `async def` — that test proves nothing. Record in Completion Notes the measured result of temporarily flipping the handler to `async def`; if that run does not fail, the test is not testing anything. (Dev Notes, "The bug you will otherwise ship")

4. **Given** `AD-9` — *"keys … never entered in the UI, never logged, never in run output"* (`ARCHITECTURE-SPINE.md:121-126`) — **When** any response is built, **Then** no endpoint returns a key value, no endpoint accepts one, and a test asserts the authoring secret's literal value appears in no response body, no response header, and no log record. Per-provider key **status** is Story 2.3's surface and must not be invented here. (AD-9, FR-12)

5. **Given** `pyproject.toml` declares `include = ["team_maker*"]` (`pyproject.toml:67`), which makes setuptools **find `api` and then silently exclude it** — `pip install -e .` appears to succeed, `import api` works from the repo root and nowhere else, and the package is absent from any wheel — **When** `api/` is added, **Then** `pyproject.toml` is edited deliberately and the edit is declared: `include = ["team_maker*", "api*"]`, a new `api` optional-dependency extra (`fastapi>=0.141,<0.142`, `uvicorn>=0.52,<0.53`) added to `all` and `dev`, `[tool.coverage.run] source` extended with `"api"`, and the `lint`/`fmt` Makefile targets extended to `api/`.

   **Do not assume this resolves cleanly:** `uvicorn 0.52.0` and `starlette 1.3.1` are **already installed transitively** (via `mcp`, from the crewai tree), and `crewai 1.14.6` pins `pydantic<2.13,>=2.11.9` and `httpx~=0.28.1`. FastAPI's narrow `starlette` range is the most common install conflict in Python. Raising `pydantic>=2.5` to `>=2.9` is cosmetic — crewai already enforces a stricter floor — so make that edit only to keep the declared floor honest, and verify the resolution either way (Task 1). **Story 2.1's AC 2 froze this file for a story that added no Python; that was never a permanent freeze.** Declare the thaw explicitly rather than avoiding the edit. (`pyproject.toml:13,67,87`; `Makefile:21-25`)

6. **Given** the dev topology is undefined anywhere in the repo, **When** this story lands, **Then** `web/next.config.ts` gains a `rewrites()` entry proxying `/api/:path*` to `process.env.API_ORIGIN ?? "http://localhost:8000"`, so the browser only ever issues same-origin requests and **no CORS middleware, preflight, or `Access-Control-*` configuration is needed**; `make api-dev` runs the API; `README.md` documents the two-terminal flow; and a smoke check proves `GET /api/health` is reachable **through the Next proxy**, not just directly. **There must be no `web/app/api/` directory** — a filesystem route would shadow the rewrite. Do not hard-code a frontend origin: `langfuse/docker-compose.yml` runs `langfuse-server` under `network_mode: host` (`:22,:34`) with no `ports:` mapping, and Langfuse's own listener is 3000 (`:7,:41`), so when that optional dev stack is up it occupies 3000 on Linux hosts and `next dev` falls forward to 3001. (Dev Notes, "Dev topology")

7. **Given** an unbounded chat drives unbounded LLM spend — `deferred-work.md:54` records *"no cap on conversation turns or consecutive failed-refinement attempts … a confused user or scripted stdin can drive unbounded LLM spend with zero guardrail"*, and an HTTP API makes this materially worse than a CLI — **When** the session registry is written, **Then** it enforces a turn cap and an idle-session eviction policy, both named constants, and both surfaced through the AC 2 error codes. Sessions live in an in-process dict, so the API is **single-worker**; a test must prove an unknown or evicted `session_id` returns a clean `session_not_found` 404 rather than a 500. (`deferred-work.md:54`; AD-3 *"one deployable process by default"*)

8. **Given** the CLI's interactive loop catches only `ComposerError` around `refine()` and any other exception kills the conversation (`deferred-work.md:53`), and the repair loop retries **only** on `pydantic.ValidationError` so a network blip propagates with zero retries (`deferred-work.md:47`), **When** a turn fails, **Then** the API catches broadly, keeps the session alive with `session.current` intact (`session.py:41-44`), returns the appropriate AC 2 error code, and **no raw stack trace, exception repr, or SDK error string appears in any response**. A test must assert, for **every** code in the AC 2 table, that the body contains no `Traceback`, no `  File "`, and no exception class name. Error *copy* for the user is Story 2.3's; error *containment* is this story's. (FR-15)

9. **Given** no Python test lane covers this seam, **When** this story lands, **Then** tests live in **`tests/api/`** (with `__init__.py`, matching every other `tests/` subdirectory) using `fastapi.testclient` with an injected fake `LLMProvider`, so the suite stays **fully offline** — no network, no real key, no SDK. The existing **393 passed / 7 skipped** baseline still passes; paste the real `pytest` tail rather than asserting a number. (CLAUDE.md test organization + transparency)

10. **Given** `AD-8` — *"all LLM access (Composer and agents alike) goes through one `LLMProvider` port. Adding a provider is adapter/config, never core"* (`ARCHITECTURE-SPINE.md:113-119`) — and **given** the spine's Deferred list already anticipates this with *"**Composer default model** — configurable behind LLMProvider; concrete default TBD"* (`:223`), **When** the authoring provider is resolved, **Then** it is **parametric, not hardcoded**:

    - **Default:** `anthropic` / `claude-sonnet-4-6` — the same default the CLI uses (`cli.py:37-38`), so behaviour is unchanged for a user who configures nothing.
    - **Selectable:** any id `create_provider` resolves — today `anthropic`, `openai`, `xai`, `google`, `ollama`, plus `openrouter` once AC 11 lands. Selection is **data, never a branch**: resolve through `create_provider(ProviderConfig(...))` and let an unknown id raise its own `ValueError`. `project-context.md:43` is explicit — *"never branch on provider name"*.
    - **Three shapes must work.** *Direct provider* (e.g. `openai` + `OPENAI_API_KEY`); *gateway* (`openrouter` + `OPENROUTER_API_KEY`, one key for many models); *local, keyless* (`ollama`, `keyless_local=True`, `default_base_url="http://localhost:11434"`, **no key required** — a keyless provider must never be refused for a missing credential, which `registry.py`'s `STATUS_KEYLESS_LOCAL` already models).
    - **Where the choice comes from:** an optional `authoring` object on `POST /api/compose/sessions` (`{ "provider": str, "model": str }`, both optional), falling back to a server-side default. **The key never comes with it** — AD-9 stands: the request may name a provider, and the server resolves that provider's credential from the Key Config. A request carrying a key value is rejected, not honoured.
    - **`authoring_unavailable` (503) must name the provider it could not use and the Key Config entry that would fix it** — never a bare "missing key". A keyless provider can only produce this error for a connection failure, not a credential one.

    Tests: one per shape (direct / gateway / keyless) proving `create_provider` is reached with the expected `ProviderConfig`, plus the default-when-unspecified case, plus a rejection test for a request that tries to supply a key. (AD-8, AD-9, FR-13, FR-22, `ARCHITECTURE-SPINE.md:223`)

11. **Given** the requirement above names OpenRouter, **When** you check the code, **Then** note that **no OpenRouter adapter exists**: `_ADAPTERS` (`team_maker/adapters/providers/__init__.py:25-43`) resolves exactly `anthropic, openai, xai, google, ollama`, so `create_provider(provider="openrouter")` raises today. The key catalog *does* know OpenRouter — `Provider(OPENROUTER, "OPENROUTER_API_KEY")` at `registry.py:105` — but only as a **routing gateway for team agents**, not as an authoring adapter. So this story **adds `team_maker/adapters/providers/openrouter_provider.py` plus one `_ADAPTERS` row**, and nothing else under `team_maker/`.

    This is legal and expected under AD-8 (*"adding a provider is adapter/config, never core"*) and is **additive** — a new file and a new dict entry, no change to any existing adapter's behaviour. Declare it anyway, because AC 12 otherwise freezes `team_maker/`.

    OpenRouter's API is OpenAI-compatible, so **`xai_provider.py` is the template**, not a new design: it is the existing OpenAI-SDK-over-`base_url` adapter (`base_url="https://api.x.ai/v1"`). Use `base_url="https://openrouter.ai/api/v1"` and `api_key_env="OPENROUTER_API_KEY"`. Keep it in the same shape as its sibling so the next reader sees one pattern, not two. A unit test must construct it through `create_provider` and assert the resolved `base_url` and `api_key_env` — offline, with no network call. (AD-8, FR-22)

12. **Given** this story's scope, **When** implementing it, **Then** these are explicitly **out of scope**: **any UI whatsoever** — no page, no component, no chat surface (that is Story 2.2, and the only `web/` change here is `next.config.ts` plus the README); per-provider key status and the key-check states (2.3); Workspace, run execution, documents, transcripts (2.4); save/rename/delete and recent teams (2.5); Settings (2.6); the public versioned API contract and its docs (Epic 4); streaming (AD-13 — v1 is batch behind a streamable interface); `teams`/`settings` endpoints from the Structural Seed's wider `api/` scope, which their own stories will add. Also out of scope: modifying any **existing** module under `team_maker/` — AC 11's OpenRouter adapter is a **new file plus one registry row**, which is the only permitted addition there (see Task 2 if you think you need more).

## Tasks / Subtasks

- [ ] **Task 1 — Create the `api/` package and prove it serves** (AC: 1, 3, 5)
  - [ ] `api/__init__.py`, `api/main.py` (the `FastAPI()` instance, `lifespan`, `/api/health`, router include), `api/deps.py`, `api/schemas.py`, `api/errors.py`, `api/routers/__init__.py`, `api/routers/compose.py`. Keep each file well under CLAUDE.md's 200–400 line guideline.
  - [ ] `pyproject.toml`: `include = ["team_maker*", "api*"]`; new `api` extra pinned `fastapi>=0.141,<0.142` + `uvicorn>=0.52,<0.53` (match the commented, justified pin style Story 1.6 established at `pyproject.toml:38-45`); add to `all` and `dev`; add `"api"` to `[tool.coverage.run] source`.
  - [ ] `Makefile`: add to `.PHONY` and targets — `api-dev` (`uvicorn api.main:app --reload --port 8000`; `--reload` implies one worker, so **do not also pass `--workers`**, uvicorn rejects the combination) and `api-serve` (`uvicorn api.main:app --port 8000 --workers 1`, with a comment that raising the worker count silently breaks the in-process session registry, AC 7). Extend `lint`/`fmt` to `team_maker/ api/ tests/`. **Leave `clean` alone** (it `rm -rf`s Python artifacts; Story 2.1 warned against extending it).
  - [ ] Declare every path operation **`def`, not `async def`** (AC 3). Log a startup warning if `WEB_CONCURRENCY` is set to anything but `1`.
  - [ ] **Verify the dependency resolution before committing the pin.** Run `pip install -e ".[dev]" --dry-run` and confirm nothing downgrades `starlette`, `httpx`, `anyio` or `pydantic`; then run the full `pytest` (393/7 baseline) **and** `tests/conformance/` to prove the crewai path is intact.
  - [ ] Verify `pip install -e ".[dev]"` then `python -c "import api"` **from a different working directory** — the `include` bug is invisible from the repo root.
  - [ ] Proof of life for this task is `GET /api/health` returning 200. The AC 3 concurrency proof needs the compose route and the fake provider, so it lands in Task 4.

- [ ] **Task 2 — Credentials and the parametric authoring provider** (AC: 4, 10, 11)
  - [ ] Resolve the authoring provider **once at application startup** in a FastAPI `lifespan`, not per request.
  - [ ] Build the adapter with `from team_maker.adapters.providers import create_provider` (`cli.py:22,270`), passing a `ProviderConfig` assembled from the requested provider/model or the default. **Never instantiate any concrete adapter directly** — AD-8 requires all LLM access through the one port, and going through the factory is what makes AC 10 parametric for free.
  - [ ] Resolve the credential from the **Key Config catalog row** for the chosen provider (`registry.py`'s `PROVIDERS` gives `env_var` per provider, and `None` for keyless). Do **not** reuse `cli.py:177-190`'s `_resolve_authoring_provider` shape verbatim — it hardcodes `anthropic` and its `ANTHROPIC_API_KEY`, which is exactly what AC 10 removes.
  - [ ] **A keyless provider must not be refused for a missing key.** `ollama` has `env_var=None` and `keyless_local=True` (`registry.py:104`); gate on the catalog row, never on "is there a key".
  - [ ] **Do not reuse `_bridged_credential` as a per-request context manager.** It sets `os.environ[env_var]` and restores the *pre-entry* value on exit (`cli.py:193-213`). Under AC 3's threadpool concurrency that is a live race: request A enters (`previous=None`), request B enters (`previous=A's key`), A finishes and **pops the variable**, and B — still mid-flight — has `AnthropicProvider` read `os.environ.get(...)` → `None` → `EnvironmentError` (`anthropic_provider.py:41-46`). "Resolve once per invocation" does not fix it. Bridge the credential **once in `lifespan` startup and hold it for the process lifetime** (single-process per AD-3/AC 7), or serialise compose calls behind a `threading.Lock`. Either way, write a test with two concurrent compose calls asserting neither loses its credential.
  - [ ] Both `cli.py` helpers are **private members of the CLI layer**. Importing them from `api/` inverts AD-4 and drags `click`, `rich` and `PipelineRunner`'s import chain into the API process. Reimplement the ~10 lines in `api/deps.py` and declare the intentional duplication, **or** promote them to a shared module — which modifies `team_maker/` and is therefore a scope change to declare loudly.
  - [ ] If the chosen provider has no usable credential, every compose route returns `authoring_unavailable` (503), **naming the provider and the Key Config entry that would fix it** (AC 10). A fresh user with only an OpenAI key can now simply choose `openai` — that is the point of AC 10, and it is why the old "dead Composer" open question is closed.

- [ ] **Task 3 — The compose routes and the session registry** (AC: 2, 7, 8)
  - [ ] Session registry: `dict[str, ComposerSession]` with a turn cap and idle eviction, both named constants. Unknown or evicted id → `session_not_found` 404.
  - [ ] `api/schemas.py`: the request/response models in AC 2. **Do not accept raw `TeamCreationRequest` as a request body.** Shape responses as a discriminated envelope (`status` + payload) so AD-13's later streaming retrofit is additive rather than a contract break.
  - [ ] `api/errors.py`: map `ComposerError.errors` — a `list[str]` of `"loc → path: msg"` (`composer.py:169-173`) — into the AC 2 `fields[]` payload with dotted paths. **There is no existing helper; this is new work**, and it is what Story 2.2's inline validation reasons depend on. Handle the `(root)` case that `_format_errors` emits for a non-field error.
  - [ ] The `PUT .../spec` merge: carry server-owned fields from `session.current`, apply only the permitted three dimensions, re-validate, and replace `session.current` **only** on success.
  - [ ] Surface `model_substitutions` on the build response by capturing what `normalize_team_routings` changed (it currently reports only to stderr, `model_resolver.py:156-185`). If capturing it cleanly requires touching `team_maker/`, **stop and declare it** — returning an empty list and a note in Completion Notes is the honest fallback.
  - [ ] Catch broadly (AC 8), never leak `str(exc)`, log server-side only.

- [ ] **Task 4 — Tests** (AC: 3, 4, 7, 8, 9)
  - [ ] `tests/api/__init__.py` + `tests/api/conftest.py` + the endpoint tests.
  - [ ] **`conftest.py` must set `TEAM_MAKER_KEYS` to a `tmp_path` Key Config in an autouse fixture.** `KeyConfig.from_file(None)` falls back to `./team_maker.keys`, which **exists in this working tree with live keys** (gitignored). An unisolated run reads real secrets, and AC 4's assertion would then be comparing against a production key — one failure message away from printing it into a terminal or CI log. Seed the temp file with a sentinel (`sk-ant-SENTINEL-DO-NOT-LEAK`), and prove the assertion can fail by temporarily echoing it.
  - [ ] Promote `FakeLLMProvider` (`tests/unit/test_composer.py:14-31`) to **`tests/support/fake_llm.py`** and re-point the two existing consumers (`test_composer.py`, `test_composer_session.py`) at it. That directory exists for exactly this — Stories 1.6 and 1.7 extracted `crewai_interception.py` and `team_factories.py` there so the next test could reuse proven helpers rather than copy them. Copying it a third time violates the CLAUDE.md rule this story invokes. Declare the two touched test files.
  - [ ] Coverage: session lifecycle (start → refine → build); refinement preserves earlier turns' facts; a failed refine leaves `session.current` intact; the turn cap; idle eviction; `session_not_found`; every AC 2 error code including the no-stack-trace assertion; the AC 3 concurrency proof; the AC 4 sentinel-absence assertion; the two-concurrent-calls credential test from Task 2.
  - [ ] Label every stub in Completion Notes. A `FakeLLMProvider` run is **not** evidence the real Anthropic path works — CLAUDE.md forbids reporting it as such. State which tests are unit, which are mocked-integration, and whether any real end-to-end call was made.

- [ ] **Task 5 — Dev topology and documentation** (AC: 6, 12)
  - [ ] `web/next.config.ts`: `rewrites()` → `/api/:path*` to `process.env.API_ORIGIN ?? "http://localhost:8000"`. No CORS middleware anywhere. Confirm `npm run build` and the existing 147 frontend tests still pass — this is the only `web/` source change in the story.
  - [ ] `README.md`: a short subsection under the existing "Web app" section — two terminals (`make api-dev`, `make web-dev`), prerequisites, the `API_ORIGIN` override, and the single-worker constraint.
  - [ ] Record the reachability check (AC 6): `GET /api/health` through the Next proxy, with the actual command and response pasted into Completion Notes. A direct hit on `:8000` does not prove the proxy.
  - [ ] Record in Completion Notes, **do not edit the planning artifacts** (Story 1.4–2.1 precedent):
    - **No story anywhere creates the FastAPI app.** Story 4.1's AC opens *"Given the API is running"*. This story creates it because the Capability Map assigns Epic 2 capability to `api/` (`:210`), not because it is borrowing from Epic 4.
    - `ARCHITECTURE-SPINE.md:171` pins **FastAPI 0.139.x; current stable is 0.141.1**. 0.140.x carried SSE status-code and event-splitting fixes that matter to AD-13's future. Stale — flag, don't edit.
    - **Uvicorn (or any ASGI server) is absent from the spine's Stack table entirely.** A gap, not staleness.
    - `ARCHITECTURE-SPINE.md:31-43`'s layer sketch puts `composer/`/`factory/`/`runtime/` under a top-level `core/`; the Structural Seed (`:181-197`) puts them inside `team_maker/`, and the repo followed the Seed. Do not create `core/`.
    - `ARCHITECTURE-SPINE.md:225-226`'s "CrewAI version pin" Deferred entry is *still* stale (resolved by Story 1.6; flagged by 1.7 and 2.1; never actioned).
  - [ ] Add to `deferred-work.md`: the session-persistence limitation (in-process, single-worker, lost on `--reload`); no CI lane runs `pytest` or `npm test`; and anything Task 3's `model_substitutions` work had to leave open.

## Dev Notes

### The bug you will otherwise ship

`Composer.compose()` makes up to **four sequential blocking LLM round-trips** (`composer.py:106-126`) and there is **no async support anywhere** in the core — `LLMProvider.complete_structured` is sync (`ports/llm_provider.py:25`), the Anthropic adapter uses the blocking client with forced tool-use (`anthropic_provider.py:48`), and grep finds no `async`/`await` in `team_maker/` outside a codegen template.

Declaring a path operation `async def` and calling into that blocks the event loop for the entire duration — **the whole API stops serving, including `/api/health`**. Declare handlers `def` and let FastAPI's threadpool handle them, or wrap explicitly in `anyio.to_thread.run_sync`. AC 3 requires a test that proves it, because the failure mode is invisible in single-request manual testing.

### What the Python core actually gives you — verified by reading it

The **entire** public Composer surface is three names (`team_maker/composer/__init__.py:4-7`):

```python
class Composer:
    def __init__(self, provider: LLMProvider, *, max_repair_attempts: int = 3,
                 key_config: KeyConfig | None = None) -> None
    def compose(self, intent: str, *, preferences: str | None = None) -> TeamCreationRequest

class ComposerSession:
    def __init__(self, composer: Composer) -> None
    current: TeamCreationRequest | None          # the only public attribute
    def start(self, intent: str) -> TeamCreationRequest
    def refine(self, message: str) -> TeamCreationRequest    # RuntimeError if before start()

class ComposerError(Exception):
    errors: list[str]                            # "loc → path: msg" strings, NOT structured
```

Facts that will surprise you:

- **There is no chat history.** `ComposerSession` holds exactly two things: the *original* intent and the *current* spec (`session.py:22-23`). Each turn re-sends `original intent + full current spec as JSON + the new message` in a single stateless call (`session.py:46-56`). Turns 2..N-1 are discarded. **The client owns the transcript** — the model does not remember turn 2 when it reaches turn 4. Do not try to make the API return a transcript it does not have.
- **A "turn" is 1–4 LLM calls, blocking, with no progress signal.** No streaming, no repair-attempt callback (`deferred-work.md:48`). Expect multi-second silent latency per request, and set client timeouts accordingly.
- **The repair loop catches only `pydantic.ValidationError`** (`composer.py:115`). A network blip, rate limit, missing key, or the adapter's own `ValueError` (`anthropic_provider.py:74-79`) gets **zero retries** and propagates raw. AC 8 is why.
- **`ComposerError.errors` is `list[str]`, not structured.** Field-addressable errors need either re-parsing `"desired_roles → 0 → name: msg"` or re-validating against the Pydantic model. This is Task 3 and it is genuinely new work.
- **`refine()` leaves `session.current` intact on failure** (`session.py:41-44`) — Story 1.3's AC 6. Preserve that contract.
- **`preferences` is unreachable through `ComposerSession`** — only `Composer.compose()` takes it. If a future story wants it, that is a session-API change.
- **`TeamCreationRequest._pre_process`** (a `@model_validator(mode="before")`, `request.py:271-354`) silently rewrites input in five ways. **Edited JSON in ≠ JSON out.** Return the re-serialised server spec as authoritative; clients must re-render from the response, not from their local edit.
- **Authoring is hardcoded to Anthropic in the CLI** (`cli.py:37-38`) — `--model` overrides the model string only, and there is no `--provider`. **This story does not inherit that.** AC 10 makes the API's authoring provider parametric through `create_provider`, so a user with only an OpenAI key, only an OpenRouter key, or only a local Ollama can compose. Note the asymmetry that remains: **the CLI stays Anthropic-only**, because `team_maker/cli.py` is outside this story's scope. Flag it in Completion Notes as a follow-up so `compose --provider` gets an owner.
- **`report_availability` reports *team-run* availability, not authoring availability** (`registry.py`). Do not use it to decide whether the Composer can run; check the chosen authoring provider's own catalog row and credential.

### The build path, and two traps inside it

Between "spec is valid" and "package built", the CLI does almost nothing (`cli.py:316-339`): dump YAML, then `PipelineRunner().run(request)`. **There is no key check, no preflight, no confirmation** — Story 1.6's credential gate covers `team-maker run` only, not `compose --build`.

Inside `PipelineRunner.run`, two things will bite an API:

1. **`normalize_team_routings(team)`** (`runner.py:144-145`) makes **live network calls** to each provider's `models.list()` and may **silently substitute the chosen model** with a fuzzy nearest match, reporting it only to **stderr** (`model_resolver.py:156-185`). That is why AC 2's build response carries `model_substitutions`. It is also called with no config, so it re-reads the *default* Key Config path and **ignores any explicit key file** — relevant once a request can name one.
2. **An empty `desired_roles` flips the build into a second LLM call** through `planning_llm`, a different provider config (`runner.py:66-69`, `llm/planner.py:24-46`). The `PUT .../spec` route should reject an empty roles list, or the cost is silent.

`PipelineResult` is `{ output_path: Path, team: GeneratedTeam, written_files: list[str], validation: ValidationResult }` (`runner.py:38-43`); `ValidationResult` is `{ passed: bool, issues: list[str], warnings: list[str] }`. `output_path` is an **absolute server-side filesystem path** (`utils/fs.py:8-10`) and `overwrite` defaults to `False` → `FileExistsError`, which AC 2 maps to `output_exists`.

### Dev topology

Two processes. There is no existing tooling that suggests otherwise: `Makefile:39` says only *"no backend yet"*, `scripts/` holds one smoke test for generated packages, `team_maker/codegen/templates/docker-compose.yml.j2` is **generated output for team packages** (its own header says *"generated by team_maker"*), and `langfuse/docker-compose.yml` is an optional dev observability sidecar.

**Use Next's `rewrites` proxy, not CORS.** The browser sees same-origin `/api/...`; Next proxies server-side. That removes preflight, credentials-mode and `Access-Control-*` debugging entirely, and it matches AD-3's eventual one-process distribution story (*"the web UI served by the backend"*). `rewrites` is intact in Next 16 — the authoritative docs are bundled at `web/node_modules/next/dist/docs/`, which `web/AGENTS.md` designates over training data.

Port note: use **8000** for the API (uvicorn's default), never 3001 — that is `next dev`'s own fallback port. `langfuse/docker-compose.yml` has no `ports:` mapping and runs `network_mode: host` (`:22,:34`), so on a Linux host with that optional stack up, Langfuse's 3000 listener (`:7,:41`) pushes `next dev` to 3001. Read the frontend origin from env; never hard-code it.

### The stack — verified against current releases, August 2026

- **FastAPI 0.141.1** is current. The spine's `0.139.x` pin (`:171`) is **two minors stale**; 0.140.x fixed SSE status codes and event-line-splitting. Pin `>=0.141,<0.142`.
- **Uvicorn 0.52.1**, `requires_python >=3.10` — compatible with this repo's `>=3.10`. Absent from the spine's stack table. Plain `uvicorn` keeps the dependency surface small; `uvloop` (in `[standard]`) is unavailable on Windows anyway.
- **Already installed transitively:** `uvicorn 0.52.0`, `starlette 1.3.1`, `httpx 0.28.1`, `pydantic 2.12.5` — pulled in by `mcp` from the crewai tree. This is why AC 5 demands a resolution check rather than assuming the pin is additive.
- **Next 16**: `params`/`searchParams` are always `Promise`. React Compiler stays off.

Known but **deliberately not used here**: FastAPI has native SSE from ~0.135 (`fastapi.sse.EventSourceResponse`) — streaming is AD-13-deferred, so shape responses as a discriminated envelope and stop there; FastAPI 0.137 made `router.routes` a tree, so don't write a route-enumerating test; Next 16 renamed Middleware to **Proxy** (root `proxy.ts`, Node runtime) which is explicitly *"not intended for slow data fetching"* — no compose call may go there.

### Previous story intelligence — the defect classes this codebase actually produces

Story 2.1's review returned **27 patches, 4 decisions, 1 deferral** on a story whose own Dev Notes had warned about the exact defects it then shipped. Its commit body says it plainly: *"Writing the warning down was not enough to avoid it."*

1. **The guard that cannot fail.** 2.1's Guard B protected its self-declared highest-risk decision and caught nothing. **Feed every new guard a fixture where the property is violated and watch it go red before trusting a green run.** Here: the AC 4 sentinel test and the AC 8 no-stack-trace test must both be proven against a response that violates them.
2. **Values and tests true by construction.** Deleting a `setTimeout` left 8/8 green; asserting a string was *absent* passed on a component returning `null`. This is why AC 2 forbids a `validation` field on the compose responses — it would always be `true`.
3. **Measuring a mirror.** The contrast test read a hand-maintained copy of the tokens rather than the shipped file. Do not build a second source of truth for the spec shape; `TeamCreationRequest` is the only one.
4. **A guard narrower than its claim.** The colour scanner walked two directories and missed the one holding the literals. Check that any assertion's scope matches its claim.
5. **A comment is a testable assertion.** Don't write "no exception text reaches the client" unless a test proves it for every error path.
6. **Declared deviations get audited.** 2.1's deviation 2 was withdrawn in review as wrong. Declare everything; expect the reason to be checked.
7. **Self-reported figures must be measured.** A "correction" to a ruff count confused two scopes. Paste real command tails.
8. **Undeclared stubs change what is tested.** Name every stub in Completion Notes.

### Project conventions (must follow)

- **`team_maker/`'s existing modules stay behaviourally frozen.** This story adds `api/`, `tests/api/` and `tests/support/fake_llm.py`, and touches two existing test files to re-point that import. Anything more under `team_maker/` is a scope change — declare it loudly (Task 2 and Task 3 each name a case where you might be tempted).
- **Environment:** `./.venv` (Python 3.13.13) for `pytest`/`ruff`/`make`.
- **Lint only what you touch.** `ruff check team_maker/` reports **9** pre-existing findings; `tests/` adds 29, for 38 across both — two different scopes, which Story 2.1 initially conflated and had to correct. Leave the drift; `api/` must be clean.
- Python: `from __future__ import annotations`, full type hints, ruff line-length 100, rule sets `E,F,I,N,W`.
- Per CLAUDE.md: files small and cohesive (~200–400 lines); tests grouped by responsibility in directories; **label every mock/stub explicitly and never report a mocked integration as proof the real one works.**
- Commit rhythm: one `feat(story-2.0)` for code+tests, one `docs(story-2.0)` for this file and `deferred-work.md`. Linear history, no merge commits. Long-form bodies explaining *why*, ending `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`.

### Git intelligence

`725b475` docs(story-2.1) · `d4dfa55` feat(story-2.1) · `a489334` Merge epic_1 into develop (the only merge commit).

`epic_2` and `story_2_1` both point at `725b475` and are pushed. `develop` remains at `a489334` — Epic 2 folds into `develop` once, after the whole epic. Cut `story_2_0` from `epic_2`.

There is **no `sprint-status.yaml`** and no `_bmad/` scaffold in this repo; status is tracked inline in this file's `Status:` field.

### Project Structure Notes

```text
api/                        # NEW — the L2 layer AD-4 requires
  __init__.py
  main.py                   # FastAPI() + lifespan + /api/health + router include
  deps.py                   # KeyConfig, authoring provider, credential bridge
  schemas.py                # request/response envelopes (NOT raw TeamCreationRequest)
  errors.py                 # ComposerError.errors -> fields[]; the error envelope
  routers/
    __init__.py
    compose.py              # the four compose routes
tests/api/                  # NEW — __init__.py + conftest.py (key isolation) + endpoint tests
tests/support/fake_llm.py   # NEW — FakeLLMProvider promoted out of tests/unit/test_composer.py
team_maker/adapters/providers/
  openrouter_provider.py    # NEW (AC 11) — OpenAI-compatible, templated on xai_provider.py
  __init__.py               # MODIFIED — one new _ADAPTERS row; no other change
```

- **Modified (repo root, declared):** `pyproject.toml` (AC 5), `Makefile` (`api-dev`, `api-serve`, lint/fmt scope), `README.md`, `web/next.config.ts` (the rewrite — the only `web/` source change), `project-docs/stories/deferred-work.md`.
- **Modified (declared, sanctioned by CLAUDE.md's reorganise-as-you-go rule):** `tests/unit/test_composer.py` and `tests/unit/test_composer_session.py`, re-pointed at `tests/support/fake_llm.py`.
- **Untouched:** everything under `team_maker/`, `tests/integration|conformance`, all of `web/app|components|lib|tests`, `examples/`, `scripts/`, `assets/`.

### References

- [Source: project-docs/architecture/architecture-team_maker-2026-07-05/ARCHITECTURE-SPINE.md:67-71] AD-4; [:60-65] AD-3; [:113-119] AD-8; [:121-126] AD-9; [:128-133] AD-10; [:135-140] AD-11; [:150-154] AD-13; [:167-177] Stack; [:181-197] Structural Seed; [:201-210] Capability Map; [:212-226] Deferred
- [Source: project-docs/epics.md:402-428] Epic 4's endpoint stories; [:135-141] Epic 2 scope; [:112-114] FR-23–FR-26
- [Source: team_maker/composer/composer.py, session.py] the API being wrapped; [team_maker/cli.py:37-38,177-213,216-350] authoring resolution, the credential bridge, `compose` end to end; [schema/request.py:174-395] the spec; [pipeline/runner.py:38-43,62-97,144-145] the build; [llm/model_resolver.py:156-185] model substitution
- [Source: project-docs/stories/1-2-compose-team-spec.md, 1-3-conversational-tuning-run-now.md] the Composer contracts this story must honour
- [Source: project-docs/stories/2-1-app-shell-sidebar-theming.md] the shipped frontend and its review's defect classes
- [Source: project-docs/stories/deferred-work.md:42-58] inherited Composer gaps
- [Source: CLAUDE.md] structure, test organization, test transparency, file size
- [Source: https://fastapi.tiangolo.com/release-notes/ · https://pypi.org/pypi/fastapi/json · https://pypi.org/pypi/uvicorn/json] current versions
- [Source: web/node_modules/next/dist/docs/] Next 16 `rewrites` — authoritative per `web/AGENTS.md`

### Open questions for the PM / architect (not blocking implementation)

1. ~~**Nobody owned the FastAPI app.**~~ **Resolved.** `epics.md` now records that this story creates the app, and assigns every group in the Structural Seed's `api/` scope: **key status → 2.3**, **run → 2.4**, **teams → 2.5**, **settings → 2.6**, **the public versioned contract → Epic 4**. No part of `api/` is orphaned. Confirm the assignment if you disagree with any row.
2. ~~**A user with only an OpenAI key gets a dead Composer.**~~ **Resolved by AC 10/11** — the authoring provider is now parametric (default `anthropic`; any `create_provider` id, incl. a new `openrouter` adapter and keyless `ollama`). Two things remain to confirm: (a) Story 2.3 owns the *user-facing copy* for `authoring_unavailable`, and (b) **the CLI stays Anthropic-only** — `compose --provider` has no owner, and the CLI/API asymmetry should get one.
3. **Are these endpoints the public contract or an internal precursor?** This story assumes internal and namespaces them `/api/compose/...`. Confirm before Epic 4 designs `/v1/...` on top.
4. **Session identity vs "Team reference."** PRD Open Question 3 (a stable Team reference for v1) is still open. `session_id` is deliberately *not* that — confirm it stays separate.
5. **Should `api/` be served by FastAPI in production?** AD-3 says *"the web UI served by the backend"*, and FastAPI 0.141 added `app.frontend()` for exactly this. Out of scope here, but worth settling before packaging.

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List

## Change Log

- 2026-08-03 — Story created by splitting the original Story 2.2 in two, on the finding that 2.2 could not be a UI-only story: AD-4 admits no exception to *"the UI reaches the system only through the API"*, no `api/` layer exists, and **no story anywhere in the plan creates one** (Epic 4's Story 4.1 opens *"Given the API is running"*). Numbered `2.0` as an enabler rather than renumbering 2.3–2.7, because 45 cross-references to those numbers exist across 6 files, four of them already-accepted stories. The `0` follows this repo's own Epic 0 precedent for work that must land before features. Research established the contract concretely: the four compose routes with full request/response shapes, a seven-code error envelope, and the reasons a naive implementation breaks — handlers must be `def` not `async def` or the event loop stalls on a 1–4-call blocking Composer turn; `_bridged_credential`'s `os.environ` mutation races under threadpool concurrency; `ComposerSession` keeps no chat history so the client owns the transcript; `ComposerError.errors` is unstructured so field-addressable errors are new work; `pyproject.toml`'s `include = ["team_maker*"]` would leave `api/` silently unpackaged; and `uvicorn`/`starlette` are already present transitively via crewai's `mcp`, so the FastAPI pin needs a resolution test. Status → ready-for-dev.
- 2026-08-03 — **Two spec changes on top of the split.** (1) **`api/` ownership assigned.** `epics.md` now maps every group in the Structural Seed's `api/` scope to a story — the app + compose/create here, key status → 2.3, run → 2.4, teams → 2.5, settings → 2.6, the public versioned contract → Epic 4 — closing the orphan this story surfaced. (2) **The authoring provider is now parametric** (AC 10). It was hardcoded to Anthropic, inherited from `cli.py:37-38`, which meant a user holding only an OpenAI, OpenRouter or local-model setup had a dead Composer. Default stays `anthropic`/`claude-sonnet-4-6`, but any id `create_provider` resolves is selectable, across three shapes: direct provider, OpenRouter gateway, and keyless local (`ollama`, which must never be refused for a missing key). Selection arrives as an optional `authoring` object on session-create; **the key never does** — AD-9 stands, and the server resolves the credential from the Key Config catalog row. This also retires the spine's Deferred entry *"Composer default model — configurable behind LLMProvider; concrete default TBD"* (`:223`). Verified against the code rather than assumed: **there is no OpenRouter adapter** — `_ADAPTERS` resolves only `anthropic, openai, xai, google, ollama`, and the `openrouter` row in `registry.py:105` exists only as a routing gateway for team agents — so AC 11 adds one new adapter file plus one registry row, templated on the existing OpenAI-compatible `xai_provider.py`. That is the sole permitted addition under `team_maker/`. Residual asymmetry flagged rather than silently fixed: the **CLI stays Anthropic-only**, since `cli.py` is outside this story's scope.
