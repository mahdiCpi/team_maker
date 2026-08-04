import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ComposerSurface } from "@/components/composer/composer-surface";
import { NavShortcuts } from "@/components/nav-shortcuts";

import { build, sessionCreate } from "./fixtures";

/**
 * AC 6 — the keyboard contract, and the chord collision it exists to prevent.
 *
 * **Mocked:** `fetch` (queue-driven stub) and `next/navigation`'s `useRouter`.
 * The router mock is copied from `web/tests/nav/shortcuts.test.tsx`, which is
 * where `NavShortcuts` is otherwise tested. Nothing here proves the API works.
 */

const pushMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
  usePathname: () => "/",
}));

let queue: { status: number; body: unknown }[] = [];
let requests: { url: string; method: string }[] = [];

function queueResponse(status: number, body: unknown) {
  queue.push({ status, body });
}

beforeEach(() => {
  queue = [];
  requests = [];
  pushMock.mockClear();
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string | URL, init?: RequestInit) => {
      requests.push({ url: String(url), method: init?.method ?? "GET" });
      const next = queue.shift();
      if (!next) throw new Error(`unexpected request to ${url}`);
      return {
        ok: next.status < 400,
        status: next.status,
        json: async () => next.body,
      } as Response;
    })
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

/**
 * Renders the Composer *alongside* `<NavShortcuts />`, because that component
 * lives in `app/layout.tsx:70` and not in the page — testing the page alone
 * would never exercise the collision this file is about.
 */
function renderSurface() {
  return render(
    <div>
      <NavShortcuts />
      <ComposerSurface />
    </div>
  );
}

function box() {
  return screen.getByRole("textbox", { name: "Describe your team" });
}

async function firstTurn(user: ReturnType<typeof userEvent.setup>) {
  queueResponse(201, sessionCreate);
  await user.type(box(), "research and write");
  await user.keyboard("{Enter}");
  await waitFor(() =>
    expect(screen.getByRole("button", { name: "Run it now" })).toBeInTheDocument()
  );
}

describe("AC 6 — the input is a real textarea", () => {
  it("is a <textarea>, which is what nav-shortcuts.tsx:11 actually guards", () => {
    renderSurface();
    // `nav-shortcuts.tsx` suppresses the `g` chord for INPUT/TEXTAREA/SELECT and
    // three exact contenteditable values, and nothing else. Any other editor
    // host and typing "grand total" navigates away mid-sentence.
    expect(box().tagName).toBe("TEXTAREA");
  });

  it("is never disabled, even mid-turn", () => {
    renderSurface();
    expect(box()).not.toBeDisabled();
    expect(box()).not.toHaveAttribute("readonly");
  });
});

describe("AC 6 — Enter and Shift+Enter", () => {
  it("sends on Enter", async () => {
    const user = userEvent.setup();
    renderSurface();
    queueResponse(201, sessionCreate);

    await user.type(box(), "research and write");
    await user.keyboard("{Enter}");

    await waitFor(() => expect(requests).toHaveLength(1));
    expect(requests[0].url).toBe("/api/compose/sessions");
    expect(box()).toHaveValue("");
  });

  it("inserts a newline on Shift+Enter and sends nothing", async () => {
    const user = userEvent.setup();
    renderSurface();

    await user.type(box(), "first line");
    await user.keyboard("{Shift>}{Enter}{/Shift}");
    await user.type(box(), "second line");

    expect(box()).toHaveValue("first line\nsecond line");
    // Counted, not "absent": zero requests is the assertion.
    expect(requests).toHaveLength(0);
  });

  it("does not send an empty or whitespace-only message", async () => {
    const user = userEvent.setup();
    renderSurface();

    await user.click(box());
    await user.keyboard("{Enter}");
    await user.type(box(), "   ");
    await user.keyboard("{Enter}");

    expect(requests).toHaveLength(0);
  });

  it("does not send while an IME is composing", async () => {
    renderSurface();
    const textarea = box() as HTMLTextAreaElement;
    textarea.value = "にほんご";

    // `isComposing` is only reachable by constructing the event: user-event
    // cannot model an IME candidate window.
    const event = new KeyboardEvent("keydown", {
      key: "Enter",
      bubbles: true,
      cancelable: true,
    });
    Object.defineProperty(event, "isComposing", { value: true });
    textarea.dispatchEvent(event);

    expect(requests).toHaveLength(0);
  });
});

