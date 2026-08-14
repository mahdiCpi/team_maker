"use client"

import * as React from "react"

import { Button } from "@/components/ui/button"
import { EmptyState } from "@/components/empty-state"
import { BuildResult } from "@/components/composer/build-result"
import { ComposerActions } from "@/components/composer/composer-actions"
import { ComposerFailure } from "@/components/composer/composer-failure"
import { ComposerInput } from "@/components/composer/composer-input"
import {
  INITIAL_COMPOSER_STATE,
  composerReducer,
} from "@/components/composer/composer-state"
import { KeyCheck } from "@/components/composer/key-check"
import { SpecEditor } from "@/components/composer/spec-editor"
import { Transcript } from "@/components/composer/transcript"
import {
  buildTeam,
  createSession,
  getKeyCheck,
  getKeyStatus,
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

  /**
   * The provider-level key read (Story 2.3, AC 1).
   *
   * On mount, and only once. This is a file read on the server — no LLM, no spend —
   * so it does not carry the objection that keeps session creation lazy. It is what
   * lets the no-keys state appear before the user has typed anything, which
   * `EXPERIENCE.md:87` places on the Composer rather than pre-run.
   *
   * The state write happens after `await`, not synchronously in the effect, which
   * is what keeps `react-hooks/set-state-in-effect` satisfied.
   */
  React.useEffect(() => {
    let cancelled = false
    void (async () => {
      const result = await getKeyStatus()
      if (cancelled) return
      // A failure is deliberately silent here: not knowing the provider report is
      // not something to interrupt the user about, and the surface renders nothing
      // rather than guessing. A team-level check failing does gate, below.
      if (result.ok) dispatch({ type: "key_status_loaded", status: result.data })
    })()
    return () => {
      cancelled = true
    }
    // Re-read on every spec change and on a restart, not once at mount. The reason
    // is the same one this story gave for re-reading the Key Config server-side: the
    // user acts on the fix hint, and a value fetched once would keep asserting the
    // pre-edit truth for the life of the page — the no-keys banner in particular
    // could never clear without a reload.
  }, [state.keyCheckEpoch])

  /**
   * The per-team check (AC 2), re-read on every adopted spec.
   *
   * Keyed on `keyCheckEpoch` rather than on the spec object: the server
   * re-serialises the spec on every turn, so an identity comparison would refetch
   * forever, and a deep comparison would miss a change the server made silently.
   * The epoch is bumped by exactly the transitions that change which providers the
   * team needs (`adoptSession`), and the value captured here is compared in the
   * reducer, so a check for a spec that has since been replaced is discarded
   * instead of applied.
   */
  React.useEffect(() => {
    const sessionId = state.sessionId
    if (!sessionId || !hasSpec) return
    const epoch = state.keyCheckEpoch
    let cancelled = false
    dispatch({ type: "key_check_requested", epoch })
    void (async () => {
      const result = await getKeyCheck(sessionId)
      if (cancelled) return
      if (result.ok) {
        dispatch({ type: "key_check_loaded", check: result.data, epoch })
      } else {
        dispatch({ type: "key_check_unavailable", failure: result, epoch })
      }
    })()
    return () => {
      cancelled = true
    }
  }, [state.sessionId, state.keyCheckEpoch, hasSpec])

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
    setSavedNotice(null)
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
    // The epoch is captured BEFORE the await and sent back with the result, so a
    // save whose editor has since been closed — or which a later save
    // superseded — is discarded by the reducer instead of reopening the dialog
    // and resetting `pending` out from under a running build.
    const epoch = state.saveEpoch + 1
    dispatch({ type: "save_requested" })
    setSaving(true)
    const result = await replaceSpec(sessionId, edit)
    setSaving(false)
    if (result.ok) {
      setSavedNotice("Saved. The team below is what the server stored.")
      dispatch({ type: "spec_replaced", session: result.data, epoch })
    } else {
      setSavedNotice(null)
      dispatch({ type: "spec_edit_failed", failure: result, epoch })
    }
  }

  /**
   * Two gates, not one.
   *
   * `reviewGate` stops even *opening* the review editor: the conversation is gone,
   * a turn is in flight, there is no spec yet. `buildGate` adds the Story 2.3 key
   * check, which stops a build but must **not** stop the editor from opening —
   * that is the one place a user can act on the spine's own advice to "switch this
   * agent to a model you have" (`EXPERIENCE.md:86`). Gating both together made the
   * remedy unreachable from the very state that recommends it.
   */
  const reviewGate = conversationBlockedReason(state)
  const buildGate = reviewGate ?? keyBlockedReason(state)
  const openingReview = state.reviewBeforeBuild && hasSpec
  // `Build team` opens review when review is on, so it answers to the review gate;
  // otherwise it builds, and answers to the build gate.
  const blockedReason = openingReview ? reviewGate : buildGate
  // `Run it now` always builds, bypassing review — so always the build gate.
  // Passed unconditionally, including the "nothing to build yet" case. Gating it
  // on `hasSpec` made the hint branch that explains a blocked `⌘/Ctrl+Enter`
  // unreachable, so the chord swallowed the keystroke and said nothing.
  const runNowReason = buildGate

  return (
    <div data-slot="composer" className="flex min-h-0 flex-1 flex-col gap-3">
      <h1
        id="page-heading"
        tabIndex={-1}
        className="text-xs font-medium tracking-wide text-muted-foreground uppercase"
      >
        New Team
      </h1>
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
          // The build panel appends no transcript entry, so without a signal of
          // its own the autoscroll effect never fired for it and the outcome
          // rendered below the fold.
          footerSignal={state.buildRevision}
        >
          {state.build ? <BuildResult result={state.build} /> : null}
        </Transcript>
      )}

      {/* Above the failure alert and outside `ComposerActions`, which only renders
          once a spec exists — the no-keys state has to be visible before the user
          has described anything (`EXPERIENCE.md:87`). */}
      <KeyCheck status={state.keyStatus} check={state.keyCheck} />

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

      {/* The only way out of a built conversation, since the output location is
          pinned per session and a second build could only ever 409. Rendered as a
          real control rather than left to the error the user would otherwise have
          to provoke first. */}
      {state.build ? (
        <div className="flex items-center gap-2">
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() => dispatch({ type: "conversation_restarted" })}
            data-slot="composer-restart"
          >
            Start a new conversation
          </Button>
          <p className="text-xs text-muted-foreground">
            This one has been built, and its output location is fixed.
          </p>
        </div>
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
          runNowBlockedReason={runNowReason}
        />
      ) : null}

      <ComposerInput
        value={input}
        onValueChange={setInput}
        onSend={() => void submitTurn()}
        // Passed only when the action can actually happen, so `⌘/Ctrl+Enter`
        // cannot fire into nothing. The reason is on screen either way.
        onRunNow={hasSpec && !buildGate ? () => void runBuild() : undefined}
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
          // The whole failure, so the modal can show a message for every code
          // rather than only distributing `spec_invalid`'s field reasons.
          failure={state.failure}
          // The key check cannot be seen behind the dialog's backdrop, so the rows
          // carry it themselves — this is where a role's provider is chosen.
          keyRoles={state.keyCheck?.roles ?? []}
          // The fourth build entry point. The *build* gate, not the review one:
          // the dialog is already open, and its own reasons (saving / unsaved
          // edits) know nothing about keys.
          blockedReason={buildGate}
          saving={saving}
          savedNotice={savedNotice}
          onSave={(edit) => void saveSpec(edit)}
          onBuild={() => void runBuild()}
          onEdit={() => dispatch({ type: "failure_dismissed" })}
          onClose={() => {
            setSavedNotice(null)
            dispatch({ type: "editor_closed" })
          }}
        />
      ) : null}
    </div>
  )
}

