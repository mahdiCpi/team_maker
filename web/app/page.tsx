import type { Metadata } from "next";

import { ComposerSurface } from "@/components/composer/composer-surface";

export const metadata: Metadata = {
  title: "New Team · team_maker",
};

/**
 * The landing route, and the Composer (AC 1).
 *
 * Kept a **server component** so this `metadata` export stays valid; every piece
 * of interactivity lives in `ComposerSurface`, which is `"use client"`.
 *
 * This replaces the placeholder Story 2.1 shipped. Its heading ("New Team") and
 * its description ("Describe the team you need, or begin from a starter team.")
 * appeared in no spine, and its primary action was a `New Team` button on the
 * New Team page that linked to `/starter-teams`.
 */
export default function NewTeamPage() {
  return <ComposerSurface />;
}
