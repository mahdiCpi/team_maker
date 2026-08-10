/**
 * Run (Story 2.4). Status-like fields are deliberately open `string`s, for the
 * same reason `KeyStatusOverall`/`KeyCheckOverall` are: a value this build has
 * not heard of must not make the whole payload — or the whole check — unreadable.
 */
import { asBoolean, asNumber, asString, asStringArray, isRecord } from "./primitives";
import type { ProviderKeyStatus } from "./keys";

// ---------------------------------------------------------------------------
// Run bounds. Mirror `api/schemas.py`'s `_MAX_PROMPT` / `_MAX_DOCUMENTS` /
// `_MAX_DOCUMENT_TEXT` / `_MAX_TOTAL_DOCUMENT_TEXT` — a decision, not a
// discovery, since no NFR in this project constrains them.
// ---------------------------------------------------------------------------

/** Same value as `MAX_MESSAGE_LENGTH` (both mirror `_MAX_PROMPT`), named
 *  separately because a run's goal and a compose message are different
 *  fields that happen to share a bound today. */
export const MAX_GOAL_LENGTH = 8_000;
export const MAX_DOCUMENTS = 5;
export const MAX_DOCUMENT_TEXT_LENGTH = 50_000;
export const MAX_TOTAL_DOCUMENT_TEXT_LENGTH = 100_000;

// ---------------------------------------------------------------------------
// View types
// ---------------------------------------------------------------------------

/** `RunView.status`: `"running" | "complete" | "failed"` today, kept open. */
export type RunStatus = string;

/** `TranscriptEntryView.kind`: one of `results.py`'s six `ENTRY_*` constants,
 *  kept open for the same reason. */
export type TranscriptEntryKind = string;

export type AgentKeyView = {
  role: string;
  provider: string;
  model: string;
  status: ProviderKeyStatus;
  detail: string;
  usable: boolean;
  fix_hint: string | null;
};

export type TaskPlanView = {
  name: string;
  agent_role: string;
  dependencies: string[];
};

/** `GET /api/runs/teams/{team_slug}`. */
export type TeamPlanView = {
  team_name: string;
  agents: AgentKeyView[];
  tasks: TaskPlanView[];
};

export type TaskOutputView = {
  name: string;
  agent_role: string;
  output: string;
};

export type RunOutcomeView = {
  final_output: string;
  task_results: TaskOutputView[];
};

/** `POST /api/runs`, `GET /api/runs/{run_id}`. The goal and any attached
 *  documents are never present here — the server never echoes them back. */
export type RunView = {
  status: RunStatus;
  run_id: string;
  team_slug: string;
  team_name: string;
  tasks: TaskPlanView[];
  result: RunOutcomeView | null;
  transcript_available: boolean;
  failure_reason: string | null;
};

export type TranscriptEntryView = {
  sequence: number;
  kind: TranscriptEntryKind;
  agent_role: string;
  task_name: string;
  content: string;
  target_role: string | null;
};

/** `GET /api/runs/{run_id}/transcript`. `available: false` means "nothing to
 *  show yet" (still running, or failed before any entry was captured) —
 *  never conflated with `entries: []` meaning "the agents said nothing". */
export type TranscriptView = {
  available: boolean;
  entries: TranscriptEntryView[];
};

// ---------------------------------------------------------------------------
// Parsers
// ---------------------------------------------------------------------------

function parseAgentKey(value: unknown): AgentKeyView | null {
  if (!isRecord(value)) return null;
  const role = asString(value.role);
  const provider = asString(value.provider);
  const status = asString(value.status);
  const usable = asBoolean(value.usable);
  if (role === null || provider === null || status === null || usable === null) {
    return null;
  }
  return {
    role,
    provider,
    model: asString(value.model) ?? "",
    status,
    detail: asString(value.detail) ?? status,
    usable,
    fix_hint: asString(value.fix_hint),
  };
}

