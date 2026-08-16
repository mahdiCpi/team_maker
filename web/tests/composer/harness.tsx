import { screen, waitFor } from "@testing-library/react";
import type userEvent from "@testing-library/user-event";
// `expect` is imported rather than relied on as a global: `globals: true` makes
// it available at runtime, but `tsc --noEmit` does not see it without the types.
import { expect, vi } from "vitest";

import { keyCheckAllGood, keyStatusHasKeys, sessionCreate } from "./fixtures";

/**
 * Shared test harness for the Composer suites.
 *
 * ## Everything here is a stub, and none of it proves the API works
 *
 * `createFetchQueue` replaces the global `fetch` with a queue. The *bodies* the
 * tests feed it are verbatim captures from a live server (see
 * `fixtures/index.ts`), so these suites verify that the real client and the real
 * components handle the real wire format — but the transport is fake. CLAUDE.md
 * forbids reporting a mocked integration as proof of the real one.
 *
 * The one genuine end-to-end run is `e2e-live-check.mjs`, which is manual.
 *
 * `vi.mock("next/navigation")` is **not** here: `vi.mock` is hoisted per test
 * file and cannot be shared from a module, so each suite that needs it declares
 * its own three-line mock.
 */

export type QueuedResponse =
  | { kind: "reply"; status: number; body: unknown }
  /** Held open until `releaseHeld()`, so a pending turn can be observed. */
  | { kind: "held"; body: unknown }
  /** A rejected `fetch`, i.e. the process is not listening. */
  | { kind: "reject"; error: Error }
  /** A 2xx whose body fails to parse, i.e. a proxy's HTML error page. */
  | { kind: "unparseable"; status: number };

export type RecordedRequest = {
  url: string;
  method: string;
  body: unknown;
};

export type FetchQueue = {
  /**
   * Compose requests only. The Story 2.3 key routes are recorded in
   * `keyRequests` instead, so that assertions like `requests[1].url` — which
   * predate those routes and mean "the second *compose* call" — keep meaning it.
   */
  requests: RecordedRequest[];
  /** `/api/keys/*` requests, in order. */
  keyRequests: RecordedRequest[];
  queueResponse: (status: number, body: unknown) => void;
  queueHeld: (body: unknown) => void;
  queueReject: (error: Error) => void;
  queueUnparseable: (status: number) => void;
  /**
   * Override the default answer for the next `/api/keys/status` request.
   *
   * Separate from `queueKeyCheck` because the Composer re-reads the provider status
   * on every spec change, so a single FIFO queue across both routes made the number
   * of status reads part of every test's setup — and a test that guessed wrong got
   * the default silently.
   */
  queueKeyStatus: (status: number, body: unknown) => void;
  queueKeyStatusReject: (error: Error) => void;
  /** Override the default answer for the next `/api/keys/check/{id}` request. */
  queueKeyCheck: (status: number, body: unknown) => void;
  queueKeyCheckReject: (error: Error) => void;
  releaseHeld: () => void;
  install: () => void;
  buildRequests: () => RecordedRequest[];
};

/**
 * The Composer reads `/api/keys/status` on mount and `/api/keys/check/{id}` once a
 * spec exists (Story 2.3). Those are answered from a **captured** has-keys body by
 * default rather than from the main queue, for two reasons: every pre-2.3 suite
 * would otherwise fail with "unexpected request", and a test about chat or builds
 * should not have to know the key routes exist. Queue an explicit key response when
 * the key state is what is under test.
 */
