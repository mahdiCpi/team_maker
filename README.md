# team_maker

A production-style Python factory that generates — and runs — **standalone multi-agent team
packages**.

Describe a team in plain language, review the spec it produces, build it to disk, then run it
against a goal and read the full transcript of what every agent said.

A generated package is self-contained: once written, it has **no dependency on `team_maker`**
to be inspected, edited, or version-controlled.

---

## Install

```bash
python -m venv .venv
.venv/Scripts/activate        # Windows;  source .venv/bin/activate on macOS/Linux

pip install -e ".[dev]"       # factory + CrewAI runtime + test tooling
```

Optional extras, if you don't want the full `dev` set:

| Extra | Pulls in | Needed for |
|-------|----------|------------|
| *(none)* | pydantic, click, pyyaml, rich, jinja2 | `create`, `list-templates` |
| `llm` | anthropic, openai, google-generativeai | `compose`, LLM-planned teams |
| `runtime` | `crewai>=1.14.6,<1.15` | `run` |
| `vector` | chromadb | `state_backend: vector` |
| `all` | all of the above | everything |

The CrewAI pin is deliberate and gated on
[tests/conformance/test_multi_provider_conformance.py](tests/conformance/test_multi_provider_conformance.py) —
see [ARCHITECTURE.md](ARCHITECTURE.md) (AD-7) before widening it.

---

## Key Config

API keys live in a **separate, user-managed file** — never in a request YAML, never in a
generated package, never printed (AD-9). Values are held as `SecretStr` and unwrapped only at
the point of use.

Create `team_maker.keys` in the project root (it is git-ignored):

```ini
# .env-style: one KEY=VALUE per line. '#' comments and blank lines ignored.
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
GOOGLE_AI_API_KEY=...
OPENROUTER_API_KEY=sk-or-...
```

Resolution order: **the file wins**; process environment variables are a fallback used only for
providers the file does not set. Override the location with `$TEAM_MAKER_KEYS` or `--key-file`.

Key names must match the provider catalog exactly. A typo is reported as a warning by
`keys status` rather than failing silently — check there first if a provider looks unavailable.

| Provider | Key name |
|----------|----------|
| `anthropic` | `ANTHROPIC_API_KEY` |
| `openai` | `OPENAI_API_KEY` |
| `google` | `GOOGLE_AI_API_KEY` |
| `groq` | `GROQ_API_KEY` |
| `xai` | `XAI_API_KEY` |
| `openrouter` | `OPENROUTER_API_KEY` |
| `ollama` | *(keyless — local)* |

---

## Quick start

The four-command loop, from an English sentence to a running team:

```bash
# 1. What can I actually route to?
python -m team_maker keys status

# 2. Describe a team -> get a spec YAML you can read and edit
python -m team_maker compose \
  "a two-person team that writes a haiku about the sea and critiques it, using anthropic claude-sonnet-4-6, output to ./generated_teams/haiku_team" \
  --out ./generated_teams/haiku_spec.yaml

# 3. Build the package to disk
python -m team_maker create --config ./generated_teams/haiku_spec.yaml --overwrite

# 4. Run it, and capture every agent turn
python -m team_maker run --package ./generated_teams/haiku_team \
  "Write and critique a haiku about the sea" \
  --transcript --transcript-out ./generated_teams/transcript.txt
```

Step 2 is the review gate: the spec is plain YAML, so you see the roles, tasks, dependency
order, and per-agent model routing **before** spending anything on a run.

To skip the file round-trip, `compose --build` composes and builds in one shot.

---

## CLI reference

```
python -m team_maker COMMAND [OPTIONS]        # or: team-maker COMMAND [OPTIONS]

Commands:
  compose           Describe a team in plain language and get a valid Team Spec.
  create            Generate a team package from a YAML request file.
  run               Run a built Team Package against a goal.
  keys status       Report which providers/models are usable.
  list-templates    Show all registered team templates.
```

### `compose`

```
python -m team_maker compose INTENT [OPTIONS]

  -o, --out PATH        Write the composed spec here (default: print to stdout)
  -f, --key-file PATH   Key Config path (default: $TEAM_MAKER_KEYS or ./team_maker.keys)
      --model TEXT      Override the authoring model (default: claude-sonnet-4-6)
      --build           Build the composed spec immediately via the pipeline
  -i, --interactive     Refine over a back-and-forth; 'run now' builds, 'done' finishes
  -q, --quiet           Suppress progress output (the spec is still emitted)
```

