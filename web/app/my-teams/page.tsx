import type { Metadata } from "next";
import Link from "next/link";

import { EmptyState } from "@/components/empty-state";
import { Button } from "@/components/ui/button";

export const metadata: Metadata = {
  title: "My Teams · team_maker",
};

export default function MyTeamsPage() {
  return (
    <EmptyState
      title="My Teams"
      description="No teams yet. Describe one, or start from a template."
    >
      <Button render={<Link href="/" />}>New Team</Button>
    </EmptyState>
  );
}
