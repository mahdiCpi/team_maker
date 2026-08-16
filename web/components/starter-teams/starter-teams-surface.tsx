"use client"

import * as React from "react"
import Link from "next/link"

import { EmptyState } from "@/components/empty-state"
import { Skeleton } from "@/components/ui/skeleton"
import { listStarterTeams } from "@/lib/api-client"
import type { StarterTeamView } from "@/lib/api-types"
import { StarterTeamCard } from "./starter-team-card"

/**
 * Starter Teams surface (Story 3-1) — replaces the Story 2.1 `EmptyState` stub
 * with a real list, fetched from Story 3-1's backend (`GET /api/starters`).
 *
 * Three distinct states, mirroring `MyTeamsSurface`'s pattern:
 * - loading (a skeleton, not the empty-state copy)
 * - failed-to-load (a plain-language message)
 * - loaded (empty-state copy only when the list is genuinely empty, or the real list)
 *
 * Note: display-only here — no run/select/"Adapt with Composer" affordance.
 * Story 3.2 adds the actions.
 */
export function StarterTeamsSurface() {
  const [starters, setStarters] = React.useState<StarterTeamView[] | null>(null)
  const [loadError, setLoadError] = React.useState<string | null>(null)

  React.useEffect(() => {
    let cancelled = false
    void (async () => {
      const result = await listStarterTeams()
      if (cancelled) return
      if (result.ok) setStarters(result.data.starters)
      else setLoadError(result.message)
    })()
    return () => {
      cancelled = true
    }
  }, [])

  if (loadError) {
    return (
      <p role="alert" data-slot="starter-teams-load-error" className="text-sm text-destructive">
        {loadError}
      </p>
    )
  }

  if (starters === null) {
    return (
      <div data-slot="starter-teams-loading" className="flex flex-col gap-2">
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-24 w-full" />
      </div>
    )
  }

  if (starters.length === 0) {
    return (
      <EmptyState
        title="Starter Teams"
        description="No starter teams available. Check your installation."
      >
        <Link href="/" className={buttonVariants()}>
          New Team
        </Link>
      </EmptyState>
    )
  }

  return (
    <ul data-slot="starter-teams-list" className="flex flex-col gap-4">
      {starters.map((starter) => (
        <li key={starter.id}>
          <StarterTeamCard starter={starter} />
        </li>
      ))}
    </ul>
  )
}
