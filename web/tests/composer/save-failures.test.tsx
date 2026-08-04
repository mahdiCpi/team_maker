import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ComposerSurface } from "@/components/composer/composer-surface";
import { MAX_TEXT_LENGTH } from "@/lib/api-types";

import { errorSessionNotFound, errorSpecInvalid, messageTurn2 } from "./fixtures";
import { createFetchQueue, failureAlert, openSpecEditor } from "./harness";

/**
 * Save failures in the review editor — the path the first review found
 * completely unguarded.
 *
 * Nothing here existed before that review. The original suite covered only
 * `spec_invalid`, which was the one code the surface happened to handle; every
 * other code rendered its message *underneath* the modal backdrop, where it
 * could not be read, focused or dismissed, while the editor showed nothing at
 * all and `Save` looked inert.
 *
 * **Mocked:** `fetch` and `next/navigation` (see `harness.tsx`). Nothing here
 * proves the API works.
 */

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  usePathname: () => "/",
}));

let queue: ReturnType<typeof createFetchQueue>;

beforeEach(() => {
  queue = createFetchQueue();
  queue.install();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function editorFailure() {
  return document.querySelector(
    '[data-slot="spec-editor-failure"]'
  ) as HTMLElement | null;
}

function dialog() {
  return screen.getByRole("dialog");
}

/** Every non-`spec_invalid` code a save can realistically produce. */
const SILENT_BEFORE = [
  { code: "unreachable", queue: "reject" as const },
  { code: "timeout", queue: "abort" as const },
  { code: "unreadable_response", queue: "unparseable" as const },
  { code: "session_busy", queue: "envelope" as const, status: 409 },
  { code: "internal_error", queue: "envelope" as const, status: 500 },
];

describe("a save failure is visible INSIDE the modal, for every code", () => {
  it.each(SILENT_BEFORE)("$code surfaces in the dialog", async (testCase) => {
    const user = userEvent.setup();
    render(<ComposerSurface />);
    await openSpecEditor(user, queue);

    await user.type(screen.getByRole("textbox", { name: "Purpose" }), " tweak");

    if (testCase.queue === "reject") {
      queue.queueReject(new TypeError("Failed to fetch"));
    } else if (testCase.queue === "abort") {
      const abort = new Error("aborted");
      abort.name = "AbortError";
      queue.queueReject(abort);
    } else if (testCase.queue === "unparseable") {
      queue.queueUnparseable(502);
    } else {
      queue.queueResponse(testCase.status as number, {
        error: { code: testCase.code, message: "Something specific went wrong." },
      });
    }

    await user.click(screen.getByRole("button", { name: "Save" }));

    // Inside the dialog, with a code — not behind the backdrop.
    await waitFor(() => expect(editorFailure()).toBeInTheDocument());
    expect(editorFailure()).toHaveAttribute("data-code", testCase.code);
    expect(dialog().contains(editorFailure())).toBe(true);
    expect(editorFailure()?.textContent?.trim().length).toBeGreaterThan(0);
    // And not duplicated into the surface, where it would be invisible anyway.
    expect(failureAlert()).toBeNull();
  });

  it("session_not_found closes the editor so the recovery control is reachable", async () => {
    const user = userEvent.setup();
    render(<ComposerSurface />);
    await openSpecEditor(user, queue);

    await user.type(screen.getByRole("textbox", { name: "Purpose" }), " tweak");
    queue.queueResponse(404, errorSessionNotFound);
    await user.click(screen.getByRole("button", { name: "Save" }));

    // Held open, the only way out ("Start a new conversation") would sit outside
    // the modal's focus scope and under its backdrop.
    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    );
    expect(
      screen.getByRole("button", { name: "Start a new conversation" })
    ).toBeInTheDocument();
  });
});

describe("client-side bounds keep an over-long field out of that path entirely", () => {
  it("catches an over-long purpose before any request", async () => {
    const user = userEvent.setup();
    render(<ComposerSurface />);
    await openSpecEditor(user, queue);

    const purpose = screen.getByRole("textbox", { name: "Purpose" });
    await user.clear(purpose);
    // `paste` rather than `type`: 2,001 keystrokes is minutes of test time.
    await user.click(purpose);
    await user.paste("x".repeat(MAX_TEXT_LENGTH + 1));
    await user.click(screen.getByRole("button", { name: "Save" }));

    expect(
      await screen.findByText(
        new RegExp(`Use ${MAX_TEXT_LENGTH} characters or fewer`)
      )
    ).toBeInTheDocument();
    // Counted: only the opening turn was ever requested.
    expect(queue.requests).toHaveLength(1);
  });

  it("catches an over-long task description before any request", async () => {
    const user = userEvent.setup();
    render(<ComposerSurface />);
    await openSpecEditor(user, queue);

    const description = screen.getByRole("textbox", {
      name: "Task 1 description",
    });
    await user.clear(description);
    await user.click(description);
    await user.paste("x".repeat(MAX_TEXT_LENGTH + 1));
    await user.click(screen.getByRole("button", { name: "Save" }));

    expect(
      await screen.findByText(
        new RegExp(`Use ${MAX_TEXT_LENGTH} characters or fewer`)
      )
    ).toBeInTheDocument();
    expect(queue.requests).toHaveLength(1);
  });
});

describe("concurrency around a save", () => {
  it("a second Save click issues no second PUT", async () => {
    const user = userEvent.setup();
    render(<ComposerSurface />);
    await openSpecEditor(user, queue);

    await user.type(screen.getByRole("textbox", { name: "Purpose" }), " tweak");
    queue.queueHeld(messageTurn2);

    const save = screen.getByRole("button", { name: "Save" });
    await user.click(save);
    await waitFor(() => expect(save).toHaveAttribute("aria-disabled", "true"));
    // `aria-disabled` was decorative before: the handler ran anyway.
    await user.click(save);
    await user.click(save);

    const puts = queue.requests.filter((r) => r.method === "PUT");
    expect(puts).toHaveLength(1);

    queue.releaseHeld();
    await waitFor(() =>
      expect(screen.getByText(/what the server stored/)).toBeInTheDocument()
    );
  });

  it("locks the fields while saving, so no keystroke is silently discarded", async () => {
    const user = userEvent.setup();
    render(<ComposerSurface />);
    await openSpecEditor(user, queue);

    await user.type(screen.getByRole("textbox", { name: "Purpose" }), " tweak");
    queue.queueHeld(messageTurn2);
    await user.click(screen.getByRole("button", { name: "Save" }));

    // The response remounts the form against the server's spec, so anything
    // typed after the click would vanish without notice.
    await waitFor(() =>
      expect(
        document.querySelector('[data-slot="spec-editor-saving"]')
      ).toBeInTheDocument()
    );
    expect(screen.getByRole("textbox", { name: "Purpose" })).toHaveAttribute(
      "readonly"
    );
    expect(screen.getByRole("textbox", { name: "Role 1 name" })).toHaveAttribute(
      "readonly"
    );
    queue.releaseHeld();
  });

  it("a save that resolves after the editor closed does not reopen it", async () => {
    const user = userEvent.setup();
    render(<ComposerSurface />);
    await openSpecEditor(user, queue);

    await user.type(screen.getByRole("textbox", { name: "Purpose" }), " tweak");
    queue.queueHeld(messageTurn2);
    await user.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() =>
      expect(
        document.querySelector('[data-slot="spec-editor-saving"]')
      ).toBeInTheDocument()
    );

    await user.keyboard("{Escape}");
    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    );

    queue.releaseHeld();
    // The late result must be discarded. Reopening a dialog the user dismissed
    // was the visible half; the invisible half was that it also reset `pending`,
    // re-enabling both build controls while a build was still running.
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});

describe("server field reasons do not outlive the edit that caused them", () => {
  it("clears a 422's field reasons once the user edits again", async () => {
    const user = userEvent.setup();
    render(<ComposerSurface />);
    await openSpecEditor(user, queue);

    const roleName = screen.getByRole("textbox", { name: "Role 1 name" });
    await user.clear(roleName);
    await user.type(roleName, "renamed_role");
    for (const index of [1, 2, 3]) {
      await user.selectOptions(
        screen.getByRole("combobox", { name: `Task ${index} role` }),
        "renamed_role"
      );
    }
    queue.queueResponse(422, errorSpecInvalid);
    await user.click(screen.getByRole("button", { name: "Save" }));

    const reason = await screen.findByText(/is assigned to 'writer'/);
    expect(reason).toBeInTheDocument();

    // Editing anything invalidates the server's verdict; leaving it pinned to a
    // row the user has since fixed is a reason for a state that no longer exists.
    await user.type(screen.getByRole("textbox", { name: "Purpose" }), " again");
    await waitFor(() =>
      expect(screen.queryByText(/is assigned to 'writer'/)).toBeNull()
    );
    expect(editorFailure()).toBeNull();
  });
});
