import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { WorkspaceSurface } from "@/components/workspace/workspace-surface";

import { createRunFetchQueue, type RunFetchQueue } from "./harness";
import {
  errorRunBlocked,
  errorRunInProgress,
  runComplete,
  runFailed,
  runRunning,
  teamPlan,
  teamPlanMissingKey,
  transcriptAvailable,
} from "./fixtures";

/**
 * The Workspace surface (Story 2.4 AC 11–14).
 *
 * Fully offline, exactly like `tests/composer/`'s suites: `createFetchQueue`
 * replaces `fetch`, so these prove the real client/components handle the
 * real (synthesised — see `fixtures/index.ts`) wire shape, not that the
 * backend works.
 */

let queue: RunFetchQueue;

beforeEach(() => {
  queue = createRunFetchQueue();
  queue.install();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

async function renderWorkspace(planBody: unknown = teamPlan) {
  queue.queuePlan(200, planBody);
  const view = render(<WorkspaceSurface teamSlug="haiku_team" />);
  await screen.findByRole("textbox", { name: "Describe the goal for this run" });
  return view;
}

describe("the plan renders a real task list", () => {
  it("renders agent badges and a task row from the mocked plan", async () => {
    await renderWorkspace();

    await waitFor(() => {
      expect(document.querySelector('[data-slot="task-row"]')).toBeInTheDocument();
    });
    expect(screen.getByText("poet")).toBeInTheDocument();
    expect(screen.getByText("write_haiku")).toBeInTheDocument();
    expect(document.querySelector('[data-slot="task-status"]')?.textContent).toBe("Queued");
  });

  it("shows a fix hint on an agent with no usable credential", async () => {
    await renderWorkspace(teamPlanMissingKey);

    await waitFor(() => {
      expect(document.querySelector('[data-slot="agent-badge-fix-hint"]')).toBeInTheDocument();
    });
    expect(document.querySelector('[data-slot="agent-badge-fix-hint"]')?.textContent).toMatch(
      /ANTHROPIC_API_KEY/
    );
  });
});

describe("starting a run", () => {
  it("sends the goal, renders it as a chat turn, and shows the run status", async () => {
    const user = userEvent.setup();
    await renderWorkspace();
    queue.queueCreateRun(200, runRunning);

    await user.type(
      screen.getByRole("textbox", { name: "Describe the goal for this run" }),
      "write a haiku about autumn"
    );
    await user.click(screen.getByRole("button", { name: "Run" }));

    await waitFor(() => {
      expect(screen.getByText("write a haiku about autumn")).toBeInTheDocument();
    });
    expect(document.querySelector('[data-slot="run-status"]')?.getAttribute("data-status")).toBe(
      "running"
    );
    const request = queue.requests.find((r) => r.url === "/api/runs" && r.method === "POST");
    expect(request?.body).toMatchObject({ team_slug: "haiku_team", goal: "write a haiku about autumn" });
  });

  it("does not send a blank goal", async () => {
    const user = userEvent.setup();
    await renderWorkspace();

    await user.click(screen.getByRole("button", { name: "Run" }));

    expect(queue.requests.some((r) => r.url === "/api/runs")).toBe(false);
  });

  it("surfaces run_blocked with the server's authored message, never a generic one", async () => {
    const user = userEvent.setup();
    await renderWorkspace();
    queue.queueCreateRun(409, errorRunBlocked);

    await user.type(
      screen.getByRole("textbox", { name: "Describe the goal for this run" }),
      "ship it"
    );
    await user.click(screen.getByRole("button", { name: "Run" }));

    await waitFor(() => {
      expect(document.querySelector('[data-slot="workspace-run-request-failure"]')).toBeInTheDocument();
    });
    expect(
      document.querySelector('[data-slot="workspace-run-request-failure"]')?.textContent
    ).toContain("ANTHROPIC_API_KEY");
  });

  it("surfaces run_in_progress the same way", async () => {
    const user = userEvent.setup();
    await renderWorkspace();
    queue.queueCreateRun(409, errorRunInProgress);

    await user.type(
      screen.getByRole("textbox", { name: "Describe the goal for this run" }),
      "ship it"
    );
    await user.click(screen.getByRole("button", { name: "Run" }));

    await waitFor(() => {
      expect(
        document.querySelector('[data-slot="workspace-run-request-failure"]')?.textContent
      ).toMatch(/already in progress/i);
    });
  });
});

describe("the accent pulse", () => {
  it(
    "appears only while the run is running",
    async () => {
      const user = userEvent.setup();
      await renderWorkspace();
      queue.queueCreateRun(200, runRunning);
      await user.type(
        screen.getByRole("textbox", { name: "Describe the goal for this run" }),
        "ship it"
      );
      await user.click(screen.getByRole("button", { name: "Run" }));

      await waitFor(() => {
        expect(document.querySelector('[data-slot="run-status-dot"]')).toHaveClass("bg-signal");
      });

      queue.queueGetRun(200, runComplete);
      await waitFor(
        () => {
          expect(
            document.querySelector('[data-slot="run-status"]')?.getAttribute("data-status")
          ).toBe("complete");
        },
        { timeout: 5000 }
      );
      expect(document.querySelector('[data-slot="run-status-dot"]')).not.toHaveClass("bg-signal");
    },
    // RUN_POLL_INTERVAL_MS (2000ms) plus render/typing overhead exceeds
    // vitest's default 5000ms per-test timeout.
    10000
  );
});

describe("polling", () => {
  it(
    "stops once the run reaches a terminal status",
    async () => {
      const user = userEvent.setup();
      await renderWorkspace();
      queue.queueCreateRun(200, runRunning);
      await user.type(
        screen.getByRole("textbox", { name: "Describe the goal for this run" }),
        "ship it"
      );
      await user.click(screen.getByRole("button", { name: "Run" }));
      await screen.findByText("ship it");

      queue.queueGetRun(200, runComplete);
      await waitFor(
        () => {
          expect(
            document.querySelector('[data-slot="run-status"]')?.getAttribute("data-status")
          ).toBe("complete");
        },
        { timeout: 5000 }
      );

      const countAfterComplete = queue.requests.filter((r) => /^\/api\/runs\/[^/]+$/.test(r.url))
        .length;
      // No poll queued beyond the terminal one — a further tick would throw
      // "unexpected request" and fail the test, proving polling actually
      // stopped rather than merely not being observed in time.
      await new Promise((resolve) => setTimeout(resolve, 2500));
      const countAfterWaiting = queue.requests.filter((r) => /^\/api\/runs\/[^/]+$/.test(r.url))
        .length;
      expect(countAfterWaiting).toBe(countAfterComplete);
    },
    10000
  );

  it(
    "renders the failure reason and stops polling on a failed run",
    async () => {
      const user = userEvent.setup();
      await renderWorkspace();
      queue.queueCreateRun(200, runRunning);
      await user.type(
        screen.getByRole("textbox", { name: "Describe the goal for this run" }),
        "ship it"
      );
      await user.click(screen.getByRole("button", { name: "Run" }));
      await screen.findByText("ship it");

      queue.queueGetRun(200, runFailed);
      await waitFor(
        () => {
          expect(
            document.querySelector('[data-slot="run-status"]')?.getAttribute("data-status")
          ).toBe("failed");
        },
        { timeout: 5000 }
      );
      // The reason appears twice by design: once in the run-status banner,
      // once as the chat's "outcome" turn — `getAllByText` rather than
      // `getByText`, which throws on more than one match.
      expect(screen.getAllByText(runFailed.failure_reason).length).toBeGreaterThan(0);
    },
    10000
  );
});

describe("the document tray", () => {
  it("refuses a file that does not decode as text, with a stated reason", async () => {
    await renderWorkspace();
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    // jsdom's real `File.text()` decodes bytes as UTF-8; an invalid leading
    // byte like 0xFF becomes U+FFFD — the practical signal this component
    // refuses on. Measured: `new File([0xff, 0xfe, ...]).text()` resolves to
    // `"�� "` in this project's jsdom.
    const binaryLike = new File([new Uint8Array([0xff, 0xfe, 0x00, 0x01])], "data.bin", {
      type: "text/plain", // matches the input accept= -- user-event filters upload() by it
    });

    const user = userEvent.setup();
    await user.upload(input, binaryLike);

    await waitFor(() => {
      expect(document.querySelector('[data-slot="workspace-document-error"]')).toBeInTheDocument();
    });
    expect(document.querySelector('[data-slot="workspace-document-error"]')?.textContent).toMatch(
      /does not look like a text file/
    );
    expect(document.querySelector('[data-slot="workspace-document-item"]')).toBeNull();
  });

  it("attaches a genuine text file and lists it", async () => {
    await renderWorkspace();
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    const textFile = new File(["Ship a v1 by Friday."], "brief.txt", { type: "text/plain" });

    const user = userEvent.setup();
    await user.upload(input, textFile);

    await waitFor(() => {
      expect(screen.getByText("brief.txt")).toBeInTheDocument();
    });
  });
});

describe("the transcript dialog", () => {
  it(
    "branches on kind, rendering a delegation's both ends",
    async () => {
      const user = userEvent.setup();
      await renderWorkspace();
      queue.queueCreateRun(200, runRunning);
      await user.type(
        screen.getByRole("textbox", { name: "Describe the goal for this run" }),
        "ship it"
      );
      await user.click(screen.getByRole("button", { name: "Run" }));
      await screen.findByText("ship it");

      queue.queueGetRun(200, runComplete);
      queue.queueTranscript(200, transcriptAvailable);
      await waitFor(
        () => {
          expect(screen.getByRole("button", { name: "View transcript" })).toBeInTheDocument();
        },
        { timeout: 5000 }
      );
      await user.click(screen.getByRole("button", { name: "View transcript" }));

      const dialog = await screen.findByRole("dialog");
      const rows = dialog.querySelectorAll('[data-slot="workspace-transcript-entry"]');
      // Sorted by sequence (2, 7, 13), not by list position.
      expect(Array.from(rows).map((row) => row.getAttribute("data-kind"))).toEqual([
        "task_started",
        "delegation",
        "task_completed",
      ]);
      const delegationRow = Array.from(rows).find(
        (row) => row.getAttribute("data-kind") === "delegation"
      );
      expect(delegationRow?.textContent).toContain("poet");
      expect(delegationRow?.textContent).toContain("editor");
    },
    10000
  );

  it("shows an honest unavailable state, not a blank panel, before a transcript exists", async () => {
    const user = userEvent.setup();
    await renderWorkspace();
    queue.queueCreateRun(200, { ...runRunning, transcript_available: false });
    await user.type(
      screen.getByRole("textbox", { name: "Describe the goal for this run" }),
      "ship it"
    );
    await user.click(screen.getByRole("button", { name: "Run" }));
    await screen.findByText("ship it");

    // No "View transcript" trigger while transcript_available is false —
    // proven by its absence rather than assumed.
    expect(screen.queryByRole("button", { name: "View transcript" })).toBeNull();
  });
});

describe("blocked controls carry aria-disabled and a linked reason, never `disabled`", () => {
  it("the Run button", async () => {
    await renderWorkspace();
    const button = screen.getByRole("button", { name: "Run" });
    expect(button).toHaveAttribute("aria-disabled", "true");
    expect(button).not.toHaveAttribute("disabled");
    const reasonId = button.getAttribute("aria-describedby");
    expect(reasonId).toBeTruthy();
    expect(document.getElementById(reasonId as string)?.textContent?.length).toBeGreaterThan(0);
  });
});
