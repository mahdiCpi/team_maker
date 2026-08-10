/** The key-status routes (Story 2.3). Read-only: AD-9 forbids sending a key. */
import {
  type ApiResult,
  type KeyCheckView,
  type KeyStatusView,
  parseKeyCheck,
  parseKeyStatus,
} from "@/lib/api-types";
import { request } from "./transport";

/**
 * A key check is a file read and some catalog arithmetic — no LLM, no network
 * beyond the proxy — so it gets a short ceiling rather than the compose one. If it
 * cannot answer quickly the UI is better off saying it does not know than holding
 * the user for three minutes.
 */
export const KEY_CHECK_TIMEOUT_MS = 10_000;

/** Per-provider key status. Sends nothing; AD-9 means it could not send a key. */
export function getKeyStatus(): Promise<ApiResult<KeyStatusView>> {
  return request(
    { path: "/api/keys/status", method: "GET", timeoutMs: KEY_CHECK_TIMEOUT_MS },
    parseKeyStatus
  );
}

/** Whether this conversation's team can actually run, role by role. */
export function getKeyCheck(sessionId: string): Promise<ApiResult<KeyCheckView>> {
  return request(
    {
      path: `/api/keys/check/${encodeURIComponent(sessionId)}`,
      method: "GET",
      timeoutMs: KEY_CHECK_TIMEOUT_MS,
    },
    parseKeyCheck
  );
}
