# Source Tree Analysis — team_maker

**Generated:** 2026-07-04

Annotated directory tree. `→` marks data flow / "calls". Entry points are flagged.

```
team_maker/                         # Repo root
│
├── team_maker/                     # ← THE PACKAGE (all logic lives here)
│   ├── __init__.py                 # Exposes __version__ (read by report generator)
│   ├── __main__.py                 # ENTRY POINT: `python -m team_maker` → cli.main()
│   ├── cli.py                      # ENTRY POINT: Click group; `create`, `list-templates`
│   │                               #   commands. Loads YAML, applies --output/--overwrite,
│   │                               #   validates, runs PipelineRunner, prints rich output.
│   │
│   ├── schema/
│   │   └── request.py              # Pydantic v2 input models. ALL validation lives here:
│   │                               #   TeamCreationRequest, RoleDefinition, ProviderConfig,
│   │                               #   DocumentationLevel, TeamTemplateId enums.
│   │
│   ├── domain/
│   │   └── models.py               # Plain dataclasses (no deps): AgentSpec, TaskSpec,
│   │                               #   GeneratedTeam, ProviderRouting. Each has to_dict().
│   │
│   ├── templates/                  # PLUGIN LAYER (extension seam)
│   │   ├── __init__.py             # Imports template modules so @register fires
│   │   ├── base.py                 # BaseTeamTemplate ABC (generate / default_* methods)
│   │   ├── registry.py             # @register decorator, get_template, list_templates
│   │   └── software_delivery/
│   │       ├── __init__.py
│   │       └── template.py         # ONLY built-in template. _ROLE_DEFAULTS (6 roles),
│   │                               #   _DEFAULT_TASKS (6-task DAG), _DEFAULT_PROVIDER.
│   │
│   ├── generators/                 # PURE STRING PRODUCERS (no disk I/O)
│   │   ├── agent.py                # AgentSpec  → agents/<role>.yaml
│   │   ├── task.py                 # TaskSpec   → tasks/<name>.yaml
│   │   ├── routing.py              # GeneratedTeam → routing_config.yaml
│   │   ├── docs.py                 # GeneratedTeam → README.md + docs/*.md
│   │   └── report.py               # GeneratedTeam + ValidationResult → generation_report.md
│   │
│   ├── pipeline/
│   │   └── runner.py               # PipelineRunner: orchestrates the whole flow. Also
│   │                               #   renders team_config.yaml + run_example.py inline.
│   │
│   ├── artifacts/
│   │   └── writer.py               # ArtifactWriter: {rel_path: content} → disk.
│   │                               #   ONLY intentional filesystem writer. Overwrite guard.
│   │
│   ├── validation/
│   │   └── validator.py            # OutputValidator: required files, per-agent/-task files,
│   │                               #   YAML integrity. Returns ValidationResult.
│   │
│   └── utils/
│       ├── fs.py                   # safe_output_path, ensure_dir, path helpers
│       └── yaml_utils.py           # load_yaml / dump_yaml wrappers
│
├── examples/
│   └── software_delivery_request.yaml   # Reference input. `make example` runs this.
│
├── tests/
│   ├── conftest.py                 # Shared fixtures (full_request, minimal_request)
│   ├── unit/                       # Isolated, in-memory tests per generator/schema/template
│   │   ├── test_agent_generator.py
│   │   ├── test_task_generator.py
│   │   ├── test_docs_generator.py
│   │   ├── test_schema.py
│   │   ├── test_templates.py
│   │   ├── test_artifact_writer.py
│   │   └── test_validation.py
│   └── integration/
│       └── test_pipeline.py        # Full PipelineRunner.run() against tmp_path
│
├── project-docs/                   # ← THIS documentation set (non-code)
├── ARCHITECTURE.md                 # Author's design-intent notes (pre-existing)
├── README.md                       # User-facing usage guide (pre-existing)
├── Makefile                        # install / test(-unit/-integration/-cov) / lint / fmt / example
├── pyproject.toml                  # Packaging, deps, [project.scripts] team-maker, ruff, pytest
├── requirements.txt                # Runtime pins (pydantic, click, pyyaml, rich)
├── requirements-dev.txt            # Dev pins (pytest, pytest-cov, ruff)
└── .gitignore
```

## Critical directories, ranked by importance for a newcomer

1. **`team_maker/pipeline/runner.py`** — read this first; it is the spine that wires
   everything together.
2. **`team_maker/schema/request.py`** — the contract for all input.
3. **`team_maker/templates/software_delivery/template.py`** — where the actual "team design"
   knowledge (roles, tasks, defaults) is encoded.
4. **`team_maker/domain/models.py`** — the vocabulary passed between layers.
5. **`team_maker/generators/`** — how each output file is produced.

## Entry points

| Invocation | Resolves to |
|------------|-------------|
| `python -m team_maker ...` | `team_maker/__main__.py` → `cli.main()` |
| `team-maker ...` (installed script) | `team_maker.cli:main` (see `pyproject.toml [project.scripts]`) |
| `make example` | `python -m team_maker create --config examples/software_delivery_request.yaml --overwrite` |
