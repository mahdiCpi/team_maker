"use client"

import { Button } from "@/components/ui/button"
import type { ApiFailure } from "@/lib/api-types"

/**
 * Every error path's user-facing state (AC 8).
 *
 * Four rules hold here:
 *
 * 1. **Only strings that are already authored copy are rendered.** `message`
 *    and `fields[].message` come from `api/errors.py`, which guarantees they are
 *    authored and never `str(exc)`. Nothing is `JSON.stringify`d, no caught
 *    exception is displayed, and the client re-checks for a leaked stack trace
 *    before it gets here (`lib/api-client.ts`).
 * 2. **A failed turn leaves the conversation usable.** This renders *beside* the
 *    transcript and the last good spec, never instead of them.
 * 3. **`session_not_found` is recoverable, not a white screen.** A backend
 *    `--reload` drops every session, so this is a routine dev-time event; it
 *    gets an explicit way out.
 * 4. **No key entry, ever.** `authoring_unavailable`'s server copy already names
 *    the provider and the Key Config entry that would fix it, so it is shown
 *    verbatim and nothing here offers to take a key (`EXPERIENCE.md:103`).
 *
 * Error *copy* refinement belongs to Story 2.3; usable *behaviour* is this
 * story's job.
 */
export function ComposerFailure({
  failure,
  expired,
  onRestart,
  onDismiss,
}: {
  failure: ApiFailure
  expired: boolean
  onRestart: () => void
  onDismiss: () => void
}) {
  return (
    <div
      data-slot="composer-failure"
      data-code={failure.code}
      role="alert"
      className="mb-3 rounded-lg border border-destructive/40 bg-card px-3 py-2"
    >
      <p data-slot="composer-failure-message" className="text-sm">
        {failure.message}
      </p>

      {failure.fields.length > 0 ? (
        <ul data-slot="composer-failure-fields" className="mt-2 flex flex-col gap-1">
          {failure.fields.map((field) => (
            <li key={`${field.path}:${field.message}`} className="text-xs">
              <span className="font-mono text-muted-foreground">{field.path}</span>{" "}
              — {field.message}
            </li>
          ))}
        </ul>
      ) : null}

      <div className="mt-2 flex items-center gap-2">
        {expired ? (
          <Button type="button" size="sm" onClick={onRestart}>
            Start a new conversation
          </Button>
        ) : (
          <Button type="button" size="sm" variant="outline" onClick={onDismiss}>
            Dismiss
          </Button>
        )}
        {expired ? (
          <p className="text-xs text-muted-foreground">
            Your messages above are kept until you start again.
          </p>
        ) : null}
      </div>
    </div>
  )
}
