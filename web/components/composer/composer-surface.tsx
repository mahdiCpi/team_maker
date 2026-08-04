"use client"

import * as React from "react"

import { EmptyState } from "@/components/empty-state"
import { BuildResult } from "@/components/composer/build-result"
import { ComposerActions } from "@/components/composer/composer-actions"
import { ComposerFailure } from "@/components/composer/composer-failure"
import { ComposerInput } from "@/components/composer/composer-input"
import {
  INITIAL_COMPOSER_STATE,
  composerReducer,
} from "@/components/composer/composer-state"
import { SpecEditor } from "@/components/composer/spec-editor"
import { Transcript } from "@/components/composer/transcript"
import {
  buildTeam,
  createSession,
  replaceSpec,
  sendMessage,
  type SpecEditInput,
} from "@/lib/api-client"

/**
 * The Composer — a conversation, not a one-shot form (AC 1).
 *
 * `EXPERIENCE.md:25` and `:70` settle the shape, and `:14` ("spines win on
 * conflict with any mock") settles the conflict with
 * `mockups/color-themes-1.html:86-88`, whose single textarea and `Build team`
 * button are the *first turn* of this chat rather than a competing design.
 *
 * This is the only client component on the route: `app/page.tsx` stays a server
 * component so its `metadata` export survives.
 *
 * **The transcript lives here and nowhere else.** The API keeps no chat history
 * — `ComposerSession` holds the original intent and the current spec, and
 * intermediate turns are discarded — so there is no replay endpoint and a reload
 * genuinely loses the conversation. That is a property of Story 2.0's design,
 * not an oversight here.
 *
 * **Nothing auto-builds.** `epics.md:321`'s "no confirmation" governs what
 * happens *at build time* — no interstitial review screen — not when a build is
 * triggered. Firing one after a successful turn would end the conversation at
 * turn 1 and contradict AC 1.
 */
