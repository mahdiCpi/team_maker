import { vi } from "vitest";

/**
 * A minimal fetch queue for the `run` routes, mirroring
 * `tests/composer/harness.tsx`'s `createFetchQueue` shape but scoped to this
 * surface — a new directory, not more files in `tests/composer/` (Story 2.4
 * Task 16).
 *
 * Everything here is a STUB: no real API process, no real crewai run. A
 * passing test proves the real client and the real components handle the
 * real wire format captured in `fixtures/`, not that the backend works.
 */

type Queued = { kind: "reply"; status: number; body: unknown } | { kind: "reject"; error: Error };

export type RecordedRequest = { url: string; method: string; body: unknown };

export type RunFetchQueue = {
  requests: RecordedRequest[];
  queuePlan: (status: number, body: unknown) => void;
  queueCreateRun: (status: number, body: unknown) => void;
  queueGetRun: (status: number, body: unknown) => void;
  queueTranscript: (status: number, body: unknown) => void;
  /** Story 2.8: `WorkspaceSurface` fires this best-effort on run completion.
   *  Optional to queue — a test that never calls this still passes, since an
   *  unqueued request here resolves to a swallowed `unreachable` failure
   *  (`transport.ts`'s `request()` catches a throwing `fetch`), exactly the
   *  "team was never saved" case this call is designed to tolerate. */
  queueRecordRun: (status: number, body: unknown) => void;
  install: () => void;
};

export function createRunFetchQueue(): RunFetchQueue {
  const planQueue: Queued[] = [];
  const createQueue: Queued[] = [];
  const getRunQueue: Queued[] = [];
  const transcriptQueue: Queued[] = [];
  const recordRunQueue: Queued[] = [];
  const requests: RecordedRequest[] = [];

  function answer(queue: Queued[], path: string): Response {
    const queued = queue.shift();
    // Loud on purpose (harness.tsx precedent): a silent default would make a
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

  const api: RunFetchQueue = {
    requests,
    queuePlan: (status, body) => planQueue.push({ kind: "reply", status, body }),
    queueCreateRun: (status, body) => createQueue.push({ kind: "reply", status, body }),
    queueGetRun: (status, body) => getRunQueue.push({ kind: "reply", status, body }),
    queueTranscript: (status, body) => transcriptQueue.push({ kind: "reply", status, body }),
    queueRecordRun: (status, body) => recordRunQueue.push({ kind: "reply", status, body }),
    install: () => {
      vi.stubGlobal(
        "fetch",
        vi.fn(async (url: string | URL, init?: RequestInit) => {
          const path = String(url);
          const method = init?.method ?? "GET";
          const body = init?.body ? JSON.parse(String(init.body)) : undefined;
          requests.push({ url: path, method, body });

          if (path.startsWith("/api/runs/teams/")) return answer(planQueue, path);
          if (path === "/api/runs" && method === "POST") return answer(createQueue, path);
          if (/\/api\/runs\/[^/]+\/transcript$/.test(path)) return answer(transcriptQueue, path);
          if (/^\/api\/runs\/[^/]+$/.test(path)) return answer(getRunQueue, path);
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
