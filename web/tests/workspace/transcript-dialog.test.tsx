import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import * as React from "react";
import { describe, expect, it, vi } from "vitest";

import { TranscriptDialog } from "@/components/workspace/transcript-dialog";

import { transcriptAvailable, transcriptUnavailable } from "./fixtures";

/** `TranscriptDialog` is controlled, and Base UI's `onOpenChange` is called
 *  with `(open, eventDetails)`, not a bare boolean — mirroring
 *  `tests/composer/keyboard.test.tsx`'s "AC 6 — Esc exits the review editor"
 *  precedent, this asserts the dialog actually disappears from the
 *  accessibility tree rather than the exact shape of the callback's args. */
function ControlledTranscriptDialog() {
  const [open, setOpen] = React.useState(true);
  return (
    <TranscriptDialog open={open} onOpenChange={setOpen} transcript={transcriptAvailable} />
  );
}

describe("TranscriptDialog", () => {
  it("shows an honest 'nothing yet' state, not a blank panel, when unavailable", () => {
    render(
      <TranscriptDialog open onOpenChange={vi.fn()} transcript={transcriptUnavailable} />
    );

    expect(screen.getByText("No transcript is available for this run yet.")).toBeInTheDocument();
    expect(document.querySelector('[data-slot="workspace-transcript-entry"]')).toBeNull();
  });

  it("shows the same 'nothing yet' state before any transcript has loaded (null)", () => {
    render(<TranscriptDialog open onOpenChange={vi.fn()} transcript={null} />);

    expect(screen.getByText("No transcript is available for this run yet.")).toBeInTheDocument();
  });

  it("sorts entries by sparse, non-contiguous sequence — never by list position", () => {
    render(
      <TranscriptDialog open onOpenChange={vi.fn()} transcript={transcriptAvailable} />
    );

    const rows = document.querySelectorAll('[data-slot="workspace-transcript-entry"]');
    expect(Array.from(rows).map((row) => row.getAttribute("data-kind"))).toEqual([
      "task_started",
      "delegation",
      "task_completed",
    ]);
  });

  it("branches on kind, not on content, and renders a delegation's both ends", () => {
    render(
      <TranscriptDialog open onOpenChange={vi.fn()} transcript={transcriptAvailable} />
    );

    const delegationRow = document.querySelector('[data-slot="workspace-transcript-entry"][data-kind="delegation"]');
    expect(delegationRow?.textContent).toContain("Delegation");
    expect(delegationRow?.textContent).toContain("poet");
    expect(delegationRow?.textContent).toContain("editor");

    const taskRow = document.querySelector('[data-slot="workspace-transcript-entry"][data-kind="task_started"]');
    expect(taskRow?.textContent).toContain("Task started");
  });

  it("does not render an empty-list panel as though nothing was said, when entries genuinely are empty but available", () => {
    render(
      <TranscriptDialog
        open
        onOpenChange={vi.fn()}
        transcript={{ available: true, entries: [] }}
      />
    );

    expect(screen.getByText("The agents recorded nothing for this run.")).toBeInTheDocument();
  });

  describe("AC 5 — Esc closes the dialog", () => {
    it("closes the transcript dialog when Escape is pressed", async () => {
      const user = userEvent.setup();

      render(<ControlledTranscriptDialog />);

      // Dialog should be open
      expect(screen.getByRole("dialog")).toBeInTheDocument();

      // Press Escape
      await user.keyboard("{Escape}");

      // Dialog should be closed
      await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    });
  });
});
