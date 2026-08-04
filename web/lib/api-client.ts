/**
 * The single place in the frontend that talks to `/api`.
 *
 * Every request is same-origin: `web/next.config.ts` rewrites `/api/:path*` to
 * the FastAPI process, so there is no base URL to configure, no CORS, and no
 * credentials mode. Nothing here reads or sends an API key — AD-9 means the
 * request may *name* a provider and the server resolves the credential from the
 * Key Config, and `EXPERIENCE.md:103` bans key entry in the UI outright.
 *
 * The public surface is one function per Story 2.0 route, each returning an
 * `ApiResult` the caller branches on by `code`. Nothing throws: a failure is a
 * value, because `EXPERIENCE.md:104` bans hiding a blocked action behind a
 * silent failure and an exception at a component boundary is exactly that.
 */
import {
  MAX_MESSAGE_LENGTH,
  MAX_NAME_LENGTH,
  MAX_TEXT_LENGTH,
  type ApiErrorCode,
  type ApiFailure,
  type ApiResult,
  type BuildResultView,
  type FieldIssue,
  type ProviderRoutingView,
  type RoleView,
  type SessionView,
  type TaskView,
  isServerErrorCode,
  parseBuildResponse,
  parseErrorEnvelope,
  parseSessionResponse,
} from "@/lib/api-types";

export * from "@/lib/api-types";

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

/**
 * Authored copy for the codes whose server message must not be shown as-is —
 * either because the client invented the code, or because the message failed
 * the leak check below.
 */
const FALLBACK_MESSAGE: Record<ApiErrorCode, string> = {
  session_not_found:
    "That conversation is no longer available. Start a new one to continue.",
  turn_cap_reached: "This conversation has reached its limit of turns.",
  spec_invalid: "Those changes do not produce a valid team specification.",
  authoring_unavailable:
    "Composing needs a model provider that is currently unavailable.",
  compose_failed:
    "The team specification could not be created. Retry once; if the problem repeats, stop and report it.",
  output_exists:
    "A directory already exists at the team's output path, and this build will not overwrite it.",
  build_failed:
    "The team package could not be built. The error has been logged on the server.",
  session_busy:
    "This conversation is still working on a previous request. Try again in a moment.",
  not_found: "That endpoint does not exist.",
  method_not_allowed: "That request is not allowed on this endpoint.",
  internal_error: "Something went wrong on the server. The error has been logged.",
  request_rejected: "The request could not be completed.",
  too_long: "That is too long to send. Shorten it and try again.",
  unreachable:
    "Could not reach team_maker. Check that the API is running, then try again.",
  timeout:
    "That took too long and was stopped. The server may still be working; try again in a moment.",
  unreadable_response:
    "team_maker sent a response this app could not read. Try again; if it repeats, stop and report it.",
  unknown_error: "Something went wrong. Try again.",
};

/**
 * True when a message carries what looks like a stack trace or file path from
 * the server's internals.
 *
 * Story 2.0 guarantees it never sends one (`api/errors.py:1-11` — `message` is
 * authored copy, never `str(exc)`). This is the client half of AC 8's promise:
 * if that guarantee ever breaks, the trace still does not reach the screen. The
 * test for it is validated against a payload that really contains a traceback,
 * because a guard proven only against clean input is a guard that cannot fail.
 */
function looksLikeLeakedInternals(message: string): boolean {
  return (
    /Traceback \(most recent call last\)/.test(message) ||
    /File "[^"]+", line \d+/.test(message) ||
    /\n\s*at .+:\d+:\d+/.test(message) ||
    /^[A-Za-z_.]*Error: /m.test(message)
  );
}

function failure(
  code: ApiErrorCode,
  message?: string,
  fields: FieldIssue[] = []
): ApiFailure {
  const authored = FALLBACK_MESSAGE[code];
  const usable =
    message !== undefined &&
    message.trim().length > 0 &&
    !looksLikeLeakedInternals(message)
      ? message
      : authored;
  return { ok: false, code, message: usable, fields };
}

function tooLong(what: string, limit: number): ApiFailure {
  return failure("too_long", `${what} must be ${limit} characters or fewer.`);
}

// ---------------------------------------------------------------------------
// Transport
// ---------------------------------------------------------------------------

type RequestSpec = {
  path: string;
  method: "GET" | "POST" | "PUT";
  body?: unknown;
  timeoutMs: number;
};

async function request<T>(
  spec: RequestSpec,
  parse: (payload: unknown) => T | null
): Promise<ApiResult<T>> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), spec.timeoutMs);

  let response: Response;
  try {
    response = await fetch(spec.path, {
      method: spec.method,
      headers: spec.body === undefined ? undefined : { "Content-Type": "application/json" },
      body: spec.body === undefined ? undefined : JSON.stringify(spec.body),
      signal: controller.signal,
    });
  } catch (error) {
    // Nothing from `error` reaches the caller: a DOMException's message is
    // browser-specific text, not product copy.
    return failure(isAbort(error) ? "timeout" : "unreachable");
  } finally {
    clearTimeout(timer);
  }

  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    // A proxy's HTML error page, or an empty body. Either way the envelope
    // promise is broken and there is nothing to read a code from.
    return failure("unreadable_response");
  }

  if (!response.ok) return toFailure(payload);

  const parsed = parse(payload);
  if (parsed === null) return failure("unreadable_response");
  return { ok: true, data: parsed };
}

function isAbort(error: unknown): boolean {
  return error instanceof Error && error.name === "AbortError";
}

/**
 * Maps a non-2xx body onto a failure.
 *
 * An unrecognised `code` degrades to `unknown_error` rather than being trusted:
 * a future server value must not flow into a `Record<ApiErrorCode, …>` lookup
 * and come back `undefined`, which is how a blank error state gets rendered.
 * The server's *message* is still shown, because it is authored copy and is
 * more specific than anything this build could invent for a code it has never
 * heard of.
 */
function toFailure(payload: unknown): ApiFailure {
  const envelope = parseErrorEnvelope(payload);
  if (envelope === null) return failure("unreadable_response");
  const code: ApiErrorCode = isServerErrorCode(envelope.code)
    ? envelope.code
    : "unknown_error";
  return failure(code, envelope.message, envelope.fields);
}

// ---------------------------------------------------------------------------
// Routes
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

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
  if (llm && llm.model.length > 200) {
    return tooLong("A model id", 200);
  }
  return null;
}
