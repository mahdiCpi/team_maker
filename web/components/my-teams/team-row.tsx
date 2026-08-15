"use client"

import * as React from "react"
import Link from "next/link"

import { Button, buttonVariants } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { deleteTeam, renameTeam } from "@/lib/api-client"
import type { TeamView } from "@/lib/api-types"
import { DeleteTeamDialog } from "./delete-team-dialog"

function formatLastRun(lastRunAt: string | null): string {
  if (!lastRunAt) return "Never run"
  const date = new Date(lastRunAt)
  if (Number.isNaN(date.getTime())) return "Never run"
  return `Last run ${date.toLocaleString()}`
}

/**
 * One saved team (Story 2.8). "Open workspace" doubles as both "reopen" and
 * "re-run" (AC 2, AC 3): a run needs a goal, which can only be entered in the
 * Workspace (Story 2.4's existing design, unchanged here) — there is no
 * separate one-click re-run affordance that could skip that. `record-run`'s
 * call site is `WorkspaceSurface`, on a completed run, not here.
 */
export function TeamRow({
  team,
  onRenamed,
  onDeleted,
}: {
  team: TeamView
  /** `oldName` is this row's name *before* the rename, since `updated.name`
   *  is the new one — the caller cannot match the row by `updated.name`. */
  onRenamed: (oldName: string, updated: TeamView) => void
  onDeleted: (name: string) => void
}) {
  const [renaming, setRenaming] = React.useState(false)
  const [draftName, setDraftName] = React.useState(team.name)
  const [renameError, setRenameError] = React.useState<string | null>(null)
  const [renamePending, setRenamePending] = React.useState(false)

  const [deleteOpen, setDeleteOpen] = React.useState(false)
  const [deleteError, setDeleteError] = React.useState<string | null>(null)
  const [deletePending, setDeletePending] = React.useState(false)

  function startRename() {
    setDraftName(team.name)
    setRenameError(null)
    setRenaming(true)
  }

  async function submitRename() {
    if (renamePending) return
    setRenamePending(true)
    setRenameError(null)
    const result = await renameTeam(team.name, draftName.trim())
    setRenamePending(false)
    if (result.ok) {
      setRenaming(false)
      onRenamed(team.name, result.data)
    } else {
      setRenameError(result.message)
    }
  }

  async function confirmDelete() {
    if (deletePending) return
    setDeletePending(true)
    setDeleteError(null)
    const result = await deleteTeam(team.name)
    setDeletePending(false)
    if (result.ok) {
      setDeleteOpen(false)
      onDeleted(team.name)
    } else {
      setDeleteError(result.message)
    }
  }

  return (
    <li
      data-slot="my-teams-row"
      className="flex flex-col gap-2 rounded-lg border p-3 sm:flex-row sm:items-center sm:justify-between"
    >
      <div className="flex flex-col gap-1">
        {renaming ? (
          <form
            className="flex items-center gap-2"
            onSubmit={(event) => {
              event.preventDefault()
              void submitRename()
            }}
          >
            <label className="sr-only" htmlFor={`rename-${team.name}`}>
              New name for {team.name}
            </label>
            <Input
              id={`rename-${team.name}`}
              value={draftName}
              onChange={(event) => setDraftName(event.target.value)}
              autoFocus
            />
            <Button type="submit" size="sm" aria-disabled={renamePending}>
              {renamePending ? "Saving…" : "Save"}
            </Button>
            <Button type="button" size="sm" variant="outline" onClick={() => setRenaming(false)}>
              Cancel
            </Button>
          </form>
        ) : (
          <p data-slot="my-teams-row-name" className="font-medium">
            {team.name}
          </p>
        )}
        {renameError ? (
          <p role="alert" className="text-xs text-destructive">
            {renameError}
          </p>
        ) : null}
        <p className="text-xs text-muted-foreground">
          {formatLastRun(team.last_run_at)} · {team.run_count}{" "}
          {team.run_count === 1 ? "run" : "runs"}
        </p>
      </div>

      <div className="flex items-center gap-2">
        <Link
          href={`/teams/${encodeURIComponent(team.name)}`}
          data-slot="my-teams-row-open"
          className={buttonVariants({ variant: "outline", size: "sm" })}
        >
          Open workspace
        </Link>
        {!renaming ? (
          <Button type="button" size="sm" variant="ghost" onClick={startRename}>
            Rename
          </Button>
        ) : null}
        <Button
          type="button"
          size="sm"
          variant="ghost"
          onClick={() => {
            setDeleteError(null)
            setDeleteOpen(true)
          }}
        >
          Delete
        </Button>
      </div>

      <DeleteTeamDialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        teamName={team.name}
        onConfirm={() => void confirmDelete()}
        pending={deletePending}
        error={deleteError}
      />
    </li>
  )
}
