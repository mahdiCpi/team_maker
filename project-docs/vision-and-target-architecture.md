# Vision & Target Architecture — from factory to running system

**Generated:** 2026-07-04
**Status:** Forward-looking design analysis. Nothing in this document is built yet; it maps
the stated goal onto the existing `team_maker` code and lays out options + a recommendation.

> ⚠️ **One term needs clarification.** The request asks *"Is it better to use openclaw for
> this project?"* I could not find a well-known tool named **"openclaw"** and do not want to
> invent facts about it. This doc answers the underlying question — *"should the L2
> orchestrator be Claude Code, or an off-the-shelf open-source agent framework?"* — and flags
> where a concrete answer depends on what "openclaw" actually is. If it refers to a specific
> project you have in mind, tell me and I'll fold a precise comparison in. See §6.

---

## 1. What exists vs. what is wanted

| | Current (`team_maker`) | Wanted |
|---|---|---|
| Input | Static YAML file | A **user conversation** (L1) |
| Design decision | Human writes the request | **Claude Code (L2)** interviews the user and composes the team |
| Output | Files on disk (a team *package*) | A **running** team the user can use |
| Agents | Described in YAML, never executed | **Executed** and able to **collaborate** (L3) |
| Interface | CLI (`create` / `list-templates`) | A **simple interface** (chat/TUI/web) |