`--interactive` prints the spec, then loops on stdin so you can say *"add a third agent that
translates it to French"* and see the updated spec each turn. The authoring LLM's output is
schema-validated, with a bounded repair loop on validation failures.

### `create`

```
python -m team_maker create --config PATH [OPTIONS]

  -o, --output PATH        Override output_path from the config
      --overwrite          Overwrite an existing output directory
      --framework CHOICE   crewai | langgraph | autogen
      --state-backend      file | vector | both
      --planner-model      Override the planner LLM model
      --no-planner         Force the template path when desired_roles is empty
  -q, --quiet              Suppress progress output
```

Exits `2` if the generated package fails validation.

### `run`

```
python -m team_maker run --package PATH GOAL [OPTIONS]

  -f, --key-file PATH       Key Config path
  -t, --transcript          Print the full agent transcript to the console
      --transcript-out PATH Write the full agent transcript to a file
  -q, --quiet               Suppress progress output
```

A pre-run gate checks every agent's provider **before** any LLM is constructed, so a missing
key or an unroutable provider fails fast with an actionable message and the resolved Key Config
path — not a stack trace mid-run.

---

## Reading the output

`run` prints a **Final result** panel plus a **per-task table** (Task | Agent | Output), so you
can see each step's contribution rather than only the last one.

The transcript is the real verification surface — one line per header, indented content:

```
[2]  write_haiku    / haiku_writer  (task_started)
[7]  write_haiku    / haiku_writer  (agent_message)
[9]  write_haiku    / haiku_writer  (task_completed)
[10] critique_haiku / haiku_critic  (task_started)
[15] critique_haiku / haiku_critic  (agent_message)
[17] critique_haiku / haiku_critic  (task_completed)
```

`grep -n "^\[" transcript.txt` gives you the run skeleton in one screen: which agent ran, in
what order, and where a handoff happened.

Two current limits worth knowing: a transcript is returned only when the run **completes** (a
failed run discards what it collected), and the standalone `run_example.py` inside a generated
package captures no transcript — only the in-process `run` command does. Both are tracked in
[deferred-work.md](project-docs/stories/deferred-work.md).

---

## What gets generated

```
generated_teams/haiku_team/
├── README.md                    ← team overview
├── team_config.yaml             ← top-level team manifest
├── routing_config.yaml          ← consolidated LLM routing table
├── run_example.py               ← standalone runner script
├── requirements.txt             ← the package's own dependencies
├── state_store.py               ← shared state backend
├── tools.py                     ← tool implementations / stubs
├── generation_report.md         ← what was built + validation status
├── agents/
│   ├── haiku_writer.yaml
│   └── haiku_critic.yaml
├── tasks/
│   ├── write_haiku.yaml
│   └── critique_haiku.yaml
└── docs/
    ├── how_to_run.md
    ├── how_to_extend.md
    └── model_routing.md
```

`docker-compose.yml`, `Dockerfile`, and `.dockerignore` are added only when the team routes at
least one agent to Ollama (they bring up the local sidecar).

---

## Provider support

`keys status` reports one of five states per provider:

| Status | Meaning |
|--------|---------|
| `available` | Key present; routable directly |
| `keyless-local` | Local provider, no key needed (Ollama) |
| `via-openrouter` | No direct key, but reachable through the OpenRouter gateway |
| `unsupported-by-runtime` | The installed runtime engine cannot construct this provider |
| `missing` | No key and no gateway route |

`groq` and `xai` are currently `unsupported-by-runtime`: CrewAI 1.14.6 has no native adapter for
either, and this repo does not install the litellm fallback. `google` needs the
`crewai[google-genai]` extra to route directly and is otherwise pointed at OpenRouter. These are
one-line catalog changes once the engine can reach them — see
[deferred-work.md](project-docs/stories/deferred-work.md).

---

## Development

```bash
make install-dev   # install with dev extras
make test          # run all tests
make test-unit     # unit tests only
make test-cov      # coverage report
make lint          # ruff lint
make fmt           # ruff format
make example       # run the example request
```

### What the tests actually cover

Per [CLAUDE.md](CLAUDE.md)'s test-transparency rule, be precise about this:

- **[tests/unit/](tests/unit/)** — the LLM is mocked throughout. Proves wiring, validation,
  CLI behavior, and error paths. Proves nothing about model output quality.