function parseTaskPlan(value: unknown): TaskPlanView | null {
  if (!isRecord(value)) return null;
  const name = asString(value.name);
  const agentRole = asString(value.agent_role);
  if (name === null || agentRole === null) return null;
  return { name, agent_role: agentRole, dependencies: asStringArray(value.dependencies) };
}

function parseTaskPlanList(value: unknown): TaskPlanView[] | null {
  if (!Array.isArray(value)) return null;
  const tasks = value.map(parseTaskPlan);
  if (tasks.some((task) => task === null)) return null;
  return tasks as TaskPlanView[];
}

export function parseTeamPlan(value: unknown): TeamPlanView | null {
  if (!isRecord(value)) return null;
  const teamName = asString(value.team_name);
  if (teamName === null) return null;
  if (!Array.isArray(value.agents)) return null;
  const agents = value.agents.map(parseAgentKey);
  if (agents.some((agent) => agent === null)) return null;
  const tasks = parseTaskPlanList(value.tasks);
  if (tasks === null) return null;
  return { team_name: teamName, agents: agents as AgentKeyView[], tasks };
}

function parseTaskOutput(value: unknown): TaskOutputView | null {
  if (!isRecord(value)) return null;
  const name = asString(value.name);
  const agentRole = asString(value.agent_role);
  const output = asString(value.output);
  if (name === null || agentRole === null || output === null) return null;
  return { name, agent_role: agentRole, output };
}

function parseRunOutcome(value: unknown): RunOutcomeView | null {
  if (!isRecord(value)) return null;
  const finalOutput = asString(value.final_output);
  if (finalOutput === null) return null;
  if (!Array.isArray(value.task_results)) return null;
  const results = value.task_results.map(parseTaskOutput);
  if (results.some((result) => result === null)) return null;
  return { final_output: finalOutput, task_results: results as TaskOutputView[] };
}

export function parseRun(value: unknown): RunView | null {
  if (!isRecord(value)) return null;
  const status = asString(value.status);
  const runId = asString(value.run_id);
  const teamSlug = asString(value.team_slug);
  const teamName = asString(value.team_name);
  const transcriptAvailable = asBoolean(value.transcript_available);
  if (
    status === null ||
    runId === null ||
    teamSlug === null ||
    teamName === null ||
    transcriptAvailable === null
  ) {
    return null;
  }
  const tasks = parseTaskPlanList(value.tasks);
  if (tasks === null) return null;
  // `null` is a legitimate value ("no result yet"); anything else must parse.
  let result: RunOutcomeView | null = null;
  if (value.result !== null && value.result !== undefined) {
    result = parseRunOutcome(value.result);
    if (result === null) return null;
  }
  return {
    status,
    run_id: runId,
    team_slug: teamSlug,
    team_name: teamName,
    tasks,
    result,
    transcript_available: transcriptAvailable,
    failure_reason: asString(value.failure_reason),
  };
}

function parseTranscriptEntry(value: unknown): TranscriptEntryView | null {
  if (!isRecord(value)) return null;
  const sequence = asNumber(value.sequence);
  const kind = asString(value.kind);
  const agentRole = asString(value.agent_role);
  const taskName = asString(value.task_name);
  const content = asString(value.content);
  if (
    sequence === null ||
    kind === null ||
    agentRole === null ||
    taskName === null ||
    content === null
  ) {
    return null;
  }
  return {
    sequence,
    kind,
    agent_role: agentRole,
    task_name: taskName,
    content,
    target_role: asString(value.target_role),
  };
}

export function parseTranscript(value: unknown): TranscriptView | null {
  if (!isRecord(value)) return null;
  const available = asBoolean(value.available);
  if (available === null) return null;
  if (!Array.isArray(value.entries)) return null;
  const entries = value.entries.map(parseTranscriptEntry);
  if (entries.some((entry) => entry === null)) return null;
  return { available, entries: entries as TranscriptEntryView[] };
}
