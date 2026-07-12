# Development Guide — team_maker

**Generated:** 2026-07-04

---

## Prerequisites

- Python ≥ 3.10 (project targets 3.11; ruff `target-version = py311`)
- `pip` / a virtual environment
- (Optional) `make` — a `Makefile` wraps the common commands. On Windows without `make`,
  run the underlying commands directly (shown below).

## Install

```bash
# with make
make install-dev        # pip install -e ".[dev]"

# without make
pip install -e ".[dev]"
```

`install-dev` pulls runtime deps (pydantic, click, pyyaml, rich) plus dev tools
(pytest, pytest-cov, ruff). Runtime-only install: `pip install -e .` (`make install`).

## Run the tool

```bash
# Generate the example team
python -m team_maker create --config examples/software_delivery_request.yaml
#   note: example config has overwrite:false → add --overwrite to regenerate

# Override output dir + overwrite
python -m team_maker create \
  --config examples/software_delivery_request.yaml \
  --output ./my_teams/startup_team \
  --overwrite

# List registered templates
python -m team_maker list-templates

# Installed console script (after pip install -e .)
team-maker create -c examples/software_delivery_request.yaml --overwrite
```

The generated package lands at the request's `output_path` (example:
`./generated_teams/acme_software_team`). To then *run* that generated team you need
`pip install crewai` and the relevant API keys — that is a separate step, outside this repo.

## Test

```bash
make test              # pytest tests/ -v --tb=short          (all)
make test-unit         # pytest tests/unit/ -v --tb=short
make test-integration  # pytest tests/integration/ -v --tb=short
make test-cov          # coverage (term-missing + html)
```

Without make: `pytest tests/ -v`. Config is in `pyproject.toml`
(`testpaths=["tests"]`, `test_*.py`, `Test*`, `test_*`).

## Lint & format

```bash
make lint    # ruff check team_maker/ tests/
make fmt     # ruff format team_maker/ tests/
```

Ruff config (`pyproject.toml`): line-length 100, rules `E,F,I,N,W`, `E501` ignored.

## Clean

```bash
make clean   # removes dist/ build/ *.egg-info .pytest_cache htmlcov .coverage __pycache__
```

---

## Common development tasks

### Add a new team template
1. Create `team_maker/templates/<your_name>/template.py`.
2. Subclass `BaseTeamTemplate`; implement `generate`, `default_role_names`,
   `default_task_names`; decorate the class with `@register("your_template_id")`.
3. Import it in `team_maker/templates/__init__.py` so the decorator fires.
4. Add it to `TeamTemplateId` in `schema/request.py` if you want it selectable via the enum.
5. Add unit tests under `tests/unit/`.

### Add a new artifact type
Add a generator under `generators/`, then call it from `PipelineRunner._build_manifest`
(and add the file to `_REQUIRED_FILES` in the validator if it must always exist).

### Add a new provider
No code change. Set `provider`/`model`/`api_key_env` in the request YAML. Ensure the
downstream runtime (e.g. CrewAI) supports it.

---

## Conventions & gotchas

- **User config always wins** over template defaults; templates only fill blanks.
- **Only `ArtifactWriter` (and the report write in the runner) touch disk** — keep generators
  pure so unit tests stay filesystem-free.
- **Idempotency is a tested contract** — avoid introducing nondeterminism into agent/task
  YAML. The only intended timestamps are in `generation_report.md` and `team_config.yaml`.
- **Role names are snake_case** (`^[a-z][a-z0-9_]*$`) and must be unique within a request.
- **Overwrite guard:** writing into a non-empty dir without `overwrite` raises
  `FileExistsError` → CLI exit code 1.

---

## Verification recap (this documentation pass)

- **Read**: all `team_maker/**` source modules, `examples/`, `tests/integration/test_pipeline.py`,
  root `README.md`, `ARCHITECTURE.md`, `pyproject.toml`, `Makefile`.
- **Not executed**: no build/test/lint commands were run during documentation generation —
  the docs describe behavior read from source, not observed at runtime. Recommended next
  check before relying on the docs operationally: run `make test` and `make example` locally.
