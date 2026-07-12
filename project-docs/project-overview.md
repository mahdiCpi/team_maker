# Project Overview — team_maker

**Generated:** 2026-07-04
**Repository type:** Monolith (single Python package)
**Primary language:** Python (≥3.10, targets 3.11)
**Project classification:** CLI tool + reusable library (code-generation factory)

---

## Purpose

`team_maker` is a **factory that generates standalone multi-agent team packages**.

It accepts a structured YAML request describing a desired team (roles, per-role LLM
providers, tasks, constraints), runs a deterministic generation pipeline, and writes a
**self-contained team package** to disk. Once written, that package has **no runtime
dependency on `team_maker`** — it is meant to be run by an agent framework such as CrewAI.

> Design philosophy, verbatim from [ARCHITECTURE.md](../ARCHITECTURE.md):
> **"Factory, not orchestrator. `team_maker` generates a team package and exits.
> The generated package is completely self-contained."**

This distinction is the single most important fact about the current codebase, and it is
the crux of the gap between *what exists* and *what is wanted* (see
[vision-and-target-architecture.md](./vision-and-target-architecture.md)).

---

## What it does today (verified against source)

1. Reads a YAML request (`examples/software_delivery_request.yaml` is the reference input).
2. Validates it against Pydantic v2 models in `team_maker/schema/request.py`.
3. Selects a **template** (`software_delivery_team` is the only one built in) via a registry.
4. The template resolves user roles + defaults into `AgentSpec` / `TaskSpec` domain objects.
5. Generators render every artifact **as an in-memory string**.
6. `ArtifactWriter` writes the manifest to the `output_path` directory.
7. `OutputValidator` re-reads the directory and checks required files + YAML integrity.
8. `ReportGenerator` writes `generation_report.md` with the validation outcome.

## What it does NOT do today

- It does **not** run/execute agents. The generated `run_example.py` is a CrewAI starter
  script the *user* runs separately.
- There is **no conversational interface** — input is a static YAML file, output is files.
- There is **no orchestrator** coordinating agents or letting agents talk to each other.
- Only **one** template exists (`software_delivery_team`); `custom` is defined in the enum
  but has no registered implementation.

---

## Tech stack

| Category | Technology | Version | Role in project |
|----------|------------|---------|-----------------|
| Language | Python | ≥3.10 (targets 3.11) | Everything |
| Validation | pydantic | ≥2.5 | Request schema + validation (`schema/request.py`) |
| CLI | click | ≥8.1 | `create` / `list-templates` commands (`cli.py`) |
| Serialization | pyyaml | ≥6.0 | Load requests, dump generated YAML (`utils/yaml_utils.py`) |
| Terminal UI | rich | ≥13.0 | Console panels/tables/tree in CLI output |
| Testing (dev) | pytest, pytest-cov | ≥7.4 / ≥4.1 | Unit + integration tests |
| Lint/format (dev) | ruff | ≥0.3 | `make lint` / `make fmt` |
| Runtime target (generated) | crewai | (not a dependency of this repo) | Runs the *generated* package, not team_maker |

The **providers** a team can route to are pure configuration (data, not code): `anthropic`,
`openai`, `ollama`, `groq`, `google` are documented as supported in the generated
`docs/model_routing.md`. Adding a provider requires **no code change** in `team_maker`.

---

## Repository layout (top level)

```
team_maker/                 ← the Python package (all logic)
examples/                   ← reference request YAML
tests/                      ← unit + integration tests
project-docs/               ← THIS documentation set (non-code)
ARCHITECTURE.md             ← authoritative design notes (pre-existing)
README.md                   ← user-facing usage guide (pre-existing)
Makefile                    ← install / test / lint / example targets
pyproject.toml              ← packaging, deps, ruff, pytest, coverage config
requirements*.txt           ← runtime + dev dependency pins
```

See [source-tree-analysis.md](./source-tree-analysis.md) for the annotated tree.

---

## Where to go next

- Understand the code: [architecture.md](./architecture.md)
- Understand the inputs/outputs: [data-models.md](./data-models.md)
- Understand each module: [component-inventory.md](./component-inventory.md)
- Build/run/test it: [development-guide.md](./development-guide.md)
- The bigger goal (orchestrator, interface, "openclaw"): [vision-and-target-architecture.md](./vision-and-target-architecture.md)
