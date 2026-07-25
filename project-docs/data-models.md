# Data Models — team_maker

**Generated:** 2026-07-04
**Reconciled:** 2026-07-25 (Story 0.5) — §1 rewritten against the live
`team_maker/schema/request.py`; see [reconciliation-notes.md](stories/reconciliation-notes.md)
divergence row 5.

`team_maker` has no database. Its "data models" are the **input schema** (Pydantic v2,
validated) and the **domain model** (plain dataclasses, produced by templates and consumed by
generators). This document is the contract reference.

---

## 1. Input schema (`team_maker/schema/request.py`)

Validated with Pydantic v2. Validation errors are surfaced field-by-field by the CLI.

### `TeamCreationRequest` (root input, 21 fields)

| Field | Type | Required | Default | Notes / validation |
|-------|------|----------|---------|--------------------|
| `team_name` | str | ✅ | — | min_length 2; must match `^[a-zA-Z][a-zA-Z0-9_ \-]*$`; stripped |
| `purpose` | str | ✅ | — | min_length 10 |
| `output_path` | str | ✅ | — | non-empty after strip |
| `stack` | str? | — | None | informational; may arrive as a dict, flattened to a string by `_pre_process` (§1a) |
| `constraints` | list[str] | — | `[]` | passed through to docs/report |
| `planning_llm` | `ProviderConfig` | — | anthropic / claude-sonnet-4-6 / `ANTHROPIC_API_KEY` | LLM the **planner** uses to infer agents/tools/topology from `purpose` — see the [`planning_llm` vs `default_llm`](#planning_llm-vs-default_llm-two-distinct-fields) note below |
| `framework` | `FrameworkChoice` enum | — | `crewai` | `crewai` \| `langgraph` \| `autogen` — agentic framework for the generated team |
| `state_backend` | `StateBackend` enum | — | `file` | `file` \| `vector` \| `both` — how agents persist state between tasks |
| `git_account` | `GitAccountConfig`? | — | None | if set, agents that need it receive a `GitAccountTool` bound to this account |
| `sandbox` | `SandboxConfig` | — | `SandboxConfig()` | Docker sandbox config for executing tools safely |
| `desired_roles` | list[`RoleDefinition`] | — | `[]` | role hints; empty ⇒ planner infers all roles; names must be unique (`check_unique_role_names` model validator) |
| `desired_tasks` | list[`TaskHint`] | — | `[]` | explicit task plan; if provided, the planner uses these as the task list |
| `suggested_tools` | list[`ToolSuggestion`] | — | `[]` | custom tools the planner may assign to agents; stubs generated in `tools.py` |
| `default_llm` | `ProviderConfig`? | — | None | fallback LLM for roles without their own `llm` — see the note below |
| `notifications` | `NotificationConfig`? | — | None | webhook / email / Telegram alert config |
| `context_dir` | str? | — | None | must be an existing directory (validated, resolved to absolute path); aliased from `auxiliary_resources_dir` (§1a) |
| `model_registry` | dict[str, Any]? | — | None | named LLM configs; string refs in `default_llm`/`planning_llm`/role `llm` resolve to inline `ProviderConfig` fields before validation (§1a) |
| `documentation_level` | `DocumentationLevel` enum | — | `standard` | `minimal` \| `standard` \| `full` \| `detailed` |
| `overwrite` | bool | — | False | allow overwriting a non-empty output dir |
| `tags` | list[str] | — | `[]` | free-form labels |
| `metadata` | dict[str, Any] | — | `{}` | free-form; carried into `GeneratedTeam.metadata` |

> A `template: TeamTemplateId` field and a top-level `tools: list[str]` field appeared in an
> earlier version of this document but do not exist on the current `TeamCreationRequest` —
> dropped as pre-merge drift, not carried forward.
>
> Two other corrections from the earlier version of this table, called out explicitly since they
> change documented behavior rather than just adding new fields: `desired_roles` was previously
> documented as **required** with `min_length 1`; the live source makes it optional
> (`default_factory=list`), with role-uniqueness still enforced but emptiness now allowed (the
> planner infers roles when it's empty). `team_name`'s regex character-class ordering was
> corrected to `^[a-zA-Z]...` to match the source byte-for-byte (previously `^[A-Za-z]...` —
> functionally identical, no behavior change).

### `RoleDefinition`

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `name` | str | ✅ | — | **snake_case**: `^[a-z][a-z0-9_]*$` |
| `display_name` | str? | — | None | `resolved_display_name` falls back to Title-cased name |
| `description` | str | ✅ | — | min_length 5 |
| `goal` | str? | — | None | template fills a default if blank |
| `backstory` | str? | — | None | template fills a default if blank |
| `capabilities` | list[str] | — | `[]` | |
| `tools` | list[str] | — | `[]` | |
| `llm` | `ProviderConfig`? | — | None | per-role override (highest priority) |
| `is_optional` | bool | — | False | |

> A role dict may also carry an **input-only** `suggested_tools` key (list of tool names). It is
> not a declared `RoleDefinition` field — `_pre_process` step 4 (§1a) consumes it and promotes
> recognized names into `tools` before validation. It does not survive into the validated model or
> `AgentSpec`.
>
> This is a **different, same-named concept** from the top-level `TeamCreationRequest.suggested_tools`
> field (list of `ToolSuggestion` objects, below) — the role-level key is a plain list of tool-name
> strings filtered through the fixed `_REGISTRY_TOOLS` allow-list, while the top-level field is
> user-defined custom tools with their own `name`/`description`/`env_vars`. They share a name but
> not a shape; don't confuse one for the other.

### `ProviderConfig`

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `provider` | str | ✅ | — | normalized to lowercase + stripped (e.g. `anthropic`, `openai`, `xai`, `google`, `ollama`) |
| `model` | str | ✅ | — | stripped (e.g. `claude-sonnet-4-6`, `gpt-4o`) |
| `api_key_env` | str? | — | None | env var name holding the key (omit for local models like Ollama) |
| `base_url` | str? | — | None | custom base URL — required for Ollama (e.g. `http://localhost:11434`). **Not currently wired through**: neither routing-resolution path (`template.py`/`mapper.py` `_resolve_routing`) copies it into `ProviderRouting` (which has no `base_url` field), and generated `routing_config.yaml` only gets an Ollama URL via a hardcoded default in `generators/routing.py` — a value set here is accepted by validation but silently has no effect on the generated team. |

### `GitAccountConfig`

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `platform` | `"github"` \| `"gitlab"` \| `"bitbucket"` | — | `github` | |
| `token_env` | str | — | `GITHUB_TOKEN` | env var holding the personal access token |
| `org_or_user` | str | ✅ | — | GitHub org or username where repos will be created |
| `default_visibility` | `"private"` \| `"public"` | — | `private` | |

### `NotificationConfig`

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `webhook_url_env` | str | — | `ALERT_WEBHOOK_URL` | env var holding the webhook URL (Slack/Discord/Teams/any HTTP endpoint accepting JSON `{"text": ...}`) |
| `email_to` | str? | — | None | recipient email address for alerts |
| `smtp_host` | str | — | `smtp.gmail.com` | |
| `smtp_port` | int | — | `587` | 587 for STARTTLS, 465 for SSL |
| `smtp_user_env` | str | — | `SMTP_USER` | env var holding the SMTP username / sender address |
| `smtp_password_env` | str | — | `SMTP_PASSWORD` | env var holding the SMTP password |
| `telegram_enabled` | bool | — | False | |
| `telegram_bot_token_env` | str | — | `TELEGRAM_BOT_TOKEN` | |
| `telegram_chat_id_env` | str | — | `TELEGRAM_CHAT_ID` | |

### `ToolSuggestion`

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `name` | str | ✅ | — | snake_case (`^[a-z][a-z0-9_]*$`), unique within the request |
| `description` | str | ✅ | — | min_length 10; shown verbatim to the planner LLM |
| `env_vars` | list[str] | — | `[]` | env vars required at runtime (e.g. `SLACK_WEBHOOK_URL`) |

### `SandboxConfig`

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `image` | str | — | `python:3.12-slim` | |
| `workspace_mount` | str | — | `./workspace` | host path mounted as `/workspace` inside the container |
| `extra_env` | dict[str, str] | — | `{}` | |
| `network` | `"none"` \| `"host"` \| `"bridge"` | — | `bridge` | |

### `TaskHint`

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `name` | str | ✅ | — | snake_case, unique within the request |
| `description` | str | ✅ | — | min_length 10 |
| `agent_role` | str | ✅ | — | which role should own this task |
| `dependencies` | list[str] | — | `[]` | task names this task depends on |

### Enums

- `DocumentationLevel`: `minimal` | `standard` | `full` | `detailed`
- `FrameworkChoice`: `crewai` | `langgraph` | `autogen`
- `StateBackend`: `file` | `vector` | `both`

---

## 1a. Input normalization (`_pre_process`)

`TeamCreationRequest` runs a `@model_validator(mode="before")` named `_pre_process`
(`team_maker/schema/request.py` lines 271-354) before normal field validation. It performs five
independent normalizations, in this order:

1. **`stack` dict-flattening.** If `stack` arrives as a dict, its string values are joined with
   `", "` into a single readable string — except values that look like a placeholder (start with
   `"deferred"`) or a bare snake_case token (`^[a-z][a-z0-9_]*$`), which are dropped. If every
   value is filtered out (or the dict is empty), the result is `""` (empty string), not the field's
   documented default of `None`.
2. **`auxiliary_resources_dir` → `context_dir` aliasing.** If the input has the
   `auxiliary_resources_dir` key and does not already have a `context_dir` key present, its value
   is copied to `context_dir`. This is a **key-presence** check, not a value check — an explicit
   `context_dir: null` alongside `auxiliary_resources_dir` counts as "already present" and blocks
   the alias, silently dropping the aux-dir value.
3. **`notification_channels.telegram` → `notifications.telegram_*` mapping.** Only fires when
   `notification_channels.telegram.enabled` is true. Credentials
   (`telegram.credentials.bot_token_env` / `chat_id_env`) are copied into
   `notifications.telegram_bot_token_env` / `telegram_chat_id_env` (defaulting to
   `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` if absent), and `telegram_enabled` is set to `True`.
   Uses `setdefault` semantics — any `notifications` values already present in the input win.
4. **`suggested_tools` → `RoleDefinition.tools` promotion.** For each role dict in
   `desired_roles` that has an input-only `suggested_tools` list and no `tools` already set, names
   are filtered through a fixed allow-list (`_REGISTRY_TOOLS`): `git_account`, `code_writer`,
   `test_runner`, `linter`, `context_reader`, `shell`, `filesystem`, `docker_runner`, `web_search`,
   `http_client`, `ci_tool`, `code_reader`, `state_reader`, `state_writer`. Unrecognized names are
   silently dropped; if any recognized names remain, they become the role's `tools`.
5. **`model_registry` string-reference resolution.** If `model_registry` is a dict, any string
   value for `default_llm`, `planning_llm`, or a role's `llm` that matches a key in the registry is
   replaced inline with that entry's `provider` / `model` / `api_key_env` / `base_url` fields,
   before normal Pydantic field validation runs. A string that does **not** match any registry key
   is passed through unchanged, which then fails normal field validation (a bare string can't
   construct a `ProviderConfig`) — the resulting error is a generic Pydantic `ValidationError`, not
   one that names the bad registry reference.

### `planning_llm` vs `default_llm` — two distinct fields

These are **not** a naming collision — they are two intentionally separate, independently
configured LLM slots:

- **`planning_llm`** powers `team_maker`'s own plan-inference step (`llm/planner.py`'s
  `TeamPlanner`), which infers agents/tools/topology from `purpose`. It never appears in the
  agent-facing LLM routing chain (§3).
- **`default_llm`** is the fallback LLM for generated agent roles that don't specify their own
  `llm` — see §3's resolution order: `role.llm → request.default_llm → _DEFAULT_PROVIDER`. **That
  chain applies only to the template-based generation strategy** (used when `desired_roles` is
  non-empty). The default strategy — the LLM planner, used when `desired_roles` is empty — never
  reads `RoleDefinition.llm` at all; it resolves each agent's routing from its own generated plan
  via a different code path (`llm/mapper.py`), with its own fallback constant. §3 does not
  currently distinguish the two strategies; treat its chain as template-strategy-specific.

`_pre_process` step 5 above resolves `model_registry` references for both fields independently,
which would be redundant if they were meant to be the same field. No rename is planned — renaming
either would be a breaking schema change for zero benefit, since no code path treats them
interchangeably (verified against `tests/unit/test_schema.py`, `test_model_registry.py`).

---

## 2. Domain model (`team_maker/domain/models.py`)

Plain dataclasses with no external dependencies. Each has a `to_dict()` used by generators.

### `ProviderRouting`
`provider: str`, `model: str`, `api_key_env: str? = None`.
`to_dict()` omits `api_key_env` when falsy.

### `AgentSpec` (fully-resolved agent → `agents/<role>.yaml`)
`role, display_name, description, goal, backstory, capabilities[], tools[],
routing: ProviderRouting, is_optional=False`.
`to_dict()` emits routing under the key **`llm`**.

### `TaskSpec` (→ `tasks/<name>.yaml`)
`name, description, expected_output, agent_role, dependencies[]=, is_optional=False`.

### `GeneratedTeam` (aggregate passed to all generators)
`team_name, purpose, template_used, agents[AgentSpec], tasks[TaskSpec], stack?,
constraints[], tags[], documentation_level="standard", metadata{}`.

---

## 3. LLM routing resolution order

For each role, the software-delivery template resolves the LLM as (first non-null wins):

```
role.llm  →  request.default_llm  →  _DEFAULT_PROVIDER (anthropic / claude-sonnet-4-6)
```

Provider values are free-form strings; the code never branches on them, so **new providers
require no code change** (only that the downstream runtime, e.g. CrewAI, understands them).

---

## 4. Generated package shape (output contract)

For a full software-delivery team, the factory writes:

```
<output_path>/
├── README.md               team_config.yaml       routing_config.yaml
├── run_example.py          generation_report.md
├── agents/<role>.yaml      (one per agent)
├── tasks/<name>.yaml       (one per task)
└── docs/how_to_run.md  docs/how_to_extend.md  docs/model_routing.md
```

- `agents/<role>.yaml` keys: `role, display_name, description, goal, backstory, capabilities,
  tools, llm{provider,model[,api_key_env]}, is_optional`.
- `tasks/<name>.yaml` keys: `name, description, expected_output, agent_role, dependencies,
  is_optional`.
- `routing_config.yaml`: `{team_name, routing: {<role>: {provider, model[, api_key_env]}}}`.

---

## 5. Default task dependency graph (software_delivery_team)

Encoded in `_DEFAULT_TASKS`. A task is only emitted when its owning role is present; a
dependency edge is dropped if its owning role is absent (`_task_dep_available`).

```
architecture_design
      ├─→ backend_implementation ─┐
      └─→ frontend_implementation ┴─→ code_review ─→ testing ─→ deployment_guidance
```

| Task | Owning role | Depends on |
|------|-------------|-----------|
| architecture_design | architect | — |
| backend_implementation | backend_engineer | architecture_design |
| frontend_implementation | frontend_engineer | architecture_design |
| code_review | reviewer_qa | backend_implementation, frontend_implementation |
| testing | reviewer_qa | code_review |
| deployment_guidance | devops | testing |
