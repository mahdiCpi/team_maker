/** The starters routes (Story 3-1's backend, `api/routers/starters.py`). */
import {
  type ApiResult,
  type StarterTeamListView,
  type StarterTeamView,
  parseStarterTeam,
  parseStarterTeamList,
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
