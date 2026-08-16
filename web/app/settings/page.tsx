import type { Metadata } from "next";

import { EmptyState } from "@/components/empty-state";
import { ThemeToggle } from "@/components/theme-toggle";
import { SettingsSurface } from "@/components/settings/settings-surface";

export const metadata: Metadata = {
  title: "Settings · team_maker",
};

export default function SettingsPage() {
  return (
    <>
      <h1
        id="page-heading"
        tabIndex={-1}
        className="text-xs font-medium tracking-wide text-muted-foreground uppercase"
      >
        Settings
      </h1>
      <EmptyState title="Settings" description="Configure providers and view key status.">
        <div className="space-y-6">
          <ThemeToggle />
          <SettingsSurface />
        </div>
      </EmptyState>
    </>
  );
}
