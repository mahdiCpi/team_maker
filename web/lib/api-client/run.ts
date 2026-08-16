/** The run routes (Story 2.4). */
import {
  MAX_DOCUMENT_TEXT_LENGTH,
  MAX_DOCUMENTS,
  MAX_GOAL_LENGTH,
  MAX_TOTAL_DOCUMENT_TEXT_LENGTH,
  type ApiFailure,
  type ApiResult,
  type RunView,
  type TeamPlanView,
  type TranscriptView,
  parseRun,
  parseTeamPlan,
  parseTranscript,
} from "@/lib/api-types";
import { request, tooLong } from "./transport";

/** A file read plus a catalog classification — no LLM, no network beyond the
 *  proxy — so this gets a short ceiling like the key-check routes. */
export const TEAM_PLAN_TIMEOUT_MS = 10_000;

/** The Workspace polls a running run at this interval. Short enough to feel
 *  live; long enough that a run in flight for minutes (no timeout of its
 *  own — AC 4) does not spend most of its life mid-poll. */
export const RUN_POLL_INTERVAL_MS = 2_000;

export const RUN_POLL_TIMEOUT_MS = 10_000;

/**
 * `POST /api/runs` returns as soon as the synchronous pre-run gate passes
 * (AD-9) and a background thread has started — it never waits for the run
 * itself, which has no timeout of its own. The gate is a file read plus a
 * credential check, so this ceiling is generous for *that* alone, not for a
 * run's duration.
 */
export const RUN_START_TIMEOUT_MS = 15_000;

/** The runnable view of a built team: its agents' key badges and its task
 *  plan in topological order. */
export function getTeamPlan(teamSlug: string): Promise<ApiResult<TeamPlanView>> {
  return request(
    {
      path: `/api/runs/teams/${encodeURIComponent(teamSlug)}`,
      method: "GET",
      timeoutMs: TEAM_PLAN_TIMEOUT_MS,
    },
    parseTeamPlan
  );
}

export type AttachedDocumentInput = { name: string; text: string };

export type CreateRunInput = {
  team_slug: string;
  goal: string;
  documents?: AttachedDocumentInput[];
};

export function createRun(input: CreateRunInput): Promise<ApiResult<RunView>> {
  const rejection = validateRunInput(input);
  if (rejection) return Promise.resolve(rejection);
  return request(
    {
      path: "/api/runs",
      method: "POST",
      body: {
        team_slug: input.team_slug,
        goal: input.goal,
        documents: input.documents ?? [],
      },
      timeoutMs: RUN_START_TIMEOUT_MS,
    },
    parseRun
  );
}

/** A run's current state — `running`, `complete`, or `failed`. */
export function getRun(runId: string): Promise<ApiResult<RunView>> {
  return request(
    {
      path: `/api/runs/${encodeURIComponent(runId)}`,
      method: "GET",
      timeoutMs: RUN_POLL_TIMEOUT_MS,
    },
    parseRun
  );
}

export function getRunTranscript(runId: string): Promise<ApiResult<TranscriptView>> {
  return request(
    {
      path: `/api/runs/${encodeURIComponent(runId)}/transcript`,
      method: "GET",
      timeoutMs: RUN_POLL_TIMEOUT_MS,
    },
    parseTranscript
  );
}

function validateRunInput(input: CreateRunInput): ApiFailure | null {
  if (input.goal.trim().length === 0) {
    return {
      ok: false,
      code: "spec_invalid",
      message: "The goal cannot be blank.",
      fields: [{ path: "goal", message: "The goal cannot be blank." }],
    };
  }
  if (input.goal.length > MAX_GOAL_LENGTH) {
    return tooLong("The goal", MAX_GOAL_LENGTH);
  }
  const documents = input.documents ?? [];
  if (documents.length > MAX_DOCUMENTS) {
    return {
      ok: false,
      code: "spec_invalid",
      message: `You can attach at most ${MAX_DOCUMENTS} documents.`,
      fields: [{ path: "documents", message: `Attach ${MAX_DOCUMENTS} or fewer.` }],
    };
  }
  let total = 0;
  for (const document of documents) {
    if (document.text.length > MAX_DOCUMENT_TEXT_LENGTH) {
      return tooLong(`"${document.name}"`, MAX_DOCUMENT_TEXT_LENGTH);
    }
    total += document.text.length;
  }
  if (total > MAX_TOTAL_DOCUMENT_TEXT_LENGTH) {
    return {
      ok: false,
      code: "spec_invalid",
      message: `Attached documents total ${total.toLocaleString()} characters; the limit is ${MAX_TOTAL_DOCUMENT_TEXT_LENGTH.toLocaleString()} across all of them.`,
      fields: [{ path: "documents", message: "Remove or shorten a document." }],
    };
  }
  return null;
}
