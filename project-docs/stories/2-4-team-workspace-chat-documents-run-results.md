---
baseline_commit: 0fd5348
---

# Story 2.4: Team Workspace — chat, documents, run, results

Status: in-progress

## Story

As a user,
I want to use a built team in one place,
so that I can give it goals, add context, and read outputs together.

## Dependency

**Stories 1.5, 1.7, 2.0, 2.1, 2.2 and 2.3 are all `done` and merged into their epic branches.** This story is the first to make the **run path remotely reachable**. Story 2.0's change log names that exact transition as the source of its three worst findings: *"this story converts local CLI-authoring behaviour into a remotely reachable primitive, and three of the four worst findings were pre-existing `team_maker/` looseness that was harmless behind a CLI and is not harmless behind an unauthenticated HTTP endpoint."* Read that sentence twice. It is this story's headline risk, one layer deeper.

Read, in this order, before writing code:

1. `project-docs/stories/2-0-api-seam-compose-endpoints.md` — **Review Findings** and **Completion Notes**. The error envelope, the containment regime, `AppState`/lifespan, and AC 13's server-owned output path are authoritative there.
2. `project-docs/stories/1-5-run-team-return-results.md` and `1-7-capture-run-transcript.md` — the result and transcript contracts you are surfacing. 1.7's Dev Notes were written *for you*; its Open Question 3 asks you a direct question (AC 14).
3. `project-docs/stories/2-3-key-check-states-plain-language-errors.md` — **Completion Notes** and **Post-Review Notes**. Its four review Decisions, and the copy and gate patterns you extend.
4. `project-docs/stories/deferred-work.md` — `:77`, `:95`, `:96`, `:101`, `:102`, `:108`, `:110`, `:111`, `:112`, `:129`, `:154`, `:155`, `:165`, `:166`, `:171`, `:172`, `:184`, `:202` all land on this story.

### Three things are broken or absent, and the story is not honest without saying so

Each was **measured in this working tree at `0fd5348`**, not inferred. Re-measure before you build on them; if any has changed, say so.

**1. The user's goal never reaches any agent.** `crewai_execution_engine.py:80` calls `crew.kickoff(inputs={"goal": goal})`, and crewai's `inputs` are a *placeholder interpolation* map. A grep for `{goal}` across `team_maker/**/*.py`, `*.j2` and `*.yaml` returns **zero matches**, and the packages the Factory actually produces confirm it — `generated_teams/haiku_team/tasks/write_haiku.yaml` reads `Write an original haiku about the sea…` with no token. So the goal string is interpolated into nothing and the team re-executes its baked-in task descriptions. This is invisible from the CLI, where the goal and the package were authored together by the same person in the same minute. **This story is the first surface where a user types a goal into a box and presses a button**, and it cannot satisfy its own AC by passing that string to `run_team_package`. AC 5 is the fix.

**2. Attached documents have no path to an agent, and the one that looks like a path is not one.** `AgentSpec.tools` is loaded by `loader.py:93` and then dropped: `crewai_execution_engine._build_agent` (`:130-138`) constructs `Agent(role=, goal=, backstory=, llm=, allow_delegation=)` with **no `tools=` argument at all**. So the `context_reader` tool the Factory bakes into a package's `tools.py` is unreachable from the in-process engine. `TeamCreationRequest.context_dir` is also not it: it is build-time, server-path-based, and its validator requires the directory to already exist on the server. **Document support is built from nothing.** AC 5 and AC 6.

**3. There is no run endpoint, no run identity, and no way to observe a run in flight.** `api/routers/` is exactly `compose.py` and `keys.py`. `run_team_package` is synchronous and blocking, has no timeout, no cancellation and no progress callback; `TranscriptRecorder` is local to the engine call (`crewai_execution_engine.py:79`) and un-inspectable from outside. `deferred-work.md:102` records, *measured*, that two concurrent runs in one process corrupt each other's transcripts because the crewai event bus is a process-global singleton.

### The core already answers most of this. Do not build a second answer.

`run_team_package(package_path, goal, key_config, engine=None)` (`team_maker/runtime/executor.py:29-56`) already gives you, for free: the framework check, the **AD-9 pre-run credential gate** (`check_credentials` at `:47`, whose comment says *"Doing it here — rather than inside an engine — means every caller (CLI today, API in Epic 4) inherits fail-fast"*), DAG ordering, and unconditional transcript capture. `describe_unresolved_provider` is documented as *"the only fix-hint generator in the system"* — and `check_credentials` **already calls it** (`preflight.py:117-122`), so `MissingCredentialsError.unresolved` hands you finished `UnresolvedProvider` objects. Read them; do not rebuild them. `keystatus.provider_reports` / `credential_source` are the one projection of `registry.classify()` and the only legal source for a per-agent key badge.

Re-deriving any of these is the **"measuring a mirror"** defect class this repo has shipped three times. Do not.

**One helper that looks reusable and is not:** `api/routings.py`'s `requested_routings` takes a `TeamCreationRequest` and runs the template to discover what each role *asked for* at compose time. The run path has neither — it has a **built package**, whose routings are already concrete in `routing_config.yaml` and are on `AgentSpec.routing` after `load_team_package`. Read them from the loaded team. Calling `requested_routings` here would re-answer a question the package has already answered.

## Acceptance Criteria

### The API — the `run` group

1. **Given** `epics.md:335` assigns the **run** group to this story and `api/routers/__init__.py:1` says *"One module per group in the Structural Seed's `api/` scope"*, **When** this story lands, **Then** a new `api/routers/run.py` defines `router = APIRouter(prefix="/runs", tags=["runs"])`, is imported at `api/main.py:31-32` and mounted with `app.include_router(run_router, prefix="/api")` before `_register_error_handlers(app)`, and declares `logger = logging.getLogger("api.runs")`. It exposes exactly four routes:

   | Method | Path | Returns |
   |---|---|---|
   | `GET` | `/api/runs/teams/{team_slug}` | `TeamPlanView` — the runnable view of a built package |
   | `POST` | `/api/runs` | `RunView` with `status: "running"` |
   | `GET` | `/api/runs/{run_id}` | `RunView` — `running` \| `complete` \| `failed` |
   | `GET` | `/api/runs/{run_id}/transcript` | `TranscriptView` |

   **Every handler is `def`, not `async def`** (`compose.py:3-10`, `keys.py:7-9`; the `health()` exemption at `main.py:44-54` applies only to a handler doing no I/O), and every handler's first statement is `state = app_state(request)` — there is no `Depends()` anywhere in `api/` and this story adds none.

   **Declare `/api/runs/teams/{team_slug}` before `/api/runs/{run_id}`.** Both are two segments under `/runs`, so FastAPI resolves them **by declaration order** — with the parameterised route first, a request for `teams` binds `run_id="teams"` and the plan route becomes unreachable. Pin the order and test it.

   **`GET /api/runs/teams/{team_slug}` stays inside this story's group deliberately.** `epics.md:336` assigns the `teams` group to Story 2.5, so this story does **not** create `api/routers/teams.py` and does not claim `/api/teams`. But a Workspace cannot render a task list for a team it cannot read, and `EXPERIENCE.md:75` requires one row per task in DAG order showing agent and model. Scope it to exactly what running needs — team name, agents (`role`, `provider`, `model`), tasks in topological order with their `agent_role` and `dependencies` — and **declare it**, noting 2.5 may consolidate it into `/api/teams`. Adding list/save/rename/delete here is out of scope (AC 15).

   **`TeamPlanView` carries each agent's key status, computed server-side.** `EXPERIENCE.md:72` wants provider badges tinted by key-check state, and Story 2.3's existing check is **`GET /api/keys/check/{session_id}`** — session-bound, and **the Workspace has no session**. Do not invent a client-side join against `GET /api/keys/status`; that would be a second availability rule, which `api/keystatus.py:1-21` forbids in the strongest terms. Project each agent's `AgentSpec.routing.provider` through `keystatus.provider_reports` / `fix_hint_for` on the server and return `status`, `detail`, `usable` and `fix_hint` per agent — the same fields, from the same source, as the Composer's badges.

2. **Given** a `session_id` is not a durable team handle — `sessions.py:19-23` (in-process dict, single-worker), `:144-149` (*"an evicted id is indistinguishable from one that never existed"*), 30-minute idle TTL, 32-session LRU — and `addendum.md:38-39` says the minimal v1 team reference is *"by output path / generated id"*, **When** a client names a team, **Then** it names a **slug**, never a path. The server resolves it as `output_root() / slugify_team_name(team_slug)` using the existing `api/output.py` functions, and:

   - The client-supplied value is **re-slugged, never trusted** — `slugify_team_name` is documented as *"A single safe path segment. Never empty, never a traversal."* (`output.py:55-58`).
   - The resolved path is additionally asserted to be **inside `output_root()`** before any read. Defence in depth is not optional here: Story 2.0's review found a **verified, browser-reachable path traversal** (`PUT /spec` with a task named `../../ESCAPED`, then `POST /build`, wrote outside `output_path`). A second, independent check is the response to having shipped that once.
   - A slug that resolves to no package, or to a directory `load_team_package` rejects with **`TeamPackageError`** (`team_maker/runtime/loader.py:17`), is `team_not_found` (404) — not a 500, and not a message that echoes a filesystem path.
   - The slug is echoed into no log line or message without `safe_label()` (`deps.py:148-157`) — *"a provider id containing a newline forges a log record"*.

   **Declare this reference as provisional.** PRD Open Q3 is open and `epics.md:414` says Story 2.5 settles it. Record in Completion Notes that 2.4 chose the slug, why, and that 2.5 may replace it.

3. **Given** `deferred-work.md:102` — *"two simultaneous `run_team_package` calls each record the other's events… run A came back with every entry duplicated, run B lost an entry and gained a `task='unknown'`, and the two runs' `emission_sequence` values collided outright"*, measured with a barrier during the 1.7 review — and given `epics.md:391-393` instructs that *"a run endpoint must serialise runs or scope capture per run"*, **When** a run is requested while another is in flight, **Then** the second request is refused immediately with `run_in_progress` (409) and an authored sentence; it does **not** queue, does **not** block a thread, and does **not** start.

   **Serialise. Do not attempt per-run event filtering.** The corruption has three independent causes and filtering fixes only one: handler fan-out on the global bus; `emission_sequence` being ContextVar-scoped and restarting at 1 per run, so sorting cannot separate two runs; and `TranscriptRecorder.__exit__`'s `crewai_event_bus.flush()` waiting on *all* process-wide pending futures. A process-wide lock is the only option that fixes all three and the only one requiring **zero** change under `team_maker/`. The API is already pinned single-worker (`Makefile:57-58`, `main.py:208-252`, `deferred-work.md:129`), so a process-wide lock is a system-wide lock.

   Record in Completion Notes that concurrency is **one run per process**, and that this is a serialisation, not a fix — `deferred-work.md:102` stays open.

