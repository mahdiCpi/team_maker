"use client"

import * as React from "react"

import { Button } from "@/components/ui/button"
import {
  MAX_DOCUMENTS,
  MAX_DOCUMENT_TEXT_LENGTH,
  MAX_TOTAL_DOCUMENT_TEXT_LENGTH,
} from "@/lib/api-types"
import { cn } from "@/lib/utils"
import type { AttachedDocument } from "@/components/workspace/workspace-state"

const REASON_ID = "workspace-document-reason"

/**
 * Attach text documents to the next run (Story 2.4 AC 6).
 *
 * Native HTML5 drag-and-drop and a native file input — no dependency added,
 * following 2.2's precedent of not installing a package for a native-capable
 * interaction. A file that does not decode as text is refused *at attach
 * time* with a plain-language reason (`EXPERIENCE.md:173-174` bans burying a
 * failure), never attached as garbage.
 *
 * Nothing here is the native `disabled` attribute: a blocked attach carries
 * `aria-disabled` plus a handler guard, and the reason is always rendered as
 * text, exactly like every blocked control on the Composer.
 */
export function DocumentTray({
  documents,
  error,
  blockedReason,
  onAttach,
  onAttachFailed,
  onRemove,
}: {
  documents: AttachedDocument[]
  error: string | null
  /** Non-null means attaching cannot proceed right now, and says why. */
  blockedReason: string | null
  onAttach: (document: { name: string; text: string }) => void
  onAttachFailed: (reason: string) => void
  /** By `id`, not by name — two files can share a basename, and removing by
   *  name deleted every document that shared one. */
  onRemove: (id: string) => void
}) {
  const [dragOver, setDragOver] = React.useState(false)
  const inputRef = React.useRef<HTMLInputElement | null>(null)

  async function readFiles(files: FileList | File[]) {
    if (blockedReason) return
    // Counted locally, not read off `documents` each pass. `documents` is a
    // prop captured by this render's closure and `onAttach` only dispatches, so
    // it does not change while this loop runs: checking `documents.length`
    // inside the loop compared every file against the count from *before* the
    // first one, and one multi-file drop sailed past the cap entirely.
    let count = documents.length
    let total = documents.reduce((sum, document) => sum + document.text.length, 0)

    for (const file of Array.from(files)) {
      if (count >= MAX_DOCUMENTS) {
        // `break`, not `return`: the message below is about the remaining
        // files as a group, and silently dropping them was its own defect.
        onAttachFailed(
          `You can attach at most ${MAX_DOCUMENTS} documents, so the rest were not attached.`
        )
        break
      }
      let text: string
      try {
        text = await file.text()
      } catch {
        onAttachFailed(`"${file.name}" could not be read as text.`)
        continue
      }
      // A binary file often still "succeeds" as text with replacement
      // characters — a lone U+FFFD run is the practical signal that this was
      // not text to begin with, so it is refused rather than attached as
      // garbage the model would then be handed.
      if (text.includes("�")) {
        onAttachFailed(`"${file.name}" does not look like a text file.`)
        continue
      }
      if (text.length === 0) {
        // The server requires `min_length=1` per document, so an empty file
        // attached here would fail the whole run request later — a refusal at
        // Run time for something knowable at attach time.
        onAttachFailed(`"${file.name}" is empty.`)
        continue
      }
      if (text.length > MAX_DOCUMENT_TEXT_LENGTH) {
        onAttachFailed(
          `"${file.name}" is too long (${text.length.toLocaleString()} characters; the limit is ${MAX_DOCUMENT_TEXT_LENGTH.toLocaleString()}).`
        )
        continue
      }
      if (total + text.length > MAX_TOTAL_DOCUMENT_TEXT_LENGTH) {
        // The total bound was checked only by `validateRunInput`, i.e. at Run
        // time, so five individually-legal files could sit in the tray looking
        // accepted and then block the run.
        onAttachFailed(
          `"${file.name}" would push the attached documents past ${MAX_TOTAL_DOCUMENT_TEXT_LENGTH.toLocaleString()} characters in total.`
        )
        continue
      }
      onAttach({ name: file.name, text })
      count += 1
      total += text.length
    }
  }

  return (
    <div data-slot="workspace-document-tray" className="flex flex-col gap-2">
      <div
        data-slot="workspace-document-dropzone"
        onDragOver={(event) => {
          event.preventDefault()
          if (!blockedReason) setDragOver(true)
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(event) => {
          event.preventDefault()
          setDragOver(false)
          void readFiles(event.dataTransfer.files)
        }}
        aria-disabled={blockedReason !== null}
        aria-describedby={REASON_ID}
        className={cn(
          "rounded-lg border border-dashed p-3 text-center text-xs text-muted-foreground",
          dragOver && "border-ring bg-muted/50"
        )}
      >
        Drag a text file here, or{" "}
        <button
          type="button"
          className="underline underline-offset-2"
          onClick={() => {
            if (!blockedReason) inputRef.current?.click()
          }}
          aria-disabled={blockedReason !== null}
          data-slot="workspace-document-browse"
        >
          browse
        </button>
        <input
          ref={inputRef}
          type="file"
          accept="text/plain,.txt,.md,.csv,.json,text/*"
          multiple
          aria-label="Attach a document"
          className="sr-only"
          tabIndex={-1}
          onChange={(event) => {
            if (event.target.files) void readFiles(event.target.files)
            event.target.value = ""
          }}
        />
      </div>
      <p id={REASON_ID} data-slot="workspace-document-reason" className="text-xs text-muted-foreground">
        {blockedReason ?? `Up to ${MAX_DOCUMENTS} text files.`}
      </p>

      {error ? (
        <p data-slot="workspace-document-error" role="alert" className="text-xs text-destructive">
          {error}
        </p>
      ) : null}

      {documents.length > 0 ? (
        <ul data-slot="workspace-document-list" className="flex flex-col gap-1">
          {documents.map((document) => (
            <li
              key={document.id}
              data-slot="workspace-document-item"
              className="flex items-center justify-between gap-2 text-xs"
            >
              <span className="truncate font-mono">{document.name}</span>
              <Button
                type="button"
                size="sm"
                variant="ghost"
                aria-label={`Remove ${document.name}`}
                onClick={() => onRemove(document.id)}
              >
                Remove
              </Button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  )
}
