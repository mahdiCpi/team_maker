"use client"

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"

/**
 * Confirms exactly what is deleted before calling `deleteTeam` (Story 2.8
 * AC 5, Story 2.5's own AC: "an explicit confirm that names what goes with
 * it"). A Base UI `Dialog`, so Esc closes it for free, matching this
 * codebase's established convention (`transcript-dialog.tsx`, Story 2.7's
 * accessibility audit).
 */
export function DeleteTeamDialog({
  open,
  onOpenChange,
  teamName,
  onConfirm,
  pending,
  error,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  teamName: string
  onConfirm: () => void
  pending: boolean
  error: string | null
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent data-slot="delete-team-dialog">
        <DialogHeader>
          <DialogTitle>Delete &ldquo;{teamName}&rdquo;?</DialogTitle>
          <DialogDescription>
            This deletes the team and all of its saved runs and results. This cannot be undone.
          </DialogDescription>
        </DialogHeader>
        {error ? (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        ) : null}
        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            type="button"
            variant="destructive"
            onClick={() => {
              if (!pending) onConfirm()
            }}
            aria-disabled={pending}
            data-slot="delete-team-confirm"
          >
            {pending ? "Deleting…" : "Delete"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
