---
project_name: 'team_maker'
user_name: 'Guru'
date: '2026-07-04'
sections_completed: ['technology_stack', 'architecture_invariants', 'language_rules', 'validation_rules', 'template_rules', 'testing_rules', 'quality_rules', 'anti_patterns']
existing_patterns_found: 12
status: 'complete'
rule_count: 27
optimized_for_llm: true
---

# Project Context for AI Agents

_This file contains critical rules and patterns that AI agents must follow when implementing code in this project. Focus on unobvious details that agents might otherwise miss._

---

## Technology Stack & Versions

- **Python** ≥3.10, code targets **3.11** (ruff `target-version = py311`; use 3.10+ syntax like `list[str]`, `X | None`).
- Runtime deps: **pydantic ≥2.5** (v2 API only), **click ≥8.1**, **pyyaml ≥6.0**, **rich ≥13.0**.
- Dev deps: **pytest ≥7.4**, **pytest-cov ≥4.1**, **ruff ≥0.3**.
- Packaging: setuptools; console script `team-maker = team_maker.cli:main`.
- `crewai` is NOT a dependency of this repo — it is only the runtime target of the *generated* `run_example.py`. Never `import crewai` in `team_maker/`.

## Critical Implementation Rules

### Architecture invariants (most important — violating these breaks the design)
- **team_maker is a factory, not a runtime.** It generates team packages and exits. Do NOT add agent-execution logic to the `team_maker/` package (that belongs in a future `runner/`, see project-docs/vision-and-target-architecture.md).
- **Generators are pure string producers.** Anything in `generators/` (and `_render_*` helpers) must return a string and never touch the filesystem, network, or clock.
- **Only `ArtifactWriter.write()` and the single report-write in `PipelineRunner.run()` touch disk.** Add new file outputs by extending the manifest in `PipelineRunner._build_manifest`, not by writing files elsewhere.
- **Idempotency is a tested contract** (`test_pipeline_is_idempotent`). Agent/task YAML must be byte-identical across runs. The ONLY permitted nondeterminism is the timestamp in `generation_report.md` and `generated_at` in `team_config.yaml`.

### Language-Specific Rules (Python)
- Start every module with `from __future__ import annotations` (universal in this codebase).
- Full type hints on all public functions/methods; prefer built-in generics (`list`, `dict`) over `typing.List/Dict` in new code, matching existing style.
- Input models = **Pydantic v2 `BaseModel`** (in `schema/`); internal data passed between layers = **plain `@dataclass`** (in `domain/`). Do not blur these — domain models must stay dependency-free.
- Each domain dataclass exposes `to_dict()`. Note the deliberate key remap: **`AgentSpec.to_dict()` emits `routing` under the key `llm`** — preserve this.

### Validation Rules
- **All input validation lives in `schema/request.py`.** Don't scatter validation into generators or the runner.
- Role `name` must be snake_case (`^[a-z][a-z0-9_]*$`) and **unique within a request** (enforced by a model validator).
- Provider names are normalized to lowercase; models are stripped. **Never branch on provider name** — routing is data-driven so new providers (openai, ollama, groq, google, …) need zero code changes.
- LLM resolution order is fixed: `role.llm → request.default_llm → _DEFAULT_PROVIDER (anthropic/claude-sonnet-4-6)`.

### Template / Extension Rules
- Templates self-register via the `@register("template_id")` class decorator and MUST be imported in `team_maker/templates/__init__.py` or the decorator never fires.
- New concrete templates subclass `BaseTeamTemplate` and implement all three abstract methods (`generate`, `default_role_names`, `default_task_names`).
- **User config always wins**; templates only fill blank fields (`role.goal or defaults[...]`). Never overwrite a user-supplied value with a default.
- A task is only emitted if its owning `agent_role` is present, and dangling dependencies are pruned (`_task_dep_available`). Keep this behavior when editing task logic.

### Testing Rules
- Generators are unit-tested **in-memory, no filesystem** — keep them pure so this stays true.
- Filesystem behavior is covered by integration tests using `tmp_path`; use `tmp_path`, never real paths.
- Shared fixtures (`full_request`, `minimal_request`) live in `tests/conftest.py` — reuse them.
- pytest discovery: files `test_*.py`, classes `Test*`, functions `test_*` (see `pyproject.toml`).

### Code Quality & Style Rules
- Ruff: line-length **100**, rule sets `E,F,I,N,W`, `E501` ignored. Run `make lint` / `make fmt` before committing.
- `I` (isort) is enforced — keep imports ordered/grouped.
- `N` (pep8-naming) is enforced — respect the snake_case/PascalCase conventions the linter checks.

### Critical Don't-Miss Rules
- Writing into a non-empty output dir without `overwrite=True` raises `FileExistsError` → CLI exit code **1**. CLI exit codes: `0` ok, `1` config/load/conflict error, `2` validation failed. Preserve this contract.
- `generation_report.md` is intentionally excluded from `OutputValidator._REQUIRED_FILES` because it's written *after* validation — don't "fix" this by adding it.
- `get_template()` raises `ValueError` for unknown ids; the CLI enum `TeamTemplateId.CUSTOM` has no registered implementation — selecting it will fail until one is added.
- Rich console output is cosmetic; never let it carry program logic or data the caller needs (use the returned `PipelineResult`).

---

## Usage Guidelines

**For AI Agents:**

- Read this file before implementing any code in `team_maker/`.
- Follow ALL rules exactly; when in doubt, prefer the more restrictive option.
- The Architecture invariants section is load-bearing — violating it breaks the factory/runtime separation. Cross-check against project-docs/architecture.md.
- Update this file if new durable patterns emerge.

**For Humans:**

- Keep this file lean and focused on what agents miss — not a general style guide.
- Update when the dependency versions in `pyproject.toml`/`requirements.txt` change.
- Review periodically; remove rules that become obvious or obsolete.

Last Updated: 2026-07-04
