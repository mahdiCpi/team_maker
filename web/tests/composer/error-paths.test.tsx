import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ComposerSurface } from "@/components/composer/composer-surface";

import {
  build,
  errorAuthoringUnavailable,
  errorOutputExists,
  errorSessionNotFound,
  sessionCreate,
} from "./fixtures";
import { box, buildPanel, createFetchQueue, failureAlert, transcript } from "./harness";

/**
 * AC 8 — every error code renders a usable state.
 *
 * **Mocked:** `fetch` and `next/navigation`. Nothing here proves the API works.
 *
 * **Captured vs synthesised.** `session_not_found`, `authoring_unavailable` and
 * `output_exists` below are the **verbatim recorded bodies** from a live server.
 * `turn_cap_reached`, `compose_failed`, `build_failed` and `session_busy` are
 * **synthesised inline from the server's own copy** in `api/sessions.py:206-216`,
 * `api/routers/compose.py:218-223` and `api/build.py:39-42`, because none of the
 * four could be provoked without 20 real LLM turns, an induced internal fault or
 * a race. The envelope *shape* they share is what the captures prove
 * (`api/errors.py:101-105`). See `fixtures/index.ts`.
 */

const pushMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
  usePathname: () => "/",
}));

let queue: ReturnType<typeof createFetchQueue>;

