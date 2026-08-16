import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

import { AppShellProvider } from "@/components/app-shell-provider";
import { AppSidebar } from "@/components/app-sidebar";
import { NavShortcuts } from "@/components/nav-shortcuts";
import { RouteFocusAnnouncer } from "@/components/route-focus-announcer";
import { ThemeProvider } from "@/components/theme-provider";
import { Separator } from "@/components/ui/separator";
import { SidebarInset, SidebarTrigger } from "@/components/ui/sidebar";
import { TooltipProvider } from "@/components/ui/tooltip";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: {
    default: "team_maker",
    template: "%s",
  },
  description: "Build and run multi-agent teams without the CLI.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
      suppressHydrationWarning
    >
      <body className="min-h-full">
        <ThemeProvider>
          <TooltipProvider>
            <AppShellProvider>
              <AppSidebar />
              <SidebarInset>
                <header className="flex h-12 shrink-0 items-center gap-2 px-4">
                  <SidebarTrigger />
                  <Separator orientation="vertical" className="h-4" />
                  {/* Placed after the trigger so it is the first focusable
                      element inside the content region; without it a keyboard
                      user tabs the whole sidebar on every route. */}
                  <a
                    href="#main-content"
                    className="sr-only rounded-md px-3 py-1.5 text-sm underline underline-offset-4 focus:not-sr-only focus:outline-2 focus:outline-offset-2 focus:outline-ring"
                  >
                    Skip to content
                  </a>
                </header>
                <div
                  id="main-content"
                  tabIndex={-1}
                  className="flex flex-1 flex-col px-4 pb-4"
                >
                  {children}
                </div>
              </SidebarInset>
            </AppShellProvider>
            <NavShortcuts />
            <RouteFocusAnnouncer />
          </TooltipProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