4. **Given** `run_team_package` is synchronous and unbounded — an LLM-driven multi-agent DAG, minutes, no timeout, no cancellation, and **no performance NFR exists anywhere in this project** (`epics.md:70-77` has seven NFRs and none is about latency) — and given a `def` handler occupies one of the 40 anyio threadpool slots for its whole duration (`main.py:46-51`), **When** a run is started, **Then** `POST /api/runs` **returns immediately** with a `run_id` and `status: "running"`, the run executes on a **dedicated `threading.Thread` owned by a run registry** (not the anyio pool), and the client learns the outcome by polling `GET /api/runs/{run_id}`.

   This is the designed use of the discriminator, not an invention: `schemas.py:16-17` says *"Responses carry a ``status`` discriminator so AD-13's later streaming retrofit can add a variant instead of breaking the contract."* A run is its first genuine consumer. `status: Literal["running", "complete", "failed"]`.

   It also satisfies AD-13 without bending it: the **results interface stays batch** (`ARCHITECTURE-SPINE.md:150-154` — *"v1 returns final + per-task outputs in batch through a results interface shaped to later stream"*). Polling delivers a batch result on completion. It does not stream.

   `RunView`'s fields, so two dev agents build the same thing: `status` (`"running" | "complete" | "failed"`), `run_id`, `team_slug`, `team_name`, `tasks[]` (the same shape as `TeamPlanView`'s, so the UI renders one list before and after), `result` (`null` until `complete`: `final_output` plus `task_results[]` of `{name, agent_role, output}`), `transcript_available` (bool), and `failure_reason` (`null` unless `failed`; **authored copy, never `str(exc)`** — the envelope rule at `errors.py:5-8` binds a failure sentence inside a 200 body exactly as it binds one inside an error). The goal and the attached documents are **not** echoed back.

   Consequences to honour:
   - `AppState` is `@dataclass(frozen=True)` with **five** fields today (`state.py:17-29`). This story appends **two**: the run registry (AC 4) and the execution-engine seam (AC 9). Both are set in the lifespan at `main.py:86-96`, never as post-hoc attributes. Note `file_providers` (`state.py:29`) already carries a default, so **any field appended after it needs one too** or the dataclass will not construct.
   - **The lifespan has no shutdown branch today** — there is nothing after `yield` at `main.py:97`. A thread that outlives the app is a new class of leak. Add one, and say what it does with a run still in flight (join with a bound, or abandon and log — decide and declare; do not silently do neither).
   - `main.py:209-215`'s `_warn_on_multiple_workers` docstring says *"Compose sessions live in an in-process dict"*. That sentence becomes incomplete the moment run state joins it. Update it. **A docstring is a testable assertion** — defect class 5.
   - Bound the registry the way `SessionRegistry` is bounded (`sessions.py:44-69`): a max record count, an idle TTL, and an **injectable clock** (`clock: Callable[[], float] = time.monotonic`) so eviction is testable without sleeping. An unbounded dict of completed runs each holding a full transcript is the next unbounded resource.
   - **Eviction makes an unknown `run_id` a normal outcome, not an anomaly** — the same reasoning as `sessions.py:144-149` (*"an evicted id is indistinguishable from one that never existed — which is the point"*). It therefore needs a real code: `run_not_found` (AC 8). Do not reuse `session_not_found`; a run is not a conversation, and `errors.py:37-44` says the framework-level `NOT_FOUND` is *"Not raisable by any authored route"*.
   - `api/runs.py` is the registry's home — a sibling of `api/sessions.py`, same shape, not an extension of it. A compose session and a run are different objects with different lifetimes.

5. **Given** finding 1 in the Dependency section — the goal is interpolated into nothing and never reaches an agent — **When** a run starts, **Then** the goal genuinely reaches the agents, by **augmenting the in-memory `GeneratedTeam` before the engine sees it**, and by no other means.

   Constraints, all binding:
   - **`ExecutionEngine.run`'s signature does not change.** Story 1.7 AC 7 pins it: *"a future story adds per-turn streaming… requires **no change to `ExecutionEngine.run`'s signature and no change to the transcript entry type**"*. The augmentation happens *before* the engine, on the team object. The port, the engine and the transcript entry type are untouched.
   - **Do not edit the Factory, the generators, or any template.** Emitting a `{goal}` token from `team_maker/generators/` would change every generated package and put `test_pipeline_is_idempotent` at risk, and it would not help the packages already on disk. `project-context.md:30-32` is explicit: generators are pure string producers, and the pipeline's byte-identical output is a tested contract.
   - **The goal text lands in `TaskSpec.description`**, not in `expected_output` and not on the agent. An agent's `goal`/`backstory` are its standing identity across every run; the user's goal belongs to *this* run's work. Naming the field here is deliberate — left open, two implementations would differ and AC 5's "reached a real prompt" test would pass or fail for reasons unrelated to correctness.
   - **Do not mutate the loaded object in place, and beware that these dataclasses are mutable.** `GeneratedTeam` (`domain/models.py:110`), `AgentSpec` (`:88`) and `TaskSpec` (`:58`) are plain `@dataclass` — only `ProviderRouting` (`:29`) is frozen. A `dataclasses.replace()` on the team still shares the *same* `TaskSpec` objects, so writing a description through it mutates the caller's team. Build new `TaskSpec` instances. `executor.py:3-4` (*"Never mutates the package, never decides team membership/roles — Runtime executes only"*) and AD-5 both bind.
   - Put it in a new pure module — `team_maker/runtime/run_context.py` is the natural home, beside `ordering.py` and `results.py`. No disk, no network, no clock. `run_team_package` grows a **keyword-only** `documents` parameter defaulting to empty, so every existing caller (`cli.py:428`, the tests) is unaffected.

   **Two things must be measured, not reasoned about, before you choose where the text goes:**

   - **Does a literal `{` or `}` in the goal or a document break the run?** crewai interpolates `inputs` into task descriptions. If you inject user text into a description and then still pass `inputs=`, a brace in a pasted document is a plausible `KeyError` mid-run. Determine empirically whether omitting `inputs` skips interpolation entirely, and whether braces then pass through safely. **Record the probe and its output.** If `inputs` becomes dead weight once the goal is injected directly, remove it — and update `tests/unit/adapters/test_crewai_execution_engine.py:232-245` deliberately, preserving its intent (*"the goal reaches the run"*), not deleting it.
   - **Does the goal actually change what the agents produce?** A test that asserts the goal string appears in a task description proves plumbing, not effect. The conformance harness (`tests/support/crewai_interception.py`) records every `BaseLLM.call`; assert the goal text is **in a prompt an agent was actually called with**. That is the difference between this story fixing the defect and this story moving it.

   State plainly in Completion Notes which tasks receive the goal (the first in topological order, or every task) and what that costs in tokens. Every agent seeing the goal is defensible; pretending the choice is free is not.

6. **Given** FR-24 (`prd.md:362-366`), AD-11 (`ARCHITECTURE-SPINE.md:138-140` — *"attached documents are transient to a run/session (not persisted)"*) and the Glossary (`prd.md:117-118`), and given `ARCHITECTURE-SPINE.md:224` **defers the mechanism and the limits** (*"Document handling mechanism — in-context vs retrieval, size/type limits (PRD Open Q6)"*), **When** documents are attached, **Then** this story **closes PRD Open Q6** with the following decisions, each declared with its reason:

   - **Mechanism: in-context.** It is the only v1-legal option — retrieval needs a vector store, which `addendum.md:69-70` and `prd.md:418-419` both place in v2. Documents ride the same `run_context.py` seam as the goal (AC 5).
   - **Transport: JSON text, not `multipart/form-data`.** The browser reads the file with `File.text()` and posts `{"name": …, "text": …}`. The evidence, measured in this tree:
     - **`python-multipart` is not a declared dependency of this project.** `pyproject.toml`'s `api` extra pins `fastapi>=0.141,<0.142` and `uvicorn` only. FastAPI declares `python-multipart` under its `[standard]`/`[all]` extras, which this repo deliberately does not use. Version `0.0.32` is present in `.venv` **solely because `mcp` — a crewai transitive dependency — requires it** (`pip show python-multipart` → `Required-by: mcp`). So `pip install -e ".[api]"` without `[runtime]` produces an API where a `File`/`Form` route fails, and FastAPI raises that at route definition, taking `/api/health` down with it. Depending on it would be an undeclared dependency on someone else's transitive dependency.
     - **Next's proxy buffers the whole body in memory.** Next 16 clones and buffers a proxied request body; `experimental.proxyClientMaxBodySize` defaults to **10 MB**. Raising it means editing `web/next.config.ts`, which **Story 2.0 owns and this story must not change** (AC 15).
     - **Nothing in this repository parses a PDF.** A PDF's bytes read as text are noise that would poison every prompt. Multipart would buy the ability to accept a file whose contents no code can read.
   - **Limits, bounded in `api/schemas.py` where the convention already lives** (`schemas.py:37-42`: *"Every client-supplied string is bounded. Nothing upstream bounds them: Starlette applies no default body-size limit… which turns a text field into a spend amplifier"*): **≤ 5 documents, ≤ 50 000 characters each, ≤ 100 000 characters total**, name bounded by `_MAX_NAME`. Write the reasoning into the constant block in that file's own idiom. These numbers are a decision, not a discovery — say so, and say that no NFR constrains them because none exists.
   - **The goal is bounded too, and must be non-empty.** `deferred-work.md:77` records that nothing validates a non-empty `goal` before `kickoff`, and this is the first surface where one is typed. `min_length=1` after stripping, `max_length=_MAX_PROMPT` (8 000). A blank goal is a `spec_invalid` 422 with a stated reason, not a run that does nothing.
   - **Lifetime: the request and the run record, and nothing else.** Documents are never written to disk, never logged, and are dropped from the run record when the run completes. A test must prove no file appears and the text is gone. Note honestly that document text can reach the **transcript** if an agent quotes it — inherent to in-context injection, and worth one sentence in the notes rather than a false claim of containment.
   - **The UI refuses what it cannot read.** A file that does not decode as text is rejected *at attach time* with a plain-language reason, not attached as garbage. `EXPERIENCE.md:173-174` bans burying a failure.

   **This is a declared deviation from `EXPERIENCE.md:188`** (*"She drags in a reference PDF; it's attached to this run"*). Text-only is what the system can honestly do today. Declare it, escalate it as a PM question (AC 16), and **do not edit `EXPERIENCE.md`**.

