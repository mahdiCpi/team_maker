import type { Metadata } from "next";

import { EmptyState } from "@/components/empty-state";
import { ThemeToggle } from "@/components/theme-toggle";

export const metadata: Metadata = {
  title: "Settings · team_maker",
};

export default function SettingsPage() {
  return (
    <EmptyState title="Settings" description="Choose how team_maker looks.">
      <ThemeToggle />
    </EmptyState>
  );
}
