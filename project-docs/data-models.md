# Data Models — team_maker

**Generated:** 2026-07-04

> ⚠️ **STALE — reconciliation pending (2026-07-12).** This document describes the minimal
> pre-merge schema. The real `team_maker/schema/request.py` (merged from `guru-explore`) has grown
> substantially and includes: `planning_llm` (`ProviderConfig`, default anthropic/claude-sonnet-4-6),
> `framework`, `state_backend`, `git_account`, `sandbox`, `desired_tasks`, `suggested_tools`,
> `context_dir`, `model_registry`, `notifications`, plus a heavy `@model_validator(mode="before")`
> `_pre_process` (stack flattening, `auxiliary_resources_dir → context_dir` aliasing, notification
> channel mapping, tool promotion, and `model_registry` reference resolution). It also uses
> `planning_llm` where the spine glossary says `default_llm`. Bringing this document in line with the
> real schema (and resolving that glossary mismatch) is **Story 0.5**. See
> [reconciliation-notes.md](stories/reconciliation-notes.md).

`team_maker` has no database. Its "data models" are the **input schema** (Pydantic v2,
validated) and the **domain model** (plain dataclasses, produced by templates and consumed by
generators). This document is the contract reference.

---

## 1. Input schema (`team_maker/schema/request.py`)

Validated with Pydantic v2. Validation errors are surfaced field-by-field by the CLI.

### `TeamCreationRequest` (root input)

| Field | Type | Required | Default | Notes / validation |
|-------|------|----------|---------|--------------------|
| `team_name` | str | ✅ | — | min_length 2; must match `^[A-Za-z][A-Za-z0-9_ \-]*$`; stripped |
| `purpose` | str | ✅ | — | min_length 10 |
| `output_path` | str | ✅ | — | non-empty after strip |
| `stack` | str? | — | None | informational only |
| `desired_roles` | list[`RoleDefinition`] | ✅ | — | min_length 1; **role names must be unique** (model validator) |
| `default_llm` | `ProviderConfig`? | — | None | fallback LLM for roles without their own |
| `tools` | list[str] | — | `[]` | shared tools (declared; not currently merged into agents by the template) |
| `constraints` | list[str] | — | `[]` | passed through to docs/report |
| `documentation_level` | `DocumentationLevel` | — | `standard` | enum: minimal / standard / full |
| `template` | `TeamTemplateId` | — | `software_delivery_team` | enum: software_delivery_team / custom |
| `overwrite` | bool | — | False | allow overwriting non-empty output dir |
| `tags` | list[str] | — | `[]` | free-form labels |
| `metadata` | dict[str, Any] | — | `{}` | free-form; carried into `GeneratedTeam.metadata` |

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

### `ProviderConfig`

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `provider` | str | ✅ | normalized to lowercase + stripped (e.g. `anthropic`, `openai`, `ollama`) |
| `model` | str | ✅ | stripped (e.g. `claude-sonnet-4-6`, `gpt-4o`) |
| `api_key_env` | str? | — | env var name holding the key (omit for local models like Ollama) |

### Enums

- `DocumentationLevel`: `minimal` | `standard` | `full`
- `TeamTemplateId`: `software_delivery_team` | `custom` *(only `software_delivery_team` is
  actually registered/implemented)*

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
