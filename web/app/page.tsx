import type { Metadata } from "next";
import Link from "next/link";

import { EmptyState } from "@/components/empty-state";
import { Button } from "@/components/ui/button";

export const metadata: Metadata = {
  title: "New Team · team_maker",
};

export default function NewTeamPage() {
  return (
    <EmptyState
      title="New Team"
      description="Describe the team you need, or begin from a starter team."
    >
      <Button render={<Link href="/starter-teams" />}>New Team</Button>
    </EmptyState>
  );
}
