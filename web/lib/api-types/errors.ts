import { asString, isRecord } from "./primitives";

/** Every code `api/errors.py` can emit, including the framework-level ones. */
export const SERVER_ERROR_CODES = [
  "session_not_found",
  "turn_cap_reached",
  "spec_invalid",
  "authoring_unavailable",
  "compose_failed",
  "output_exists",
  "build_failed",
  // Added by Story 2.0's code review; AC 8's original table predates it.
  "session_busy",
  // Added by Story 2.4 (the `run` group). There is deliberately no
  // `run_failed` — a run that fails does so on a background thread, minutes
  // after `POST /api/runs` already returned 200; failure is reported as
  // `RunView.status === "failed"`, not an error envelope.
  "team_not_found",
  "run_blocked",
  "run_in_progress",
  "run_not_found",
  // Framework-level: reachable via an unknown path, a 405, or a fault that
  // escapes the routes.
  "not_found",
  "method_not_allowed",
  "internal_error",
  "request_rejected",
] as const;

export type ServerErrorCode = (typeof SERVER_ERROR_CODES)[number];

/**
 * Codes this client originates. **These are additions, not part of Story 2.0's
 * contract** — the server never sends them. They exist because a browser has
 * failure modes an HTTP envelope cannot describe: the process is down, the
 * request was aborted, a proxy answered with HTML, or a future server sent a
 * code this build does not know. `EXPERIENCE.md:104` forbids a silent failure,
 * so each one gets authored copy rather than an empty state.
 */
export const CLIENT_ERROR_CODES = [
  "too_long",
  "unreachable",
  "timeout",
  "unreadable_response",
  "unknown_error",
] as const;

export type ClientErrorCode = (typeof CLIENT_ERROR_CODES)[number];
export type ApiErrorCode = ServerErrorCode | ClientErrorCode;

export type FieldIssue = { path: string; message: string };

export type ApiFailure = {
  ok: false;
  code: ApiErrorCode;
  message: string;
  /** Non-empty only for `spec_invalid`, matching `api/errors.py:93-94`. */
  fields: FieldIssue[];
};

export type ApiResult<T> = { ok: true; data: T } | ApiFailure;

export function isServerErrorCode(value: unknown): value is ServerErrorCode {
  return (
    typeof value === "string" &&
    (SERVER_ERROR_CODES as readonly string[]).includes(value)
  );
}

export function parseFieldIssues(value: unknown): FieldIssue[] {
  if (!Array.isArray(value)) return [];
  const issues: FieldIssue[] = [];
  for (const entry of value) {
    if (!isRecord(entry)) continue;
    const path = asString(entry.path);
    const message = asString(entry.message);
    if (path === null || message === null) continue;
    issues.push({ path, message });
  }
  return issues;
}

/** Reads `{ error: { code, message, fields? } }` without trusting any of it. */
export function parseErrorEnvelope(
  value: unknown
): { code: string; message: string; fields: FieldIssue[] } | null {
  if (!isRecord(value)) return null;
  if (!isRecord(value.error)) return null;
  const code = asString(value.error.code);
  const message = asString(value.error.message);
  if (code === null || message === null) return null;
  return { code, message, fields: parseFieldIssues(value.error.fields) };
}