7. **Given** `deferred-work.md:184` — *"**Story 2.4 should enforce it server-side when it adds the run endpoint**, which is also the point at which FR-10's 'fail fast at run start' becomes literally true over HTTP"* — and AD-9's rule that *"Key-aware resolution runs **before** any run and fails fast with a plain-language reason"* (`ARCHITECTURE-SPINE.md:126`), **When** a run is requested that cannot proceed, **Then** `POST /api/runs` refuses it with `run_blocked` (409) **synchronously, before the thread is spawned**.

   - The gate is an **early application of the same functions**, never a second rule: `load_team_package` then `preflight.check_credentials`, both public, both already the single source of truth. `run_team_package` will re-run the same check on the thread; that redundancy is deliberate and cheap, and it means no client can reach the engine through a path the gate does not cover. Say so in a comment — otherwise it reads as a duplicated rule.
   - **`check_credentials` already calls `describe_unresolved_provider`** (`preflight.py:117-122`), so `MissingCredentialsError.unresolved` is a tuple of finished, frozen `UnresolvedProvider` objects carrying `provider`, `roles`, `expected_key` and `reason`. **Read those fields and author the API's sentence from them.** Do not call the generator again on a provider name — that rebuilds an object you were handed. Do not render `str(exc)` either: that is `preflight._render_message`, CLI copy, and `errors.py:5-8` forbids it.
   - **Do not reach for `keystatus.blocking_reason` here.** It authors the Composer's sentence from `list[RoleReport]` (`keystatus.py:345-393`), which is produced by `role_reports(...)` from a compose session's requested routings. Bridging a `GeneratedTeam` into that shape is a second path to the same sentence for a different surface. The **pre-run badges** in `TeamPlanView` (AC 1) already carry `keystatus`'s per-provider projection; the **refusal** is authored from `.unresolved`. Two surfaces, two shapes, one availability rule underneath — say which you used where.
   - **`run_blocked` covers three distinct causes, each with its own sentence.** The code is shared because the client's handling is identical (refuse, state why); the copy must not be, because the remedies differ and *"telling someone to add a key that would not help is worse than telling them the truth"*:
     1. **Credentials** — `MissingCredentialsError`. Names the provider, the env var, and the affected roles.
     2. **An internally inconsistent package** — `InvalidPackageError` and its subclasses `DuplicateAgentRoleError` and `InvalidTaskNamesError` (`preflight.py:47,56,68`). No key fixes this; do not say one would. Flattening it into the credential sentence is the "two false statements in sequence" defect the `groq` dead end taught.
     3. **A framework this server cannot execute** — `UnsupportedFrameworkError` (`executor.py:25`), raised for a package built for anything but crewai. `cli.py:429-431` already handles it as its own category. Left unmapped it becomes a 500 for a perfectly legitimate client condition.
   - `deferred-work.md:96`'s dangling `(agents: )` for a role-less `UnresolvedProvider` **has since been fixed** — `preflight.py:242` now renders `"none recorded"`. The entry is stale; close it in `deferred-work.md` rather than inheriting it, and say you verified the fix rather than assuming it.
   - **The build-time gate is still not closed.** `POST .../build` still does not consult the key check (`deferred-work.md:184`), and `deferred-work.md:131`/`:147` record that it also does not guard an empty `desired_roles`. This story closes the *run* gate only. Say which one you closed, and leave the other in `deferred-work.md` rather than widening scope into Story 2.0's route.

8. **Given** `errors.py:23` — `# --- AC 2's authored codes. Adding a row here is a contract change. ----------` — **When** this story adds codes, **Then** it adds exactly **four**, each with a comment in the `SESSION_BUSY` precedent's style (`errors.py:32-35`) naming *why it is not in AC 2's original table*, and each carried through all four files (`api/errors.py` constant, `STATUS_BY_CODE` row, `SERVER_ERROR_CODES` in `web/lib/api-types.ts`, `FALLBACK_MESSAGE` in `web/lib/api-client.ts`):

   | Code | Status | Raised by | Condition |
   |---|---|---|---|
   | `team_not_found` | 404 | plan route, `POST /api/runs` | the slug resolves to no readable Team Package (`TeamPackageError`) |
   | `run_blocked` | 409 | `POST /api/runs` | the run cannot start — credentials, an inconsistent package, or an unrunnable framework (AC 7) |
   | `run_in_progress` | 409 | `POST /api/runs` | another run holds the process lock (AC 3) |
   | `run_not_found` | 404 | `GET /api/runs/{run_id}`, `…/transcript` | an unknown or evicted run id (AC 4) |

   **There is no `run_failed` code, deliberately.** A run that fails does so on a background thread, minutes after `POST /api/runs` returned `200`. There is no request left to attach a 5xx to. Failure is reported as `RunView.status = "failed"` with an authored `failure_reason` on a `200`. Adding an error code nothing can raise would be the *"field that exists, looks load-bearing, and is never read"* class this repo has shipped four times.

   **Declare this as the contract change `errors.py:23` calls it.** A fifth code is a decision to stop and state, not to make quietly.

   The envelope does **not** grow. `tests/api/containment.py:53` pins `_ENVELOPE_KEYS = {"code","message","fields"}` and `fields` is valid only for `spec_invalid` (`errors.py:91-94` raises at construction otherwise). **A `run_id` cannot ride on an error.** A malformed run body needs no new code: `_STRICT` plus the field bounds make it a `spec_invalid` 422 through `_handle_request_validation_error` automatically — note that `main.py:152-158` strips the `body.` prefix, so field paths come out as `documents.0.text`.

   `failure_reason`'s copy is **causally neutral**, following `compose.py:208-217` verbatim in spirit: *"This branch catches everything that is not a ComposerError — a network fault, yes, but equally a TypeError from a bug in this repo. The previous copy… asserted a cause the code has not established."* Do not blame the provider. Log the exception server-side with `logger.exception` and serialise none of it. And **do not catch crewai exception types in `api/`** — the same comment says *"Classifying the exception properly would mean recognising SDK-specific types inside api/, which is precisely what AD-8 keeps out of this layer."*

9. **Given** AD-8/AD-6 keep crewai out of `api/`, and given `routings.py:42-47` documents the pattern — *"a module-scope import would turn any fault reachable from `team_maker.templates` into a server that will not start — including `/api/health`"* — **When** `api/` reaches the runtime, **Then** it calls `team_maker.runtime.executor.run_team_package` and imports nothing from `team_maker/adapters/runtime_crewai/`. Verify that `team_maker.runtime.executor`'s own module-scope imports are crewai-free (its docstring at `:6-9` claims the crewai import is lazy, inside the function body — **confirm it, do not trust it**; a docstring is a testable assertion). If importing `executor` at `api/` module scope can fail on a machine without crewai, import it inside the handler.

   **`create_app` grows a second injection seam.** `main.py:59-65` documents the existing one: *"`provider_factory` exists so tests can inject a fake `LLMProvider` and stay fully offline (AC 9)."* Without the equivalent for execution, `tests/api/` cannot exercise the run routes at all without a real crewai run and real spend. Add an optional execution-engine parameter with the same rationale, threaded through `AppState` to `run_team_package`'s existing `engine=` parameter. Production passes `None` and gets the lazy default, so AD-6 holds.

10. **Given** AD-9, NFR3, and Story 2.0's containment regime, **When** the four routes exist, **Then** no sentinel key value appears in any response body, header or log record of any of them, and the sweep genuinely reaches them:

    - `tests/api/test_secret_containment.py` asserts `authored <= visited` against `/openapi.json`. **A new route not added to `_exercise_every_route` fails this test by design.** Its `_template()` helper normalises only the existing path shapes; `/api/runs/teams/{slug}` and `/api/runs/{id}/transcript` are **both four segments** and a naive by-count rule turns the second into `/api/runs/{id}/{id}`. Add explicit, ordered branches, and add a test that the templating is unambiguous — a normaliser that silently collapses two routes into one makes the coverage assertion pass while covering less.
    - `tests/api/test_health.py:14-40` asserts the OpenAPI path set is **exactly** the authored routes. Seven → **eleven**, updated deliberately.
    - **A run response carries raw LLM output**, which no other route in `api/` does. Sweep `final_output`, every `task_results[].output` and every `transcript[].content` with `assert_no_sentinels` and `assert_no_exception_leak`, using a fake engine that returns a `RunResult` with a sentinel key planted **in the fields that actually render**. `deferred-work.md` records the precedent failure: *"1.6's put it on a provider that resolved cleanly, so the renderer never saw it."*
    - `.get_secret_value()` in `api/` **stays at exactly two call sites, both in `api/deps.py`** (`:220` and `:266`). `grep -rn get_secret_value api/` returns **three** text hits — the third is the explanatory comment at `:213` — so count call sites, not grep lines. Story 2.3 had to correct this exact invariant once already. The engine resolves credentials from the `KeyConfig` object itself; pass the object down and unwrap nothing.
    - `preflight.check_credentials` returns `ResolvedCredential` objects that **do** carry real secrets (`field(repr=False)` exists precisely for that reason). They must not enter the run record, a log line, or a response.
    - `deferred-work.md:108` records that transcript content can carry **ANSI/OSC escape sequences** from an agent echoing colourised tool output or a prompt-injection payload. It reached a terminal before; it now reaches a browser. React escapes HTML, so this is not XSS — but state what you checked rather than assuming, and note that `content` is untrusted LLM text rendered verbatim.

### The Workspace surface

11. **Given** `EXPERIENCE.md:35` (*"Chat with a built Team; upload documents; run against a goal; read results"*), `:74-75` and UX-DR6 (`epics.md:99` — *"Team Workspace layout — chat pane + document loader + task list (accent pulse on active) + results"*), and given Story 2.1 settled that **the Workspace is a surface, not a sidebar destination** (`2-1-…:212`, four nav items, `EXPERIENCE.md:35`), **When** this story lands, **Then** the Workspace lives at `web/app/teams/[slug]/page.tsx` — a **server component** exporting `metadata`, rendering exactly one `"use client"` root in `web/components/workspace/`, with pure logic in `.ts` siblings and `data-slot` on every node a test addresses (namespace them `workspace-…`, `run-…`, `task-…`; do not reuse `composer-…`).

    - **The title is static: `"Team Workspace · team_maker"`.** Putting the team's name in it would need `generateMetadata({ params })`, which means a server-side fetch, which contradicts *"`lib/api-client.ts` is the single place in the frontend that talks to `/api`"*. Every existing route exports a plain object (`web/app/my-teams/page.tsx:7-9`); `web/tests/shell/routes.test.tsx` asserts the `"<Name> · team_maker"` shape. Match it, and declare that the title does not name the team.
    - `web/tests/shell/app-sidebar.test.tsx:23-28` asserts **four** links (the exact `hrefs` array is at `:30-35`). **Both must stay green unchanged** — do not add a nav entry.
    - The user reaches the Workspace from the Composer's build result. `build-result.tsx:14-17` currently says navigating there *"would send the user somewhere that cannot show any of this"* — that sentence becomes false, so **update it**. Render a **link**, not a redirect: Story 2.2 deliberately asserts `router.push` is never called, and auto-navigating would destroy the conversation that produced the team. `EXPERIENCE.md:186`'s *"she's dropped into its workspace"* is not shipped as an automatic navigation; declare that.
    - `web/tests/composer/route.test.tsx:133-136` asserts `not.toMatch(/My Teams|workspace|Adapt with/i)`; `build.test.tsx:414-416` asserts `not.toMatch(/My Teams|workspace/i)` — **two different patterns; do not assume they match**. Amend both **deliberately and narrowly**: `My Teams` and `Adapt with` stay banned (2.5 and 3.2); `workspace` becomes legitimate. `build.test.tsx:411`'s test is *titled* `"does not navigate to a surface that cannot show the outcome"` — that title goes false the moment the Workspace exists, so **rename it to what it still guards** (no automatic navigation). A test title is a claim; defect class 5 applies to it. Keep each guard's falsification (`route.test.tsx:45-48`, `:99-101` — *"Proof the haystack is real"*).
    - Reuse, do not fork: `message-bubble.tsx` was built from `mockups/team-workspace.html:49-58` explicitly *"so it would not diverge from the surface Story 2.4 inherits"*; `transcript.tsx`'s sizing (`min-h-0 flex-1`, never `100vh`), autoscroll-by-sentinel and `role="log"` idiom; `composer-failure.tsx`'s alert shell; `composer-actions.tsx:52-110`'s `aria-disabled` + `aria-describedby` pattern; `proposal.ts`'s `orderedTasks` for DAG ordering. `"Ask a follow-up or refine the goal…"` (`composer-input.tsx:13-18`) is **reserved for this surface** — it is yours; use it.
    - Layout per `EXPERIENCE.md:157-161`: side-by-side at `lg`, stacked at `md`, single column below. Note `vitest.setup.ts`'s `matchMedia` is backed by `window.innerWidth` with `setViewportWidth` — **use it**, and be aware `deferred-work.md:125` records the mobile `Sheet` branch is still unreachable in every test.

