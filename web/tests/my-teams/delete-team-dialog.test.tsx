import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import * as React from "react";
import { describe, expect, it, vi } from "vitest";

import { DeleteTeamDialog } from "@/components/my-teams/delete-team-dialog";

/** Mirrors `tests/workspace/transcript-dialog.test.tsx`'s "AC 5 — Esc closes
 *  the dialog" precedent (Story 2.7's accessibility floor). */
function ControlledDeleteDialog() {
  const [open, setOpen] = React.useState(true);
  return (
    <DeleteTeamDialog
      open={open}
      onOpenChange={setOpen}
      teamName="Article Team"
      onConfirm={vi.fn()}
      pending={false}
      error={null}
    />
  );
}

describe("DeleteTeamDialog", () => {
  it("names the team and what will be deleted", () => {
    render(
      <DeleteTeamDialog
        open
        onOpenChange={vi.fn()}
        teamName="Article Team"
        onConfirm={vi.fn()}
        pending={false}
        error={null}
      />
    );

    expect(screen.getByRole("heading", { name: /Article Team/ })).toBeInTheDocument();
    expect(screen.getByText(/saved runs and results/)).toBeInTheDocument();
  });

  it("shows an error inside the dialog without closing it", () => {
    render(
      <DeleteTeamDialog
        open
        onOpenChange={vi.fn()}
        teamName="Article Team"
        onConfirm={vi.fn()}
        pending={false}
        error="Something went wrong on the server."
      />
    );

    expect(screen.getByRole("alert").textContent).toBe("Something went wrong on the server.");
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("does not call onConfirm again while a delete is pending", async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();
    render(
      <DeleteTeamDialog
        open
        onOpenChange={vi.fn()}
        teamName="Article Team"
        onConfirm={onConfirm}
        pending
        error={null}
      />
    );

    await user.click(screen.getByRole("button", { name: "Deleting…" }));
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it("closes when Escape is pressed", async () => {
    const user = userEvent.setup();
    render(<ControlledDeleteDialog />);

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });
});