beforeEach(() => {
  queue = createFetchQueue();
  queue.install();
  pushMock.mockClear();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function queueResponse(status: number, body: unknown) {
  queue.queueResponse(status, body);
}

function envelope(code: string, message: string) {
  return { error: { code, message } };
}

/** Non-null assertion: every caller has already waited for the alert. */
function alertNode(): HTMLElement {
  return failureAlert() as HTMLElement;
}

/** Submit the first intent and let it fail with the queued response. */
async function failFirstTurn(
  user: ReturnType<typeof userEvent.setup>,
  status: number,
  body: unknown
) {
  render(<ComposerSurface />);
  queueResponse(status, body);
  await user.type(box(), "research and write");
  await user.click(screen.getByRole("button", { name: "Send" }));
  await waitFor(() => expect(alertNode()).toBeInTheDocument());
}

/** Reach a good spec, then fail the build with the queued response. */
async function failBuild(
  user: ReturnType<typeof userEvent.setup>,
  status: number,
  body: unknown
) {
  render(<ComposerSurface />);
  queueResponse(201, sessionCreate);
  await user.type(box(), "research and write");
  await user.click(screen.getByRole("button", { name: "Send" }));
  await waitFor(() =>
    expect(screen.getByRole("button", { name: "Run it now" })).toBeInTheDocument()
  );
  queueResponse(status, body);
  await user.click(screen.getByRole("button", { name: "Run it now" }));
  await waitFor(() => expect(alertNode()).toBeInTheDocument());
}

// ---------------------------------------------------------------------------

describe("AC 8 — the eight server codes each render a usable state", () => {
  const CASES: {
    code: string;
    status: number;
    body: unknown;
    provenance: "captured" | "synthesised";
    expect: RegExp;
  }[] = [
    {
      code: "session_not_found",
      status: 404,
      body: errorSessionNotFound,
      provenance: "captured",
      expect: /no longer available/i,
    },
    {
      code: "authoring_unavailable",
      status: 503,
      body: errorAuthoringUnavailable,
      provenance: "captured",
      expect: /ollama/i,
    },
    {
      code: "output_exists",
      status: 409,
      body: errorOutputExists,
      provenance: "captured",
      // The client replaces the server's "choose a different output path" —
      // a remedy the hard constraint forbids this UI from offering.
      expect: /already exists/i,
    },
    {
      code: "turn_cap_reached",
      status: 409,
      body: envelope(
        "turn_cap_reached",
        "This conversation has reached its limit of 20 turns. Build the team as it stands, or start a new conversation."
      ),
      provenance: "synthesised",
      expect: /limit of 20 turns/i,
    },
    {
      code: "compose_failed",
      status: 502,
      body: envelope(
        "compose_failed",
        "The team specification could not be created. Retry once; if the problem repeats, stop and report it."
      ),
      provenance: "synthesised",
      expect: /could not be created/i,
    },
    {
      code: "build_failed",
      status: 500,
      body: envelope(
        "build_failed",
        "The team package could not be built. The error has been logged on the server."
      ),
      provenance: "synthesised",
      expect: /could not be built/i,
    },
    {
      code: "session_busy",
      status: 409,
      body: envelope(
        "session_busy",
        "This conversation is still working on a previous request. Try again in a moment."
      ),
      provenance: "synthesised",
      expect: /try again in a moment/i,
    },
    {
      code: "spec_invalid",
      status: 422,
      body: {
        error: {
          code: "spec_invalid",
          message:
            "The team specification could not be completed from that description. Try rephrasing it, or simplifying the requirements.",
          fields: [{ path: "desired_roles", message: "Add at least one role." }],
        },
      },
      // The envelope is shaped inline here, but `spec_invalid` itself was
      // captured live (`fixtures/error-spec-invalid.json`) and is used as a
      // capture in `build.test.tsx`. Labelling it synthesised made five test
      // names disagree with the four this file's header declares.
      provenance: "captured",
      expect: /could not be completed/i,
    },
  ];

  it.each(CASES)(
    "$code ($provenance) shows plain-language copy and no raw JSON",
    async ({ status, body, code, expect: pattern }) => {
      const user = userEvent.setup();
      await failFirstTurn(user, status, body);

      const alert = alertNode();
      expect(alert).toHaveAttribute("data-code", code);
      expect(alert.textContent ?? "").toMatch(pattern);

      // No envelope, no serialised object, no key/value dump.
      const text = alert.textContent ?? "";
      expect(text).not.toMatch(/[{}]/);
      expect(text).not.toMatch(/"code"|"message"|"error"/);
      // No stack trace or server file path.
      expect(text).not.toMatch(/Traceback|File "|\.py:\d+/);
      // The transcript survived: the user's words are still there.
      expect(
        within(transcript()).getByText(
          "research and write"
        )
      ).toBeInTheDocument();
      // And the input is still usable.
      expect(box()).not.toBeDisabled();
    }
  );

  it("announces the failure rather than only drawing it", async () => {
    const user = userEvent.setup();
    await failFirstTurn(user, 502, envelope("compose_failed", "It broke."));
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });
});

describe("AC 8 — session_not_found is recoverable, not a white screen", () => {
  it("offers a way to start a new conversation and keeps the transcript", async () => {
    const user = userEvent.setup();
    await failBuild(user, 404, errorSessionNotFound);

    const restart = screen.getByRole("button", {
      name: "Start a new conversation",
    });
    expect(restart).toBeInTheDocument();
    // Not a blank page: the conversation is still on screen.
    expect(
      within(transcript()).getByText(
        "research and write"
      )
    ).toBeInTheDocument();

    await user.click(restart);
    // Back to the first-turn state, ready to compose again.
    await waitFor(() =>
      expect(screen.getByText("Describe your team.")).toBeInTheDocument()
    );
    expect(alertNode()).toBeNull();

    queueResponse(201, sessionCreate);
    await user.type(box(), "starting over");
    await user.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Run it now" })
      ).toBeInTheDocument()
    );
    // A fresh session, so the retry is a create and not a doomed message.
    expect(queue.requests.at(-1)?.url).toBe("/api/compose/sessions");
  });

  it("blocks the build with a stated reason while the session is gone", async () => {
    const user = userEvent.setup();
    await failBuild(user, 404, errorSessionNotFound);
    expect(screen.getByRole("button", { name: "Run it now" })).toHaveAttribute(
      "aria-disabled",
      "true"
    );
    expect(
      document.querySelector('[data-slot="composer-actions-reason"]')?.textContent
    ).toMatch(/no longer available/i);
  });
});

describe("AC 8 — a failed turn allows a retry", () => {
  it("keeps the last good spec and succeeds on the second attempt", async () => {
    const user = userEvent.setup();
    render(<ComposerSurface />);

    queueResponse(201, sessionCreate);
    await user.type(box(), "research and write");
    await user.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Run it now" })
      ).toBeInTheDocument()
    );

    // A refinement that fails. `session.current` is untouched server-side.
    queueResponse(502, envelope("compose_failed", "Could not be created."));
    await user.type(box(), "make it worse");
    await user.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() => expect(alertNode()).toBeInTheDocument());

    // Run it now is available again — the spec was never lost.
    expect(screen.getByRole("button", { name: "Run it now" })).not.toHaveAttribute(
      "aria-disabled",
      "true"
    );

    queueResponse(200, build);
    await user.click(screen.getByRole("button", { name: "Run it now" }));
    await waitFor(() => expect(buildPanel()).toBeInTheDocument());
    // The stale error is gone once the next action succeeds.
    expect(alertNode()).toBeNull();
  });

  it("can be dismissed without losing the conversation", async () => {
    const user = userEvent.setup();
    await failBuild(user, 409, errorOutputExists);
    await user.click(screen.getByRole("button", { name: "Dismiss" }));
    await waitFor(() => expect(alertNode()).toBeNull());
    expect(
      within(transcript()).getByText(
        "research and write"
      )
    ).toBeInTheDocument();
  });
});

describe("AC 8 — authoring_unavailable never offers to take a key", () => {
  it("shows the server's guidance and no key input anywhere", async () => {
    const user = userEvent.setup();
    await failFirstTurn(user, 503, errorAuthoringUnavailable);

    expect(alertNode().textContent).toMatch(/ollama/);
    // `EXPERIENCE.md:103` bans key entry in the UI outright.
    const inputs = document.querySelectorAll("input, textarea");
    for (const field of inputs) {
      const label = `${field.getAttribute("aria-label") ?? ""} ${
        field.getAttribute("placeholder") ?? ""
      } ${field.getAttribute("name") ?? ""}`;
      expect(label).not.toMatch(/key|token|secret|credential/i);
      expect(field.getAttribute("type")).not.toBe("password");
    }
  });

  it("renders the missing-hosted-key variant without inviting one", async () => {
    // The other `authoring_unavailable` shape (`api/deps.py:119-124`): it names
    // the Key Config entry, which is guidance, not an invitation.
    const user = userEvent.setup();
    await failFirstTurn(
      user,
      503,
      envelope(
        "authoring_unavailable",
        "No usable credential for the authoring provider 'openai'. Add an 'OPENAI_API_KEY' entry to your Key Config file, or choose a different authoring provider when starting the conversation."
      )
    );
    expect(alertNode().textContent).toMatch(/Key Config/);
    expect(document.querySelector('input[type="password"]')).toBeNull();
  });
});

