"use client"

import * as React from "react"

/**
 * Subscribes to a CSS media query.
 *
 * Uses `useSyncExternalStore` rather than useState + useEffect: it gives a
 * correct server snapshot without an extra render, and it avoids the
 * `react-hooks/set-state-in-effect` pattern the project's lint config rejects.
 */
export function useMediaQuery(query: string): boolean {
  const subscribe = React.useCallback(
    (onChange: () => void) => {
      const mql = window.matchMedia(query)
      mql.addEventListener("change", onChange)
      return () => mql.removeEventListener("change", onChange)
    },
    [query]
  )

  return React.useSyncExternalStore(
    subscribe,
    () => window.matchMedia(query).matches,
    () => false
  )
}
