# Running Generated Teams with Local Models (Ollama)

team_maker can wire any generated team to a local Ollama instance, so agents run
on models you host yourself — free, private, offline. This doc covers **what
fits on modest hardware** and **how to pick a model** before you generate the
team.

For the mechanics of how the sidecar is wired into `docker-compose.yml`, see
`docs/how_to_run.md` inside any generated team that uses Ollama.

---

## TL;DR — a concrete baseline

A **small server with 6 CPU cores and 16 GB RAM, no GPU** can comfortably run:

- `qwen3:8b` (strong tool-calling — recommended default)
- `hermes3:8b` (explicitly tuned for function calling)
- `llama3.1:8b`
- `mistral:7b`
- `deepseek-r1:8b` (reasoning distill)

It can also run (tightly, slowly, one at a time):

- `qwen3:14b`, `phi-4:14b`

It **cannot** run:

- Anything 30 B or larger: `qwen3:32b`, `mixtral:8x7b`, full `deepseek-v3`,
  `llama3.3:70b`, `kimi-k2`, full `minimax-m2`, `glm-5` class. These need a
  GPU rig or a server with 64 GB+ RAM.

---

## Sizing: why 16 GB is the ceiling for ~14 B

Ollama defaults to Q4_K_M quantisation (~0.6 GB per 1 B parameters) plus
1–2 GB of KV-cache / context overhead. After OS and Docker leave ~13 GB usable,
you get roughly:

| Param class | RAM at Q4 | Feasible on 16 GB? | Expected CPU tok/s (6 cores) |
|-------------|-----------|--------------------|------------------------------|
| 1–3 B       | ~1–2 GB   | yes, comfortable   | 15–30                        |
| 7–8 B       | ~5 GB     | yes, recommended   | 3–8                          |
| 13–14 B     | ~8–9 GB   | tight, one at a time | 1–3                        |
| 30–34 B     | ~20 GB    | **no** — swaps to disk | unusable                |
| 70 B        | ~40 GB    | **no**             | n/a                          |
| MoE 100 B+  | 100 GB+   | **no**             | n/a                          |

> **Per-token latency** on CPU is roughly linear in parameter count, so an 8 B
> model does ~5 tokens/sec and a 70 B model would do ~0.5 tokens/sec even if
> it fit — multi-minute single responses are normal at large sizes.

---

## Recommended shortlist for a 16 GB / 6 CPU host

These are the tags team_maker treats as "known-good local options". You can
still specify any other Ollama tag — it just may not fit.

| Tag                 | Role it suits                              | RAM   | Notes                                   |
|---------------------|--------------------------------------------|-------|-----------------------------------------|
| `llama3.2:3b`       | fast worker, chatty tasks                  | ~2 GB | 20 tok/s; cheap to run many             |
| `phi-4-mini`        | short-context reasoning                    | ~3 GB | Microsoft; fast                         |
| `qwen3:1.7b`        | micro-agent, summarisation                 | ~1 GB | useful for dispatcher roles             |
| `mistral:7b`        | general-purpose                            | ~4 GB | fast, decent instruction-following      |
| `qwen3:8b`          | **default for tool-calling agents**        | ~5 GB | best overall at this size               |
| `hermes3:8b`        | agents that make many tool calls           | ~5 GB | tuned for function-calling              |
| `llama3.1:8b`       | general-purpose                            | ~5 GB | solid baseline                          |
| `deepseek-r1:8b`    | reasoning / planning                       | ~5 GB | step-by-step reasoning trace            |
| `qwen3:14b`         | harder tasks, one agent at a time          | ~9 GB | tight; close any other heavy processes  |
| `phi-4:14b`         | alt at this size                           | ~9 GB | Microsoft, strong reasoning             |

---

## Practical guidance

**Pick one model for the whole team** whenever possible. Ollama caches weights
in RAM on first use; if two agents use different 8 B models you pay the load
cost twice and may OOM at 16 GB.

**Keep context windows to ~8 K tokens.** Each additional 2 K of context costs
100–500 MB of KV cache depending on the model. Cranking `num_ctx` to 32 K on a
16 GB host will almost certainly swap.

**Serialise agent calls on this hardware.** Two agents hitting Ollama
concurrently halves the effective tok/s for each and increases memory
pressure. For CrewAI this means `Process.sequential`; for LangGraph it means
not fanning out parallel nodes; for AutoGen's `GroupChat` this is already
the default.

**Design for 30–90 second per-turn latency.** A 3-agent sequential crew on
8 B models will take 2–5 minutes end-to-end. Fine for offline/batch work, not
for interactive chat.

**Auto-fallback if a tag 404s.** If a tag like `qwen3.6` doesn't exist in the
Ollama registry, the generated init script falls back to the last known-good
major version (`qwen3`). This keeps the team runnable even when the user
requests a speculative version number.

**Don't put cloud and local agents in the same team unless you have to.** The
compose file still works — cloud agents keep using their API keys — but
network policy gets fiddly because the `runner` container needs both outbound
internet (for the cloud call) and in-network access to `ollama:11434`.

---

## How to request a local model

In your request YAML, set the provider on either the team-wide default or a
specific role:

```yaml
# Team-wide default: all agents use Ollama unless overridden
default_llm:
  provider: ollama
  model: qwen3:8b

# Or: mix cloud + local per agent
desired_roles:
  - name: architect
    description: System design
    llm:
      provider: openai
      model: gpt-4o-mini
  - name: coder
    description: Implementation
    llm:
      provider: ollama
      model: qwen3:8b
```

When `team_maker create` detects any agent routed through `ollama`, it emits:

- `docker-compose.yml` — two services (`ollama` + `runner`) with an init step
  that pulls the requested model(s) on first boot.
- `Dockerfile` — the runner container image.
- A named volume (`ollama_models`) so the weights persist across restarts.

Then the team runs with:

```bash
docker compose up --build
```

No other host setup is needed beyond Docker and Docker Compose.

---

## Known not to work on 16 GB CPU

If you request one of these, team_maker still generates the compose file, but
the container will either fail to pull (no free disk / no registry entry) or
run so slowly it's unusable:

- `kimi-k2`, `kimi-k2-thinking` — ~1 T params MoE; weights alone exceed 500 GB
- `minimax-m2` (full) — similar scale
- `glm-5` / `glm-5-air` — if/when released at the GLM-4.5 plus sizes
- `llama3.3:70b`, `qwen3:72b`, `deepseek-v3` (full), `mixtral:8x22b`

For these, route through a cloud provider (`openai`, `anthropic`) or a hosted
inference endpoint that speaks OpenAI-compatible — not Ollama.
