import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ComposerSurface } from "@/components/composer/composer-surface";
import { FIRST_TURN_PLACEHOLDER } from "@/components/composer/composer-input";

import { messageTurn2, sessionCreate } from "./fixtures";
import { box, completeFirstTurn, createFetchQueue, transcript } from "./harness";

/**
 * AC 1 and AC 2 — the surface is a conversation, and a turn in flight stays
 * usable.
 *
 * `fetch` is stubbed (see `harness.tsx`); the bodies are live captures. This is
 * a mocked integration, not proof the API works.
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

function messages(container: HTMLElement) {
  return container.querySelectorAll('[data-slot="composer-message"]');
}

describe("AC 1 — the initial state", () => {
  it("heads the page `Describe your team.` with the mockup's placeholder", () => {
    const { container } = render(<ComposerSurface />);
    expect(
      container.querySelector('[data-slot="empty-title"]')?.textContent
    ).toBe("Describe your team.");
    expect(box()).toHaveAttribute("placeholder", FIRST_TURN_PLACEHOLDER);
  });

  it("offers no build controls before there is anything to build", () => {
    render(<ComposerSurface />);
    expect(
      screen.queryByRole("button", { name: "Run it now" })
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Build team" })
    ).not.toBeInTheDocument();
  });
});

describe("AC 1 — the first turn", () => {
  it("posts the intent to POST /api/compose/sessions", async () => {
    const user = userEvent.setup();
    render(<ComposerSurface />);
    await completeFirstTurn(user, queue);

    expect(queue.requests).toHaveLength(1);
    expect(queue.requests[0]).toMatchObject({
      url: "/api/compose/sessions",
      method: "POST",
      body: { intent: "research and write" },
    });
  });

  it("appends one user message and one assistant message", async () => {
    const user = userEvent.setup();
    const { container } = render(<ComposerSurface />);
    await completeFirstTurn(user, queue);

    expect(messages(container)).toHaveLength(2);
    expect(messages(container)[0].getAttribute("data-author")).toBe("user");
    expect(messages(container)[1].getAttribute("data-author")).toBe("assistant");
    expect(within(transcript()).getByText("research and write")).toBeInTheDocument();
  });

  it("labels the turns `You` and `team_maker`, left-aligned and avatar-free", async () => {
    const user = userEvent.setup();
    const { container } = render(<ComposerSurface />);
    await completeFirstTurn(user, queue);

    expect(within(transcript()).getByText("You")).toBeInTheDocument();
    expect(within(transcript()).getByText("team_maker")).toBeInTheDocument();

    const bubbles = container.querySelectorAll('[data-slot="composer-bubble"]');
    // Non-empty asserted before looping: `for (const x of [])` passes trivially.
    expect(bubbles.length).toBeGreaterThan(0);
    for (const bubble of bubbles) {
      expect(bubble.className).not.toMatch(/ml-auto|justify-end|self-end/);
    }
    expect(container.querySelector("img")).toBeNull();
  });

  it("names the roles in pipeline order and asks exactly one follow-up", async () => {
    const user = userEvent.setup();
    const { container } = render(<ComposerSurface />);
    await completeFirstTurn(user, queue);

    const text = messages(container)[1].textContent ?? "";
    expect(text).toContain("researcher");
    expect(text.indexOf("researcher")).toBeLessThan(text.indexOf("writer"));
    expect(text.indexOf("writer")).toBeLessThan(text.indexOf("critic"));
    // One targeted question, not a checklist (`EXPERIENCE.md:184`).
    expect((text.match(/\?/g) ?? []).length).toBe(1);
  });

  it("clears the input after sending", async () => {
    const user = userEvent.setup();
    render(<ComposerSurface />);
    await completeFirstTurn(user, queue);
    expect(box()).toHaveValue("");
  });
});

describe("AC 1 — multi-turn", () => {
  it("sends the second turn to the messages route and appends both messages", async () => {
    const user = userEvent.setup();
    const { container } = render(<ComposerSurface />);
    await completeFirstTurn(user, queue);

    queue.queueResponse(200, messageTurn2);
    await user.type(box(), "add a fact-checker");
    await user.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() => expect(messages(container)).toHaveLength(4));
    expect(queue.requests[1].url).toMatch(/\/messages$/);
    expect(queue.requests[1].body).toEqual({ message: "add a fact-checker" });
    expect(within(transcript()).getByText(/fact_checker/)).toBeInTheDocument();
  });

  it("re-proposes in the refinement's pipeline order, not declaration order", async () => {
    const user = userEvent.setup();
    const { container } = render(<ComposerSurface />);
    await completeFirstTurn(user, queue);

    queue.queueResponse(200, messageTurn2);
    await user.type(box(), "add a fact-checker");
    await user.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() => expect(messages(container)).toHaveLength(4));

    const reply = messages(container)[3].textContent ?? "";
    expect(reply.indexOf("writer")).toBeLessThan(reply.indexOf("fact_checker"));
    expect(reply.indexOf("fact_checker")).toBeLessThan(reply.indexOf("critic"));
  });

  it("keeps the same session for the second turn", async () => {
    const user = userEvent.setup();
    render(<ComposerSurface />);
    await completeFirstTurn(user, queue);

    queue.queueResponse(200, messageTurn2);
    await user.type(box(), "again");
    await user.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() => expect(queue.requests).toHaveLength(2));
    expect(queue.requests[1].url).toContain(
      `/api/compose/sessions/${(sessionCreate as { session_id: string }).session_id}/`
    );
  });
});

describe("AC 2 — a turn in flight", () => {
  it("shows a thinking indicator and never disables the input", async () => {
    const user = userEvent.setup();
    const { container } = render(<ComposerSurface />);

    queue.queueHeld(sessionCreate);
    await user.type(box(), "research and write");
    await user.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() =>
      expect(
        container.querySelector('[data-slot="composer-thinking"]')
      ).toBeInTheDocument()
    );
    expect(box()).not.toBeDisabled();

    // AC 2's whole point: the user can keep typing through a multi-second call.
    await user.type(box(), "meanwhile");
    expect(box()).toHaveValue("meanwhile");

    queue.releaseHeld();
    await waitFor(() =>
      expect(
        container.querySelector('[data-slot="composer-thinking"]')
      ).not.toBeInTheDocument()
    );
    // And what they typed during the turn is not discarded.
    expect(box()).toHaveValue("meanwhile");
  });

  it("survives a slow call rather than timing the pending state out", async () => {
    const user = userEvent.setup();
    const { container } = render(<ComposerSurface />);

    queue.queueHeld(sessionCreate);
    await user.type(box(), "slow one");
    await user.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() =>
      expect(
        container.querySelector('[data-slot="composer-thinking"]')
      ).toBeInTheDocument()
    );

    // Several macrotasks later the pending state is still there: nothing
    // self-cancels it. (A turn is 1-4 blocking LLM calls.)
    for (let i = 0; i < 25; i++) await Promise.resolve();
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(
      container.querySelector('[data-slot="composer-thinking"]')
    ).toBeInTheDocument();

    queue.releaseHeld();
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Run it now" })).toBeInTheDocument()
    );
  });

  it("reports no fake progress — no percentage and no token stream", async () => {
    const user = userEvent.setup();
    const { container } = render(<ComposerSurface />);

    queue.queueHeld(sessionCreate);
    await user.type(box(), "x");
    await user.click(screen.getByRole("button", { name: "Send" }));
    const indicator = await waitFor(() => {
      const node = container.querySelector('[data-slot="composer-thinking"]');
      expect(node).toBeInTheDocument();
      return node as HTMLElement;
    });

    // There is no progress callback anywhere in the core, so a percentage would
    // be invented.
    expect(indicator.textContent ?? "").not.toMatch(/\d+\s*%/);
    expect(container.querySelector("progress")).toBeNull();
    expect(container.querySelector('[role="progressbar"]')).toBeNull();
    queue.releaseHeld();
  });

  it("announces the turn politely and uses no Signal Teal token", async () => {
    const user = userEvent.setup();
    const { container } = render(<ComposerSurface />);
    await completeFirstTurn(user, queue);

    // A declared addition: no source specifies a live region for chat.
    expect(transcript()).toHaveAttribute("aria-live", "polite");
    // AC 7: the surface references the reserved token zero times.
    expect(container.innerHTML).not.toMatch(/signal/i);
  });
});
