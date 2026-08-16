import { Skeleton } from "@/components/ui/skeleton"

/**
 * The pending state for a turn (AC 2).
 *
 * `EXPERIENCE.md:84` asks for a "`Skeleton`/typing indicator while the app
 * drafts the spec". It is deliberately **opaque**: a turn is 1–4 sequential
 * blocking LLM calls behind one request, with no streaming and no progress
 * callback anywhere in the core, so a percentage or a token stream would be
 * fabricated. There is nothing to report but "still working".
 *
 * No `role="status"` and no `aria-live` of its own: this renders *inside* the
 * transcript's `aria-live="polite"` region, and a nested live region would
 * either double-announce or swallow the announcement depending on the reader.
 * The `sr-only` line is what gets read when the parent region updates.
 *
 * Every colour is a neutral semantic token. Signal Teal is untouched — Guard B's
 * consumer whitelist is empty and Story 2.4 owns the first use (AC 7). The token
 * is deliberately not spelled out here: Guard B greps raw file text, so even a
 * comment naming it is a violation, and that is the guard working rather than
 * over-reaching.
 */
export function ThinkingIndicator() {
  return (
    <div data-slot="composer-thinking" className="mb-3">
      <div className="mb-1 text-xs text-muted-foreground">team_maker</div>
      <div className="rounded-lg border bg-card px-3 py-2">
        <span className="sr-only">Working on your team.</span>
        <div aria-hidden="true" className="flex flex-col gap-2">
          <Skeleton className="h-3 w-48" />
          <Skeleton className="h-3 w-32" />
        </div>
      </div>
    </div>
  )
}
