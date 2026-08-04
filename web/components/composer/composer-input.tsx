"use client"

import * as React from "react"

import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { MAX_MESSAGE_LENGTH } from "@/lib/api-types"

/** Verbatim from `mockups/color-themes-1.html:87`, for the first turn. */
export const FIRST_TURN_PLACEHOLDER =
  "e.g. a team that researches a topic, drafts an article, and critiques it…"

/**
 * Authored for this surface. `Ask a follow-up or refine the goal…` belongs to
 * the Team Workspace chat (Story 2.4) and is explicitly on this story's
 * do-not-borrow list, so the refinement placeholder is deliberately distinct.
 */
export const REFINE_PLACEHOLDER = "Tell team_maker what to change…"

/**
 * The composer input (AC 2, AC 6).
 *
 * **It is a real `<textarea>`,** which matters beyond semantics:
 * `nav-shortcuts.tsx:11,23-31` only suppresses the global `g` chord for
 * `INPUT`/`TEXTAREA`/`SELECT` and three exact `contenteditable` values. Any
 * other editor host and typing "**g**rand total" navigates the user away
 * mid-sentence.
 *
 * **The input is never `disabled`** (AC 2 — "user can keep typing"). While a
 * turn is in flight the *send* control reports itself unavailable with
 * `aria-disabled` and a stated reason instead, because `EXPERIENCE.md:104`
 * bans a silently blocked action and Story 2.1's review found a truly
 * `disabled` control used as the answer to "not ready yet".
 */
export function ComposerInput({
  value,
  onValueChange,
  onSend,
  onRunNow,
  isFirstTurn,
  sendBlockedReason,
  runNowBlockedReason,
}: {
  value: string
  onValueChange: (next: string) => void
  onSend: () => void
  /** Absent when there is nothing to build yet, so the chord cannot fire. */
  onRunNow?: () => void
  isFirstTurn: boolean
  /** Non-null means "cannot send right now, and here is why". */
  sendBlockedReason: string | null
  runNowBlockedReason: string | null
}) {
  const tooLong = value.length > MAX_MESSAGE_LENGTH
  const empty = value.trim().length === 0
  const blocked = sendBlockedReason ?? (tooLong ? lengthMessage(value.length) : null)

  function handleKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key !== "Enter") return

    // An IME composing a candidate uses Enter to commit it. Sending here would
    // dispatch a half-typed word and clear the box mid-composition.
    if (event.nativeEvent.isComposing) return

    if (event.metaKey || event.ctrlKey) {
      // `⌘/Ctrl+Enter` is Run it now (`EXPERIENCE.md:98`). `⌘/Ctrl+B` is left
      // alone — it is shadcn's sidebar toggle.
      event.preventDefault()
      onRunNow?.()
      return
    }
    // Shift+Enter is left to the browser, which inserts the newline. This is an
    // addition: `EXPERIENCE.md:98` specifies Enter but is silent on Shift+Enter.
    if (event.shiftKey) return

    event.preventDefault()
    if (!empty && !blocked) onSend()
  }

  return (
    <div data-slot="composer-input" className="flex flex-col gap-2">
      <Textarea
        aria-label="Describe your team"
        placeholder={isFirstTurn ? FIRST_TURN_PLACEHOLDER : REFINE_PLACEHOLDER}
        value={value}
        rows={3}
        // Deliberately NOT `maxLength`: silently truncating a paste loses text
        // the user can no longer see. The count and the message below say what
        // is wrong instead.
        onChange={(event) => onValueChange(event.target.value)}
        onKeyDown={handleKeyDown}
        className="max-h-40 min-h-16 resize-none"
      />
      <div className="flex items-center gap-2">
        <Button
          type="button"
          onClick={() => {
            if (!empty && !blocked) onSend()
          }}
          // `aria-disabled`, not `disabled`: the reason stays reachable by
          // keyboard and is stated in text beside it.
          aria-disabled={empty || blocked !== null}
          data-slot="composer-send"
        >
          Send
        </Button>
        <p
          data-slot="composer-send-hint"
          className="text-xs text-muted-foreground"
        >
          {hintFor({ blocked, runNowBlockedReason, empty, hasRunNow: !!onRunNow })}
        </p>
      </div>
      {tooLong ? (
        <p data-slot="composer-length-error" className="text-xs text-destructive">
          {lengthMessage(value.length)}
        </p>
      ) : null}
    </div>
  )
}

function lengthMessage(length: number): string {
  return `That is ${length.toLocaleString()} characters. Shorten it to ${MAX_MESSAGE_LENGTH.toLocaleString()} or fewer to send.`
}

/**
 * One line of text under the send control. It always says something: an empty
 * hint would make a non-actionable control look like a dead one.
 */
function hintFor({
  blocked,
  runNowBlockedReason,
  empty,
  hasRunNow,
}: {
  blocked: string | null
  runNowBlockedReason: string | null
  empty: boolean
  hasRunNow: boolean
}): string {
  if (blocked) return blocked
  if (empty) return "Enter sends. Shift+Enter adds a line."
  if (hasRunNow) return "Enter sends. ⌘/Ctrl+Enter builds the team as it stands."
  if (runNowBlockedReason) return `Enter sends. ${runNowBlockedReason}`
  return "Enter sends. Shift+Enter adds a line."
}