`team_maker` already nails the **"design a team" → "materialize it as config"** half. The
missing half is: (a) a conversational front door, (b) an orchestrator that both *drives*
team_maker and *runs* the resulting agents, and (c) inter-agent execution. Note the root
[ARCHITECTURE.md](../ARCHITECTURE.md) "Future work" section already anticipates exactly this
("Provider adapter layer for runtime execution", "Interactive TUI", "integration layer for
multi-provider agent runtime").

---

## 2. The three layers, mapped to concrete pieces

```
L1  USER
     │  natural language ("I need a team that can ship a Django app")
     ▼
L2  CLAUDE CODE  (orchestrator, inside an interface)
     │  ├─ interviews the user, drafts a TeamCreationRequest
     │  ├─ calls team_maker to generate the team package        ← REUSE existing code
     │  ├─ spins up / supervises the agents
     │  └─ routes messages between user ↔ agents ↔ agents
     ▼
L3  TEAM MEMBERS  (the generated agents)
        architect, backend_engineer, ...   — each with its own LLM + task
        can hand work to each other (the task dependency DAG already encodes order)
```

Key insight: **`team_maker` is L2's "team-construction tool", not a competitor to the
orchestrator.** The orchestrator *uses* it. Two distinct responsibilities live at L2:

- **L2a – Composer:** talk to user → produce a validated `TeamCreationRequest` → run
  `PipelineRunner` → get a team package. (team_maker already does everything after the arrow.)
- **L2b – Runtime/Router:** load the generated agents/tasks and actually execute them,
  passing outputs between agents. **This does not exist yet** and is the real build.

---

## 3. The central architectural decision: who runs L3?

There are three credible ways to execute the generated team. They are not mutually exclusive.

### Option A — Claude Code *is* the runtime (subagents + MCP)
Claude Code (Agent SDK) acts as L2 and spawns each team member as a **subagent**; team_maker
is exposed to it as an **MCP tool** ("generate_team") or invoked as a subprocess.
- **Pros:** one system for orchestration *and* execution; native tool-use, delegation, and a
  ready-made interface (Claude Code UI / SDK). Agents can call each other via the orchestrator.
- **Cons:** every agent effectively runs on Claude/Anthropic models via the SDK; the
  per-agent *multi-provider* routing that team_maker carefully models (openai, ollama, groq,
  google) is not honored unless you bridge those providers behind MCP tools.

### Option B — CrewAI is the runtime; Claude Code is the composer/supervisor
This matches what team_maker **already emits** (`run_example.py` targets CrewAI, agents have
`allow_delegation`, tasks have a dependency DAG).
- **Pros:** honors true per-agent multi-provider routing (CrewAI supports many LLM backends);
  minimal new code — you're wiring a runner around generated artifacts; inter-agent
  collaboration is a first-class CrewAI feature.
- **Cons:** two engines to operate (Claude Code for L2, CrewAI for L3); the CrewAI starter
  script is currently a *stub*, not production runtime.

### Option C — Off-the-shelf open-source agent framework as L2+L3 ("openclaw"?)
Adopt a single open-source framework to be both orchestrator and runtime.
- **Pros:** potentially less bespoke glue; community features (memory, tools, routing).
- **Cons:** you'd likely **replace** team_maker's role or force it into the framework's config
  format; you lose the clean factory/runtime separation you already have; lock-in to that
  framework's abstractions.

---

## 4. Recommendation

**Recommended: a hybrid of A + B — Claude Code as L2 (composer + supervisor), CrewAI as the
L3 runtime — and do it incrementally.** Rationale:

1. **Reuse, don't rewrite.** team_maker + its CrewAI-shaped output are assets. Option B turns
   the existing `run_example.py` from a stub into the actual runtime with the least new code.
2. **Preserve the multi-provider promise.** Per-agent routing to anthropic/openai/ollama/etc.
   is a real feature of team_maker. CrewAI can honor it; a pure Claude-Code-subagent runtime
   (Option A alone) cannot without extra provider bridges.
3. **Claude Code is the strongest L2.** It is purpose-built to be a conversational orchestrator
   with tool use, planning, and delegation — ideal for L2a (interview → request) and L2b
   (supervise a run, relay results to the user). Expose team_maker to it as an **MCP server**
   or a subprocess CLI call (the CLI already returns structured results + exit codes).
4. **Keep the seam.** Composition (team_maker) and execution (CrewAI) stay decoupled, exactly
   like the current design intends. If you later want Claude Code to also *execute* agents
   (Option A), that becomes an alternative runtime adapter, not a rewrite.

**On "openclaw" specifically:** unless "openclaw" gives you something the A+B hybrid doesn't —
e.g. a hosted multi-provider runtime with built-in memory and a UI — adopting a whole new
framework as L2 is likely **not** better here, because it would sideline `team_maker` and the
clean factory/runtime split you already have. If "openclaw" is a lightweight open-source Claude
Code *client/interface* (i.e. just the L2 shell), it could be a fine substitute for the
"interface" box without changing this architecture. **I need to know which it is to give a
firm yes/no.**

---

## 5. Concrete build plan (incremental, each step shippable)

1. **Runtime adapter (highest value).** Turn the generated `run_example.py` stub into a real
   `runner/` capable of loading `agents/*.yaml` + `tasks/*.yaml`, wiring per-agent LLMs, and
   executing the task DAG via CrewAI. (Root ARCHITECTURE.md lists this as `runner/` "out of
   scope for V1" — this is V2.)
2. **Expose team_maker to Claude Code.** Wrap `PipelineRunner.run` behind an **MCP tool**
   `generate_team(request_yaml) -> package_path + validation`, or just have L2 shell out to
   `python -m team_maker create ...` and read the exit code / `generation_report.md`.
3. **L2 conversation flow.** A Claude Code agent that: interviews the user → drafts a
   `TeamCreationRequest` → validates it (reuse the Pydantic schema for instant feedback) →
   calls the tool from step 2 → hands the package to the runtime from step 1 → streams results.
4. **Simple interface.** Start with the Claude Code CLI/TUI itself (fastest), then optionally a
   thin web chat that talks to the Agent SDK. Keep the transport swappable.
5. **Inter-agent collaboration.** Use CrewAI delegation (agents already have
   `allow_delegation`) and the existing task dependencies so L3 members pass work to each other;
   L2 supervises and surfaces progress/blockers to L1.
6. **Second template.** Prove the composer generalizes by registering a non-software template
   (the registry + ABC already support this with no core changes).

---

## 6. Open questions to resolve before building

1. **What is "openclaw"?** A framework, a Claude Code client, or something else? (Determines
   §3 Option C vs. just swapping the §5-step-4 interface.)
2. **Must per-agent multi-provider routing be preserved at runtime?** If yes → CrewAI runtime
   (Option B) is strongly favored; if "all agents on Claude is fine" → Option A gets simpler.
3. **Where do agents actually run** — user's machine, a server, containers? (Affects how L2
   supervises L3 and how API keys/secrets are handled.)
4. **Statefulness:** is a team generated once and reused, or regenerated per conversation?
   (Affects whether team packages are persisted, versioned, or ephemeral.)
5. **Human-in-the-loop:** should the user approve the drafted `TeamCreationRequest` before
   generation, and approve agent outputs during a run?

---

## 7. Summary

- Keep `team_maker` as the **team-composition tool** — it already does that job well.
- Build the missing **runtime** (`runner/`) so generated agents actually execute and
  collaborate (L3).
- Use **Claude Code as L2**: conversational composer + run supervisor, calling team_maker via
  MCP/subprocess.
- Prefer **CrewAI** as the execution engine to honor multi-provider routing.
- **"openclaw"**: probably not a better fit *as a replacement orchestrator* given your existing
  assets — but the answer hinges on what it is. Clarify §6-Q1.
