"use client"

import * as React from "react"

import { ScrollArea } from "@/components/ui/scroll-area"
import { MessageBubble } from "@/components/composer/message-bubble"
import { ThinkingIndicator } from "@/components/composer/thinking-indicator"
import type { TranscriptEntry } from "@/components/composer/composer-state"

/**
 * The conversation, and the only scrolling region on the surface.
 *
 * Sized against `flex-1` inside the layout's `<main class="flex flex-1
 * flex-col">`, never `100vh`: the header is `h-12`, so a viewport-height scroll
 * region would push the input off the bottom of the page on every route.
 *
 * ## Two declared additions
 *
 * `aria-live="polite"` — no source specifies a live region for incoming chat
 * messages (the spines' only mandate is run progress, which is Story 2.4/2.7).
 * A transcript that appends asynchronously after a multi-second call is
 * unusable with a screen reader without one.
 *
 * Autoscroll — also unspecified. Implemented by scrolling a sentinel at the end
 * into view rather than by setting `scrollTop` on an ancestor, because the
 * scrolling node here belongs to Base UI's `ScrollArea` internals and reaching
 * into it would break on a re-generate. `scrollIntoView` is absent in jsdom, so
 * the call is guarded rather than assumed.
 */
export function Transcript({
  entries,
  thinking,
  footerSignal,
  children,
}: {
  entries: TranscriptEntry[]
  thinking: boolean
  /**
   * Changes whenever `children` changes.
   *
   * Required, not decorative: the build panel appends no transcript entry, so
   * `entries.length` and `thinking` are both unchanged when it appears and the
   * effect below would not run. The outcome of the primary action then rendered
   * below the fold with nothing visibly happening.
   */
  footerSignal?: number
  /** Rendered after the last entry — the build outcome reads as the next thing
   *  that happened, and autoscroll brings it into view like any other entry. */
  children?: React.ReactNode
}) {
  const endRef = React.useRef<HTMLDivElement | null>(null)

  React.useEffect(() => {
    const node = endRef.current
    if (node && typeof node.scrollIntoView === "function") {
      node.scrollIntoView({ block: "end" })
    }
  }, [entries.length, thinking, footerSignal])

  return (
    <ScrollArea className="min-h-0 flex-1">
      <div
        data-slot="composer-transcript"
        // `role="log"` is the accessible role for an append-only transcript, and
        // it is what makes the region addressable by name to a screen reader.
        // `aria-live` is stated explicitly rather than left to the role's
        // implicit `polite`, because that implicit value is not applied
        // uniformly across engines.
        role="log"
        aria-live="polite"
        aria-label="Conversation"
        className="py-2 pr-3"
      >
        {entries.map((entry) => (
          <MessageBubble
            key={entry.id}
            author={entry.author}
            text={entry.text}
            undelivered={entry.undelivered}
          />
        ))}
        {thinking ? <ThinkingIndicator /> : null}
        {children}
        <div ref={endRef} />
      </div>
    </ScrollArea>
  )
}