/**
 * True when the open editor is already rendering this failure.
 *
 * Any failure present while the editor is open came from a save: `editor_opened`
 * clears the previous one, and `build_requested` closes the editor before a build
 * can fail. So the condition is simply "the editor is open" — narrowing it to
 * `spec_invalid` was the bug, because every other code then rendered in the
 * surface, underneath a modal backdrop, where it could not be read or dismissed.
 */
function editorOwnsFailure(state: ReturnType<typeof composerReducer>): boolean {
  return state.editorOpen && state.failure !== null
}

/**
 * Why nothing can proceed at all — not a build, and not even opening review.
 *
 * Every reason here is about the conversation's own state, so none of them can be
 * fixed from inside the editor.
 */
function conversationBlockedReason(
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
  // A turn we stopped waiting for may have succeeded server-side, so this spec
  // may no longer be the session's. Building it would write a team the user
  // never saw.
  if (state.specMayBeStale) {
    return "That last turn timed out, so this team may not match what the server has. Send another message before building."
  }
  // `output_path` is derived from the first spec and pinned for the session's
  // life, so a second build in this conversation can only ever return 409. Say
  // so instead of offering a button whose sole outcome is an error that wipes
  // the success panel — the one place the output path was ever shown.
  if (state.build) {
    return "This team has been built. Start a new conversation to build another — the output location is fixed per conversation."
  }
  return null
}

/**
 * Why a *build* cannot proceed on key grounds (Story 2.3, AC 5).
 *
 * Kept separate from the reasons above because this one is fixable from inside the
 * review editor — by switching an agent to a model the user has — so it must not
 * also close the door to that editor.
 *
 * Only a check that actually arrived and actually says `blocked` gates anything.
 * `keyCheck === null` means "not established" — either still in flight or the read
 * failed — and blocking on that would strand the user over a condition nobody
 * verified. UX-DR5 asks for a blocked run on a *missing key*, not on an unanswered
 * question.
 */
function keyBlockedReason(
  state: ReturnType<typeof composerReducer>
): string | null {
  // "Credential missing" and "credential check failed" are different facts, and
  // neither may silently permit a build.
  //
  // The first version returned `null` for everything except a `blocked` check, so
  // "in flight" and "the read failed" both read as permission. That left the build
  // open for a round-trip after every turn, and open *forever* if `/api/keys/*`
  // started failing — with nothing on screen to say so, which `EXPERIENCE.md:104`
  // bans outright.
  if (state.keyCheckState === "checking") {
    return "Checking which models your keys can reach…"
  }
  if (state.keyCheckState === "failed") {
    return "Could not check your key setup, so this build has not been allowed to start. Try again in a moment."
  }
  if (!state.keyCheck?.blocked) return null
  return (
    state.keyCheck.blocking_reason ??
    "This team cannot run yet: one of its models has no usable credential."
  )
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
    // Says only what is true. The previous wording — "Keep typing — it will send
    // when that finishes" — promised a queue that does not exist, so a user who
    // believed it waited for a message that never left the box.
    return "Still working on your last message. You can keep typing; send it when this finishes."
  }
  if (state.pending === "build") return "Building the team…"
  // The cap is a server limit on authoring turns; sending past it appends a
  // bubble for a message that never reaches the model.
  if (state.sessionId && state.turnsRemaining <= 0) {
    return "This conversation has used all its turns. Build the team as it stands, or start a new conversation."
  }
  return null
}