12. **Given** `DESIGN.md:79-80` — *"**Signal Teal (`#2DD4BF`)** — accent. Reserved for **"live / running / now"**: the pulse on a running team, the active task in a run. Not for chrome, not decorative."* — and given Story 2.1 shipped `--signal` with an **empty** consumer whitelist naming this story as the first consumer, **When** this story lands, **Then** it adds **exactly one** path to `SIGNAL_CONSUMER_WHITELIST` at `web/tests/theme/signal-token.test.ts:141` — the one line Story 2.1 designed to be flipped (*"Whitelist a path here rather than rewriting this"*) — and Guard B's assertions otherwise stay unmodified.

    - **The test's own title becomes false and must change.** `signal-token.test.ts:143` reads *"finds no source referencing --signal or bg-signal yet"*; with a consumer whitelisted, the assertion still passes while the sentence lies. Rename it to what it now guards (no consumer outside the whitelist). This is defect class 5 again, and it is the one place in this AC where "unmodified" would be the wrong instruction.
    - The whitelist is **per file, not per token** — once whitelisted, every mention in that file is unguarded. Confine the accent to one component.
    - Guard B greps **raw file text**, so even a comment naming the token is a violation elsewhere. Two files document working around this (`thinking-indicator.tsx:17-21`, `key-check.tsx:24-26`); do not undo their care.
    - Guard A (`color-literals.test.ts`) stays green unmodified: `bg-signal` is already an allowed semantic utility (`color-literals.test.ts:61`), and no hex, `oklch()`, palette class or arbitrary colour may appear outside `globals.css`. `animate-pulse` is already used by `skeleton.tsx:7` and is not flagged.
    - **If you create a new top-level directory under `web/`, `color-scan.ts`'s `SCAN_ROOTS = ["app","components","lib","hooks"]` will not reach it** — that exact gap made a prior AC's "only place in the repo" clause false. `components/workspace/` is inside `components/`, so the default placement is safe; anything else is not.
    - Add **no new colour token.** There is no `--warning` and no `--success`, and inventing one contradicts `DESIGN.md:85` (*"Avoid: a second brand hue, gradients, custom destructive colors (use shadcn's)"*). The mockup's `--destructive:#DC2626` (`team-workspace.html:16`) is banned; use shadcn's.

13. **Given** UX-DR6 requires a task list *"(accent pulse on active)"*, `EXPERIENCE.md:89` says *"task list advances"*, `:58` gives the copy `Running · 2 of 4 tasks`, and `:113-114` requires an `aria-live` announcement of the form `("Task 2 of 4, writer, running")` — **but** AD-13's rule reads *"the UI reads run progress via that interface (**v1: on-completion**; v2: incremental)"* (`ARCHITECTURE-SPINE.md:154`), FR-11 says batch (`prd.md:236`), `EXPERIENCE.md:89` itself ends *"Batch result on completion (v1)"*, and **PRD Open Q4 explicitly leaves open *"how is Run progress shown in the UI?"*** (`prd.md:457-458`) — **When** a run is in flight, **Then** the UI shows **only what it actually knows**, and that is:

    | Moment | Known | Rendered |
    |---|---|---|
    | before a run | the task DAG, each task's agent and model | one row per task in topological order, status `Queued` |
    | during a run | that *this run* is in flight; the task count | run-level `Running` state, **accent pulse on the team/run**; rows stay `Queued` |
    | on completion | every task's real output | rows become `Done`, expandable to their output |
    | on failure | that it failed, and the authored reason | run-level failure with the reason in text |

    **The accent pulse goes on the running team, not on a fabricated "active task".** `DESIGN.md:125-126` reads *"the `{colors.accent}` pulse dot meaning a team/task is running. Accent appears *here* and on the active task row, nowhere decorative."* — it authorises **both** placements, and the team-level one is the only one this story can render truthfully.

    **Ship no fabricated count.** `Running · 2 of 4 tasks` cannot be rendered truthfully — mid-run the server knows nothing about which task is active. The task *count* is real and pre-run, so a truthful variant naming only the count is permitted; `2 of 4` is not. Same for the `aria-live` region: announce the transitions that genuinely occur (run started with the task count, run complete, run failed with the reason), not `Task 2 of 4, writer, running`.

    **This is the story's largest declared deviation, and it deviates from this story's own epic AC.** `epics.md:381-383` says in plain text *"the task list shows progress (accent pulse on the active task)"* — name that first, not just the UX spine. Record it against `epics.md:381-383`, `EXPERIENCE.md:58`, `:75`, `:89` and `:113-114`, cite AD-13 and PRD Open Q4, and escalate it (AC 16) with the concrete recommendation: a per-task progress channel is buildable — one crewai `TaskStartedEvent`/`TaskCompletedEvent` subscriber, made unambiguous by AC 3's serialisation, exposed behind a Runtime-owned callback so `api/` never touches the bus — and it is precisely the incremental delivery AD-13 assigns to v2. Name the seam; do not build it here.

    **Colour is never the only carrier** (`EXPERIENCE.md:117`, UX-DR9, NFR4). Every task row carries a text status. The mockup's bare colour dots (`team-workspace.html:60-62`) are non-compliant and are not shipped. **The `✓` glyph stays banned** (`route.test.tsx:184-189` — *"the real states are words, not ticks"*).

14. **Given** `epics.md:384-386` — *"I can open the full agent transcript for that run (Story 1.7) — every agent message and handoff in order, attributed to agent and task"* — and given **`EXPERIENCE.md` and `DESIGN.md` contain the word "transcript" zero times** (FR-27 postdates both spines, the PRD has no FR-27, and `ARCHITECTURE-SPINE.md` has no Capability Map row for it), **When** the transcript is opened, **Then** it renders inside the one constraint that does exist — `EXPERIENCE.md:38-39`, *"Modal depth: one level (a `Dialog` over a surface, never dialog-over-dialog)"* — as a `Dialog` over the Workspace, using the already-installed `dialog` and `scroll-area`. Declare the whole shape as designed-here, because no source specifies it.

    Rendering rules, all from Story 1.7's own instructions to you:
    - **Sort by `sequence`; never rely on list position and never assume contiguity.** `results.py:44-47`: *"Values are monotonically increasing but **sparse**… Sort by it; never assume contiguity."* Observed real values: `[2,5,7,8,11,13]`.
    - **Branch on `kind`, never on `content`.** 1.7: *"The UI groups by task row and renders 'message' vs 'handoff' differently, so it must not be asked to regex `content` to tell them apart."* The six constants exist so a typo is an error rather than a dead branch (`results.py:16-24`).
    - **Join to task rows by `task_name`.** 1.7 passes `name=task_spec.name` when building each crewai `Task` specifically because otherwise *"Story 2.4 [would be] unable to line a transcript entry up with its task row"*. Blank and duplicate task names now raise `InvalidPackageError` because that name became a join key.
    - `target_role` names the delegate on `delegation` / `delegation_result` entries. Render both ends.
    - **A delegation entry may precede the `agent_action` that caused it** — faithful to `emission_sequence`, dismissed in 1.7's review as not a defect but *"worth a note for Story 2.4's renderer"*. This is that note. Do not assume causal order.
    - **A failed run returns no transcript at all.** `deferred-work.md:101`: the entries collected before `kickoff` raised are discarded with the exception. On the wire this is a **`200` with an empty `entries` list and an explicit boolean saying why it is empty** — not a `404`, which would mean "no such run", and not a bare empty list, which would mean "the agents said nothing". AC 8 adds no code for it because it is not an error. Say so in the UI rather than showing a blank panel, and record that PRD Open Q5 (partial results) stays open.
    - **On the wire the transcript is a separate GET.** `results.py:65-66` says it *"is independently omittable so an API caller can drop it from a response without reshaping anything else"*, and `epics.md:467-475` has Story 4.2 make it *"available on request rather than always inlined"*. Follow that; a run result carrying every agent turn inline is a large payload the Workspace does not need until asked.
    - **Answer 1.7's Open Question 3.** It asks this story directly: *"The event bus can yield per-LLM-call, per-agent-turn, or per-task entries. This story specifies per-turn… If Story 2.4's UI wants something coarser or finer, saying so now is cheaper than reshaping the contract later."* Say per-turn is right (or say it is not) and record the answer.

15. **Given** this story's scope, **When** implementing it, **Then** these are explicitly **out of scope**, declared not forgotten:

    - **Save / rename / delete / My Teams / recent teams** — Story 2.5 (FR-25, FR-26, FR-28; `epics.md:394-414`). `EXPERIENCE.md:90` puts the prompt *"Save this team and its results?"* in the run-complete state on this surface, but the persistence behind it is 2.5's and `EXPERIENCE.md:103-104`/`:172-174` ban dead affordances. **Omit the prompt and declare it**, following Story 2.3's precedent exactly: *"the seam must be left, the states must **not** be faked"*.
    - **Settings key guidance** — 2.6. `web/tests/shell/routes.test.tsx:85-93` asserts Settings contains nothing key-related and **must stay green**.
    - **The WCAG 2.2 AA audit** — 2.7. This story meets the a11y floor it touches (keyboard-operable run controls per `EXPERIENCE.md:112`, one live region, colour paired with a word) but does not perform the audit.
    - **A provider/model picker.** `EXPERIENCE.md:102`'s *"badges are click-to-change (opens a small model picker)"* collides with the settled modal-depth-one rule, and 2.3 already ruled it out. `components/ui/popover.tsx` stays installed and unused; `deferred-work.md:165` guessed this story would be its first consumer — it is not. Say so.
    - **A run-failed `Toast`.** `EXPERIENCE.md:91` names one, and **no toast/sonner component is installed**. Installing one is a dependency decision; 2.2 faced the identical choice with `alert` and rolled its own using the `composer-failure.tsx` idiom rather than installing. Do the same, and declare the deviation.
    - **Per-task live progress, streaming, and partial results** — AC 13, AD-13 v2, PRD Open Q4/Q5.
    - **Binary or PDF documents, and any document parsing** — AC 6.
    - **A server-side gate on `POST .../build`** — AC 7. Still 2.0's route.
    - **A global unsaved-work guard.** `deferred-work.md:172` says the `g` chord fires from focus on any `BUTTON` and asks for this to be *"settled before Story 2.4 adds a workspace with even more transient state"*. Note what this story's design already changes: because the run lives **server-side behind a `run_id`**, navigating away no longer destroys the run — it destroys the view of it. Attached documents and the on-screen log are still lost. Record that improvement and leave the guard open.
    - **Unconditional autoscroll** — `deferred-work.md:166` explicitly hands it to this story; it is worse on a surface where a user reads a long result. Inherit it, and say you did.
    - **Adding a dependency of any kind.** Native HTML5 drag-and-drop (`onDragOver`/`onDrop`/`DataTransfer`), native `<details>`/`<summary>` for per-task expansion — there is no `accordion` or `collapsible` installed and none is needed. If you believe you need a package, **stop and declare it**; 2.2 kept `playwright` out of `web/package.json` on exactly this ground.
    - **Entering an API key anywhere** — `EXPERIENCE.md:103` bans it outright; AD-9 binds `ui`.