- **[tests/conformance/](tests/conformance/)** — builds **real CrewAI objects** and asserts on
  per-agent routing and transcript capture, but intercepts before any network call. These are
  the AD-7 gate for a CrewAI version bump. Note they `importorskip("crewai")`, so they report
  `SKIPPED` (green) in an environment without the `runtime` extra.
- **[tests/integration/](tests/integration/)** — the only tests that make **real API calls**.
  They read `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` from the *process environment*, not from
  `team_maker.keys`, and skip when unset. Export the variable to run them.

A green suite is not evidence that a team produces good output — run the four-command loop above
for that.

---

## Request YAML schema

Most fields are optional; `compose` fills them in for you.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `team_name` | string | Yes | Short unique name |
| `purpose` | string | Yes | Natural-language description of what the team must build |
| `output_path` | string | Yes | Where to write the team package |
| `stack` | string | — | Technology stack hint |
| `constraints` | list | — | Hard constraints the team must respect |
| `planning_llm` | ProviderConfig | — | LLM used to design the team (default: anthropic claude-sonnet-4-6) |
| `framework` | enum | — | `crewai` (default) / `langgraph` / `autogen` |
| `state_backend` | enum | — | `file` (default) / `vector` / `both` |
| `desired_roles` | list | — | Role hints; if empty, the planner infers all roles from `purpose` |
| `desired_tasks` | list | — | Explicit task plan with dependencies |
| `suggested_tools` | list | — | Custom tools the planner may assign; stubs land in `tools.py` |
| `default_llm` | ProviderConfig | — | Fallback LLM for agents without an explicit one |
| `sandbox` | object | — | Docker sandbox settings for tool execution |
| `git_account` | object | — | Binds a GitAccountTool to agents that need it |
| `notifications` | object | — | Webhook / email / Telegram alert config |
| `context_dir` | string | — | Directory of context files injected into the planner prompt |
| `model_registry` | object | — | Named LLM configs, referenced by key from any `llm` field |
| `documentation_level` | enum | — | `minimal` / `standard` / `full` / `detailed` |
| `overwrite` | bool | — | Overwrite existing output dir |
| `tags` | list | — | Free-form labels |

### RoleDefinition

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | snake_case string | Yes | Unique role identifier |
| `description` | string | Yes | What this role does |
| `display_name` | string | — | Human-readable title |
| `goal` | string | — | Primary goal (filled by template if absent) |
| `backstory` | string | — | Narrative backstory (filled by template if absent) |
| `capabilities` | list | — | Skill tags |
| `tools` | list | — | Tool names available to this agent |
| `llm` | ProviderConfig | — | Per-role LLM override |
| `is_optional` | bool | — | Mark role as optional |

### TaskHint

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | snake_case string | Yes | Unique task identifier |
| `description` | string | Yes | What the task does |
| `agent_role` | string | Yes | Which role owns this task |
| `dependencies` | list | — | Task names this task depends on |

### ProviderConfig

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `provider` | string | Yes | `anthropic` / `openai` / `google` / `xai` / `ollama` / `openrouter` |
| `model` | string | Yes | Model ID (e.g. `claude-sonnet-4-6`, `gpt-4o`) |
| `api_key_env` | string | — | Env-var name recorded in the package |
| `base_url` | string | — | Custom base URL — required for Ollama |

---

## Troubleshooting

**`UnicodeEncodeError: 'charmap' codec can't encode character '✅'` on Windows.**
The legacy Windows console defaults to cp1252 and cannot render the status glyphs in `create`'s
report. The package is written correctly before this point — only the summary crashes. Set
`PYTHONIOENCODING=utf-8` (or use Windows Terminal) before running.

**A provider shows `via-openrouter` when you added its key.**
The key name almost certainly doesn't match the catalog — Google in particular is
`GOOGLE_AI_API_KEY`, not `GOOGLE_API_KEY`. `keys status` prints a warning line naming the
unrecognized key.

**`Missing credentials` on `run`.**
The message names each unresolved provider, the agents routed to it, and the resolved Key Config
path. Check that path is the file you edited.

---

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for module design and extension points, and
[project-docs/](project-docs/) for the PRD, architecture spine, epics, and story records.

---

## Adding a new template

1. Create `team_maker/templates/<your_name>/template.py`
2. Subclass `BaseTeamTemplate` and decorate with `@register("your_template_id")`
3. Import your module in `team_maker/templates/__init__.py`
4. Write unit tests under `tests/unit/`

---

## License

MIT
