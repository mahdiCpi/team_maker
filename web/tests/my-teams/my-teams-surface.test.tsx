import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { MyTeamsSurface } from "@/components/my-teams/my-teams-surface";
import { createTeamsFetchQueue, type TeamsFetchQueue } from "./harness";

const articleTeam = {
  name: "Article Team",
  created_at: "2026-08-01T00:00:00Z",
  last_run_at: null,
  run_count: 0,
};
const researchTeam = {
  name: "Research Team",
  created_at: "2026-08-01T00:00:00Z",
  last_run_at: "2026-08-10T00:00:00Z",
  run_count: 3,
};

let queue: TeamsFetchQueue;

beforeEach(() => {
  queue = createTeamsFetchQueue();
  queue.install();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("loading and empty states", () => {
  it("shows a loading state before the fetch resolves, not the empty-state copy", () => {
    // Never resolved within this test, deliberately: proves the loading
    // frame is distinct from "no teams yet" (AC 1), not merely a fast flash.
    render(<MyTeamsSurface />);

    expect(document.querySelector('[data-slot="my-teams-loading"]')).toBeInTheDocument();
    expect(screen.queryByText("No teams yet. Describe one, or start from a template.")).toBeNull();
  });

  it("shows the empty-state copy and a New Team link only once the list resolves empty", async () => {
    queue.queueBrowse(200, { teams: [] });
    render(<MyTeamsSurface />);

    await waitFor(() =>
      expect(screen.getByText("No teams yet. Describe one, or start from a template.")).toBeInTheDocument()
    );
    const link = screen.getByRole("link", { name: "New Team" });
    expect(link).toHaveAttribute("href", "/");
  });

  it("shows a plain-language message, not a crash, when the list fails to load", async () => {
    // The client shows the server's own authored message verbatim when it
    // does not look like a leaked internal (`transport.ts`'s `toFailure`) —
    // this proves the failure renders as text and never crashes the surface,
    // not that any particular wording is chosen.
    queue.queueBrowse(500, {
      error: { code: "internal_error", message: "The team list could not be loaded." },
    });
    render(<MyTeamsSurface />);

    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toBe("The team list could not be loaded.");
  });
});

describe("a populated list", () => {
  async function renderPopulated() {
    queue.queueBrowse(200, { teams: [articleTeam, researchTeam] });
    render(<MyTeamsSurface />);
    await waitFor(() => expect(screen.getAllByRole("listitem")).toHaveLength(2));
  }

  it("shows each team's name, last-run, and run count", async () => {
    await renderPopulated();

    expect(screen.getByText("Article Team")).toBeInTheDocument();
    expect(screen.getByText(/Never run/)).toBeInTheDocument();
    expect(screen.getByText(/0 runs/)).toBeInTheDocument();

    expect(screen.getByText("Research Team")).toBeInTheDocument();
    expect(screen.getByText(/3 runs/)).toBeInTheDocument();
  });

  it("links Open workspace to the team's exact name, not a slugified version", async () => {
    await renderPopulated();

    const rows = screen.getAllByRole("listitem");
    const link = within(rows[0]).getByRole("link", { name: "Open workspace" });
    expect(link).toHaveAttribute("href", "/teams/Article%20Team");
  });

  it("renames a team and reflects the new name without a full reload", async () => {
    const user = userEvent.setup();
    await renderPopulated();
    queue.queueRename(200, { ...articleTeam, name: "Renamed Team" });

    const rows = screen.getAllByRole("listitem");
    await user.click(within(rows[0]).getByRole("button", { name: "Rename" }));
    const input = within(rows[0]).getByRole("textbox");
    await user.clear(input);
    await user.type(input, "Renamed Team");
    await user.click(within(rows[0]).getByRole("button", { name: "Save" }));

    await waitFor(() => expect(screen.getByText("Renamed Team")).toBeInTheDocument());
    expect(screen.queryByText("Article Team")).toBeNull();
  });

  it("shows a server-side rename rejection inline instead of applying it", async () => {
    const user = userEvent.setup();
    await renderPopulated();
    queue.queueRename(409, {
      error: { code: "output_exists", message: "Team name 'Research Team' already exists (case-insensitive)." },
    });

    const rows = screen.getAllByRole("listitem");
    await user.click(within(rows[0]).getByRole("button", { name: "Rename" }));
    const input = within(rows[0]).getByRole("textbox");
    await user.clear(input);
    await user.type(input, "Research Team");
    await user.click(within(rows[0]).getByRole("button", { name: "Save" }));

    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toMatch(/already exists/);
    // Nothing was applied: the row stays in edit mode with the rejected
    // draft still showing (so the user can see and fix it), and the other
    // row's real name is untouched.
    expect(within(rows[0]).getByRole("textbox")).toHaveValue("Research Team");
    expect(screen.getByText("Research Team", { selector: '[data-slot="my-teams-row-name"]' })).toBeInTheDocument();
  });

  it("deletes a team only after the confirmation dialog is confirmed", async () => {
    const user = userEvent.setup();
    await renderPopulated();

    const rows = screen.getAllByRole("listitem");
    await user.click(within(rows[0]).getByRole("button", { name: "Delete" }));

    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(/Article Team/)).toBeInTheDocument();

    await user.click(within(dialog).getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(queue.requests.some((r) => r.url.startsWith("/api/teams/delete"))).toBe(false);

    await user.click(within(rows[0]).getByRole("button", { name: "Delete" }));
    queue.queueDelete(200, { message: "deleted" });
    await user.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Delete" }));

    await waitFor(() => expect(screen.queryByText("Article Team")).toBeNull());
    expect(screen.getByText("Research Team")).toBeInTheDocument();
  });

  it("keeps the team and the dialog open when delete fails, showing why", async () => {
    const user = userEvent.setup();
    await renderPopulated();
    queue.queueDelete(500, { error: { code: "internal_error", message: "boom" } });

    const rows = screen.getAllByRole("listitem");
    await user.click(within(rows[0]).getByRole("button", { name: "Delete" }));
    const dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: "Delete" }));

    await waitFor(() => expect(within(dialog).getByRole("alert")).toBeInTheDocument());
    expect(screen.getByText("Article Team")).toBeInTheDocument();
  });
});
