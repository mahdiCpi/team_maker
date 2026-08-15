"use client"

import * as React from "react"
import Link from "next/link"

import { EmptyState } from "@/components/empty-state"
import { buttonVariants } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { listTeams } from "@/lib/api-client"
import type { TeamView } from "@/lib/api-types"
import { TeamRow } from "./team-row"

/**
 * My Teams (Story 2.8) — replaces the Story 2.1 `EmptyState` stub with a real
 * list, fetched from Story 2.5's backend (`GET /api/teams/browse`).
 *
 * Three distinct states, per AC 1: loading (a skeleton, not the empty-state
 * copy — a load in progress is not the same fact as "no teams exist"),
 * failed-to-load (a plain-language message, `EXPERIENCE.md:104`'s "never a
 * silent failure"), and loaded (empty-state copy only when the list is
 * genuinely empty, or the real list).
 */
export function MyTeamsSurface() {
  const [teams, setTeams] = React.useState<TeamView[] | null>(null)
  const [loadError, setLoadError] = React.useState<string | null>(null)

  React.useEffect(() => {
    let cancelled = false
    void (async () => {
      const result = await listTeams()
      if (cancelled) return
      if (result.ok) setTeams(result.data.teams)
      else setLoadError(result.message)
    })()
    return () => {
      cancelled = true
    }
  }, [])

  function handleRenamed(oldName: string, updated: TeamView) {
    setTeams((current) =>
      current ? current.map((team) => (team.name === oldName ? updated : team)) : current
    )
  }

  function handleDeleted(name: string) {
    setTeams((current) => (current ? current.filter((team) => team.name !== name) : current))
  }

  if (loadError) {
    return (
      <p role="alert" data-slot="my-teams-load-error" className="text-sm text-destructive">
        {loadError}
      </p>
    )
  }

  if (teams === null) {
    return (
      <div data-slot="my-teams-loading" className="flex flex-col gap-2">
        <Skeleton className="h-16 w-full" />
        <Skeleton className="h-16 w-full" />
        <Skeleton className="h-16 w-full" />
      </div>
    )
  }

  if (teams.length === 0) {
    return (
      <EmptyState title="My Teams" description="No teams yet. Describe one, or start from a template.">
        <Link href="/" className={buttonVariants()}>
          New Team
        </Link>
      </EmptyState>
    )
  }

  return (
    <ul data-slot="my-teams-list" className="flex flex-col gap-2">
      {teams.map((team) => (
        <TeamRow key={team.name} team={team} onRenamed={handleRenamed} onDeleted={handleDeleted} />
      ))}
    </ul>
  )
}
