"use client"

import * as React from "react"

import type { TranscriptEntry } from "@/components/composer/composer-state"
import { Transcript } from "@/components/composer/transcript"
import { Button } from "@/components/ui/button"
import {
  RUN_POLL_INTERVAL_MS,
  createRun,
  getRun,
  getRunTranscript,
  getTeamPlan,
} from "@/lib/api-client"
import { DocumentTray } from "@/components/workspace/document-tray"
import { GoalInput } from "@/components/workspace/goal-input"
import { RunStatus } from "@/components/workspace/run-status"
import { TaskList } from "@/components/workspace/task-list"
import { TranscriptDialog } from "@/components/workspace/transcript-dialog"
import {
  INITIAL_WORKSPACE_STATE,
  currentTurn,
  isRunInFlight,
  workspaceReducer,
  type ChatTurn,
} from "@/components/workspace/workspace-state"

/**
 * The Team Workspace (Story 2.4 AC 11) — chat with a built team, attach
 * documents, run against a goal, read results (`EXPERIENCE.md:35`).
 *
 * This is the one `"use client"` root for the route; `app/teams/[slug]/page.tsx`
 * stays a server component so its `metadata` export survives, exactly as
 * `ComposerSurface`/`app/page.tsx` are split.
 *
 * **FR-23's reading, shipped here:** `prd.md:356-358` asks for a chat surface
 * to "give goals, ask follow-ups", and `prd.md:385` says "not a
 * general-purpose chatbot". With AD-5 ("the Runtime executes only" — no
 * conversational agent exists to talk back), the only honest reading is that
 * this chat is a **goal-entry and outcome log**: the user's turn is a goal,
 * the system's turn is the run's outcome. It does not simulate a reply while
 * a run is in flight (`RunStatus` reports that instead) — reused from
 * `components/composer/` are exactly `Transcript` and `MessageBubble`, per
 * this story's instruction not to fork them.
 */
