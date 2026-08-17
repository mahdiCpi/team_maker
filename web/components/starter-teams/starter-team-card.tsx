"use client"

import * as React from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"

import { Button, buttonVariants } from "@/components/ui/button"
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { runStarterTeam } from "@/lib/api-client"
import type { StarterTeamView } from "@/lib/api-types"

/**
 * One starter team card (Story 3-1 display, Story 3-2 actions).
 * 
 * Exposes "Run" and "Adapt with Composer" controls (Story 3-2).
 */
export function StarterTeamCard({ starter }: { starter: StarterTeamView }) {
  const router = useRouter()
  const [runPending, setRunPending] = React.useState(false)
  const [runError, setRunError] = React.useState<string | null>(null)

  async function handleRun() {
    if (runPending) return
    setRunPending(true)
    setRunError(null)

    const result = await runStarterTeam(starter.id)
    setRunPending(false)

    if (result.ok) {
      // Navigate to the team's workspace
      router.push(`/teams/${encodeURIComponent(result.data.team_slug)}`)
    } else {
      setRunError(result.message)
    }
  }

  return (
    <Card data-slot="starter-team-card" className="hover:shadow-md transition-shadow">
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <span>{starter.name}</span>
          <span className="text-sm font-normal text-muted-foreground">
            {starter.agent_count} agents
          </span>
        </CardTitle>
        <CardDescription>{starter.purpose}</CardDescription>
      </CardHeader>
      <div className="p-4 pt-0">
        <div className="flex gap-2">
          <Button
            onClick={handleRun}
            disabled={runPending}
            data-slot="starter-team-card-run"
            className="flex-1"
          >
            {runPending ? "Building..." : "Run"}
          </Button>
          <Link
            href={`/?starter=${encodeURIComponent(starter.id)}`}
            data-slot="starter-team-card-adapt"
            className={buttonVariants({ variant: "outline", className: "flex-1" })}
          >
            Adapt with Composer
          </Link>
        </div>
        {runError ? (
          <p role="alert" className="mt-2 text-xs text-destructive">
            {runError}
          </p>
        ) : null}
      </div>
    </Card>
  )
}
