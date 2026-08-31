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

## Tool execution integrity (P0 remediation, spec `specs/001-p0-tool-execution-integrity/`)

Runtime execution (`team_maker/runtime/`, `team_maker/adapters/runtime_crewai/`,
`team_maker/ports/execution_engine.py`) predates this section and is unchanged by it except where
noted below.

- **Canonical catalog** (`tools/catalog.py`) — the single source of tool identity. `prompts.py`,
  `schema/request.py` and the generated registry all derive their view from `TOOL_CATALOG` rather than
  restating it. Each entry carries a `RiskClass` (SAFE/RISKY) and `required_credentials`.
  `CONDITIONALLY_AVAILABLE_TOOL_NAMES` marks the few entries whose codegen binding depends on an
  optional dependency (`crewai-tools`, never a team_maker dependency itself).
- **Authorization boundary** (`tools/authorization.py`, `tools/config.py`) — a RISKY tool executes only
  when assigned, canonical, and either SAFE or explicitly operator-enabled. Authorization policy is a
  single operator-owned file (`team_maker.tools.yaml`, mirroring the `team_maker.keys` convention),
  entirely separate from the team-authoring schema — the requesting user's request can never grant
  itself permission.
- **Execution policy** (`tools/policy.py`, `tools/limits.py`, `tools/identifiers.py`) — mandatory
  Docker sandboxing with no opt-out, a mount allowlist evaluated resolve→allow→deny→mode, a
  dangerous-location floor that no configuration can reduce, and a single defaults table for every
  resource control (network, timeouts, CPU/memory/process/output/storage). The same algorithm is
  rendered as self-contained Python into the generated package's `tools.py` (no team_maker import
  there) so a standalone run enforces identically to the product's own run path.
- **`ToolResolver` port** (`ports/tool_resolver.py`) and its **`PackageToolResolver` adapter**
  (`adapters/tools/package_tool_resolver.py`) — the one seam where a declared tool name becomes a
  usable instance, and the only code that ever loads a generated package's `tools.py`. Wired into
  `CrewAIExecutionEngine` via an optional `tool_resolver` constructor argument (defaults to a
  no-package fallback so the engine's own unit tests need no package on disk). Detects and refuses a
  pre-remediation-shape package outright rather than partially loading it.
- **Receipts and completion** (`runtime/results.py`'s `ToolReceipt`, `runtime/completion.py`) — every
  tool execution is recorded (success or failure) via `transcript_capture.py`'s existing crewai event
  subscription; a task cannot be reported successfully complete unless every capability it marks
  *required* has a receipt, and a claimed action needs a *successful* receipt specifically.
- **Preflight gate** (`runtime/preflight.py`) — before any agent is constructed:
  `check_tool_authorization` (denied vs. permitted) and `check_tool_availability` (unknown, missing
  credential, unresolvable) are deliberately separate checks/exceptions, so a diagnostic can always
  tell "not permitted here" from "not available here". `check_mount_allowlist_safety` catches an
  operator policy edited to add a dangerous mount between build and run.
- **Unchanged by this remediation**: the CrewAI version pin and AD-7's provider-routing/credential
  conformance gate (`tests/conformance/`) — verified, not merely assumed, by running that suite
  unmodified against every change above.

---

## Future work (V2+)

- Multiple output formats: JSON schema, LangGraph configs, AutoGen configs
- `team_maker validate <path>` command to validate an existing team package
- Team composition templates (analytics team, data engineering team, ops team)
- Provider adapter layer for runtime execution (use generated team directly)
- Interactive TUI for guided team creation
- Hermes integration layer for multi-provider agent runtime
- Remote template registry (pull templates from a registry URL)
