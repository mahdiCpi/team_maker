import { vi } from "vitest";

/**
 * A minimal fetch queue for the starters routes, mirroring
 * `tests/my-teams/harness.tsx`'s `createTeamsFetchQueue` shape but scoped to
 * this surface (Story 3-1).
 *
 * Everything here is a STUB: no real API process. A passing test proves the
 * real client and the real components handle the real wire format, not that
 * the backend works.
 */

type Queued = { kind: "reply"; status: number; body: unknown } | { kind: "reject"; error: Error };

export type RecordedRequest = { url: string; method: string; body: unknown };

export type StartersFetchQueue = {
  requests: RecordedRequest[];
  queueList: (status: number, body: unknown) => void;
  queueGet: (status: number, body: unknown) => void;
  queueRun: (status: number, body: unknown) => void;
  install: () => void;
};

export function createStartersFetchQueue(): StartersFetchQueue {
  const listQueue: Queued[] = [];
  const getQueue: Queued[] = [];
  const runQueue: Queued[] = [];
  const requests: RecordedRequest[] = [];

  function answer(queue: Queued[], path: string): Response {
    const queued = queue.shift();
    // Loud on purpose (harness precedent): a silent default would make a
    // component that stopped calling the API — or called an unexpected one —
    // look like a passing test.
    if (!queued) throw new Error(`unexpected request to ${path}`);
    if (queued.kind === "reject") throw queued.error;
    return {
      ok: queued.status < 400,
      status: queued.status,
      json: async () => queued.body,
    } as Response;
  }

  const api: StartersFetchQueue = {
    requests,
    queueList: (status, body) => listQueue.push({ kind: "reply", status, body }),
    queueGet: (status, body) => getQueue.push({ kind: "reply", status, body }),
    queueRun: (status, body) => runQueue.push({ kind: "reply", status, body }),
    install: () => {
      vi.stubGlobal(
        "fetch",
        vi.fn(async (url: string | URL, init?: RequestInit) => {
          const path = String(url);
          const method = init?.method ?? "GET";
          const body = init?.body ? JSON.parse(String(init.body)) : undefined;
          requests.push({ url: path, method, body });

          if (path === "/api/starters" && method === "GET") return answer(listQueue, path);
          if (path.startsWith("/api/starters/") && method === "GET") return answer(getQueue, path);
          if (path.startsWith("/api/starters/") && path.endsWith("/run") && method === "POST") {
            return answer(runQueue, path);
          }
          throw new Error(`unexpected request to ${path}`);
        })
      );
    },
  };

  return api;
}
