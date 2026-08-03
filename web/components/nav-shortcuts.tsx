"use client"

import * as React from "react"
import { useRouter } from "next/navigation"

import { NAV_DESTINATIONS } from "@/lib/nav-items"

export const CHORD_LEADER = "g"
export const CHORD_WINDOW_MS = 1000

const TYPING_TAGS = new Set(["INPUT", "TEXTAREA", "SELECT"])

/**
 * True when the key belongs to whatever has focus rather than to the app.
 *
 * The contenteditable check reads the attribute rather than
 * `element.isContentEditable`, because jsdom does not implement that property
 * (it is `undefined`, not `false`), which would make the guard's tests
 * unfalsifiable. `plaintext-only` is included: it is a valid, shipping value
 * and the natural choice for a plain-text composer, so omitting it left the
 * exact Story 2.2 case this guard exists for unprotected.
 */
function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false
  if (TYPING_TAGS.has(target.tagName)) return true
  return (
    target.closest(
      '[contenteditable=""], [contenteditable="true" i], [contenteditable="plaintext-only" i]'
    ) !== null
  )
}

/**
 * Global `g n` / `g t` chord navigation (Story 2.1, AC 11). Renders nothing.
 * Pressing the leader key arms a ~1s window for the destination key.
 */
export function NavShortcuts() {
  const router = useRouter()
  const armedRef = React.useRef(false)
  const timerRef = React.useRef<ReturnType<typeof setTimeout> | null>(null)

  React.useEffect(() => {
    function clearTimer() {
      if (timerRef.current !== null) {
        clearTimeout(timerRef.current)
        timerRef.current = null
      }
    }

    function disarm() {
      armedRef.current = false
      clearTimer()
    }

    function arm() {
      armedRef.current = true
      clearTimer()
      timerRef.current = setTimeout(disarm, CHORD_WINDOW_MS)
    }

    function handleKeyDown(event: KeyboardEvent) {
      // Auto-repeat from a held key would otherwise toggle the armed flag on
      // every tick, making the chord succeed or fail on the parity of how
      // long the key was held.
      if (event.repeat) return
      if (event.metaKey || event.ctrlKey || event.altKey) return

      // Focus inside a text field cancels a pending chord rather than merely
      // ignoring the keystroke — otherwise the arm survives the excursion and
      // fires on the next key typed back on the page.
      if (isTypingTarget(event.target)) {
        disarm()
        return
      }

      const key = event.key.toLowerCase()

      if (armedRef.current) {
        // A second leader press re-arms: tapping `g` again after an uncertain
        // first press is a retry, not a cancel.
        if (key === CHORD_LEADER) {
          arm()
          return
        }
        const destination = NAV_DESTINATIONS.find((item) => item.shortcut === key)
        disarm()
        if (destination) {
          event.preventDefault()
          router.push(destination.href)
        }
        return
      }

      if (key === CHORD_LEADER) arm()
    }

    window.addEventListener("keydown", handleKeyDown)
    return () => {
      window.removeEventListener("keydown", handleKeyDown)
      disarm()
    }
  }, [router])

  return null
}