export function ComposerSurface() {
  const [state, dispatch] = React.useReducer(
    composerReducer,
    INITIAL_COMPOSER_STATE
  )
  const [input, setInput] = React.useState("")
  const [saving, setSaving] = React.useState(false)
  /** Set on a successful save so the reopened form confirms what happened. */
  const [savedNotice, setSavedNotice] = React.useState<string | null>(null)

  const hasSpec = state.spec !== null
  const isFirstTurn = state.sessionId === null

  async function submitTurn() {
    const text = input.trim()
    if (text.length === 0) return
    const sessionId = state.sessionId

    dispatch({ type: "turn_requested", text })
    setInput("")

    const result = sessionId
      ? await sendMessage(sessionId, text)
      : await createSession({ intent: text })

    if (result.ok) dispatch({ type: "turn_succeeded", session: result.data })
    else dispatch({ type: "turn_failed", failure: result })
  }

  async function runBuild() {
    const sessionId = state.sessionId
    if (!sessionId) return
    dispatch({ type: "build_requested" })
    const result = await buildTeam(sessionId)
    if (result.ok) dispatch({ type: "build_succeeded", result: result.data })
    else dispatch({ type: "build_failed", failure: result })
  }

  /** `Build team` honours the review toggle; `Run it now` bypasses it. */
  function commit() {
    if (state.reviewBeforeBuild && hasSpec) {
      dispatch({ type: "editor_opened" })
      return
    }
    void runBuild()
  }

  async function saveSpec(edit: SpecEditInput) {
    const sessionId = state.sessionId
    if (!sessionId) return
    setSaving(true)
    const result = await replaceSpec(sessionId, edit)
    setSaving(false)
    if (result.ok) {
      setSavedNotice("Saved. The team below is what the server stored.")
      dispatch({ type: "spec_replaced", session: result.data })
    } else {
      setSavedNotice(null)
      dispatch({ type: "spec_edit_failed", failure: result })
    }
  }

  const blockedReason = actionBlockedReason(state)
  const runNowReason = hasSpec ? blockedReason : null

  return (
    <div data-slot="composer" className="flex min-h-0 flex-1 flex-col gap-3">
      {state.transcript.length === 0 ? (
        <div className="flex min-h-0 flex-1 flex-col justify-center">
          <EmptyState
            title="Describe your team."
            description="Say what work you want done. team_maker proposes the roles and tasks, then you refine them here."
          />
        </div>
      ) : (
        <Transcript
          entries={state.transcript}
          thinking={state.pending === "turn"}
        >
          {state.build ? <BuildResult result={state.build} /> : null}
        </Transcript>
      )}

      {/* Suppressed while the editor is showing the same `fields[]` inline: the
          dialog is over this, so the alert behind it would be invisible and only
          duplicate every reason. */}
      {state.failure && !editorOwnsFailure(state) ? (
        <ComposerFailure
          failure={state.failure}
          expired={state.expired}
          onRestart={() => dispatch({ type: "conversation_restarted" })}
          onDismiss={() => dispatch({ type: "failure_dismissed" })}
        />
      ) : null}

      {hasSpec ? (
        <ComposerActions
          reviewBeforeBuild={state.reviewBeforeBuild}
          onReviewChange={(enabled) =>
            dispatch({ type: "review_toggled", enabled })
          }
          onBuild={commit}
          onRunNow={() => void runBuild()}
          buildBlockedReason={blockedReason}
          runNowBlockedReason={blockedReason}
        />
      ) : null}

      <ComposerInput
        value={input}
        onValueChange={setInput}
        onSend={() => void submitTurn()}
        // Passed only when the action can actually happen, so `⌘/Ctrl+Enter`
        // cannot fire into nothing. The reason is on screen either way.
        onRunNow={hasSpec && !blockedReason ? () => void runBuild() : undefined}
        isFirstTurn={isFirstTurn}
        sendBlockedReason={sendBlockedReason(state)}
        runNowBlockedReason={runNowReason}
      />

      {state.editorOpen && state.spec ? (
        <SpecEditor
          // Remounts on every adopted server spec, which is what makes "re-render
          // from the response, never from local state" true rather than intended.
          key={state.specRevision}
          spec={state.spec}
          serverIssues={
            state.failure?.code === "spec_invalid" ? state.failure.fields : []
          }
          saving={saving}
          savedNotice={savedNotice}
          onSave={(edit) => void saveSpec(edit)}
          onBuild={() => void runBuild()}
          onClose={() => {
            setSavedNotice(null)
            dispatch({ type: "editor_closed" })
          }}
        />
      ) : null}
    </div>
  )
}

/** True when the open editor is already rendering this failure's reasons. */
function editorOwnsFailure(state: ReturnType<typeof composerReducer>): boolean {
  return state.editorOpen && state.failure?.code === "spec_invalid"
}

/** Why `Build team` / `Run it now` cannot proceed, or null when they can. */
function actionBlockedReason(
  state: ReturnType<typeof composerReducer>
): string | null {
  if (state.expired) {
    return "This conversation is no longer available. Start a new one to continue."
  }
  if (state.pending === "turn") return "Still working on your last message."
  if (state.pending === "build") return "Building the team…"
  if (!state.spec) {
    return "Describe your team first — there is nothing to build yet."
  }
  return null
}

/**
 * Why the send control cannot fire.
 *
 * A turn or a build in flight holds the per-session lock, so a second request
 * would come straight back as `session_busy` (409). Saying so is better than
 * spending a round-trip to be told.
 */
function sendBlockedReason(
  state: ReturnType<typeof composerReducer>
): string | null {
  if (state.expired) {
    return "This conversation is no longer available. Start a new one to continue."
  }
  if (state.pending === "turn") {
    return "Still working on your last message. Keep typing — it will send when that finishes."
  }
  if (state.pending === "build") return "Building the team…"
  return null
}
