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

/**
 * First-visit orientation for new users (Story 2.11, AC 1, 2, 4).
 *
 * Shown only once per browser: when a user first lands on New Team and has
 * neither dismissed this orientation nor completed a build before.
 * Uses localStorage for client-only state — no backend/session persistence.
 *
 * Voice and Tone: plain, confident, helpful — matches EXPERIENCE.md:52-62.
 */
export function FirstVisitOrientation({
  onDismiss,
}: {
  onDismiss: () => void
}) {
  const [isOpen, setIsOpen] = React.useState(false)

  React.useEffect(() => {
    // Check if orientation should be shown:
    // - Not already dismissed
    // - Not already completed a build
    const orientationShown = localStorage.getItem(ORIENTATION_KEY)
    const buildCompleted = localStorage.getItem(BUILD_COMPLETED_KEY)
    
    if (!orientationShown && !buildCompleted) {
      setIsOpen(true)
    }
  }, [])

  function handleDismiss() {
    localStorage.setItem(ORIENTATION_KEY, "true")
    setIsOpen(false)
    onDismiss()
  }

  if (!isOpen) return null

  return (
    <Dialog open={isOpen} onOpenChange={handleDismiss}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="text-lg font-semibold">
            What team_maker does
          </DialogTitle>
        </DialogHeader>
        <DialogDescription className="text-base leading-relaxed">
          team_maker turns a description into a runnable team of AI agents.
          Describe what work you want done, then build and run the team.
        </DialogDescription>
        <div className="flex justify-end gap-2">
          <Button
            type="button"
            variant="outline"
            onClick={handleDismiss}
            data-slot="orientation-dismiss"
          >
            Dismiss
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}

/**
 * Mark that a build has been completed (Story 2.11, AC 2).
 * Call this when a build succeeds so the orientation won't reappear.
 */
export function markBuildCompleted(): void {
  localStorage.setItem(BUILD_COMPLETED_KEY, "true")
}

/**
 * Check if the first-visit orientation should be shown.
 * Returns true if neither dismissed nor build completed.
 */
export function shouldShowOrientation(): boolean {
  const orientationShown = localStorage.getItem(ORIENTATION_KEY)
  const buildCompleted = localStorage.getItem(BUILD_COMPLETED_KEY)
  return !orientationShown && !buildCompleted
}

/**
 * Reset orientation state for testing purposes.
 */
export function resetOrientationState(): void {
  localStorage.removeItem(ORIENTATION_KEY)
  localStorage.removeItem(BUILD_COMPLETED_KEY)
}
