"use client"

import * as React from "react"
import { useSearchParams } from "next/navigation"
import { useRouter } from "next/navigation"

import { createSessionFromStarter } from "@/lib/api-client"
import type { ComposerAction } from "./composer-state"

/**
 * Starter seed effect (Story 3-2).
 * 
 * Reads the `?starter=<starter_id>` query param and, if present, creates a
 * Composer session from that starter and dispatches it into the state.
 * 
 * Isolated in a Suspense boundary because useSearchParams() requires it for
 * static generation (next/build fails without it).
 * 
 * Only runs once on mount. If the session creation fails, the error is
 * surfaced inline; the user can still use the Composer normally.
 */
export function StarterSeedEffect({
  dispatch,
}: {
  dispatch: React.Dispatch<ComposerAction>;
}) {
  const searchParams = useSearchParams();
  const router = useRouter();
  const [seeding, setSeeding] = React.useState(false);
  const [seedError, setSeedError] = React.useState<string | null>(null);
  // Holds the in-flight (or settled) `createSessionFromStarter` promise, so
  // React Strict Mode's dev-only double-invoke of this effect (mount ->
  // cleanup -> mount again, on the same component instance — a ref survives
  // that, unlike a local variable) reuses one request instead of firing a
  // second, orphaned from-starter session server-side. A plain "already
  // seeded" boolean guard does not work here: it would block the *second*
  // invocation's own async call from starting at all, but the *first*
  // invocation's `cancelled` flag still flips true when its cleanup runs
  // (immediately, as part of the same synthetic mount/cleanup/mount
  // sequence) — discarding the only response anyone ever asked for. Sharing
  // the promise lets both invocations await the same request while each
  // still gates on its *own* `cancelled`, so whichever invocation survives
  // (is not immediately cleaned up) is the one that applies the result.
  const seedPromiseRef = React.useRef<ReturnType<typeof createSessionFromStarter> | null>(null);

  React.useEffect(() => {
    const starterId = searchParams.get("starter");
    if (!starterId) return;

    // Clear the query param from the URL after reading it
    // (optional - the user can navigate back to see it, but it's no longer needed)
    const url = new URL(window.location.href);
    url.searchParams.delete("starter");
    router.replace(url.toString());

    // Set once this invocation's cleanup runs, so a late-arriving response
    // never sets state on a component instance that has moved on — the same
    // pattern `composer-surface.tsx`'s own effects already use.
    let cancelled = false;

    async function seedFromStarter(id: string) {
      setSeeding(true);
      setSeedError(null);

      if (!seedPromiseRef.current) {
        seedPromiseRef.current = createSessionFromStarter({ starter_id: id });
      }
      const result = await seedPromiseRef.current;
      if (cancelled) return;
      setSeeding(false);

      if (result.ok) {
        // Dispatch the session into state - no transcript entry (no turn spent)
        dispatch({ type: "session_seeded", session: result.data });
      } else {
        setSeedError(
          `Failed to load starter team: ${result.message}. You can still describe a team from scratch.`
        );
      }
    }

    void seedFromStarter(starterId);

    return () => {
      cancelled = true;
    };
  }, [searchParams, dispatch, router]);

  // Render error if seeding failed
  if (seedError) {
    return (
      <p role="alert" className="text-sm text-destructive" data-slot="starter-seed-error">
        {seedError}
      </p>
    );
  }

  // Render loading state
  if (seeding) {
    return (
      <p className="text-sm text-muted-foreground" data-slot="starter-seed-loading">
        Loading starter team...
      </p>
    );
  }

  // No starter param or seeding complete - render nothing
  return null;
}
