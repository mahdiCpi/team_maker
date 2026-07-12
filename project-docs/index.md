# Project Documentation Index — team_maker

**Generated:** 2026-07-04
**Primary entry point for AI-assisted development.** Point future PRD/architecture/dev
workflows at this file.

## Project Overview

- **Type:** Monolith (single Python package) — a CLI tool + reusable library
- **Primary language:** Python (≥3.10, targets 3.11)
- **Classification:** Code-generation **factory** (generates standalone multi-agent team packages)
- **Architecture pattern:** Layered pipeline (pipes-and-filters) + plugin registry for templates

## Quick Reference

- **Entry points:** `python -m team_maker` (`__main__.py` → `cli.py`); installed script `team-maker`
- **Spine to read first:** `team_maker/pipeline/runner.py`
- **Input contract:** `team_maker/schema/request.py` (Pydantic v2)
- **Where team design knowledge lives:** `team_maker/templates/software_delivery/template.py`
- **Only intentional disk writer:** `team_maker/artifacts/writer.py`
- **Tech stack:** pydantic, click, pyyaml, rich (runtime) · pytest, pytest-cov, ruff (dev)
- **Supported LLM providers (data-driven, no code change):** anthropic, openai, ollama, groq, google

## Generated Documentation

- [Project Overview](./project-overview.md) — what it is, tech stack, current vs. wanted
- [Architecture](./architecture.md) — layers, data flow, pipeline, validation, gaps
- [Source Tree Analysis](./source-tree-analysis.md) — annotated directory tree + entry points
- [Data Models](./data-models.md) — input schema, domain model, routing, output contract, task DAG
- [Component Inventory](./component-inventory.md) — every module, its API, and collaborators
- [Development Guide](./development-guide.md) — install, run, test, lint, common tasks, gotchas
- [Vision & Target Architecture](./vision-and-target-architecture.md) — L1/L2/L3 design, orchestrator
  wiring, the "openclaw" question, and an incremental build plan

## Existing Documentation (pre-existing, at repo root)

- [README.md](../README.md) — user-facing usage, CLI reference, request YAML schema
- [ARCHITECTURE.md](../ARCHITECTURE.md) — author's design-intent notes, extension points, future work
- [examples/software_delivery_request.yaml](../examples/software_delivery_request.yaml) — reference input

## Getting Started

```bash
pip install -e ".[dev]"
python -m team_maker list-templates
python -m team_maker create --config examples/software_delivery_request.yaml --overwrite
make test
```

## Reading order for a newcomer

1. [Project Overview](./project-overview.md) → 2. [Architecture](./architecture.md) →
3. [Source Tree](./source-tree-analysis.md) → 4. [Data Models](./data-models.md) →
5. [Component Inventory](./component-inventory.md) → 6. [Development Guide](./development-guide.md) →
7. [Vision & Target Architecture](./vision-and-target-architecture.md)

---

## Notes / caveats

- This documentation was produced by **reading source** (deep scan), not by executing the
  project. Before relying on it operationally, run `make test` and `make example` locally.
- The **"what we want"** system (conversational interface + Claude Code orchestrator + running,
  collaborating agents) is **not yet implemented**. It is analyzed in
  [Vision & Target Architecture](./vision-and-target-architecture.md).
- **Open question flagged:** the meaning of *"openclaw"* is unconfirmed — a firm
  recommendation depends on clarifying it (see that doc, §6).
