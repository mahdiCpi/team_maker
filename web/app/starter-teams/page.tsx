import type { Metadata } from "next";

import { StarterTeamsSurface } from "@/components/starter-teams/starter-teams-surface";

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
      <StarterTeamsSurface />
    </>
  );
}
