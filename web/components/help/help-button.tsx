"use client"

import * as React from "react"
import { HelpCircle } from "lucide-react"

import {
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar"
import { HelpContent } from "@/components/help/help-content"

/**
 * Help button for the app sidebar (Story 2.11, AC 3).
 *
 * A small, persistent, discoverable help affordance in the app shell
 * that links to a short, static in-app dialog answering orientation questions.
 */
export function HelpButton() {
  const [open, setOpen] = React.useState(false)

  return (
    <>
      <SidebarMenuItem>
        <SidebarMenuButton
          tooltip="Help"
          onClick={() => setOpen(true)}
          aria-haspopup="dialog"
          aria-expanded={open}
          data-slot="sidebar-help"
        >
          <HelpCircle />
          <span>Help</span>
        </SidebarMenuButton>
      </SidebarMenuItem>
      <HelpContent open={open} onOpenChange={setOpen} />
    </>
  )
}
