/**
 * Named teams (Story 2.5's backend, `api/routers/teams.py`; Story 2.8's
 * frontend). Mirrors `run.ts`'s shape: one view type plus one parser per
 * response, everything else narrowed through `primitives.ts`.
 */
import { asNumber, asString, isRecord } from "./primitives";

/** Mirrors `api/schemas.py`'s `_MAX_NAME` (also the bound for a team name). */
export const MAX_TEAM_NAME_LENGTH = 120;

/** `TeamView` (`GET /api/teams/browse`, `PUT /api/teams/rename`,
 *  `POST /api/teams/{team_name}/record-run`). `last_run_at` is `null` for a
 *  team that has never been run since being saved. */
export type TeamView = {
  name: string;
  created_at: string;
  last_run_at: string | null;
  run_count: number;
};

/** `GET /api/teams/browse`. */
export type TeamListView = {
  teams: TeamView[];
};

export function parseTeam(value: unknown): TeamView | null {
  if (!isRecord(value)) return null;
  const name = asString(value.name);
  const createdAt = asString(value.created_at);
  const runCount = asNumber(value.run_count);
  if (name === null || createdAt === null || runCount === null) return null;
  return {
    name,
    created_at: createdAt,
    last_run_at: asString(value.last_run_at),
    run_count: runCount,
  };
}

export function parseTeamList(value: unknown): TeamListView | null {
  if (!isRecord(value)) return null;
  if (!Array.isArray(value.teams)) return null;
  const teams = value.teams.map(parseTeam);
  if (teams.some((team) => team === null)) return null;
  return { teams: teams as TeamView[] };
}

/** `DELETE /api/teams/delete` (`MessageView` on the server). */
export type TeamMessageView = { message: string };

export function parseTeamMessage(value: unknown): TeamMessageView | null {
  if (!isRecord(value)) return null;
  const message = asString(value.message);
  if (message === null) return null;
  return { message };
}
