# Architecture — team_maker

**Generated:** 2026-07-04
**Scope:** Current, as-built architecture of the `team_maker` package.
**Companion:** The pre-existing [ARCHITECTURE.md](../ARCHITECTURE.md) at repo root is the
author's design-intent document; this file is a verified, navigation-oriented restatement
plus notes on what the code actually does.

> ⚠️ **Superseded in part (2026-07-12).** This describes the original single-pass factory. Since the
> `guru-explore` merge the package also contains an **LLM-driven planning path** (`team_maker/llm/`),
> a **Jinja code-generation engine** (`team_maker/codegen/`), and **framework adapters**
> (`team_maker/frameworks/`: crewai/langgraph/autogen) — a richer design than the pipeline described
> here. That code **diverges from the target ports-and-adapters spine** (see
> `architecture/architecture-team_maker-2026-07-05/ARCHITECTURE-SPINE.md`), which **remains the
> target**. Migrating the merged code onto the spine is **Epic 0**. See
> [reconciliation-notes.md](stories/reconciliation-notes.md).
>
> ⚠️ **Update (2026-07-18 — Story 0.3 complete):** The `crewai` adapter has been reconciled
> to the spine: `CrewAIAdapter` now lives in `team_maker/adapters/runtime_crewai/` and satisfies
> the new `team_maker/ports/runtime_engine.RuntimeEngine` Protocol; `frameworks/crewai_adapter.py`
> is a back-compat shim. The `langgraph` and `autogen` adapters remain in `frameworks/` and are
> still pending reconciliation (Stories TBD).

---

## 1. Executive summary

`team_maker` is a **single-pass code-generation factory**. A validated request flows through
a fixed pipeline of pure, single-responsibility components and produces a directory of files.
The architecture is deliberately **stateless** and **side-effect-isolated**: every generator
returns a *string*, and only one component (`ArtifactWriter`) — plus one direct write of the
report in the runner — touches the filesystem.

Architectural style: **layered pipeline / pipes-and-filters**, with a **plugin registry** for
templates.

---

## 2. Layers & responsibilities

| Layer | Module(s) | Responsibility | Touches disk? |
|-------|-----------|----------------|---------------|
| Interface | `cli.py`, `__main__.py` | Parse args, load YAML, print results | Reads config only |
| Schema | `schema/request.py` | Validate & normalize input (Pydantic v2) | No |
| Domain | `domain/models.py` | Plain dataclasses (`AgentSpec`, `TaskSpec`, `GeneratedTeam`, `ProviderRouting`) | No |
| Template | `templates/*` | Turn a request into a `GeneratedTeam` (fill defaults) | No |
| Generators | `generators/*` | Render each artifact to a string | No |
| Orchestration | `pipeline/runner.py` | Wire template → generators → writer → validator → report | Writes report only |
| Artifacts | `artifacts/writer.py` | Write the manifest `{path: content}` to disk | **Yes** |
| Validation | `validation/validator.py` | Re-read output, verify files & YAML integrity | Reads output |
| Utils | `utils/fs.py`, `utils/yaml_utils.py` | Path + YAML helpers (no business logic) | fs helpers |

---

## 3. Data flow (verified against `pipeline/runner.py`)

```
YAML file
   │  load_yaml()  (utils/yaml_utils)
   ▼
raw dict  ──(CLI overrides: --output / --overwrite)
   │  TeamCreationRequest.model_validate()   (schema/request.py)
   ▼
TeamCreationRequest (validated, Pydantic)
   │  get_template(request.template).generate(request)   (templates/registry + software_delivery)
   ▼
GeneratedTeam (dataclasses: agents[], tasks[], metadata)   (domain/models.py)
   │  PipelineRunner._build_manifest()
   ▼
ArtifactManifest = { "README.md": "...", "agents/architect.yaml": "...", ... }
   │  ArtifactWriter.write(output_path, manifest, overwrite)   (artifacts/writer.py)
   ▼
files on disk
   │  OutputValidator.validate(output_path, team)   (validation/validator.py)
   ▼
ValidationResult (passed / issues / warnings)
   │  ReportGenerator.render(...)  →  output_path/generation_report.md
   ▼
PipelineResult(output_path, team, written_files, validation)
```

**Exit codes** (`cli.py`): `0` success, `1` bad config / load error / output conflict,
`2` pipeline ran but validation failed.

---

## 4. The generation pipeline in detail

`PipelineRunner.run(request)` performs, in order:

