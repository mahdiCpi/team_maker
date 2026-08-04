"use client"

import { Button } from "@/components/ui/button"
import { Switch } from "@/components/ui/switch"

const REVIEW_LABEL_ID = "composer-review-before-build"

/**
 * The persistent action bar (AC 3, AC 4).
 *
 * It renders below the transcript, outside the only scrolling region, which is
 * what satisfies "does not scroll away with the transcript" (UX-DR4) — no
 * sticky positioning is involved.
 *
 * **Two controls with different meanings, not a duplicate pair.**
 * `Build team` commits the current spec *honouring* the review toggle;
 * `Run it now` *bypasses* the toggle and builds immediately, which is what
 * `EXPERIENCE.md:70`'s "skips further tuning" means. With review off they
 * converge, and that is expected.
 *
 * Neither builds *and runs*: a run needs a goal, and the goal is entered in the
 * Workspace (`EXPERIENCE.md:188`), which is Story 2.4.
 *
 * Nothing here is `disabled`. An unavailable action carries `aria-disabled` and
 * the reason is rendered as text — `EXPERIENCE.md:104` bans hiding a blocked
 * action behind a silent failure.
 */
export function ComposerActions({
  reviewBeforeBuild,
  onReviewChange,
  onBuild,
  onRunNow,
  buildBlockedReason,
  runNowBlockedReason,
}: {
  reviewBeforeBuild: boolean
  onReviewChange: (enabled: boolean) => void
  onBuild: () => void
  onRunNow: () => void
  /** Non-null means the action cannot proceed, and says why. */
  buildBlockedReason: string | null
  runNowBlockedReason: string | null
}) {
  return (
    <div
      data-slot="composer-actions"
      className="flex flex-col gap-2 border-t pt-3"
    >
      <div className="flex flex-wrap items-center gap-3">
        <Button
          type="button"
          onClick={() => {
            if (!buildBlockedReason) onBuild()
          }}
          aria-disabled={buildBlockedReason !== null}
          data-slot="composer-build"
        >
          Build team
        </Button>
        <Button
          type="button"
          variant="outline"
          onClick={() => {
            if (!runNowBlockedReason) onRunNow()
          }}
          aria-disabled={runNowBlockedReason !== null}
          data-slot="composer-run-now"
        >
          Run it now
        </Button>

        <div className="ml-auto flex items-center gap-2">
          {/* `aria-labelledby` rather than a `<label for>`: the Switch renders a
              button, and a label element is not a naming mechanism for one. */}
          <span id={REVIEW_LABEL_ID} className="text-sm">
            Review before build
          </span>
          <Switch
            aria-labelledby={REVIEW_LABEL_ID}
            checked={reviewBeforeBuild}
            onCheckedChange={onReviewChange}
            data-slot="composer-review-toggle"
          />
        </div>
      </div>

      {buildBlockedReason || runNowBlockedReason ? (
        <p
          data-slot="composer-actions-reason"
          className="text-xs text-muted-foreground"
        >
          {buildBlockedReason ?? runNowBlockedReason}
        </p>
      ) : (
        <p
          data-slot="composer-actions-reason"
          className="text-xs text-muted-foreground"
        >
          {reviewBeforeBuild
            ? "Build team opens the spec for review first. Run it now skips it."
            : "Build team writes the package. Run it now does the same, skipping review."}
        </p>
      )}
    </div>
  )
}
