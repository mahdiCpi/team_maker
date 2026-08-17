/**
 * Starter teams (Story 3-1's backend, `api/routers/starters.py`;
 * Story 3-1's frontend listing). Mirrors `teams.ts`'s shape: one view type
 * plus one parser per response.
 */
import { asNumber, asString, isRecord } from "./primitives";

/** `StarterTeamView` (`GET /api/starters`, `GET /api/starters/{starter_id}`). */
export type StarterTeamView = {
  id: string;
  name: string;
  purpose: string;
  template_id: string;
  agent_count: number;
};

/** `GET /api/starters`. */
export type StarterTeamListView = {
  starters: StarterTeamView[];
};

export function parseStarterTeam(value: unknown): StarterTeamView | null {
  if (!isRecord(value)) return null;
  const id = asString(value.id);
  const name = asString(value.name);
  const purpose = asString(value.purpose);
  const templateId = asString(value.template_id);
  const agentCount = asNumber(value.agent_count);
  
  if (id === null || name === null || purpose === null || templateId === null || agentCount === null) {
    return null;
  }
  
  return {
    id,
    name,
    purpose,
    template_id: templateId,
    agent_count: agentCount,
  };
}

export function parseStarterTeamList(value: unknown): StarterTeamListView | null {
  if (!isRecord(value)) return null;
  if (!Array.isArray(value.starters)) return null;
  const starters = value.starters.map(parseStarterTeam);
  if (starters.some((starter) => starter === null)) return null;
  return { starters: starters as StarterTeamView[] };
}

/** `StarterRunView` (`POST /api/starters/{starter_id}/run`). */
export type StarterRunView = {
  status: string;
  team_slug: string;
  team_name: string;
};

export function parseStarterRunView(value: unknown): StarterRunView | null {
  if (!isRecord(value)) return null;
  const status = asString(value.status);
  const teamSlug = asString(value.team_slug);
  const teamName = asString(value.team_name);
  
  if (status === null || teamSlug === null || teamName === null) {
    return null;
  }
  
  return {
    status,
    team_slug: teamSlug,
    team_name: teamName,
  };
}
