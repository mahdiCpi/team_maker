import { HelpCircle, LayoutTemplate, Settings, Sparkles, Users } from "lucide-react"
import type { LucideIcon } from "lucide-react"

export type NavDestination = {
  title: string
  href: string
  icon: LucideIcon
  /** Second key of the `g <key>` chord that navigates here (Story 2.1, AC 11). */
  shortcut?: string
}

export const NAV_DESTINATIONS: NavDestination[] = [
  { title: "New Team", href: "/", icon: Sparkles, shortcut: "n" },
  { title: "Starter Teams", href: "/starter-teams", icon: LayoutTemplate },
  { title: "My Teams", href: "/my-teams", icon: Users, shortcut: "t" },
]

export const SETTINGS_DESTINATION: NavDestination = {
  title: "Settings",
  href: "/settings",
  icon: Settings,
}

export const HELP_DESTINATION: NavDestination = {
  title: "Help",
  href: "/help",
  icon: HelpCircle,
}
