import type { Metadata } from "next";
import Link from "next/link";

import { EmptyState } from "@/components/empty-state";
import { Button } from "@/components/ui/button";

export const metadata: Metadata = {
  title: "Starter Teams · team_maker",
};

export default function StarterTeamsPage() {
  return (
    <EmptyState
      title="Starter Teams"
      description="No starter teams yet. team_maker will offer ready-made templates here."
    >
      <Button render={<Link href="/" />}>New Team</Button>
    </EmptyState>
  );
}