1. `safe_output_path()` — expand `~`, resolve to an absolute path.
2. `get_template(request.template.value).generate(request)` → `GeneratedTeam`.
3. `_build_manifest(team, request)` — assembles the full `{rel_path: content}` map:
   - `README.md`, `team_config.yaml`, `routing_config.yaml`, `run_example.py`
   - `agents/<role>.yaml` for each agent
   - `tasks/<name>.yaml` for each task
   - `docs/how_to_run.md`, `docs/how_to_extend.md`, `docs/model_routing.md`
4. `ArtifactWriter.write(...)` — raises `FileExistsError` if the dir is non-empty and
   `overwrite=False`.
5. `OutputValidator.validate(...)` — post-write check (see §6).
6. Renders and writes `generation_report.md` *after* validation (so it can include results),
   then appends it to the `written_files` list.

Note: `team_config.yaml` and `run_example.py` are rendered **inside the runner**
(`_render_team_config`, `_render_run_example`), not in a dedicated generator. `team_config.yaml`
embeds a `generated_at` UTC timestamp — the one intentional source of non-determinism.

---

## 5. Template subsystem (the extension seam)

- `templates/base.py` — `BaseTeamTemplate` ABC: `generate()`, `default_role_names()`,
  `default_task_names()`.
- `templates/registry.py` — module-level `_REGISTRY` dict; `@register("id")` class decorator
  sets `cls.template_id` and registers it; `get_template()` returns a fresh instance;
  `list_templates()` returns `{id: description}`.
- `templates/__init__.py` — imports each template module so its `@register` decorator fires
  at import time. `PipelineRunner` and `cli.list-templates` both import `team_maker.templates`
  to guarantee registration before lookup.
- `templates/software_delivery/template.py` — the only concrete template.
  - Holds `_ROLE_DEFAULTS` (6 known roles: architect, backend_engineer, frontend_engineer,
    reviewer_qa, devops, coordinator) and `_DEFAULT_TASKS` (6 tasks with a dependency DAG).
  - **User config always wins**; template fills blanks (`role.goal or defaults[...]`).
  - `_DEFAULT_PROVIDER = anthropic / claude-sonnet-4-6` is the final routing fallback
    (role LLM → request `default_llm` → this default).
  - A task is emitted only if its owning `agent_role` is present, and dependencies are
    filtered to those whose owning role is also present (`_task_dep_available`).

To add a template: implement `BaseTeamTemplate`, decorate with `@register`, import it in
`templates/__init__.py`. No other change needed.

---

## 6. Validation model

`OutputValidator.validate(output_path, team)` returns a `ValidationResult`:

- `_check_required_files` — `README.md`, `team_config.yaml`, `run_example.py`,
  `docs/how_to_run.md`, `docs/how_to_extend.md`, `docs/model_routing.md` must exist.
  (`generation_report.md` is intentionally excluded — it is written *after* validation.)
- `_check_agent_files` — one `agents/<role>.yaml` per agent.
- `_check_task_files` — `tasks/` dir + one file per task; **warns** (does not fail) if the
  team has zero tasks.
- `_check_yaml_integrity` — `yaml.safe_load` every `*.yaml` under the output; malformed YAML
  becomes an issue (fails validation).

`add_issue` flips `passed=False`; `add_warning` does not.

---

## 7. Key design properties

- **Purity / testability:** generators are pure string producers → unit-tested with in-memory
  data, no filesystem. Only `ArtifactWriter` + the report write hit disk.
- **Idempotency:** two runs with `overwrite=True` produce identical agent/task YAML (verified
  by `test_pipeline_is_idempotent`); only report/`team_config.yaml` timestamps differ.
- **Explicit over implicit:** no hidden global state except the template registry (populated
  deterministically at import).
- **Data-driven providers:** provider/model routing is config that flows straight through to
  YAML; the code never branches on provider name.

---

## 8. Known gaps / limitations (as-built)

- Runtime execution of agents is **out of scope** (explicitly, per root ARCHITECTURE.md
  "Future work"). The generated `run_example.py` targets CrewAI but is a starter, not a
  supported runtime.
- Only `software_delivery_team` is registered; `TeamTemplateId.CUSTOM` has no implementation.
- No conversational/interactive input path — the input is a static YAML file.
- No inter-agent communication or orchestration layer exists in this repo.

These gaps are exactly the surface area of the proposed L1/L2/L3 system — see
[vision-and-target-architecture.md](./vision-and-target-architecture.md).
