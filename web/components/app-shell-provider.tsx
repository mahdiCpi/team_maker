"use client"

import * as React from "react"

import { SidebarProvider } from "@/components/ui/sidebar"
import { useMediaQuery } from "@/lib/use-media-query"

/** `lg` in Tailwind's default scale — the boundary AC 5 names. */
export const DESKTOP_QUERY = "(min-width: 1024px)"

/**
 * Supplies the three responsive sidebar states AC 5 requires:
 *
 *   ≥ lg (1024px)  full sidebar
 *   md  (768–1023) collapsed to icons
 *   < md (768px)   off-canvas Sheet — handled inside shadcn's `Sidebar`
 *
 * shadcn's `collapsible="icon"` alone only describes what a *user-initiated*
 * toggle does; the component's sole automatic breakpoint is the 768px switch
 * to the mobile Sheet. So the md band is driven here, through the component's
 * own controlled `open` API rather than a hand-rolled layout.
 *
 * An explicit user toggle pins the sidebar for the rest of the session:
 * `override` starts null (follow the viewport) and any interaction takes it
 * over, so resizing never fights a choice the user just made.
 */
export function AppShellProvider({ children }: { children: React.ReactNode }) {
  const isDesktop = useMediaQuery(DESKTOP_QUERY)
  const [override, setOverride] = React.useState<boolean | null>(null)

  return (
    <SidebarProvider open={override ?? isDesktop} onOpenChange={setOverride}>
      {children}
    </SidebarProvider>
  )
}
