"use client"

import { Monitor, Moon, Sun } from "lucide-react"
import { useTheme } from "next-themes"

import { Button } from "@/components/ui/button"

const MODES = [
  { value: "light", label: "Light", icon: Sun },
  { value: "dark", label: "Dark", icon: Moon },
  { value: "system", label: "System", icon: Monitor },
] as const

/**
 * Three-way theme control (Story 2.1, AC 9).
 *
 * `system` is a real, reachable choice rather than only the initial default.
 * A two-way toggle made the provider's own `defaultTheme="system"`
 * unreachable after the first click: the app stopped following the OS with no
 * UI path back short of clearing localStorage.
 */
export function ThemeToggle() {
  const { theme, setTheme } = useTheme()

  // next-themes reports `undefined` until it mounts; render a stable
  // placeholder rather than guessing a value and mismatching on hydration.
  if (theme === undefined) {
    return (
      <div className="flex gap-1" aria-busy="true">
        {MODES.map((mode) => (
          <Button key={mode.value} variant="outline" disabled>
            <mode.icon />
            {mode.label}
          </Button>
        ))}
      </div>
    )
  }

  return (
    <div className="flex gap-1" role="group" aria-label="Theme">
      {MODES.map((mode) => (
        <Button
          key={mode.value}
          variant={theme === mode.value ? "default" : "outline"}
          aria-pressed={theme === mode.value}
          onClick={() => setTheme(mode.value)}
        >
          <mode.icon />
          {mode.label}
        </Button>
      ))}
    </div>
  )
}
