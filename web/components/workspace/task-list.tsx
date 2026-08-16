import type { AgentKeyView, RunView, TaskPlanView } from "@/lib/api-types"

/**
 * Agent key badges plus the task plan, one row per task in topological order
 * (Story 2.4 AC 1 / AC 13, UX-DR6).
 *
 * Three task states are rendered, and each is something the server actually
 * tells us: `Queued`, `Done`, and `Unknown`. `run_team_package` returns a
 * batch result with no per-task status (AD-13, v1), so a row can never show
 * progress *during* a run — but it can distinguish the three run-level
 * outcomes. On `complete` the engine has returned a result for every submitted
 * task or raised (`CrewAIExecutionEngine.run`'s count-mismatch guard), so all
 * rows are `Done` together.
 *
 * On `failed`, the honest answer is `Unknown`: the run consumed real time and
 * real spend, some tasks very likely ran, and the server discards a failed
 * run's partial transcript (`deferred-work.md:101`) — so we know that we do
 * not know. Rendering `Queued` beside a run-level "Failed", as this did,
 * asserts that nothing was attempted, which is a claim no data supports.
 *
 * Per-task output expansion uses the native `<details>`/`<summary>` — no
 * `accordion` or `collapsible` is installed, and none is needed for this.
 */
export function TaskList({
  agents,
  tasks,
  run,
}: {
  agents: AgentKeyView[]
  tasks: TaskPlanView[]
  run: RunView | null
}) {
  const agentByRole = new Map(agents.map((agent) => [agent.role, agent]))
  const outputByName = new Map((run?.result?.task_results ?? []).map((r) => [r.name, r]))
  const done = run?.status === "complete"
  const rowStatus = done ? "Done" : run?.status === "failed" ? "Unknown" : "Queued"

  return (
    <div data-slot="task-list-panel" className="flex flex-col gap-3">
      {agents.length > 0 ? (
        <ul data-slot="agent-badges" className="flex flex-wrap gap-2">
          {agents.map((agent) => (
            <li
              key={agent.role}
              data-slot="agent-badge"
              data-usable={agent.usable}
              className="rounded-full border px-2 py-1 text-xs"
            >
              <span className="font-medium">{agent.role}</span>{" "}
              <span className="text-muted-foreground">
                {agent.provider}/{agent.model}
              </span>
              {!agent.usable ? (
                <span data-slot="agent-badge-fix-hint" className="ml-1 text-destructive">
                  · {agent.fix_hint ?? "not usable"}
                </span>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}

      <ol data-slot="task-list" className="flex flex-col gap-2">
        {tasks.map((task) => {
          const agent = agentByRole.get(task.agent_role)
          const output = outputByName.get(task.name)
          const status = rowStatus
          return (
            <li
              key={task.name}
              data-slot="task-row"
              data-status={status.toLowerCase()}
              className="rounded-lg border bg-card px-3 py-2 text-sm"
            >
              <div className="flex items-center justify-between gap-2">
                <div>
                  <p data-slot="task-name" className="font-medium">
                    {task.name}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {task.agent_role}
                    {agent ? ` · ${agent.provider}/${agent.model}` : ""}
                  </p>
                </div>
                <span data-slot="task-status" className="text-xs text-muted-foreground">
                  {status}
                </span>
              </div>
              {done && output ? (
                <details data-slot="task-output" className="mt-2 text-xs">
                  <summary className="cursor-pointer text-muted-foreground">
                    View output
                  </summary>
                  <p className="mt-1 whitespace-pre-wrap">{output.output}</p>
                </details>
              ) : null}
            </li>
          )
        })}
      </ol>
    </div>
  )
}
