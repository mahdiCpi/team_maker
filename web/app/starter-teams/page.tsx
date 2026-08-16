import type { Metadata } from "next";
import Link from "next/link";

import { EmptyState } from "@/components/empty-state";
import { buttonVariants } from "@/components/ui/button";

export const metadata: Metadata = {
  title: "Starter Teams · team_maker",
};

export default function StarterTeamsPage() {
  return (
    <>
      <h1
        id="page-heading"
        tabIndex={-1}
        className="text-xs font-medium tracking-wide text-muted-foreground uppercase"
      >
        Starter Teams
      </h1>
      <EmptyState
        title="Starter Teams"
        description="No starter teams yet. team_maker will offer ready-made templates here."
      >
        <Link href="/" className={buttonVariants()}>
          New Team
        </Link>
      </EmptyState>
    </>
  );
}
