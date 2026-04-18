# team_maker

A production-style Python factory that generates **standalone multi-agent team packages**.

`team_maker` accepts a structured YAML request, runs a generation pipeline, and writes a
complete, self-contained team package to disk.  Once written, that package requires **no
dependency on `team_maker`** at runtime.

---

## Quick Start

```bash
# Install
pip install -e ".[dev]"

# Generate the example software delivery team
python -m team_maker create --config examples/software_delivery_request.yaml

# List available templates
python -m team_maker list-templates
```

The generated team lands in the `output_path` defined in your request YAML.

---

## What it generates

```
generated_teams/acme_software_team/
├── README.md                    ← team overview
├── team_config.yaml             ← top-level team manifest
├── routing_config.yaml          ← consolidated LLM routing table
├── run_example.py               ← standalone runner script (CrewAI)
├── generation_report.md         ← what was built + validation status
├── agents/
│   ├── architect.yaml
│   ├── backend_engineer.yaml
│   ├── frontend_engineer.yaml
│   ├── reviewer_qa.yaml
│   ├── devops.yaml
│   └── coordinator.yaml
├── tasks/
│   ├── architecture_design.yaml
│   ├── backend_implementation.yaml
│   ├── frontend_implementation.yaml
│   ├── code_review.yaml
│   ├── testing.yaml
│   └── deployment_guidance.yaml
└── docs/
    ├── how_to_run.md
    ├── how_to_extend.md
    └── model_routing.md
```

---

## CLI reference

```
python -m team_maker COMMAND [OPTIONS]

Commands:
  create            Generate a team package from a YAML request file.
  list-templates    Show all registered team templates.

Options for `create`:
  -c, --config PATH     Path to request YAML (required)
  -o, --output PATH     Override output_path from the config
  --overwrite           Overwrite an existing output directory
  -q, --quiet           Suppress progress output
```

### Example

```bash
python -m team_maker create \
  --config examples/software_delivery_request.yaml \
  --output ./my_teams/startup_team \
  --overwrite
```

---

## Request YAML schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `team_name` | string | Yes | Short unique name |
| `purpose` | string | Yes | One-paragraph purpose |
| `output_path` | string | Yes | Where to write the team package |
| `stack` | string | — | Technology stack (informational) |
| `desired_roles` | list | Yes | At least one RoleDefinition |
| `default_llm` | object | — | Fallback LLM for roles without an explicit one |
| `template` | enum | — | software_delivery_team (default) |
| `documentation_level` | enum | — | minimal / standard / full |
| `overwrite` | bool | — | Overwrite existing output dir |
| `constraints` | list | — | Constraints passed to docs |
| `tags` | list | — | Free-form labels |

### RoleDefinition schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | snake_case string | Yes | Unique role identifier |
| `description` | string | Yes | What this role does |
| `display_name` | string | — | Human-readable name |
| `goal` | string | — | Agent's primary goal (filled by template if absent) |
| `backstory` | string | — | Narrative backstory (filled by template if absent) |
| `capabilities` | list | — | Skill/capability tags |
| `tools` | list | — | Tool names available to this agent |
| `llm` | object | — | Per-role LLM override |
| `is_optional` | bool | — | Mark role as optional |

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

---

## Architecture

See ARCHITECTURE.md for module design, extension points, and future roadmap notes.

---

## Adding a new template

1. Create team_maker/templates/<your_name>/template.py
2. Subclass BaseTeamTemplate and decorate with @register("your_template_id")
3. Import your module in team_maker/templates/__init__.py
4. Write unit tests in tests/unit/

---

## License

MIT
