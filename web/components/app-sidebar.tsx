"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"

import { BrandWordmark } from "@/components/brand-wordmark"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
} from "@/components/ui/sidebar"
import type { NavDestination } from "@/lib/nav-items"
import { NAV_DESTINATIONS, SETTINGS_DESTINATION } from "@/lib/nav-items"

function NavItem({
  item,
  isActive,
}: {
  item: NavDestination
  isActive: boolean
}) {
  const shortcut = item.shortcut ? `g ${item.shortcut}` : undefined

  return (
    <SidebarMenuItem>
      <SidebarMenuButton
        isActive={isActive}
        tooltip={item.title}
        aria-keyshortcuts={shortcut}
        render={<Link href={item.href} />}
      >
        <item.icon />
        <span>{item.title}</span>
        {shortcut ? (
          // aria-hidden: the shortcut is exposed through aria-keyshortcuts
          // above. Left visible to assistive tech it became part of every
          // link's accessible name ("New Team g n, link").
          <kbd
            aria-hidden="true"
            className="ml-auto text-xs text-muted-foreground group-data-[collapsible=icon]:hidden"
          >
            {shortcut}
          </kbd>
        ) : null}
      </SidebarMenuButton>
    </SidebarMenuItem>
  )
}

export function AppSidebar() {
  const pathname = usePathname()

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <BrandWordmark />
      </SidebarHeader>
      <SidebarContent>
        {/* SidebarGroup supplies the horizontal padding that aligns menu rows
            with the header and footer; SidebarContent has none of its own. */}
        <nav aria-label="Primary">
          <SidebarGroup>
            <SidebarMenu>
              {NAV_DESTINATIONS.map((item) => (
                <NavItem
                  key={item.href}
                  item={item}
                  isActive={pathname === item.href}
                />
              ))}
            </SidebarMenu>
          </SidebarGroup>
        </nav>
      </SidebarContent>
      <SidebarFooter>
        <nav aria-label="Settings">
          <SidebarMenu>
            <NavItem
              item={SETTINGS_DESTINATION}
              isActive={pathname === SETTINGS_DESTINATION.href}
            />
          </SidebarMenu>
        </nav>
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  )
}