export function createFetchQueue(): FetchQueue {
  const queue: QueuedResponse[] = [];
  const statusQueue: QueuedResponse[] = [];
  const checkQueue: QueuedResponse[] = [];
  const requests: RecordedRequest[] = [];
  const keyRequests: RecordedRequest[] = [];
  let held: (() => void)[] = [];

  const api: FetchQueue = {
    requests,
    keyRequests,
    queueResponse: (status, body) => queue.push({ kind: "reply", status, body }),
    queueHeld: (body) => queue.push({ kind: "held", body }),
    queueReject: (error) => queue.push({ kind: "reject", error }),
    queueUnparseable: (status) => queue.push({ kind: "unparseable", status }),
    queueKeyStatus: (status, body) => statusQueue.push({ kind: "reply", status, body }),
    queueKeyStatusReject: (error) => statusQueue.push({ kind: "reject", error }),
    queueKeyCheck: (status, body) => checkQueue.push({ kind: "reply", status, body }),
    queueKeyCheckReject: (error) => checkQueue.push({ kind: "reject", error }),
    releaseHeld: () => {
      held.forEach((resolve) => resolve());
      held = [];
    },
    buildRequests: () => requests.filter((r) => r.url.endsWith("/build")),
    install: () => {
      vi.stubGlobal(
        "fetch",
        vi.fn(async (url: string | URL, init?: RequestInit) => {
          const recorded: RecordedRequest = {
            url: String(url),
            method: init?.method ?? "GET",
            body: init?.body ? JSON.parse(String(init.body)) : undefined,
          };

          if (recorded.url.startsWith("/api/keys/")) {
            keyRequests.push(recorded);
            const isCheck = recorded.url.startsWith("/api/keys/check/");
            const queued = (isCheck ? checkQueue : statusQueue).shift();
            if (queued?.kind === "reject") throw queued.error;
            if (queued?.kind === "reply") {
              return {
                ok: queued.status < 400,
                status: queued.status,
                json: async () => queued.body,
              } as Response;
            }
            // Default: the captured body for whichever route was asked, so a suite
            // that does not care about keys renders the same "has keys, nothing
            // blocked" state a developer with working keys would see. Answering both
            // routes with the same body would make the check unparseable, which
            // happens to look the same from outside but for the wrong reason.
            return {
              ok: true,
              status: 200,
              json: async () => (isCheck ? keyCheckAllGood : keyStatusHasKeys),
            } as Response;
          }

          requests.push(recorded);

          const next = queue.shift();
          // Loud on purpose: a silent empty response would make a component
          // that stopped calling the API look like a passing test.
          if (!next) throw new Error(`unexpected request to ${url}`);

          if (next.kind === "reject") throw next.error;
          if (next.kind === "unparseable") {
            return {
              ok: next.status < 400,
              status: next.status,
              json: async () => {
                throw new SyntaxError("Unexpected token < in JSON at position 0");
              },
            } as unknown as Response;
          }
          if (next.kind === "held") {
            await new Promise<void>((resolve) => held.push(resolve));
            return { ok: true, status: 200, json: async () => next.body } as Response;
          }
          return {
            ok: next.status < 400,
            status: next.status,
            json: async () => next.body,
          } as Response;
        })
      );
    },
  };

  return api;
}

type User = ReturnType<typeof userEvent.setup>;

export function box() {
  return screen.getByRole("textbox", { name: "Describe your team" });
}

export function transcript() {
  return screen.getByRole("log", { name: "Conversation" });
}

export function failureAlert() {
  return document.querySelector('[data-slot="composer-failure"]') as HTMLElement | null;
}

export function buildPanel() {
  return document.querySelector('[data-slot="build-result"]') as HTMLElement | null;
}

/** Drive one successful first turn against the captured 201, and wait for it. */
export async function completeFirstTurn(
  user: User,
  queue: FetchQueue,
  intent = "research and write"
) {
  queue.queueResponse(201, sessionCreate);
  await user.type(box(), intent);
  await user.click(screen.getByRole("button", { name: "Send" }));
  await waitFor(() =>
    expect(screen.getByRole("button", { name: "Run it now" })).toBeInTheDocument()
  );
}

/** Reach a spec, turn review on, and open the editor. */
export async function openSpecEditor(user: User, queue: FetchQueue) {
  await completeFirstTurn(user, queue);
  await user.click(screen.getByRole("switch", { name: "Review before build" }));
  await user.click(screen.getByRole("button", { name: "Build team" }));
  await screen.findByRole("textbox", { name: "Role 1 name" });
}
