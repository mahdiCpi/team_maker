/** The starters routes (Story 3-1's backend, `api/routers/starters.py`). */
import {
  type ApiResult,
  type StarterRunView,
  type StarterTeamListView,
  type StarterTeamView,
  parseStarterTeam,
  parseStarterTeamList,
  parseStarterRunView,
} from "@/lib/api-types";
import { request } from "./transport";

/** Reading static YAML files from disk — fast, same ceiling as the
 *  key-check routes' "a file read plus a catalog classification". */
export const STARTERS_TIMEOUT_MS = 5_000;

/** GET /api/starters — list all starter teams. */
export function listStarterTeams(): Promise<ApiResult<StarterTeamListView>> {
  return request(
    { path: "/api/starters", method: "GET", timeoutMs: STARTERS_TIMEOUT_MS },
    parseStarterTeamList
  );
}

/** GET /api/starters/{starter_id} — get a specific starter team by ID. */
export function getStarterTeam(starterId: string): Promise<ApiResult<StarterTeamView>> {
  return request(
    {
      path: `/api/starters/${encodeURIComponent(starterId)}`,
      method: "GET",
      timeoutMs: STARTERS_TIMEOUT_MS,
    },
    parseStarterTeam
  );
}

/** Building a starter performs per-provider model-list network calls, then writes files. */
export const BUILD_STARTER_TIMEOUT_MS = 120_000;

/** POST /api/starters/{starter_id}/run — build a starter team and return its slug. */
export function runStarterTeam(starterId: string): Promise<ApiResult<StarterRunView>> {
  return request(
    {
      path: `/api/starters/${encodeURIComponent(starterId)}/run`,
      method: "POST",
      timeoutMs: BUILD_STARTER_TIMEOUT_MS,
    },
    parseStarterRunView
  );
}
