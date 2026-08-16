import { vi } from "vitest";

/**
 * A minimal fetch queue for the teams routes, mirroring
 * `tests/workspace/harness.tsx`'s `createRunFetchQueue` shape but scoped to
 * this surface (Story 2.8) — a new directory, not more files in
 * `tests/workspace/` or `tests/composer/`.
 *
 * Everything here is a STUB: no real API process. A passing test proves the
 * real client and the real components handle the real wire format, not that
 * the backend works.
 */

type Queued = { kind: "reply"; status: number; body: unknown } | { kind: "reject"; error: Error };

export type RecordedRequest = { url: string; method: string; body: unknown };

export type TeamsFetchQueue = {
  requests: RecordedRequest[];
  queueBrowse: (status: number, body: unknown) => void;
  queueRename: (status: number, body: unknown) => void;
  queueDelete: (status: number, body: unknown) => void;
  queueRecordRun: (status: number, body: unknown) => void;
  install: () => void;
};

export function createTeamsFetchQueue(): TeamsFetchQueue {
  const browseQueue: Queued[] = [];
  const renameQueue: Queued[] = [];
  const deleteQueue: Queued[] = [];
  const recordRunQueue: Queued[] = [];
  const requests: RecordedRequest[] = [];

  function answer(queue: Queued[], path: string): Response {
    const queued = queue.shift();
    // Loud on purpose (harness precedent): a silent default would make a
    // component that stopped calling the API — or called an unexpected one
    // — look like a passing test.
    if (!queued) throw new Error(`unexpected request to ${path}`);
    if (queued.kind === "reject") throw queued.error;
    return {
      ok: queued.status < 400,
      status: queued.status,
      json: async () => queued.body,
    } as Response;
  }

  const api: TeamsFetchQueue = {
    requests,
    queueBrowse: (status, body) => browseQueue.push({ kind: "reply", status, body }),
    queueRename: (status, body) => renameQueue.push({ kind: "reply", status, body }),
    queueDelete: (status, body) => deleteQueue.push({ kind: "reply", status, body }),
    queueRecordRun: (status, body) => recordRunQueue.push({ kind: "reply", status, body }),
    install: () => {
      vi.stubGlobal(
        "fetch",
        vi.fn(async (url: string | URL, init?: RequestInit) => {
          const path = String(url);
          const method = init?.method ?? "GET";
          const body = init?.body ? JSON.parse(String(init.body)) : undefined;
          requests.push({ url: path, method, body });

          if (path === "/api/teams/browse" && method === "GET") return answer(browseQueue, path);
          if (path === "/api/teams/rename" && method === "PUT") return answer(renameQueue, path);
          if (path.startsWith("/api/teams/delete") && method === "DELETE") {
            return answer(deleteQueue, path);
          }
          if (/\/api\/teams\/[^/]+\/record-run$/.test(path) && method === "POST") {
            return answer(recordRunQueue, path);
          }
          throw new Error(`unexpected request to ${path}`);
        })
      );
    },
  };

  return api;
}
