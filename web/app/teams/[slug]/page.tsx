import type { Metadata } from "next";

import { WorkspaceSurface } from "@/components/workspace/workspace-surface";

/**
 * The title is static and does not name the team (Story 2.4 AC 11).
 *
 * Naming it would need `generateMetadata({ params })`, which means a
 * server-side fetch — and `lib/api-client.ts`'s own docstring is explicit
 * that it is "the single place in the frontend that talks to `/api`". Every
 * existing route (`web/app/my-teams/page.tsx:7-9`) exports a plain object;
 * `web/tests/shell/routes.test.tsx` asserts the `"<Name> · team_maker"`
 * shape. This matches it, and declares the title does not name the team.
 */
export const metadata: Metadata = {
  title: "Team Workspace · team_maker",
};

/**
 * Kept a **server component** so `metadata` stays valid — every piece of
 * interactivity lives in `WorkspaceSurface`, which is `"use client"`.
 *
 * `params` is a `Promise` (Next 16's dynamic API), so this is `async`.
 */
export default async function TeamWorkspacePage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  return <WorkspaceSurface teamSlug={slug} />;
}
