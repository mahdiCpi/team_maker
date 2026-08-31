# Contract: Legacy package handling and the advisory migration report

**Modules**: `team_maker/tools/migration.py` (new), `team_maker/cli.py` (new subcommand)
**Requirements**: FR-037 to FR-042 | **Decision**: Q1 (2026-08-29)
**Steps**: 1 (report) and 6 (validation/preflight rejection)

## Scope — read this before writing any code

Two populations, treated differently. Conflating them is the error this contract exists to prevent.

| Population | Behaviour | Requirement |
|---|---|---|
| Existing packages whose declared tools **all resolve safely** through the canonical catalog | **Fully compatible.** Build, validate and run exactly as today. Do **not** appear in the migration report | FR-038, FR-039, FR-047 |
| Existing packages declaring at least one **unknown, invalid, unresolvable, unauthorized or unsafe** tool | Fail validation and fail at run, naming the offending declaration. Appear in the report | FR-037, FR-039 |

**Carrying tool assignments is not a failure condition.** Nine of fifteen examined packages carry
tool assignments; only the subset with non-canonical declarations is affected.

## Failure behaviour (FR-037, FR-038)

1. Failure is **scoped to the offending declarations**. The message names the tool, the declaring
   agent and the package.
2. A package with four safe tools and one invented one fails, and the message names the **single**
   offending declaration rather than implying the whole package is invalid.
3. No package runs with a declared tool silently absent — that is the fabrication path this feature
   closes.

## Report contract (FR-039 to FR-042)

```text
Input:   a directory of generated packages
Reads:   agents/*.yaml per package
Writes:  nothing
Output:  findings for affected packages only
```

Rules, each traceable to a constraint set on 2026-08-29:

1. **Advisory only.** The report MUST NOT modify, rewrite, regenerate or otherwise alter any package.
   Remediation is a user action (FR-040). It opens no file for writing — satisfied by construction,
   not by discipline.
2. **Unambiguous suggestions only.** `suggested_replacement` is set **only** when exactly one catalog
   entry lists the declared name as an alias. Zero candidates or more than one →
   `requires_human_decision = True` and no suggestion (FR-041).
3. **Affected packages only.** A package whose declarations are all canonical yields no findings and
   MUST NOT appear (FR-039).
4. **Reproducible, no side effects.** Running it twice produces the same output and changes nothing
   (FR-042).
5. **Read-only with respect to the packages it inspects.** No mutation, no regeneration, no cache
   written into the package tree.

## Finding shape

See [data-model.md](../data-model.md#8-migrationfinding--team_makertoolsmigrationpy): package, agent
role, declared name, optional suggested replacement, human-decision flag.

## Worked examples from the audit

| Declared | Catalog status | Report says |
|---|---|---|
| `shell_command` | Alias of canonical `shell`, exactly one candidate | Suggest `shell` |
| `code_reader_tool` | Alias of canonical `code_reader`, exactly one candidate | Suggest `code_reader` |
| `SerperDevTool` | CrewAI class name; in no catalog, no alias | Requires human decision |
| `text_summarizer` | Invented; no candidate | Requires human decision |
| `web_scraper` | Could map to `web_search` or `http_client` — ambiguous | Requires human decision, **no suggestion** |
| `code_reader` | Canonical | Not a finding |

## CLI surface

A new subcommand under the existing group. Adding a subcommand does not alter existing command
behaviour (FR-048). It is read-only and safe to run repeatedly.

## Test obligations

| Test | Asserts |
|---|---|
| Safe package unaffected | An all-canonical package builds, validates, runs unchanged and is absent from the report |
| Mixed package | Four safe tools + one invented → fails, naming only the offending declaration |
| No writes | Package tree is byte-identical before and after a report run |
| Ambiguity | A name with two plausible candidates yields no suggestion and flags human decision |
| Idempotence | Two consecutive runs produce identical output |
| Report scope | Zero all-canonical packages appear in the report |
