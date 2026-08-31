# Contract: `ToolResolver` port

**Module**: `team_maker/ports/tool_resolver.py` (new)
**Adapter**: `team_maker/adapters/tools/package_tool_resolver.py` (new)
**Requirements**: FR-019 to FR-025 | **Root cause**: RC-5 | **Audit**: §2.1 (P0-1)
**Step**: 3-4

## Why a port

`GeneratedTeam` carries no package path and `ExecutionEngine.run(team, credentials, goal)` carries
none either, so `_build_agent` has no route to the package's `tools.py`. The audit's conclusion is
that the fix is "a runtime tool-resolution boundary". This port is that boundary: one named, testable
seam where a declaration becomes an instance, and the only place a generated package's tool module is
ever loaded.

## Interface

```text
class ToolResolver(ABC):

    def resolve(declaration: ToolDeclaration) -> ResolvedTool
        Resolve one validated declaration to a usable instance.

        Preconditions:
          - declaration.name is canonical (validated upstream, Step 1)

        Raises:
          - UnknownToolError       name is not in TOOL_CATALOG
          - UnresolvableToolError  canonical, but no implementation available here
          - ToolPolicyError        resolution would violate execution policy

        Never returns a partially-usable tool. Never returns None.

    def resolve_all(declarations: Sequence[ToolDeclaration]) -> list[ResolvedTool]
        Resolve every declaration or raise. Collects all failures before raising,
        following preflight.check_credentials' "collect, don't short-circuit" rule.
```

## Behavioural contract

1. **Fail closed.** Any failure to resolve refuses the run before it starts (FR-023). There is no
   partially-resolved run and no run that proceeds with a declared tool silently absent.
2. **Collect, don't short-circuit.** `resolve_all` reports every unresolvable declaration in one
   error, matching the established convention in `runtime/preflight.py`.
3. **Credentials are resolved here, separately from model-provider credentials** (FR-022). This path
   MUST NOT call, alter, or duplicate `preflight.check_credentials`, and MUST NOT change credential
   precedence: the key file wins, environment is a per-provider fallback (FR-045).
4. **No credential value is stored on a `ResolvedTool`** or appears in any error this port raises
   (FR-029).
5. **Loading is controlled** (FR-024). The package adapter is the only code that loads a generated
   package's tool module, and what it loads is subject to the execution policy in
   [execution-policy.md](./execution-policy.md).
6. **Engine-agnostic.** The port module MUST NOT import crewai. Enforced the same way
   `preflight.py` is, by the existing port-boundary test.

## Wiring

```text
run_team_package(package_path, goal, key_config, engine=None)
    │
    ├─ load_team_package(package_path)          # unchanged
    ├─ check_runnable(team)                     # unchanged
    ├─ augment_team_for_run(team, goal, ...)    # unchanged
    ├─ check_credentials(team, key_config)      # unchanged — model providers only
    │
    ├─ resolver = PackageToolResolver(package_path, key_config)   # NEW
    └─ engine = CrewAIExecutionEngine(tool_resolver=resolver)     # NEW constructor arg
           └─ engine.run(team, credentials, goal)                 # SIGNATURE UNCHANGED
                  └─ _build_agent(agent, credential)
                         └─ Agent(..., tools=resolver.resolve_all(agent.tools))   # FR-020
```

**The `run()` signature does not change.** The port docstring states it deliberately does not grow to
add capability. The resolver arrives via the engine constructor, defaulting to `None` so every
existing caller and all 15 existing engine tests are unaffected (FR-048).

## Divergence closure

`codegen/templates/crewai_runner.py.j2:105` already does `tools=get_tools_for(cfg.get("tools", []))`.
After this contract lands, the product run path and the standalone package agree on whether declared
tools are attached (FR-025). That agreement is itself a test: the same team, run both ways, attaches
the same tool names.

## Test obligations

| Test | Asserts | Location |
|---|---|---|
| Step 0 oracle | Agent declaring `tools=["shell"]` is constructed carrying a matching tool | `tests/unit/adapters/test_crewai_execution_engine.py` |
| Unresolvable refuses | A canonical tool with no implementation refuses the run, naming it | `tests/unit/runtime/` |
| No partial resolution | One bad declaration among four good ones refuses the whole run | `tests/unit/runtime/` |
| Credential isolation | Tool credential resolution does not alter provider routing or precedence | `tests/unit/adapters/` |
| Port stays engine-agnostic | No crewai import reachable from the port module | existing port-boundary test |
| Path parity | Product run and standalone package attach the same tool names | `tests/integration/` |
