"use client"

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { ScrollArea } from "@/components/ui/scroll-area"
import type { TranscriptView } from "@/lib/api-types"

/** `results.py`'s six `ENTRY_*` kinds. Branched on for the label only —
 *  never used to decide how `content` is rendered, which never regexes it. */
const KIND_LABEL: Record<string, string> = {
  task_started: "Task started",
  task_completed: "Task completed",
  agent_message: "Message",
  agent_action: "Action",
  delegation: "Delegation",
  delegation_result: "Delegation result",
}

/**
 * The full agent transcript for a run (Story 2.4 AC 14; `epics.md:384-386`).
 *
 * A `Dialog` over the Workspace — the one modal-depth-one constraint that
 * does exist (`EXPERIENCE.md:38-39`); no source specifies the transcript's
 * own shape, so it is designed here.
 *
 * Renders every entry sorted by `sequence` — never by list position, and
 * never assuming contiguity (`results.py`: "Values are monotonically
 * increasing but sparse"). Branches on `kind`, never on `content`, per Story
 * 1.7's instruction to this story. A delegation entry may precede the
 * `agent_action` that caused it (1.7's review); no causal order is assumed.
 */
export function TranscriptDialog({
  open,
  onOpenChange,
  transcript,
  loadFailed = false,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  transcript: TranscriptView | null
  /** The transcript GET failed. Kept distinct from every other empty state:
   *  "we could not fetch it" and "the server says there is nothing" are
   *  different facts, and only one of them is the server's claim. */
  loadFailed?: boolean
}) {
  const entries = transcript
    ? [...transcript.entries].sort((a, b) => a.sequence - b.sequence)
    : []

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent data-slot="workspace-transcript-dialog" className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Transcript</DialogTitle>
          <DialogDescription>Every agent message and handoff, in order.</DialogDescription>
        </DialogHeader>
        <ScrollArea className="max-h-[60vh]">
          {loadFailed ? (
            // Before this branch existed, a failed fetch fell through to the
            // "nothing available yet" copy below — telling the user the server
            // had said something it never said, about a transcript that exists.
            <p
              data-slot="workspace-transcript-load-failed"
              role="alert"
              className="text-sm text-destructive"
            >
              The transcript could not be loaded. Close this and open it again to retry.
            </p>
          ) : !transcript || !transcript.available ? (
            // Covers both "still running" and "failed before any entry was
            // captured" (`deferred-work.md:101`) — an honest "nothing yet",
            // never a blank panel.
            <p
              data-slot="workspace-transcript-unavailable"
              className="text-sm text-muted-foreground"
            >
              No transcript is available for this run yet.
            </p>
          ) : entries.length === 0 ? (
            <p data-slot="workspace-transcript-empty" className="text-sm text-muted-foreground">
              The agents recorded nothing for this run.
            </p>
          ) : (
            <ul data-slot="workspace-transcript-entries" className="flex flex-col gap-2 text-sm">
              {entries.map((entry) => (
                <li
                  key={entry.sequence}
                  data-slot="workspace-transcript-entry"
                  data-kind={entry.kind}
                  className="rounded-lg border bg-card px-3 py-2"
                >
                  <p className="text-xs text-muted-foreground">
                    {KIND_LABEL[entry.kind] ?? entry.kind} · {entry.agent_role}
                    {entry.target_role ? ` → ${entry.target_role}` : ""}
                  </p>
                  <p className="mt-1 whitespace-pre-wrap">{entry.content}</p>
                </li>
              ))}
            </ul>
          )}
        </ScrollArea>
      </DialogContent>
    </Dialog>
  )
}
