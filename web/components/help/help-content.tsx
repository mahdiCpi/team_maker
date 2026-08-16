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

/**
 * Help content for orientation and wayfinding (Story 2.11, AC 3, 4).
 *
 * Plain-language answers to the concrete orientation questions a lost user
 * actually asks: what is a team, what do the build controls do, where do
 * built teams go, how to run one again.
 *
 * Voice and Tone: plain, confident, helpful — matches EXPERIENCE.md:52-62.
 * Reuses existing established copy where it already exists.
 */
export function HelpContent({
  open,
  onOpenChange,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="text-lg font-semibold">
            About team_maker
          </DialogTitle>
        </DialogHeader>
        <DialogDescription className="space-y-4 text-base leading-relaxed">
          <p>
            team_maker turns a description into a runnable team of AI agents.
            Describe what work you want done, then build and run the team.
          </p>
          
          <section className="space-y-2">
            <h3 className="font-medium text-foreground">What is a team?</h3>
            <p className="text-muted-foreground">
              A team is a group of AI agents configured to work together on a task.
              Each agent has a role, a model, and specific responsibilities.
            </p>
          </section>

          <section className="space-y-2">
            <h3 className="font-medium text-foreground">Build team vs Run it now</h3>
            <p className="text-muted-foreground">
              Build team writes the package. Run it now does the same, skipping review.
            </p>
          </section>

          <section className="space-y-2">
            <h3 className="font-medium text-foreground">Where do my teams go?</h3>
            <p className="text-muted-foreground">
              Built teams appear in My Teams. Open a team to chat with it or re-run it.
            </p>
          </section>

          <section className="space-y-2">
            <h3 className="font-medium text-foreground">How do I run a team again?</h3>
            <p className="text-muted-foreground">
              Go to My Teams, open your team, and use the run controls in the workspace.
            </p>
          </section>

          <section className="space-y-2 border-t pt-4">
            <h3 className="font-medium text-foreground">First visit orientation</h3>
            <p className="text-muted-foreground">
              team_maker turns a description into a runnable team of AI agents.
              Describe what work you want done, then build and run the team.
            </p>
          </section>
        </DialogDescription>
        <div className="flex justify-end">
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
            data-slot="help-close"
          >
            Close
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
