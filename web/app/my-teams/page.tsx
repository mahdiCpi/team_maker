import type { Metadata } from "next";

import { MyTeamsSurface } from "@/components/my-teams/my-teams-surface";

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
      <MyTeamsSurface />
    </>
  );
}
