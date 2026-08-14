"use client"

import { usePathname } from "next/navigation"
import * as React from "react"

/**
 * Route Focus Announcer (AC 4)
 *
 * Observes pathname changes and moves focus to the page heading
 * (`#page-heading`) on every route change after the first mount.
 * This provides screen reader users with immediate context about
 * which surface they have navigated to.
 *
 * The initial page load is not re-focused — the browser already places
 * focus at document start. Only subsequent client-side route changes
 * trigger the focus move.
 */
export function RouteFocusAnnouncer() {
  const pathname = usePathname()
  const initialMount = React.useRef(true)

  React.useEffect(() => {
    // Skip the initial mount — the browser already handles focus placement
    if (initialMount.current) {
      initialMount.current = false
      return
    }

    // Focus the page heading on route changes. Fall back to the main content
    // region on a route with no heading (e.g. a not-found page) so focus is
    // never silently dropped.
    const target =
      document.getElementById("page-heading") ?? document.getElementById("main-content")
    target?.focus()
  }, [pathname])

  // This component renders nothing to the DOM
  return null
}