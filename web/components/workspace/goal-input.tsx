"use client"

import * as React from "react"

import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { MAX_GOAL_LENGTH } from "@/lib/api-types"

const SEND_HINT_ID = "workspace-goal-hint"

/**
 * Reserved for this surface — `composer-input.tsx`'s docstring names it as
 * such explicitly, so it is used here and nowhere in `components/composer/`.
 */
export const GOAL_PLACEHOLDER = "Ask a follow-up or refine the goal…"

/**
 * Where the user gives this team a goal (Story 2.4 AC 5).
 *
 * Enter sends (Shift+Enter adds a line, mirroring `composer-input.tsx`), and
 * `⌘/Ctrl+Enter` also runs — `EXPERIENCE.md:99` names it explicitly, even
 * though on this surface it is redundant with plain Enter: there is no
 * separate "build" action here to disambiguate from, since sending *is*
 * running.
 *
 * Nothing here is the native `disabled` attribute — see `composer-input.tsx`
 * for the same rule and the same reason.
 */
export function GoalInput({
  value,
  onValueChange,
  onSend,
  sendBlockedReason,
}: {
  value: string
  onValueChange: (next: string) => void
  onSend: () => void
  /** Non-null means sending cannot proceed right now, and says why. */
  sendBlockedReason: string | null
}) {
  const empty = value.trim().length === 0
  const overLong = value.length > MAX_GOAL_LENGTH
  // An empty goal is a blocked state like any other, and it needs its own
  // sentence: the button was `aria-disabled` for it while `aria-describedby`
  // pointed at "Enter sends. Shift+Enter adds a line." — a hint, not a reason.
  // `EXPERIENCE.md:104` bans a blocked control that does not say why.
  const blocked =
    sendBlockedReason ??
    (overLong
      ? `That is ${value.length.toLocaleString()} characters. Shorten it to ${MAX_GOAL_LENGTH.toLocaleString()} or fewer to send.`
      : empty
        ? "Describe what you want this team to do, then press Run."
        : null)

  function trySend() {
    if (!blocked) onSend()
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (event.nativeEvent.isComposing) return
    if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
      event.preventDefault()
      trySend()
      return
    }
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault()
      trySend()
    }
  }

  return (
    <div data-slot="workspace-goal-input" className="flex flex-col gap-2 border-t pt-3">
      <Textarea
        aria-label="Describe the goal for this run"
        placeholder={GOAL_PLACEHOLDER}
        value={value}
        onChange={(event) => onValueChange(event.target.value)}
        onKeyDown={handleKeyDown}
        rows={3}
        data-slot="workspace-goal-textarea"
      />
      <div className="flex items-center justify-between gap-2">
        <p id={SEND_HINT_ID} data-slot="workspace-goal-hint" className="text-xs text-muted-foreground">
          {blocked ?? "Enter sends. Shift+Enter adds a line."}
        </p>
        <Button
          type="button"
          onClick={trySend}
          aria-disabled={blocked !== null}
          aria-describedby={SEND_HINT_ID}
          data-slot="workspace-run"
        >
          Run
        </Button>
      </div>
    </div>
  )
}
