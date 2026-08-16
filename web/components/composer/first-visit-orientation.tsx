"use client"

import * as React from "react"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"

const ORIENTATION_KEY = "team_maker_orientation_shown"
const BUILD_COMPLETED_KEY = "team_maker_build_completed"

/** Voice and Tone: plain, confident, helpful — matches EXPERIENCE.md:52-62. */
export const ORIENTATION_COPY =
  "team_maker turns a description into a runnable team of AI agents. Describe what work you want done, then build and run the team."

/**
 * `localStorage` can throw (quota exceeded, private browsing, security
 * policy) — this is a UI nicety, not a correctness requirement, so a failed
 * read/write should never break the surrounding page.
 */
function readFlag(key: string): boolean {
  try {
    return localStorage.getItem(key) !== null
  } catch {
    return false
  }
}

function writeFlag(key: string): void {
  try {
    localStorage.setItem(key, "true")
  } catch {
    // Best-effort — see readFlag.
  }
}

/**
 * True when neither the orientation was dismissed nor a build has completed
 * in this browser (Story 2.11, AC 1, 2).
 */
export function shouldShowOrientation(): boolean {
  return !readFlag(ORIENTATION_KEY) && !readFlag(BUILD_COMPLETED_KEY)
}

/** Call when a build succeeds so the orientation won't reappear (AC 2). */
export function markBuildCompleted(): void {
  writeFlag(BUILD_COMPLETED_KEY)
}

/**
 * First-visit orientation for new users (Story 2.11, AC 1, 2, 4).
 *
 * Rendered only from the Composer's empty-state branch. Shown once per
 * browser via a `localStorage` flag — no backend/session persistence.
 */
export function FirstVisitOrientation() {
  const [isOpen, setIsOpen] = React.useState(false)

  React.useEffect(() => {
    // Deferred to a microtask, not called synchronously in the effect body,
    // which is what keeps `react-hooks/set-state-in-effect` satisfied — the
    // same convention `ComposerSurface`'s key-status effect follows.
    queueMicrotask(() => setIsOpen(shouldShowOrientation()))

    // The `storage` event fires only in OTHER tabs/windows, not the one that
    // wrote the flag — so a tab already showing the dialog closes once a
    // second tab dismisses it or completes a build.
    function handleStorage(event: StorageEvent) {
      if (event.key === ORIENTATION_KEY || event.key === BUILD_COMPLETED_KEY) {
        setIsOpen(shouldShowOrientation())
      }
    }
    window.addEventListener("storage", handleStorage)
    return () => window.removeEventListener("storage", handleStorage)
  }, [])

  function handleOpenChange(open: boolean) {
    if (open) return
    writeFlag(ORIENTATION_KEY)
    setIsOpen(false)
  }

  return (
    <Dialog open={isOpen} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="text-lg font-semibold">
            What team_maker does
          </DialogTitle>
        </DialogHeader>
        <DialogDescription className="text-base leading-relaxed">
          {ORIENTATION_COPY}
        </DialogDescription>
        <div className="flex justify-end gap-2">
          <Button
            type="button"
            variant="outline"
            onClick={() => handleOpenChange(false)}
            data-slot="orientation-dismiss"
          >
            Dismiss
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
