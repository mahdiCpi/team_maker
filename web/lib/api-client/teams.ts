/** The teams routes (Story 2.5's backend; Story 2.8's frontend). */
import {
  MAX_TEAM_NAME_LENGTH,
  type ApiFailure,
  type ApiResult,
  type TeamListView,
  type TeamMessageView,
  type TeamView,
  parseTeam,
  parseTeamList,
  parseTeamMessage,
} from "@/lib/api-types";
import { request, tooLong } from "./transport";

/** SQLite reads/writes and small filesystem moves — fast, same ceiling as the
 *  key-check routes' "a file read plus a catalog classification". */
export const TEAMS_TIMEOUT_MS = 10_000;

export function listTeams(): Promise<ApiResult<TeamListView>> {
  return request(
    { path: "/api/teams/browse", method: "GET", timeoutMs: TEAMS_TIMEOUT_MS },
    parseTeamList
  );
}

export function renameTeam(oldName: string, newName: string): Promise<ApiResult<TeamView>> {
  const rejection = validateNewName(newName);
  if (rejection) return Promise.resolve(rejection);
  return request(
    {
      path: "/api/teams/rename",
      method: "PUT",
      body: { old_name: oldName, new_name: newName },
      timeoutMs: TEAMS_TIMEOUT_MS,
    },
    parseTeam
  );
}

export function deleteTeam(teamName: string): Promise<ApiResult<TeamMessageView>> {
  return request(
    {
      path: `/api/teams/delete?team_name=${encodeURIComponent(teamName)}`,
      method: "DELETE",
      timeoutMs: TEAMS_TIMEOUT_MS,
    },
    parseTeamMessage
  );
}

export function recordTeamRun(teamName: string): Promise<ApiResult<TeamView>> {
  return request(
    {
      path: `/api/teams/${encodeURIComponent(teamName)}/record-run`,
      method: "POST",
      body: {},
      timeoutMs: TEAMS_TIMEOUT_MS,
    },
    parseTeam
  );
}

/** Mirrors `run.ts`'s `validateRunInput` convention: `spec_invalid` (with a
 *  field path) for a shape violation, `tooLong` specifically for a length
 *  ceiling — both pre-empt a request the server would reject anyway. */
function validateNewName(name: string): ApiFailure | null {
  if (name.trim().length < 2) {
    return {
      ok: false,
      code: "spec_invalid",
      message: "A team name must be at least 2 characters.",
      fields: [{ path: "new_name", message: "Must be at least 2 characters." }],
    };
  }
  if (name.length > MAX_TEAM_NAME_LENGTH) {
    return tooLong("The team name", MAX_TEAM_NAME_LENGTH);
  }
  return null;
}
