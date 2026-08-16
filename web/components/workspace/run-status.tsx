import { cn } from "@/lib/utils"
import type { RunView } from "@/lib/api-types"

const STATUS_LABEL: Record<string, string> = {
  running: "Running",
  complete: "Complete",
  failed: "Failed",
}

/**
 * The run-level state — the ONLY place this surface renders Signal Teal
 * (Story 2.4 AC 12: DESIGN.md reserves the accent for "live / running / now",
 * confined to exactly one component; whitelisted at `signal-token.test.ts`).
 *
 * Ships no fabricated progress. `EXPERIENCE.md:58`'s `Running · 2 of 4 tasks`
 * cannot be rendered truthfully — mid-run the server knows nothing about
 * which task is active (AD-13 / PRD Open Q4 scope incremental progress to
 * v2) — so only the task *count*, which is real and known before the run
 * starts, is shown.
 *
 * One `aria-live="polite"` region, deliberately not nested inside the chat's
 * `role="log"` region: `thinking-indicator.tsx` and `key-check.tsx` both
 * document why a nested live region either double-announces or swallows the
 * announcement depending on the screen reader. Its text changes only on a
 * genuine transition (started / complete / failed), so it announces only
 * those, never a per-task update this surface does not have.
 */
export function RunStatus({ run }: { run: RunView | null }) {
  const announcement = !run
    ? ""
    : run.status === "running"
      ? `Run started. ${run.tasks.length} ${run.tasks.length === 1 ? "task" : "tasks"}.`
      : run.status === "complete"
        ? "Run complete."
        : `Run failed. ${run.failure_reason ?? ""}`.trim()

  // The live region is rendered even with no run, and outside the card below.
  // A live region must already be in the accessibility tree when its content
  // changes; inserting the region and its first text in the same commit is the
  // standard reason an announcement is dropped, and it meant a screen-reader
  // user was told a run had *finished* without ever being told it started.
  const liveRegion = (
    <span role="status" aria-live="polite" className="sr-only">
      {announcement}
    </span>
  )

  if (!run) return liveRegion

  const label = STATUS_LABEL[run.status] ?? run.status

  return (
    <div
      data-slot="run-status"
      data-status={run.status}
      className="flex items-center gap-2 rounded-lg border bg-card px-3 py-2 text-sm"
    >
      <span
        aria-hidden="true"
        data-slot="run-status-dot"
        className={cn(
          "size-2 rounded-full bg-muted-foreground",
          run.status === "running" && "animate-pulse bg-signal"
        )}
      />
      <span data-slot="run-status-label" className="font-medium">
        {label}
      </span>
      {run.status === "running" ? (
        <span className="text-xs text-muted-foreground">
          {run.tasks.length} {run.tasks.length === 1 ? "task" : "tasks"}
        </span>
      ) : null}
      {run.status === "failed" && run.failure_reason ? (
        <span data-slot="run-status-failure-reason" className="text-xs text-destructive">
          {run.failure_reason}
        </span>
      ) : null}
      {liveRegion}
    </div>
  )
}
