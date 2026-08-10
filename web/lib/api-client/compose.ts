/** The compose seam's routes (Story 2.0–2.2). */
import {
  MAX_MESSAGE_LENGTH,
  MAX_MODEL_ID_LENGTH,
  MAX_NAME_LENGTH,
  MAX_TEXT_LENGTH,
  type ApiFailure,
  type ApiResult,
  type BuildResultView,
  type ProviderRoutingView,
  type RoleView,
  type SessionView,
  type TaskView,
  parseBuildResponse,
  parseSessionResponse,
} from "@/lib/api-types";
import { request, tooLong } from "./transport";

/**
 * A compose turn is 1–4 *sequential blocking* LLM round-trips behind a single
 * request (`api/routers/compose.py:1-11`), with no streaming and no progress
 * callback. The ceiling is therefore generous by design; a captured turn in
 * this repo took several seconds, and a four-call refinement on a slow provider
 * can take far longer. Too short a timeout would abort work the server is still
 * doing and has already paid for.
 */
export const COMPOSE_TIMEOUT_MS = 180_000;

/** A build performs per-provider model-list network calls, then writes files. */
export const BUILD_TIMEOUT_MS = 120_000;

export type AuthoringSelection = { provider?: string; model?: string };

export type CreateSessionInput = {
  intent: string;
  /** Optional. Omitted entirely when absent — the server default (`anthropic`
   *  / `claude-sonnet-4-6`) is the path this story's ACs describe. */
  authoring?: AuthoringSelection;
};

export function createSession(
  input: CreateSessionInput
): Promise<ApiResult<SessionView>> {
  if (input.intent.length > MAX_MESSAGE_LENGTH) {
    return Promise.resolve(tooLong("Your description", MAX_MESSAGE_LENGTH));
  }
  const body: Record<string, unknown> = { intent: input.intent };
  if (input.authoring) body.authoring = input.authoring;

  return request(
    {
      path: "/api/compose/sessions",
      method: "POST",
      body,
      timeoutMs: COMPOSE_TIMEOUT_MS,
    },
    parseSessionResponse
  );
}

export function sendMessage(
  sessionId: string,
  message: string
): Promise<ApiResult<SessionView>> {
  if (message.length > MAX_MESSAGE_LENGTH) {
    return Promise.resolve(tooLong("Your message", MAX_MESSAGE_LENGTH));
  }
  return request(
    {
      path: `${sessionPath(sessionId)}/messages`,
      method: "POST",
      body: { message },
      timeoutMs: COMPOSE_TIMEOUT_MS,
    },
    parseSessionResponse
  );
}

export type SpecEditInput = {
  team_name: string;
  purpose: string;
  desired_roles: RoleView[];
  desired_tasks: TaskView[];
};

export function replaceSpec(
  sessionId: string,
  edit: SpecEditInput
): Promise<ApiResult<SessionView>> {
  const rejection = validateEdit(edit);
  if (rejection) return Promise.resolve(rejection);

  return request(
    {
      path: `${sessionPath(sessionId)}/spec`,
      method: "PUT",
      // Built field by field rather than spread, so a spec object that picked
      // up `output_path` somewhere upstream cannot ride along into a body that
      // `extra="forbid"` turns into a 422.
      body: {
        team_name: edit.team_name,
        purpose: edit.purpose,
        desired_roles: edit.desired_roles.map(toRoleBody),
        desired_tasks: edit.desired_tasks.map((task) => ({
          name: task.name,
          description: task.description,
          agent_role: task.agent_role,
          dependencies: task.dependencies,
        })),
      },
      timeoutMs: BUILD_TIMEOUT_MS,
    },
    parseSessionResponse
  );
}

export function buildTeam(sessionId: string): Promise<ApiResult<BuildResultView>> {
  return request(
    {
      path: `${sessionPath(sessionId)}/build`,
      method: "POST",
      timeoutMs: BUILD_TIMEOUT_MS,
    },
    parseBuildResponse
  );
}

function sessionPath(sessionId: string): string {
  // Encoded even though the server's ids are URL-safe base64: an id that ever
  // contained a slash would otherwise address a different route entirely.
  return `/api/compose/sessions/${encodeURIComponent(sessionId)}`;
}

function toRoleBody(role: RoleView): Record<string, unknown> {
  const body: Record<string, unknown> = {
    name: role.name,
    description: role.description,
  };
  // Omitted, not null: `ProviderSelection` requires both fields when present,
  // so `llm: null` would be a 422 where "leave it as it is" was meant.
  if (role.llm) body.llm = { provider: role.llm.provider, model: role.llm.model };
  return body;
}

function validateEdit(edit: SpecEditInput): ApiFailure | null {
  if (edit.team_name.length > MAX_NAME_LENGTH) {
    return tooLong("The team name", MAX_NAME_LENGTH);
  }
  if (edit.purpose.length > MAX_TEXT_LENGTH) {
    return tooLong("The purpose", MAX_TEXT_LENGTH);
  }
  if (edit.desired_roles.length === 0) {
    // Refused here rather than at the server, because an empty roles list does
    // not fail there: it flips the build into a second LLM call through
    // `planning_llm` — a different provider config, and silent cost
    // (`api/routers/compose.py:249-257`).
    return {
      ok: false,
      code: "spec_invalid",
      message: "A team needs at least one role.",
      fields: [{ path: "desired_roles", message: "Add at least one role." }],
    };
  }

  for (const role of edit.desired_roles) {
    const bound = boundsFailure("role", role.name, role.description, role.llm);
    if (bound) return bound;
  }
  for (const task of edit.desired_tasks) {
    const bound = boundsFailure("task", task.name, task.description);
    if (bound) return bound;
  }
  return null;
}

function boundsFailure(
  kind: "role" | "task",
  name: string,
  description: string,
  llm?: ProviderRoutingView
): ApiFailure | null {
  if (name.length > MAX_NAME_LENGTH) {
    return tooLong(`Each ${kind} name`, MAX_NAME_LENGTH);
  }
  if (description.length > MAX_TEXT_LENGTH) {
    return tooLong(`Each ${kind} description`, MAX_TEXT_LENGTH);
  }
  if (llm && llm.model.length > MAX_MODEL_ID_LENGTH) {
    return tooLong("A model id", MAX_MODEL_ID_LENGTH);
  }
  return null;
}
