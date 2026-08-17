"use client"

import * as React from "react"
import Link from "next/link"

import { buttonVariants } from "@/components/ui/button"
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import type { StarterTeamView } from "@/lib/api-types"

/**
 * One starter team card (Story 3-1). Display-only — no run/select/"Adapt with
 * Composer" affordance here; Story 3.2 adds the actions.
 */
export function StarterTeamCard({ starter }: { starter: StarterTeamView }) {
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
    </Card>
  )
}