16. **Given** CLAUDE.md's test-organisation and test-transparency rules, **When** this story lands, **Then**:

    - Python tests live in **`tests/api/test_run.py`** and **`tests/api/test_run_documents.py`** (new files), with shared helpers in a `tests/api/runroutes.py` module if they exceed one file — following the precedent 2.3 set when `test_key_status.py` reached 728 lines and was split into `test_key_status.py` + `test_key_check.py` + `tests/api/keyroutes.py`. **Do not add to `tests/api/test_review_patches.py`** (636 lines, already over guideline and flagged twice). Core-side tests for AC 5 go in `tests/unit/runtime/test_run_context.py`.
    - Frontend tests live in **`web/tests/workspace/`** — a new directory mirroring `components/workspace/`, not more files in `tests/composer/`.
    - **The autouse `isolated_key_config` fixture is load-bearing, not hygiene.** `./team_maker.keys` exists in this working tree with live keys and `KeyConfig.from_file(None)` falls back to it. Never weaken it; keep the `os.environ` snapshot/restore and the pop of every catalog `env_var`.
    - **Every guard is fed a violating fixture and watched go red before it is trusted**, following `tests/api/test_containment_guards.py`. Specifically prove: the concurrency guard fails if the lock is removed; the traversal check fails if the slug is not re-slugged; the containment sweep fails if a sentinel is echoed into `final_output`; the goal-injection test fails if the goal is dropped. 2.1's commit body records the meta-lesson — *"Writing the warning down was not enough to avoid it"* — and 2.3 found that reverting a real bug failed **nothing**, because the test exercised the branch that worked. A falsification that fails to apply is indistinguishable from a guard that cannot fail; 2.3 lost time to `perl` `\n` patterns silently not matching CRLF files.
    - **Assert counts, not absences**, and assert a collection is non-empty before looping over it. `for entry in result.transcript:` over an empty transcript is a vacuous pass — and because the adapter unit tests monkeypatch `Crew.kickoff` wholesale, **an empty transcript is the default state in most of the suite**.
    - **Label every stub, fake and monkeypatch**, and distinguish unit / mocked-integration / local-integration / real end-to-end. A fake `ExecutionEngine` and a mocked `fetch` are never evidence the real integration works. The only real proof for a run is `tests/conformance/` (which `importorskip`s crewai — `deferred-work.md:104`) and a manual live check.
    - **New frontend fixtures are captured from a real server** with a provenance row in `web/tests/composer/fixtures/index.ts` (date, branch, exact command, status), or labelled `provenance: "synthesised"` and said so in the test name. `generated_teams/haiku_team/` already exists and is small — capture a real run against it rather than a large team, and say what it cost.
    - `make test`, `make test-api`, `make lint`, `npm test`, `npm run lint`, `npx tsc --noEmit` and `npm run build` are all green. **State before/after counts and paste the real command tails.** The baseline was **measured at `0fd5348`**, not copied: Python **`572 passed, 7 skipped`**; web **`22 files, 390 tests`**. `ruff check api/` must stay at **0**; `team_maker/` is at **9** and `tests/` at **29** — **different scopes**, and conflating them is how 2.1 mis-reported its numbers. Do not assert a number you did not measure: 2.1 reported ruff's 38 as 9, 2.2 claimed "17/17 E2E checks" against a harness with 16 `check()` calls, 2.0 reported 71 tests where it was 89, and 2.3's frontend count was wrong in two directions in the same document.

## Tasks / Subtasks

- [ ] **Task 1 — Read the code you are about to change, and re-measure the three broken things** (AC: 1–7)
  - [ ] `api/main.py` in full (lifespan, router registration, the four error handlers, `_warn_on_multiple_workers`), `api/state.py` (all 33 lines — `AppState` is frozen, five fields), `api/sessions.py` (the registry shape you are mirroring, and every tunable constant), `api/errors.py` (the whole envelope contract), `api/schemas.py` (`…Request`/`…View`, `_STRICT`, the bounds block, the `status` discriminator), `api/output.py` in full (the server-owned-path rationale that governs where anything may be written), `api/routings.py` (the deferred-import pattern), `api/keystatus.py:325-398` (`check_overall`, `blocking_reason`, `safe_label` usage), `api/deps.py:239-268` (`providers_needing_restart` — why a run needs no restart to see a new key).
  - [ ] `team_maker/runtime/` in full: `executor.py`, `loader.py`, `ordering.py`, `results.py`, `preflight.py`. Then `team_maker/adapters/runtime_crewai/crewai_execution_engine.py` and `transcript_capture.py:1-66` (the best document in the repo on the bus).
  - [ ] `web/components/composer/composer-surface.tsx`, `composer-state.ts` (the full action union, `saveEpoch`, `keyCheckEpoch`, `adoptSession`), `composer-actions.tsx:52-110`, `composer-failure.tsx`, `transcript.tsx`, `message-bubble.tsx`, `proposal.ts`; `web/lib/api-client.ts` (the `request()` wrapper, the timer rule, `FALLBACK_MESSAGE`, `looksLikeLeakedInternals`, `scrubFields`) and `api-types.ts` (the `parseX` convention and the refuse-vs-default decisions).
  - [ ] `tests/api/conftest.py` in full, `tests/api/containment.py`, `tests/api/test_secret_containment.py`, `web/tests/composer/harness.tsx` (`createFetchQueue`, and why key routes have their own queue).
  - [ ] **Re-measure the three findings.** Probe that the goal reaches no prompt; probe that `_build_agent` passes no `tools=`; confirm `api/routers/` has no run route. Paste each probe and its output. If any has changed since this story was written, say so and adjust.

- [ ] **Task 2 — The run-context seam in `team_maker/`** (AC: 5, 6)
  - [ ] New pure module `team_maker/runtime/run_context.py`: goal + documents → a **new** `GeneratedTeam`. No disk, no network, no clock. `from __future__ import annotations`, full type hints, built-in generics.
  - [ ] Extend `run_team_package` with a **keyword-only** `documents` parameter defaulting to empty. Every existing caller keeps working unchanged; `tests/unit/runtime/test_executor.py` and `tests/unit/cli/test_cli_run.py` stay green.
  - [ ] **Resolve the brace question empirically** (AC 5) and record the probe. If `inputs=` becomes dead weight, remove it and update `test_crewai_execution_engine.py:232-245` with its intent preserved.
  - [ ] Prove the goal reaches a **real prompt**, not just a description string, using `tests/support/crewai_interception.py`'s call recorder.
  - [ ] Declare the `team_maker/` footprint in Completion Notes (Story 2.0 AC 12 precedent: an exhaustive table, with the standing rule that any file not named remains frozen).

- [ ] **Task 3 — The run registry** (AC: 3, 4)
  - [ ] `api/runs.py` — the run record, the process-wide run lock, thread ownership, bounded record count, idle TTL, injectable clock. Mirror `api/sessions.py`'s shape and its comment discipline; do not extend `SessionRegistry`.
  - [ ] Sixth field on `AppState`; constructed in the lifespan; **add the shutdown branch** after `yield` and state what it does with a run in flight.
  - [ ] Update `_warn_on_multiple_workers`'s docstring so it stops being false.
  - [ ] Prove the lock: a second `POST /api/runs` while one is held returns `run_in_progress` immediately, and **prove the guard fails when the lock is removed**.

- [ ] **Task 4 — The four routes** (AC: 1, 2, 7, 8, 9, 10)
  - [ ] `api/routers/run.py`; register in `api/main.py`; new views in `api/schemas.py` with `_STRICT` on the request model only. **If `api/schemas.py` crosses ~400 lines**, split it into an `api/schemas/` package by group with a re-exporting `__init__.py` so no import churns — CLAUDE.md says reorganise the crowded area as part of the story. State which you did and the resulting counts.
  - [ ] Slug resolution with re-slugging **and** a containment check against `output_root()`. `team_not_found` for anything unreadable.
  - [ ] Synchronous key gate before the thread spawns, via `load_team_package` + `check_credentials`, mapped through `describe_unresolved_provider`; `InvalidPackageError` kept distinct from `run_blocked`.
  - [ ] The four error codes, four files each, each with its `SESSION_BUSY`-style comment.
  - [ ] The execution-engine injection seam on `create_app`, threaded to `run_team_package(engine=…)`.
  - [ ] Extend `_exercise_every_route` and `_template()` (explicit branches — the two four-segment paths are ambiguous by count); update `test_health.py` to eleven; sweep both result and transcript bodies with a sentinel planted in the rendered fields.

