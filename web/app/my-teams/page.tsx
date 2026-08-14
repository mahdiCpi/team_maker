import type { Metadata } from "next";
import Link from "next/link";

import { EmptyState } from "@/components/empty-state";
import { Button } from "@/components/ui/button";

export const metadata: Metadata = {
  title: "My Teams · team_maker",
};

export default function MyTeamsPage() {
  return (
    <>
      <h1
        id="page-heading"
        tabIndex={-1}
        className="text-xs font-medium tracking-wide text-muted-foreground uppercase"
      >
        My Teams
      </h1>
      <EmptyState
        title="My Teams"
        description="No teams yet. Describe one, or start from a template."
      >
        <Button render={<Link href="/" />}>New Team</Button>
      </EmptyState>
    </>
  );
}
