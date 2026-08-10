"use client"

import * as React from "react"

import { Button } from "@/components/ui/button"
import { MAX_DOCUMENTS, MAX_DOCUMENT_TEXT_LENGTH } from "@/lib/api-types"
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
  onAttach: (document: AttachedDocument) => void
  onAttachFailed: (reason: string) => void
  onRemove: (name: string) => void
}) {
  const [dragOver, setDragOver] = React.useState(false)
  const inputRef = React.useRef<HTMLInputElement | null>(null)

  async function readFiles(files: FileList | File[]) {
    if (blockedReason) return
    for (const file of Array.from(files)) {
      if (documents.length >= MAX_DOCUMENTS) {
        onAttachFailed(`You can attach at most ${MAX_DOCUMENTS} documents.`)
        return
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
      if (text.length > MAX_DOCUMENT_TEXT_LENGTH) {
        onAttachFailed(
          `"${file.name}" is too long (${text.length.toLocaleString()} characters; the limit is ${MAX_DOCUMENT_TEXT_LENGTH.toLocaleString()}).`
        )
        continue
      }
      onAttach({ name: file.name, text })
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
              key={document.name}
              data-slot="workspace-document-item"
              className="flex items-center justify-between gap-2 text-xs"
            >
              <span className="truncate font-mono">{document.name}</span>
              <Button
                type="button"
                size="sm"
                variant="ghost"
                onClick={() => onRemove(document.name)}
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
