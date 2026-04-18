# Architecture Notes — team_maker

## Design philosophy

- **Factory, not orchestrator.** `team_maker` generates a team package and exits.
  The generated package is completely self-contained.
- **Modular, low-coupling.** Each concern is in its own module with a clear interface.
- **Explicit over implicit.** No hidden global state. Pydantic models for all I/O.
- **Testable by design.** All generators produce pure strings; the writer is the only
  module that touches the filesystem.

---

## Module map

```
team_maker/
├── cli.py              # Click CLI — orchestrates pipeline.runner via CLI args
├── schema/
│   └── request.py      # Pydantic v2 models: TeamCreationRequest, RoleDefinition, etc.
│                         All validation lives here.
├── domain/
│   └── models.py       # Plain dataclasses: AgentSpec, TaskSpec, GeneratedTeam.
│                         No dependencies. Easy to unit-test.
├── templates/
│   ├── base.py         # Abstract BaseTeamTemplate interface
│   ├── registry.py     # @register decorator + get_template() / list_templates()
│   └── software_delivery/
│       └── template.py # First built-in template. Registered via @register.
│                         Fills in defaults; user config always wins.
├── generators/
│   ├── agent.py        # AgentSpec → YAML string
│   ├── task.py         # TaskSpec → YAML string
│   ├── docs.py         # GeneratedTeam → markdown strings (README, guides)
│   ├── routing.py      # GeneratedTeam → routing_config.yaml
│   └── report.py       # GeneratedTeam + ValidationResult → generation_report.md
├── artifacts/
│   └── writer.py       # ArtifactWriter: Dict[rel_path, content] → disk
├── pipeline/
│   └── runner.py       # PipelineRunner: orchestrates template → generators → writer
│                         → validator → report
├── validation/
│   └── validator.py    # OutputValidator: checks required files, YAML integrity
└── utils/
    ├── fs.py           # Path utilities (no business logic)
    └── yaml_utils.py   # load_yaml / dump_yaml wrappers
```

---

## Data flow

```
TeamCreationRequest (Pydantic)
        │
        ▼
  BaseTeamTemplate.generate()
        │
        ▼
  GeneratedTeam (dataclass)
        │
        ├── AgentGenerator  →  agents/*.yaml
        ├── TaskGenerator   →  tasks/*.yaml
        ├── DocsGenerator   →  docs/*.md + README.md
        ├── RoutingGenerator →  routing_config.yaml
        └── PipelineRunner  →  team_config.yaml + run_example.py
              │
              ▼
        ArtifactWriter.write()
              │
              ▼
        OutputValidator.validate()
              │
              ▼
        ReportGenerator.render() → generation_report.md
```

---

## Template registration

Templates self-register via the `@register("template_id")` decorator.
The registry is populated by importing `team_maker.templates` (which transitively
imports every template module).  `PipelineRunner` imports the templates package at
startup, so no manual registration call is needed.

To add a template:

```python
# team_maker/templates/my_team/template.py
from team_maker.templates.base import BaseTeamTemplate
from team_maker.templates.registry import register

@register("my_team")
class MyTeamTemplate(BaseTeamTemplate):
    description = "My custom team template."
    ...
```

Then add to `team_maker/templates/__init__.py`:

```python
from team_maker.templates.my_team.template import MyTeamTemplate  # noqa
```

---

## Extension points

| What you want to add | Where to change |
|----------------------|-----------------|
| New team template | `templates/<name>/template.py` + register in `templates/__init__.py` |
| New artifact type | `generators/<name>.py` + call from `pipeline/runner.py` |
| New output format (JSON) | New `artifacts/json_writer.py`; add format flag to CLI |
| New provider | No code change — provider is config; routing is data-driven |
| Runtime agent execution | New `runner/` module (out of scope for V1) |
| Streaming generation | Replace `ArtifactWriter.write` with a streaming variant |

---

## Testing strategy

- **Unit tests**: Each generator is tested in isolation with in-memory data.
  No filesystem required.
- **Integration tests**: `PipelineRunner.run()` is tested with `tmp_path` fixtures.
  Produces real files; assertions check content and structure.
- **Schema tests**: Cover all validation paths including edge cases.
- **Idempotency**: Running the pipeline twice with `overwrite=True` should produce
  identical agent/task YAML (modulo timestamps in the report).

---

## Future work (V2+)

- Multiple output formats: JSON schema, LangGraph configs, AutoGen configs
- `team_maker validate <path>` command to validate an existing team package
- Team composition templates (analytics team, data engineering team, ops team)
- Provider adapter layer for runtime execution (use generated team directly)
- Interactive TUI for guided team creation
- Hermes integration layer for multi-provider agent runtime
- Remote template registry (pull templates from a registry URL)
