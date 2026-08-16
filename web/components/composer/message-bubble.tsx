import { cn } from "@/lib/utils"

/**
 * One transcript entry.
 *
 * Anatomy from `mockups/team-workspace.html:49-58`: the role label sits *above*
 * the bubble in `muted-foreground`, the bubble is `card` with a 1px border at
 * `--radius`, and the user's turn is differentiated by a `muted` background
 * alone. Both authors are left-aligned and full width — the mock has no
 * right-aligned bubbles and no avatars, and inventing them here would diverge
 * from the surface Story 2.4 inherits.
 *
 * The labels `You` / `team_maker` are the mock's own convention
 * (`team-workspace.html:101,104`).
 */
export const AUTHOR_LABEL = {
  user: "You",
  assistant: "team_maker",
} as const

export function MessageBubble({
  author,
  text,
  undelivered,
}: {
  author: "user" | "assistant"
  text: string
  /** The turn this message belonged to failed, so the model never saw it. */
  undelivered?: boolean
}) {
  return (
    <div data-slot="composer-message" data-author={author} className="mb-3">
      <div className="mb-1 text-xs text-muted-foreground">
        {AUTHOR_LABEL[author]}
      </div>
      <div
        data-slot="composer-bubble"
        className={cn(
          "rounded-lg border bg-card px-3 py-2 text-sm leading-relaxed whitespace-pre-wrap",
          // Last in the same tailwind-merge group, so it wins over `bg-card`.
          author === "user" && "bg-muted"
        )}
      >
        {text}
      </div>
      {/* Text, not colour alone: a message that never reached the model would
          otherwise be indistinguishable from one that did — which matters most at
          the turn cap, where every further attempt looks like it was sent. */}
      {undelivered ? (
        <p
          data-slot="composer-undelivered"
          className="mt-1 text-xs text-muted-foreground"
        >
          Not delivered.
        </p>
      ) : null}
    </div>
  )
}
