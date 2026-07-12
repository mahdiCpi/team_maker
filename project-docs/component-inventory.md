# Component Inventory — team_maker

**Generated:** 2026-07-04

> ⚠️ **INCOMPLETE — reconciliation pending (2026-07-12).** This inventory predates the
> `guru-explore` merge and documents only the original factory. The following **existing (pre-plan)
> components are now in the tree and NOT yet inventoried below** — they are to be refactored to the
> spine (Epic 0):
> - `team_maker/llm/` — `providers.py` (`LLMProvider` ABC + `create_provider`), `model_resolver.py`
>   (live model availability/substitution), `mapper.py`, `planner.py` (`TeamPlanner`), `prompts.py`,
>   `schemas.py`.
> - `team_maker/frameworks/` — `base.py` (`FrameworkAdapter` ABC) + `crewai_adapter.py`,
>   `langgraph_adapter.py`, `autogen_adapter.py`, and a `get_adapter()` registry.
> - `team_maker/codegen/` — `engine.py` (Jinja2 `render_template`) + `templates/*.j2` (runner, tools,
>   state store, Dockerfile/compose, notify helper).
> - `team_maker/keyconfig.py` + `team_maker/providers/registry.py` (Story 1.1; see split-brain note).
>
> The `cli.py` entry below also now has a `keys` group (`keys status`). See
> [reconciliation-notes.md](stories/reconciliation-notes.md).

Every code component, its responsibility, key public surface, and collaborators. Grouped by
layer. All paths are under `team_maker/`.

---

## Interface layer

### `cli.py` — `main` (Click group)
- **Commands:** `create` (`-c/--config`, `-o/--output`, `--overwrite`, `-q/--quiet`) and
  `list-templates`.
- **Responsibility:** load YAML → apply overrides → `TeamCreationRequest.model_validate` →
  `PipelineRunner().run()` → print rich panel/tree.
- **Exit codes:** 0 ok · 1 config/load/conflict error · 2 validation failed.
- **Collaborators:** `utils.yaml_utils.load_yaml`, `schema.request`, `pipeline.runner`.

### `__main__.py`
- Enables `python -m team_maker`; delegates to `cli.main()`.

---

## Schema layer

### `schema/request.py`
- **Classes:** `TeamCreationRequest`, `RoleDefinition`, `ProviderConfig`,
  `DocumentationLevel`, `TeamTemplateId`.
- **Responsibility:** the single source of input validation (regex on names, min lengths,
  unique role names, provider/model normalization).
- See [data-models.md](./data-models.md) for the full field reference.

---

## Domain layer

### `domain/models.py`
- **Dataclasses:** `ProviderRouting`, `AgentSpec`, `TaskSpec`, `GeneratedTeam`.
- **Responsibility:** dependency-free vocabulary passed between template → generators.
- Each provides `to_dict()`; `AgentSpec.to_dict()` maps `routing` → `llm` key.

---

## Template layer (extension seam)

### `templates/base.py` — `BaseTeamTemplate` (ABC)
- Abstract methods: `generate(request) -> GeneratedTeam`, `default_role_names()`,
  `default_task_names()`. Class attrs `template_id`, `description`.

### `templates/registry.py`
- **Public API:** `register(template_id)` (class decorator), `get_template(id)` (fresh
  instance, raises `ValueError` on unknown id), `list_templates()` (`{id: description}`).
- Module-level `_REGISTRY` dict.

### `templates/software_delivery/template.py` — `SoftwareDeliveryTemplate`
- Registered as `software_delivery_team`.
- **Data:** `_ROLE_DEFAULTS` (architect, backend_engineer, frontend_engineer, reviewer_qa,
  devops, coordinator), `_DEFAULT_TASKS` (6-task DAG), `_DEFAULT_PROVIDER`
  (anthropic/claude-sonnet-4-6).
- **Logic:** merges user role fields over defaults (user wins); resolves routing; emits only
  tasks whose owning role exists; prunes dangling dependencies.

### `templates/__init__.py`
- Imports concrete template modules so their `@register` decorators run at import time.

---

## Generator layer (pure string producers, no disk I/O)

| Component | Input → Output | Notes |
|-----------|----------------|-------|
| `generators/agent.py` `AgentGenerator` | `AgentSpec` → YAML | `filename()` = `<role>.yaml` |
| `generators/task.py` `TaskGenerator` | `TaskSpec` → YAML | `filename()` = `<name>.yaml` |
| `generators/routing.py` `RoutingGenerator` | `GeneratedTeam` → `routing_config.yaml` | role→routing map |
| `generators/docs.py` `DocsGenerator` | `GeneratedTeam` → markdown | `render_readme`, `render_how_to_run`, `render_how_to_extend`, `render_model_routing` |
| `generators/report.py` `ReportGenerator` | `GeneratedTeam` + `ValidationResult` → `generation_report.md` | reads `team_maker.__version__` |

> `team_config.yaml` and `run_example.py` are **not** separate generators — they are rendered
> inline by `PipelineRunner` (`_render_team_config`, `_render_run_example`).

---

## Orchestration layer

### `pipeline/runner.py` — `PipelineRunner`
- **Public:** `run(request) -> PipelineResult`.
- **`PipelineResult`:** `output_path, team, written_files, validation`.
- Constructs one instance of each generator + writer + validator; `_build_manifest` assembles
  the full `{rel_path: content}` map. Writes `generation_report.md` after validation.

---

## Artifacts layer

### `artifacts/writer.py` — `ArtifactWriter`
- **Public:** `write(output_path, manifest, *, overwrite=False) -> list[str]`.
- **Type alias:** `ArtifactManifest = Dict[str, str]`.
- Raises `FileExistsError` when the target dir is non-empty and `overwrite=False`. Only
  intentional filesystem writer.

---

## Validation layer

### `validation/validator.py` — `OutputValidator`, `ValidationResult`
- **Public:** `validate(output_path, team) -> ValidationResult`.
- Checks required files, per-agent/per-task files, and parses every `*.yaml`.
- `ValidationResult`: `passed`, `issues[]`, `warnings[]`; `add_issue` sets `passed=False`.

---

## Utilities

| Component | Functions |
|-----------|-----------|
| `utils/fs.py` | `safe_output_path`, `ensure_dir`, `path_is_empty_or_missing`, `relative_file_list` |
| `utils/yaml_utils.py` | `load_yaml`, `dump_yaml` |

---

## Test components (`tests/`)

- **Fixtures:** `conftest.py` provides `full_request` / `minimal_request`.
- **Unit** (`tests/unit/`): one file per generator + `test_schema`, `test_templates`,
  `test_artifact_writer`, `test_validation`. In-memory, no disk.
- **Integration** (`tests/integration/test_pipeline.py`): full `PipelineRunner.run()` against
  `tmp_path`; asserts files exist, YAML validity, per-agent routing round-trips, overwrite
  behavior, and **idempotency**.