- [ ] **Task 5 — The Workspace surface** (AC: 11, 12, 13, 14)
  - [ ] `web/app/teams/[slug]/page.tsx` (server component, `metadata`) + `web/components/workspace/`: the `"use client"` root, a pure reducer sibling, goal input, document tray, task list, results, transcript dialog.
  - [ ] Four new functions in `web/lib/api-client.ts` — **the only module that calls `fetch`** — each with a **named timeout constant carrying its own justification** in the style of `COMPOSE_TIMEOUT_MS`/`KEY_CHECK_TIMEOUT_MS`, plus a named poll-interval constant. Narrow every response with `parseX(payload): X | null` in `api-types.ts`: **view types naming only the fields the UI renders**, never a mirror of the pydantic model, never a cast.
  - [ ] Follow the union-vs-string rule (`api-types.ts:106-116,159-167`): `status` and any task status stay **open strings**, not closed unions. A closed union already caused *"one new server aggregate made `parseKeyStatus` return null, which silently removed the whole panel *and* the build gate"*.
  - [ ] Poll with an epoch guard — a third instance of the `saveEpoch`/`keyCheckEpoch` pattern, captured **before** the `await`. Dispatch after `await` inside effects; never a synchronous `setState` in an effect body; **never add an `eslint-disable`** — 2.3 measured that one it wrote was itself reported as unnecessary.
  - [ ] The accent, in exactly one file, whitelisted in exactly one line of `signal-token.test.ts`.
  - [ ] Every blocked control: handler guard + `aria-disabled` + `aria-describedby` + an always-rendered reason. Never `disabled`.
  - [ ] One live region for run state. **Do not nest it inside the log's `role="log"`** — `thinking-indicator.tsx:12-15` documents why a nested live region either double-announces or swallows, and `key-check.tsx:267-269` documents why two assertive regions talk over each other.
  - [ ] Any editor host must be `INPUT`/`TEXTAREA`/`SELECT` or carry a recognised `contenteditable` value, or typing "**g**rand total" navigates the user away mid-sentence (`nav-shortcuts.tsx:11,23-31`).
  - [ ] `⌘/Ctrl+Enter` runs the current team (`EXPERIENCE.md:99`); leave `⌘/Ctrl+B` alone (shadcn's sidebar toggle); `Esc` closes the transcript dialog via Base UI's `onOpenChange`.

- [ ] **Task 6 — Pre-reject the mockup's fabricated data** (AC: 11, 13)
  - [ ] `mockups/team-workspace.html` is a **composition reference** by name (`EXPERIENCE.md:41-42`) and *"Spines win on conflict with any mock"* (`:14`). Ship none of: `:80` the `Keys: anthropic ✓ · gemini ✓ · openrouter ✓` footer (**already rejected twice**, by 2.1 AC 13 and 2.2 AC 9, with a live regression test at `route.test.tsx:95,108,175,185`); `:86` the team name `Research & Content` (it is `DESIGN.md:90`'s *typography* example, not a team); `:88-91` the four fabricated agent/provider pills; `:93`'s `2 of 4`; `:101`'s sample goal; `:102`'s fabricated filename, the `📄` emoji (`DESIGN.md:135` bans emoji energy) and the unsourced phrase `attached to this run`; **`:104`'s assistant narration** — *"On it — researcher is gathering sources…"* — which requires a conversational team agent that **AD-5 forbids** (*"the Runtime **executes only**"*) and no port, endpoint or service provides; `:106`'s `memory is a v2 option` (advertising a v2 feature the UI must only *reserve room* for, `EXPERIENCE.md:140`); `:110`'s Mac-only `Run ⌘⏎` glyph; `:118-121`'s fabricated task rows; `:124`/`:127`'s `Draft (in progress)` and `feedback (pending)`, which imply partial results that FR-11, AD-13 and `EXPERIENCE.md:89` all forbid in v1; `:126`'s invented `sources (6)` count; the `:13-17` palette (rejected by 2.1); the `:60-62` colour-only dots.
  - [ ] **State the reading of FR-23 you are shipping.** `prd.md:356-358` says a chat surface to *"give goals, ask follow-ups"*, and `prd.md:385` says *"Not a general-purpose chatbot"*. With AD-5, the only honest reading is that the chat is a **goal-entry and outcome log**: the user's turn is a goal, the system's turn is the run's outcome. Say so explicitly rather than leaving a reader to wonder why the team never talks back.

- [ ] **Task 7 — Tests, red first** (AC: 10, 16)
  - [ ] `tests/unit/runtime/test_run_context.py`: purity (no disk/network/clock), the package is not mutated, the returned team is new, documents and goal both land, bounds respected, braces survive.
  - [ ] `tests/api/test_run.py`: the four routes, and that the plan route is reachable at all (declaration order — a parameterised `/{run_id}` declared first swallows `/teams/{slug}`); slug re-slugging and traversal refusal; `team_not_found` from a real `TeamPackageError`; `run_blocked`'s **three distinct sentences** — `MissingCredentialsError`, `InvalidPackageError`, `UnsupportedFrameworkError` — each asserted on its own copy, not just its shared code; `run_in_progress` under a held lock; `run_not_found` after eviction; the `running → complete` and `running → failed` transitions, the latter from a raising fake engine, with `failure_reason` authored and carrying no exception text; registry eviction against the injected clock; transcript ordering by sparse, non-contiguous `sequence`; a failed run's transcript returning `200` with an empty list and the flag that says why.
  - [ ] `tests/api/test_run_documents.py`: each bound; the over-limit rejection is a `spec_invalid` 422 with the right field path; documents reach the prompt; documents are absent from disk and from the run record after completion.
  - [ ] `web/tests/workspace/`: the surface renders a real task list from a mocked response; the accent appears only in the running state; blocked run controls are `aria-disabled` with a linked reason; the document tray refuses an unreadable file with a stated reason; the transcript dialog renders messages and handoffs differently **from `kind`**; polling stops on a terminal status; a superseded poll response is discarded.
  - [ ] Feed every new guard a violating fixture and watch it go red first (AC 16). List each falsification and the test that failed.
  - [ ] Extend `harness.tsx` for the run routes following the existing three-queue precedent — the run routes get their own recording array so assertions that mean "the second *compose* call" keep meaning it.
  - [ ] **Prove the out-of-scope boundaries held** (AC 15), not just that you declared them: `web/components/ui/popover.tsx` still has no consumer; `web/app/settings/page.tsx` is untouched and `web/tests/shell/routes.test.tsx:85-93` is green; `web/package.json` gained no dependency; `web/next.config.ts` is unchanged; `git diff --stat` names no file under `team_maker/generators/`, `templates/` or `codegen/`.
  - [ ] **Run all seven commands and record the tails** (AC 16): `pytest -q`, `make test-api`, `ruff check api/`, `ruff check team_maker/`, `ruff check tests/`, `npm test`, `npm run lint`, `npx tsc --noEmit`, `npm run build`. State before/after counts against the measured baseline (Python 572/7; web 22 files / 390 tests) and say plainly if `tests/conformance/` skipped.

- [ ] **Task 8 — Declare, do not silently edit** (AC: 5, 6, 7, 13, 14, 15)
  - [ ] Record in Completion Notes, and **do not edit the planning artifacts** (Stories 1.4–2.3 precedent):
    - The goal was reaching no agent before this story, with the probe that proved it. This is a **Story 1.5 defect surfaced, not created, here.**
    - Documents are **text-only**, and why (`python-multipart` undeclared, Next's 10 MB in-memory proxy buffer, nothing parses a PDF). Deviation from `EXPERIENCE.md:188`.
    - **PRD Open Q6 is closed by decision** — mechanism, limits, lifetime, security, error copy — and the limits are a judgement call with no NFR behind them.
    - Per-task progress is **not** shipped; the accent pulses the running team. Deviation from `EXPERIENCE.md:58`, `:75`, `:89`, `:113-114`; PRD Open Q4 stays open with the named seam.
    - `"Save this team and its results?"` is **omitted, not faked** (2.5).
    - The run-failed `Toast` is **not** a Toast (nothing installed; 2.2's precedent).
    - The team reference is the **slug, provisional**; PRD Open Q3 and 2.5 still own it.
    - Concurrency is **one run per process**; `deferred-work.md:102` is serialised around, not fixed.
    - `deferred-work.md:101` (no partial transcript on failure) and `:112` (`TranscriptEntry` carries no run identity — the `run_id` lives in `api/`, so the entry type is untouched, which is the outcome that entry hoped for) are both surfaced by this story for the first time.
    - The **answer to 1.7's Open Question 3** on entry granularity.
    - **Four codes, not five, and why there is no `run_failed`** (AC 8) — a background failure has no request left to attach a status to. Declare the whole set as the contract change `errors.py:23` names.
    - **A failed run's transcript is a `200` with an empty list**, not a `404` and not a bare empty list. Say which of the three it is and why the other two would each state something false.
    - **The Workspace's page title does not name the team** (`"Team Workspace · team_maker"`), because a dynamic title needs `generateMetadata` and therefore a fetch outside `lib/api-client.ts`.
    - **The pre-run key badges come from `TeamPlanView`, server-side** — `GET /api/keys/check/{session_id}` is session-bound and the Workspace has no session. Say that you did not build a client-side join.
    - Inherited and not fixed: unconditional autoscroll (`:166`), the `g`-chord unsaved-work gap (`:172`, improved but open — the run itself now survives navigation), `components/ui/popover.tsx` still unused (`:165`, which guessed this story would be its first consumer; it is not).
    - **`deferred-work.md:96` is stale and should be closed, not inherited** — `preflight.py:242` already renders `"none recorded"` for a role-less `UnresolvedProvider`. Say you verified the fix rather than assuming it.
    - **Three file-size figures in `deferred-work.md:173,204` have grown since they were written** (`api-client.test.ts` 583, `build.test.tsx` 511, `error-paths.test.tsx` 460). Correct them there rather than repeating them.
    - **Story 2.1's light `--primary` at 4.12:1** (below AA's 4.5:1) is now on a `Run` primary button too. Do not change the token unilaterally; keep it escalated.
    - Stale planning artifacts to keep flagging rather than fixing: `ARCHITECTURE-SPINE.md:171` pins FastAPI `0.139.x` while **`0.141.1` is installed**; `:172` and `:225-226`'s CrewAI-pin entries were closed by Story 1.6 and have now been flagged by 1.7, 2.1, 2.0, 2.3 and this story without ever being actioned; `:175`'s *"shadcn/ui | current"* is materially wrong (**Base UI, not Radix**); `project-context.md:24,29` still says `crewai` is not a dependency and describes the project as a factory and not a runtime — both false since 1.5, flagged for the seventh story running; `component-inventory.md` and `development-guide.md` both predate `api/` and `web/`.
  - [ ] Add to `deferred-work.md`: everything above that a later story must pick up, in the file's existing prose style.

## Dev Notes

### The contract you are adding, in one place

```
GET  /api/runs/teams/{team_slug}     → 200 TeamPlanView | 404 team_not_found
POST /api/runs                       → 200 RunView(status="running")
                                       | 404 team_not_found | 409 run_blocked
                                       | 409 run_in_progress | 422 spec_invalid
GET  /api/runs/{run_id}              → 200 RunView(running|complete|failed) | 404 run_not_found
GET  /api/runs/{run_id}/transcript   → 200 TranscriptView | 404 run_not_found
```

Snake_case on the wire — there is no alias generator anywhere in `api/`, and the frontend reads snake_case. Every response carries the `status` discriminator. `RunView.status` is the first place it varies *over the life of one resource* — `HealthView` is already `Literal["ok"]`, but nothing else has ever had more than one possible value — which is exactly what `schemas.py:16-17` built it for.

### What the core hands you, and its exact shape

`team_maker/runtime/results.py`, plain dependency-free dataclasses:

```python
TaskResult(name: str, agent_role: str, output: str)
TranscriptEntry(sequence: int, kind: str, agent_role: str, task_name: str,
                content: str, target_role: str | None = None)
RunResult(final_output: str, task_results: list[TaskResult],
          transcript: list[TranscriptEntry] = field(default_factory=list))
```

Kinds (`results.py:19-24`, whose comment names you): `task_started`, `task_completed`, `agent_message`, `agent_action`, `delegation`, `delegation_result`.

**There is no `to_dict()`** on any of the three — unlike `domain/models.py`, deliberately. You write the projection into your `…View` models, field by field, and that projection is the containment boundary.

**What the core object does not carry, so you know what your `…View` must supply or omit:** no timestamps, no token counts, no cost, no per-task status, no partial state, and **no run identity** (`deferred-work.md:112` asked for that to be settled before an HTTP consumer built on it — you are it, and the answer this story gives is that `run_id` lives in `api/`'s run record, leaving `TranscriptEntry` untouched, which is the outcome that entry hoped for).

`task_results` is in topological order and its `name` is the guaranteed join key to `transcript[].task_name`; `tests/conformance/test_transcript_conformance.py:204-231` proves the two agree on `agent_role` per task.

### What a Team Package actually contains, and what the run path reads

`generated_teams/<slug>/` holds `README.md`, `team_config.yaml`, `routing_config.yaml`, `agents/<role>.yaml`, `tasks/<name>.yaml`, `docs/`, `tools.py`, `state_store.py`, `run_example.py`, `requirements.txt`, `generation_report.md`. **There is no manifest file on disk** — `ArtifactManifest` is an in-memory dict.

`load_team_package` reads exactly four kinds: `team_config.yaml`, `routing_config.yaml`, `agents/<role>.yaml` for each name in `team_config.agents`, and `tasks/<name>.yaml` for each name in `team_config.tasks`. `run_example.py`, `tools.py`, `state_store.py` and `docs/` are **never read** by the in-process run path. Build your `TeamPlanView` from the loaded `GeneratedTeam`, not by re-reading YAML.

`generated_teams/haiku_team/` and `generated_teams/research_brief/` already exist in this working tree — real packages, small, and the cheapest honest fixture source you have.

### The three-cause concurrency problem, stated once so you do not half-fix it

1. **Handler fan-out.** `crewai_event_bus.on(EventType)(handler)` is process-global; recorder B receives recorder A's events.
2. **`emission_sequence` collision.** ContextVar-scoped, restarts at 1 per run, so `sorted(..., key=sequence)` interleaves two runs irrecoverably. Even perfect filtering leaves ordering correct only *within* a run.
3. **`flush()` is process-wide.** `__exit__` waits on *all* pending futures, so run A's teardown blocks on run B's handlers.

A process-wide lock fixes all three and touches no core code. Event filtering fixes only (1), and `AgentLogsExecutionEvent` carries neither a task nor an agent reference, so filtering would have to ride the same lazy parent-chain walk that is only resolvable *after* flush. Do not attempt it.

### Never branch on provider name

`project-context.md:43`: *"Never branch on provider name — routing is data-driven so new providers need zero code changes."* Every provider difference is a field on the catalog row. `api/routers/compose.py` branches on `entry.choice.keyless` (a flag), not on `"ollama"`. Follow that.

### The defect classes this codebase actually produces

Ranked by frequency. Every one passed review at least once before being caught.

1. **The guard that cannot fail.** 2.1's Guard B protected its own self-declared highest-risk decision and caught nothing. A 2.0 review guard **passed while disabled**. 2.3 reverted a real bug and the suite stayed green, because the test injected through the branch that worked. → Prove red first, and prove the falsification actually applied.
2. **True by construction.** `assert sequences == sorted(sequences)` against a function returning `sorted(...)`. Asserting a string was absent passed on a component returning `null`. → **Your version of this trap: the transcript is empty by default in every test that monkeypatches `kickoff`, so any assertion looping over it passes vacuously.** Assert non-emptiness first.
3. **Measuring a mirror.** A contrast test read `lib/brand-tokens.ts` instead of the shipped CSS. → On this story's path the single sources of truth are `registry.classify()` (availability), `keystatus.provider_reports` (its projection, for badges), `describe_unresolved_provider` (fix hints — already applied for you inside `MissingCredentialsError.unresolved`), and the loaded `GeneratedTeam`'s own `AgentSpec.routing` (what each agent will actually use). Capture fixtures from a real server. Note the two mirrors this story explicitly does **not** reach for: `requested_routings` answers a compose-time question, and `blocking_reason` authors a different surface's sentence from a different input shape.
4. **A guard narrower than its claim.** The colour scanner walked only `app/` and `components/`, so `lib/`'s hex literals went unguarded. → `SCAN_ROOTS` will not reach a new top-level `web/` directory, and `_template()` will not reach a new path shape.
5. **A comment, docstring or test title is a testable assertion.** `api/sessions.py` called the per-session cap "the real spend ceiling"; it wasn't. `spec-editor.tsx`'s docstring described the opposite of its shipped behaviour. → You have four to correct in this story: `_warn_on_multiple_workers`'s docstring, `build-result.tsx:14-17`, `build.test.tsx:411`'s test title, and `signal-token.test.ts:143`'s test title. Also verify — do not trust — `executor.py:6-9`'s claim that the crewai import is lazy.
6. **Declared deviations get audited, and their reasons get checked.** 2.1's deviation 2 was withdrawn as wrong; 2.0's deviation 3's reason was disproven by its own test.
7. **Self-reported figures must be measured.** See AC 16.
8. **Undeclared stubs change what is tested.** An always-`false` `matchMedia` silently pinned every test to the desktop branch.
9. **Dead affordances.** A permanently disabled button as the primary action. `EXPERIENCE.md:104` bans hiding a blocked action behind a silent failure.
10. **Verify the real API before writing assertions.** This is **Base UI**, not Radix: `render={}` not `asChild`, `data-open`/`data-closed` not `data-state`, `Backdrop` not `Overlay`, no `forwardRef`.
11. **Collect all failures; never short-circuit on the first.** Four instances across 1.5–1.6.
12. **Fields that exist, look load-bearing, and are never read.** `ProviderRouting.api_key_env`, `turns_remaining`, `load_warnings` — and now **`AgentSpec.tools`**, which is loaded and dropped. Do not add a fifth.
13. **A behaviour that is remotely reachable for the first time.** 2.0's own change log: three of its four worst findings were pre-existing `team_maker/` looseness *"harmless behind a CLI and not harmless behind an unauthenticated HTTP endpoint"*. **The run path is that, this time.** `deferred-work.md:77` (no non-empty goal validation), `:95` (a zero-agent package passes the pre-run gate) and `:96` (a dangling `(agents: )` reachable only from the API path) are the specific known instances.

### Project conventions (must follow)

- `from __future__ import annotations` at the top of every Python module; full type hints; built-in generics. Pydantic v2 only; input models in `schema/`, internal data as plain dataclasses in `domain/`/`runtime/`.
- Ruff line-length 100, rules `E,F,I,N,W`, `E501` ignored. Lint only what you touch.
- Files ~200–400 lines. **Measured at `0fd5348`**, over guideline and **not to be worsened**: `tests/api/test_review_patches.py` 636, `web/tests/composer/api-client.test.ts` 583, `web/lib/api-types.ts` 560, `web/components/composer/spec-editor.tsx` 517, `web/tests/composer/build.test.tsx` 511, `web/tests/composer/error-paths.test.tsx` 460, `web/lib/api-client.ts` 454, `web/components/composer/composer-surface.tsx` 428. `api/keystatus.py` is 398 and at the ceiling. (`deferred-work.md:173,204` lists smaller figures for three of these — they have grown since; do not copy that list.) You will add to `api-client.ts` and `api-types.ts`; if that pushes them further, split by domain (transport vs routes; compose vs keys vs run) as this story's reorganisation and say so.
- One logger per module named `"api.<module>"`; `%s` lazy formatting, never f-strings into the logger; `logger.exception(..., exc_info=exc)` only inside `log_and_wrap`.
- Frontend: `web/components/<feature>/`, kebab-case files, PascalCase exports, pure logic in `.ts` siblings, `data-slot` as the test query surface, one `"use client"` root per surface with `page.tsx` staying a server component that keeps its `metadata` export. TypeScript strict, **no `any`**. `web/components/ui/` is vendored and never hand-edited; anything the shadcn CLI drops outside it must be added to **all three** exclusion lists (`eslint.config.mjs`, `vitest.config.mts`, `tests/theme/color-scan.ts`).
- Commits: `feat(story-2.4)` for code+tests, `docs(story-2.4)` for this file and `deferred-work.md`. Long-form bodies explaining *why*, ending `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`. Linear history, no merge commits. Branch `story_2_4` from `epic_2`, pushed to remote immediately.

### Git intelligence

Recent history on `epic_2`: `0fd5348` (2.3's story, its review's 24 findings, and **three claims of the author's corrected**), `417f48b` (2.3 feat), `2e89846` (2.2 review findings and *a corrected E2E figure*), `7350b66` (2.2's 29 review patches and **three false claims corrected**), `9da62c5` (2.2 completion notes and *measured* figures).

The rhythm is `feat` → external three-layer adversarial review → `fix` commit carrying the patches → `docs` commit recording findings and corrections. **Four of the last five commit subjects mention correcting figures or claims made in a previous commit.** Expect your Completion Notes to be audited line by line. Write only what you measured, and when you are unsure, say you are unsure.

### Latest technical information

- **Dependencies are hard-pinned with a documented widening procedure** (`pyproject.toml:38-61`): `crewai>=1.14.6,<1.15`, `fastapi>=0.141,<0.142`, `uvicorn>=0.52,<0.53`. Installed and verified in `.venv` (Python **3.13.13**): FastAPI **0.141.1**, Starlette **1.3.1**, `python-multipart` **0.0.32** (transitive, via `mcp`), crewai present. **This story needs no new dependency** — that is a conclusion of AC 6, not an assumption. If you think you need one, stop and declare it.
- **`python-multipart` is required by `mcp`, not by this project.** `pip show python-multipart` → `Required-by: mcp`. FastAPI declares it only under `[standard]`/`[all]`. This is the measured fact behind AC 6's transport decision.
- **Starlette's own multipart limits** are `max_files=1000`, `max_fields=1000`, `max_part_size=1 MiB` on `request.form()`, and FastAPI's `UploadFile` path does not expose them. Irrelevant if you follow AC 6, and listed so that a future story reversing that decision knows what it inherits — and knows to **measure** what actually bounds an upload rather than assume.
- **Next 16 buffers proxied request bodies in memory**, capped by `experimental.proxyClientMaxBodySize` (default **10 MB**). `web/next.config.ts` is Story 2.0's file and must not change (AC 15).
- **Frontend:** Next `16.2.12`, React `19.2.4`, Vitest `4.1.10`, jsdom `29`, Tailwind v4 (CSS-first — there is **no `tailwind.config.*`**; all tokens live in `web/app/globals.css`), shadcn CLI pinned `4.16.1` on `@base-ui/react` 1.6. **Not installed**: accordion, collapsible, tabs, progress, table, alert, toast/sonner, select, label. `popover` and `dropdown-menu` are installed and unused.
- **`npm audit` reports 3 high-severity transitive advisories through `next@16.2.12`** — not actionable without violating the pinned floor; do not "fix" them.
- `plain uvicorn`, not `uvicorn[standard]` — the extra's `uvloop` has no Windows wheel. `--reload` already implies a single worker; do not also pass `--workers`.

### Project Structure Notes

New files:

```
team_maker/runtime/run_context.py                  # goal + documents → a new GeneratedTeam (AC 5, 6)
tests/unit/runtime/test_run_context.py             # its tests

api/runs.py                                        # the run registry, lock and thread ownership (AC 3, 4)
api/routers/run.py                                 # the four routes (AC 1)
tests/api/test_run.py                              # routes, gate, concurrency, containment (AC 16)
tests/api/test_run_documents.py                    # document bounds and lifetime

web/app/teams/[slug]/page.tsx                      # server component + metadata (AC 11)
web/components/workspace/*.tsx | *.ts              # the surface (AC 11–14)
web/tests/workspace/*.test.tsx                     # its tests
```

Modified: `api/main.py` (router registration, lifespan shutdown, `AppState` construction, the `_warn_on_multiple_workers` docstring, the engine injection seam), `api/state.py` (sixth field), `api/schemas.py` (the run views; split into a package if it crosses ~400 lines), `api/errors.py` (four codes), `team_maker/runtime/executor.py` (the keyword-only `documents` parameter), possibly `team_maker/adapters/runtime_crewai/crewai_execution_engine.py` (only if AC 5's brace probe requires it), `tests/api/test_health.py`, `tests/api/test_secret_containment.py`, `tests/unit/adapters/test_crewai_execution_engine.py`, `web/lib/api-client.ts`, `web/lib/api-types.ts`, `web/components/composer/build-result.tsx` (the link and the stale docstring), `web/tests/composer/route.test.tsx`, `web/tests/composer/build.test.tsx`, `web/tests/theme/signal-token.test.ts` (one whitelist line), `web/tests/composer/harness.tsx`, `web/tests/composer/fixtures/index.ts`.

Must **not** change: `web/next.config.ts` (2.0 owns it); anything under `web/components/ui/` (vendored); `web/app/settings/page.tsx` (2.6); `web/tests/shell/routes.test.tsx:85-93` and `app-sidebar.test.tsx`'s four-link assertion; `tests/api/containment.py`'s `_ENVELOPE_KEYS`; the error-envelope shape; `team_maker/generators/`, `team_maker/templates/`, `team_maker/codegen/`; `make clean`. Must **not** create `web/app/api/` — it shadows the rewrite and `tests/api/test_dev_topology.py` fails if it appears.

### Verification commands

```bash
# Python  (from the repo root, using ./.venv)
python -m pytest -q                    # baseline measured at 0fd5348: 572 passed, 7 skipped
pytest tests/api/ -v --tb=short        # make test-api
pytest tests/unit/runtime/ tests/unit/adapters/ tests/unit/cli/ -v   # Task 2's blast radius
pytest tests/conformance/              # the real crewai path (importorskip — say if it skipped)
ruff check api/ && ruff check team_maker/ && ruff check tests/
grep -rn get_secret_value api/         # must stay at exactly two hits, both in api/deps.py
grep -rn "{goal}" team_maker/          # zero before Task 2; state what it is after

# Web (from web/)
npm test          # baseline measured at 0fd5348: 22 files, 390 tests
npm run lint ; npx tsc --noEmit ; npm run build

# Two-terminal dev topology, for fixture capture
make api-dev      # uvicorn api.main:app --reload --port 8000
make web-dev
curl -s -i http://localhost:3000/api/runs/teams/haiku_team   # MUST go through the Next proxy
```

Proof the proxy was actually used is `server: uvicorn` on a response from port **3000** plus a second differently-sourced connection in uvicorn's access log. **A direct hit on `:8000` proves nothing.**

Two known E2E harness defects (`web/tests/composer/e2e-live-check.mjs`) that both bite harder here: it is **not idempotent** — a leftover `output_path` directory makes a build 409 and surfaces as a bare 240 s timeout — and **`aria-disabled` is not `disabled` to Playwright**, so its actionability wait treats such a control as not-enabled and clicks need `{ force: true }`. This story adds more `aria-disabled` states and a control whose action takes minutes.

**A real run costs real money and real time.** Use `generated_teams/haiku_team/` — two agents, two tasks. Say what you ran, how long it took, and what it cost.

### References

- `project-docs/epics.md:99` (UX-DR6), `:335` (the run row) + `:336` (the teams row, Story 2.5's) + `:375-393` (this story's scope and ownership, with `:381-383` the progress clause AC 13 deviates from), `:70-77` (NFR1–7), `:104-115` (FR coverage), `:262-270` (Story 1.5), `:283-297` (Story 1.7), `:394-414` (Story 2.5's boundary), `:467-475` (Story 4.2, the API twin)
- `project-docs/prds/prd-team_maker-2026-07-05/prd.md:356-360` (FR-23), `:362-366` (FR-24), `:283-294` (FR-14), `:224-230` (FR-10), `:232-236` (FR-11), `:296-301` (FR-15), `:110-118` (Glossary — use these terms verbatim), `:380-395` (Non-Goals), `:448-467` (Open Q3/Q4/Q5/Q6); `addendum.md:19-22,36-40,65-73`
- `project-docs/architecture/architecture-team_maker-2026-07-05/ARCHITECTURE-SPINE.md:60-66` (AD-3), `:67-72` (AD-4), `:90-96` (AD-5), `:98-102` (AD-6), `:104-111` (AD-7), `:121-127` (AD-9), `:135-140` (AD-11), `:142-148` (AD-12), `:150-154` (AD-13), `:158-163` (Consistency Conventions), `:179-197` (Structural Seed), `:205-210` (Capability Map), `:212-226` (Deferred — note `:224`)
- `project-docs/ux-designs/ux-team_maker-2026-07-05/EXPERIENCE.md:12-14` (precedence), `:35` (IA), `:41-42` (the mock is a composition reference), `:74-75` (the two component rows that are this story's contract), `:85-92` (State Patterns), `:96-104` (Interaction Primitives and the banned list), `:102` (the click-to-change badge line ruled out of scope), `:106-117` (a11y floor), `:133-140` (v1/v2 line), `:157-162` (responsive), `:164-174` (rejected patterns), `:186-196` (Flow 1), `:200-202` (Flow 2)
- `.../DESIGN.md:60-65` (the discipline clause), `:79-85` (the accent rule and the bans), `:89-98` (typography, layout), `:107-108` (rounding), `:112-114` (use-as-is components), `:122-134` (badges, run-status-live, the Do/Don't table)
- `.../mockups/team-workspace.html` — a composition reference only; see Task 6 for the fabricated-data inventory
- `team_maker/runtime/results.py` (the whole file), `executor.py:1-10,25,29-56`, `loader.py:17,21-57,93`, `ordering.py:16-40`, `preflight.py:33-44,47-73,94-124,117-122,177-234,242`; `team_maker/domain/models.py:29,58,88,110` (which of these are frozen — only one); `team_maker/ports/execution_engine.py:19-41`; `team_maker/adapters/runtime_crewai/crewai_execution_engine.py:33-101,130-138`, `transcript_capture.py:1-66,203-259`; `team_maker/cli.py:371-505,636-688` (the rendering precedent)
- `api/__init__.py:1-10`, `api/main.py:44-54,58-130,161-205,208-252`, `api/errors.py` (whole), `api/state.py` (whole), `api/deps.py:1-28,148-157,209-268`, `api/schemas.py:1-49,104-115`, `api/sessions.py:1-24,44-69,143-218`, `api/output.py:1-31,49-63`, `api/routings.py:1-17,27-60`, `api/keystatus.py:1-21,95-133,196-215,262-269,325-398`, `api/routers/compose.py:3-10,52-128,176-223`, `api/routers/keys.py:7-32,63-116`
- `web/next.config.ts` (whole), `web/app/layout.tsx:36-75`, `web/app/globals.css:46-47,91-117`, `web/components/composer/composer-surface.tsx:28-49,71-123,181-190,319-428`, `composer-state.ts:37-135,194-213`, `composer-actions.tsx:7-29,52-110`, `composer-failure.tsx:6-45`, `transcript.tsx:10-29,38-58,60-87`, `message-bubble.tsx:3-15`, `composer-input.tsx:13-34,58-89,132-160`, `build-result.tsx:14-17,59-77`, `proposal.ts:1-14,25-81`, `key-check.tsx:5-33,42-55,148-176,254-289`, `spec-editor.tsx:44-67,494-498`; `web/lib/api-client.ts:1-14,41-58,100-162,172-254`, `api-types.ts:1-34,106-116,159-167,205-261`; `web/tests/theme/signal-token.test.ts:14-48,123-156`, `color-scan.ts:97-110`, `contrast.test.ts:59,111-115`; `web/tests/composer/harness.tsx:9-25,42-80,144,175-211`, `fixtures/index.ts:1-108`, `e2e-live-check.mjs:1-29,122-138,171-197`
- `project-docs/stories/deferred-work.md:70,74,77,92,95,96,101,102,104,108,110,111,112,121,125,129,131,146,147,154,155,160,161,164,165,166,171,172,184,185,197,202,204`
- `CLAUDE.md` (test organisation, test transparency, file size); `project-docs/project-context.md:29-32,41-50,63-67`

### Open questions for the PM / designer (not blocking implementation)

1. **How should run progress be shown?** PRD Open Q4, unanswered since Rev 2. This story ships an honest run-level state because AD-13 scopes incremental progress to v2, which means `EXPERIENCE.md:58`'s `Running · 2 of 4 tasks`, `:75`'s active-row pulse and `:113-114`'s `Task 2 of 4, writer, running` are all specified but not shipped. A per-task channel is buildable now that runs are serialised. **Is it worth pulling forward, or is the run-level state acceptable for v1?**
2. **Text-only documents.** `EXPERIENCE.md:188` shows a PDF being dragged in. Nothing in this system can read one, and in-context is the only v1-legal mechanism. Is text-only acceptable for v1, or does PDF extraction become its own story?
3. **Are the document limits right?** ≤5 files, ≤50 000 characters each, ≤100 000 total. No NFR constrains them; these are a judgement call about spend and context windows, and the project has **no performance NFR at all**. That absence is itself worth a decision.
4. **Should the server enforce the key gate on `POST .../build` as well as on run?** This story closes the run gate. `deferred-work.md:184` recommends the build gate too; it is Story 2.0's route, so it was not widened here. Story 2.3 raised this and no answer was recorded.
5. **`EXPERIENCE.md:87` versus `:129`** — *"You'll need at least one model key to run"* is false for a keyless local `ollama` team, which `:129` explicitly supports. Raised by 2.3 and still open; it now affects a real run gate, not just a banner.
6. **Is this story too large for one pass?** It adds a run group, a document mechanism, a server-side gate, run serialisation, a run registry, a whole new surface and a transcript view. The natural split is the **transcript view** (AC 14), which has no UX spec, no upstream FR in the PRD, and no Capability Map row — it could be its own story without blocking anything. The full scope is specified here as the epic defines it; splitting is a product call, not the dev agent's.

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