describe("AC 8 — nothing internal ever reaches the screen", () => {
  it("suppresses a server-sent stack trace, proven against one that contains it", async () => {
    // Guard validated against a real violation (Dev Notes rule 1): this payload
    // genuinely carries a traceback and an absolute path.
    const user = userEvent.setup();
    await failFirstTurn(
      user,
      500,
      envelope(
        "build_failed",
        'Traceback (most recent call last):\n  File "C:\\srv\\api\\build.py", line 30, in run_build\n    raise FileExistsError(secret_path)\nFileExistsError: C:\\srv\\secrets\\key.txt'
      )
    );

    const text = document.body.textContent ?? "";
    expect(text).not.toMatch(/Traceback/);
    expect(text).not.toMatch(/build\.py/);
    expect(text).not.toMatch(/secrets/);
    // Replaced by authored copy, not by nothing at all.
    expect(alertNode().textContent).toMatch(/could not be built/i);
  });

  it("degrades an unknown code rather than rendering an empty alert", async () => {
    const user = userEvent.setup();
    await failFirstTurn(
      user,
      418,
      envelope("a_code_from_the_future", "Something specific happened.")
    );
    expect(alertNode()).toHaveAttribute("data-code", "unknown_error");
    expect(alertNode().textContent).toMatch(/Something specific happened/);
  });

  it("degrades a proxy's HTML error page into authored copy", async () => {
    const user = userEvent.setup();
    render(<ComposerSurface />);
    queue.queueUnparseable(502);
    await user.type(box(), "research and write");
    await user.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() => expect(alertNode()).toBeInTheDocument());
    expect(alertNode()).toHaveAttribute("data-code", "unreadable_response");
    expect(alertNode().textContent).not.toMatch(/SyntaxError|Unexpected token/);
    expect(alertNode().textContent?.trim().length).toBeGreaterThan(0);
  });

  it("says the API is unreachable when the process is down", async () => {
    const user = userEvent.setup();
    render(<ComposerSurface />);
    queue.queueReject(new TypeError("Failed to fetch"));
    await user.type(box(), "research and write");
    await user.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() => expect(alertNode()).toBeInTheDocument());
    expect(alertNode()).toHaveAttribute("data-code", "unreachable");
    expect(alertNode().textContent).toMatch(/Check that the API is running/i);
    expect(alertNode().textContent).not.toMatch(/Failed to fetch|TypeError/);
  });
});

describe("output_exists copy is replaced, not relayed", () => {
  it("drops the server's instruction to choose a different output path", async () => {
    const user = userEvent.setup();
    await failBuild(user, 409, errorOutputExists);

    const text = alertNode().textContent ?? "";
    // The captured server body really does say this — asserted below — and the
    // hard constraint (Story 2.0 AC 13) forbids this UI from offering any way to
    // change the path, so relaying the instruction sends the user hunting for a
    // control that must not exist.
    expect(JSON.stringify(errorOutputExists)).toMatch(
      /Choose a different output path/
    );
    expect(text).not.toMatch(/choose a different output path/i);
    // Replaced by authored copy that states the same fact and offers only a
    // remedy the UI can actually reach.
    expect(text).toMatch(/already exists/i);
    expect(text).toMatch(/start a new conversation/i);
  });
});

describe("fields[].message is leak-checked too", () => {
  it("suppresses a traceback smuggled through a field reason", async () => {
    // `api/errors.py` guarantees `message` is authored copy. It makes no such
    // guarantee for `fields[].message`, which Story 2.0's own review recorded as
    // pydantic-derived text carrying the offending input — so this was the one
    // part of the envelope reaching the screen unchecked.
    const user = userEvent.setup();
    await failFirstTurn(user, 422, {
      error: {
        code: "spec_invalid",
        message: "Those changes are not valid.",
        fields: [
          {
            path: "desired_roles.0.name",
            message:
              'Traceback (most recent call last):\n  File "C:\srv\api\request.py", line 88, in validate',
          },
        ],
      },
    });

    const text = document.body.textContent ?? "";
    expect(text).not.toMatch(/Traceback/);
    expect(text).not.toMatch(/request\.py/);
    // The path survives — the user still needs to know which row is wrong.
    expect(alertNode().textContent).toMatch(/desired_roles\.0\.name/);
    expect(alertNode().textContent).toMatch(/rejected by the server/i);
  });
});