describe("AC 6 — ⌘/Ctrl+Enter triggers Run it now", () => {
  it.each([
    ["Control", "{Control>}{Enter}{/Control}"],
    ["Meta", "{Meta>}{Enter}{/Meta}"],
  ])("builds on %s+Enter", async (_label, chord) => {
    const user = userEvent.setup();
    renderSurface();
    await firstTurn(user);

    queueResponse(200, build);
    await user.click(box());
    await user.keyboard(chord);

    await waitFor(() => expect(requests).toHaveLength(2));
    expect(requests[1].url).toMatch(/\/build$/);
    expect(requests[1].method).toBe("POST");
  });

  it("does not also send the message", async () => {
    const user = userEvent.setup();
    renderSurface();
    await firstTurn(user);

    queueResponse(200, build);
    await user.type(box(), "unsent text");
    await user.keyboard("{Control>}{Enter}{/Control}");

    await waitFor(() => expect(requests).toHaveLength(2));
    expect(requests.filter((r) => r.url.endsWith("/messages"))).toHaveLength(0);
    // The typed text survives; the chord was not a send.
    expect(box()).toHaveValue("unsent text");
  });

  it("fires nothing before the first proposal, when there is nothing to build", async () => {
    const user = userEvent.setup();
    renderSurface();
    await user.type(box(), "not sent yet");
    await user.keyboard("{Control>}{Enter}{/Control}");
    expect(requests).toHaveLength(0);
  });
});

describe("AC 6 — Esc exits the review editor", () => {
  it("closes the editor and leaves the conversation intact", async () => {
    const user = userEvent.setup();
    renderSurface();
    await firstTurn(user);

    await user.click(screen.getByRole("switch", { name: "Review before build" }));
    await user.click(screen.getByRole("button", { name: "Build team" }));
    await screen.findByRole("dialog");

    await user.keyboard("{Escape}");

    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    );
    // The transcript and the actions survive.
    expect(
      within(screen.getByRole("log", { name: "Conversation" })).getByText("You")
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Run it now" })
    ).toBeInTheDocument();
    expect(requests.filter((r) => r.url.endsWith("/build"))).toHaveLength(0);
  });
});

describe("AC 6 — the `g` chord must not fire while typing", () => {
  it("does not navigate for g,n typed into the composer, but DOES from the body", async () => {
    const user = userEvent.setup();
    renderSurface();

    // 1. Focused in the composer: the chord must be inert.
    await user.click(box());
    await user.keyboard("gn");
    expect(pushMock).toHaveBeenCalledTimes(0);
    // Proof the keystrokes really landed somewhere — otherwise a mock that
    // simply never fires would satisfy the assertion above.
    expect(box()).toHaveValue("gn");

    // 2. Same keys with focus on the body: the chord MUST fire exactly once.
    // Without this half, the test passes for a component that swallowed every
    // keystroke, or for a router mock wired to nothing.
    (box() as HTMLTextAreaElement).blur();
    document.body.focus();
    await user.keyboard("gn");
    expect(pushMock).toHaveBeenCalledTimes(1);
    expect(pushMock).toHaveBeenCalledWith("/");
  });

  it("does not navigate for g,t typed into the review editor's fields", async () => {
    const user = userEvent.setup();
    renderSurface();
    await firstTurn(user);

    await user.click(screen.getByRole("switch", { name: "Review before build" }));
    await user.click(screen.getByRole("button", { name: "Build team" }));
    await screen.findByRole("dialog");

    await user.click(screen.getByRole("textbox", { name: "Role 1 name" }));
    await user.keyboard("gt");
    expect(pushMock).toHaveBeenCalledTimes(0);
  });

  it("leaves ⌘/Ctrl+B alone — it is shadcn's sidebar toggle", async () => {
    const user = userEvent.setup();
    renderSurface();
    await user.click(box());
    await user.keyboard("{Control>}b{/Control}");
    expect(pushMock).not.toHaveBeenCalled();
    expect(requests).toHaveLength(0);
  });
});
