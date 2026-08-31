# Contract: Canonical tool catalog and declaration validation

**Module**: `team_maker/tools/catalog.py`, `team_maker/tools/validation.py` (new)
**Requirements**: FR-001 to FR-005, FR-043, FR-044, FR-056 to FR-060, FR-065 to FR-069 | **Root cause**: RC-3 | **Audit**: §2.2(a)
**Step**: 1

## The single source

`TOOL_CATALOG: dict[str, ToolDefinition]` is the only authoritative definition of tool identity
(FR-001). Entry shape is in [data-model.md](../data-model.md#1-tooldefinition--team_makertoolscatalogpy).

## Derived views — none may hold its own literal

| Consumer | Today | After |
|---|---|---|
| `team_maker/llm/prompts.py:12-62` | `AVAILABLE_TOOLS` — 13 hardcoded names + descriptions | Derived `{name: definition.description}` view over the catalog |
| `team_maker/schema/request.py:378-382` | `_REGISTRY_TOOLS` — 14 hardcoded names, contains the phantom `"linter"`, filters only `suggested_tools` and only `if not role.get("tools")` | Set deleted. Membership tests read the catalog. Validation additionally covers per-agent `tools` |
| `team_maker/codegen/templates/tools.py.j2:277-306` | `TOOL_REGISTRY` — 13 hardcoded keys, plus stub entries appended | Registry keys and `@tool(...)` decorator arguments both rendered from the catalog key (D-2) |

**Invariant**: after Step 1, `grep` for a hardcoded tool-name list outside `catalog.py` returns
nothing. This is a testable property, not a convention.

## Validation contract

```text
validate_declarations(declarations) -> ValidationOutcome

  For each declaration:
    name in TOOL_CATALOG              → accept
    name matches only an alias        → reject, suggest the canonical name
    name unknown                      → reject, naming the name and its source surface
```

**Stage-deterministic rejection** (FR-056 to FR-060, Amendment 2). One shared validation core, three
named stages with specified outcomes — so the verdict cannot differ between stages while each stage
behaves deterministically (D-11):

| Stage | Behaviour | Requirement |
|---|---|---|
| Compose | **Visibly rejects** the invalid assignment to the user — not a log line | FR-056 |
| Build | **Rejects**; no package containing the declaration is produced | FR-057 |
| Pre-run | **Hard-fails** on unavailable, unauthorized or unresolvable tools | FR-058 |

At no stage may the system substitute a different tool, emit a stub, skip the declaration, or fall
back to a degraded path (FR-059). Every rejection names the offending tool, the declaring agent, the
stage, and the reason class — unknown, invalid, unresolvable, unauthorized or unsafe (FR-060).

**Three availability states** (FR-065 to FR-069, Amendment 4). A canonical tool whose optional
dependency or credential is absent is *known but unavailable* — not unknown, and not a missing
implementation:

| State | Detected at | Outcome |
|---|---|---|
| Unknown — not in catalog | Compose / build / pre-run | Reject per FR-056 to FR-058 |
| Known, no implementation | Build | Build failure (FR-010) |
| Known but unavailable here | Pre-run | Actionable hard failure naming the missing prerequisite (FR-068) |

Build validates the catalog definition and emits the tool's dependency and credential requirements
into the package (FR-066); pre-run validates the actual dependencies, credentials, authorization and
executability in the current environment (FR-067). A stub, silent skip or fallback is prohibited in
all three states.

Rules:

1. **The gate is enforcement, not advice.** `prompts.py:104` Rule 7 ("Do not invent tool names") stays
   as prompt guidance but is never relied on as a gate (FR-003).
2. **Per-agent `tools` is validated.** This is the surface the current `_REGISTRY_TOOLS` filter never
   sees, and where every confirmed invented name landed (FR-002).
3. **`suggested_tools` is validated identically**, including proposed credential variable names,
   which must match a catalog entry's `required_credentials` (FR-004). This closes the path that put
   `SERPAPI_API_KEY` — a name appearing nowhere in the codebase — into a shipped file.
4. **Model-authored descriptions are discarded** (FR-005). The catalog description is what the agent
   sees. This closes the case where a stub's docstring promised *"fetches current information from
   the live web"* four lines above `raise NotImplementedError`.
5. **Aliases are report-only.** A declaration matching only an alias is rejected, not resolved (D-2).

## Confirmed invented names this gate rejects

From audit §2.2(a), verified in shipped artifacts:

`code_reader_tool`, `file_writer_tool`, `shell_tool`, `file_read`, `text_summarizer`, `web_scraper`,
`url_reader`, `twitter_search_tool`, `git_account_tool`, `search_tool`, `file_writer`

Plus the CrewAI class-name leak in `customer_persona_creator/agents/*.yaml`: `FileReadTool`,
`FileWriterTool`, `ScrapeWebsiteTool`, `SerperDevTool` — Python class identifiers, in none of the
three current allowlists.

Plus the phantom `"linter"`, which exists only in `_REGISTRY_TOOLS` and is deleted with it.

## Starter-team correction (FR-043, FR-044)

`team_maker/templates/education/template.py` declares two names in no catalog:

| Line | Declared | Status |
|---|---|---|
| `:38` | `diagram_generator` | Phantom — must be corrected or removed |
| `:74` | `text_analyser` | Phantom — must be corrected or removed |
| `:38,55,74` | `code_reader` | Canonical — unchanged |
| `:55` | `web_search` | Canonical — unchanged |

Scope fence: tool-name declarations only. No other aspect of the starter team, and no other P1
finding, enters on this exception (FR-044).

## Test obligations

| Test | Asserts |
|---|---|
| Single source | No hardcoded tool-name list exists outside `catalog.py` |
| Per-agent gate | Each confirmed invented name above is rejected, naming its source surface |
| Alias not accepted | `shell_command` is rejected as a declaration, with `shell` suggested |
| Suggested-tools gate | An invented `env_vars` entry is rejected |
| Description authority | A model-supplied description never reaches the agent-facing contract |
| Starter team | The education template builds and validates clean |
| Stage determinism | The same invalid declaration is rejected at compose, build and pre-run with a consistent verdict |
| No fallback | No stage substitutes, stubs, skips or degrades on an invalid declaration |
| Rejection content | Every rejection names tool, agent, stage and reason class |
| Known-but-unavailable | A canonical tool with a missing optional dependency hard-fails at pre-run, not at build, and is never treated as unknown |
| Requirements emitted | A built package declares the dependency and credential requirements of its tools |