export function WorkspaceSurface({ teamSlug }: { teamSlug: string }) {
  const [state, dispatch] = React.useReducer(workspaceReducer, INITIAL_WORKSPACE_STATE)
  const [goal, setGoal] = React.useState("")

  // The team plan is read once. Unlike the Composer's key status, nothing on
  // this surface changes which team is being viewed within one page load —
  // `teamSlug` is this route's own param, not a value a user edits here.
  React.useEffect(() => {
    let cancelled = false
    void (async () => {
      const result = await getTeamPlan(teamSlug)
      if (cancelled) return
      if (result.ok) dispatch({ type: "plan_loaded", plan: result.data })
      else dispatch({ type: "plan_load_failed" })
    })()
    return () => {
      cancelled = true
    }
  }, [teamSlug])

  // A ref *and* a state value, deliberately. The ref is the guard: `useState`
  // updates on re-render, so two clicks dispatched before React re-renders
  // would both read `submitting === false` and both POST. The state value
  // exists only so the blocked reason can be rendered.
  const submittingRef = React.useRef(false)
  const [submitting, setSubmitting] = React.useState(false)

  const turn = currentTurn(state)
  const running = isRunInFlight(state)
  // Read as primitives before the effect below, so its dependency array
  // names exactly what it uses — no `turn` object identity to reason about,
  // and no `eslint-disable` (2.3 measured that one it wrote was itself
  // reported as unnecessary).
  const pollingRunId = running ? (turn?.runId ?? null) : null
  const pollEpoch = state.pollEpoch

  // Poll while the current run is in flight. The epoch is captured before
  // the interval starts and compared on every tick's result, so a poll
  // answer for a run the user has since superseded (a new run started) is
  // discarded rather than applied — the same guard `keyCheckEpoch` gives the
  // Composer's key check.
  React.useEffect(() => {
    if (!pollingRunId) return
    let cancelled = false
    const timer = setInterval(() => {
      void (async () => {
        const result = await getRun(pollingRunId)
        if (cancelled) return
        if (result.ok) {
          dispatch({ type: "run_updated", run: result.data, epoch: pollEpoch })
        } else if (result.code === "run_not_found") {
          // The one poll failure that is permanent, not transient: the record
          // was evicted (30-minute idle TTL) or the server restarted, so every
          // future tick can only 404 too. Treating it as retryable left the tab
          // polling forever and the `Run` control blocked on "a run is already
          // in progress" — a state only a page reload escaped.
          dispatch({ type: "run_lost", runId: pollingRunId, message: result.message })
        }
        // Anything else is genuinely transient (a timeout, a dropped
        // connection, a 5xx): the next tick retries and the last known run
        // state is kept.
      })()
    }, RUN_POLL_INTERVAL_MS)
    return () => {
      cancelled = true
      clearInterval(timer)
    }
  }, [pollingRunId, pollEpoch])

  // Once transcript_available flips true, fetch the transcript once — it is
  // a separate GET (1.7 / this story's own AC 14), not inlined into every
  // poll response, so the Workspace does not pay for it until it exists.
  const transcriptRunId = turn?.run.transcript_available ? turn.runId : null
  // Read as primitives so the dependency array names exactly what it uses.
  // `transcriptAttempt` is bumped on every dialog open, which is what makes a
  // failed load retry when the user does what the failure copy tells them to;
  // `transcriptLoaded` stops that from refetching one already in hand.
  const transcriptLoaded = state.transcript !== null
  const transcriptAttempt = state.transcriptAttempt

  React.useEffect(() => {
    if (!transcriptRunId || transcriptLoaded) return
    let cancelled = false
    void (async () => {
      const result = await getRunTranscript(transcriptRunId)
      if (cancelled) return
      if (result.ok) dispatch({ type: "transcript_loaded", transcript: result.data })
      // Swallowing this left the dialog saying "No transcript is available for
      // this run yet" — a claim the server never made, about a transcript that
      // exists and is thirty minutes from eviction.
      else dispatch({ type: "transcript_load_failed" })
    })()
    return () => {
      cancelled = true
    }
  }, [transcriptRunId, transcriptLoaded, transcriptAttempt])

  async function submitGoal() {
    const text = goal.trim()
    if (text.length === 0) return
    // `running` only becomes true once `createRun` resolves, and the server's
    // synchronous gate (a package load plus a credential check) means that is
    // not instant. Without this, a double-click or a double Enter sent two
    // POSTs: the server serialised them correctly, and the client then showed
    // the second one's `run_in_progress` as a red alert over the user's own
    // perfectly healthy run.
    if (submittingRef.current) return
    submittingRef.current = true
    setSubmitting(true)
    try {
      const documents = state.documents
      dispatch({ type: "run_requested" })
      const result = await createRun({
        team_slug: teamSlug,
        goal: text,
        documents: documents.map(({ name, text: body }) => ({ name, text: body })),
      })
      if (result.ok) {
        setGoal("")
        dispatch({
          type: "run_started",
          runId: result.data.run_id,
          goal: text,
          run: result.data,
          sentDocumentIds: documents.map((document) => document.id),
        })
      } else {
        dispatch({ type: "run_request_failed", failure: result })
      }
    } finally {
      submittingRef.current = false
      setSubmitting(false)
    }
  }

  const sendBlockedReason = running
    ? "A run is already in progress. Wait for it to finish before starting another."
    : submitting
      ? "Starting the run…"
      : state.plan === null
        ? state.planFailed
          ? "Could not load this team. Reload the page to try again."
          : "Loading this team…"
        : null

  return (
    <div data-slot="workspace" className="flex min-h-0 flex-1 flex-col gap-4 md:flex-row">
      <h1
        id="page-heading"
        tabIndex={-1}
        className="text-xs font-medium tracking-wide text-muted-foreground uppercase"
      >
        Team Workspace
      </h1>
      <div className="flex min-h-0 flex-1 flex-col gap-3 md:basis-2/3">
        {state.turns.length === 0 ? (
          <div className="flex min-h-0 flex-1 flex-col items-center justify-center gap-1 text-center">
            <p data-slot="workspace-empty-title" className="text-sm font-medium">
              Give this team a goal.
            </p>
            <p className="text-xs text-muted-foreground">
              Describe what you want it to do. Attach reference documents if it helps.
            </p>
          </div>
        ) : (
          <Transcript
            entries={chatEntries(state.turns)}
            thinking={false}
            footerSignal={state.failureRevision}
          />
        )}

        {/* A sibling of the transcript/empty-state branch above, not nested
            inside it — a run can fail to start (`run_blocked`, before any
            turn exists) exactly as easily as one can fail once a
            conversation is under way, so this must render regardless of
            which branch above is showing. */}
        {state.runRequestFailure ? (
          <p
            data-slot="workspace-run-request-failure"
            role="alert"
            className="text-sm text-destructive"
          >
            {state.runRequestFailure.message}
          </p>
        ) : null}

        {state.runLost ? (
          <p
            data-slot="workspace-run-lost"
            role="alert"
            className="text-sm text-destructive"
          >
            {state.runLost.message}
          </p>
        ) : null}

        {/* Rendered unconditionally, not gated on `turn`. A live region has to
            exist in the accessibility tree *before* its content changes, or the
            first announcement is dropped — which is why a screen-reader user
            used to be told a run had finished without ever being told it had
            started. `RunStatus` renders the region always and the visible card
            only when there is a run. */}
        <RunStatus run={turn?.run ?? null} />

        <DocumentTray
          documents={state.documents}
          error={state.documentError}
          blockedReason={
            running ? "Documents apply to the next run — wait for this one to finish." : null
          }
          onAttach={(document) => dispatch({ type: "document_attached", document })}
          onAttachFailed={(reason) => dispatch({ type: "document_attach_failed", reason })}
          onRemove={(id) => dispatch({ type: "document_removed", id })}
        />

        <GoalInput
          value={goal}
          onValueChange={setGoal}
          onSend={() => void submitGoal()}
          sendBlockedReason={sendBlockedReason}
        />
      </div>

      <div className="flex min-h-0 flex-1 flex-col gap-3 md:basis-1/3">
        {state.plan ? (
          <TaskList
            agents={state.plan.agents}
            tasks={state.plan.tasks}
            run={turn?.run ?? null}
          />
        ) : state.planFailed ? (
          <p data-slot="workspace-plan-failure" className="text-sm text-muted-foreground">
            Could not load this team&apos;s plan.
          </p>
        ) : null}

        {turn?.run.transcript_available ? (
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => dispatch({ type: "transcript_dialog_opened" })}
            data-slot="workspace-open-transcript"
          >
            View transcript
          </Button>
        ) : null}
      </div>

      <TranscriptDialog
        open={state.transcriptDialogOpen}
        onOpenChange={(open) =>
          dispatch({ type: open ? "transcript_dialog_opened" : "transcript_dialog_closed" })
        }
        transcript={state.transcript}
        loadFailed={state.transcriptFailed}
      />
    </div>
  )
}

/** Every turn's goal, plus its outcome once the run that goal started
 *  reaches a terminal status. While a run is still in flight, `RunStatus`
 *  reports its progress — no assistant reply is fabricated for it here. */
function chatEntries(turns: ChatTurn[]): TranscriptEntry[] {
  const entries: TranscriptEntry[] = []
  for (const turn of turns) {
    entries.push({ id: `${turn.runId}-goal`, author: "user", text: turn.goal })
    if (turn.run.status === "complete" && turn.run.result) {
      entries.push({
        id: `${turn.runId}-outcome`,
        author: "assistant",
        text: turn.run.result.final_output,
      })
    } else if (turn.run.status === "failed") {
      entries.push({
        id: `${turn.runId}-outcome`,
        author: "assistant",
        text: turn.run.failure_reason ?? "The run failed.",
      })
    }
  }
  return entries
}
