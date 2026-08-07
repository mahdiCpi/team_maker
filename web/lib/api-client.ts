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
  MAX_MODEL_ID_LENGTH,
  MAX_NAME_LENGTH,
  MAX_TEXT_LENGTH,
  type ApiErrorCode,
  type ApiFailure,
  type ApiResult,
  type BuildResultView,
  type FieldIssue,
  type KeyCheckView,
  type KeyStatusView,
  type ProviderRoutingView,
  type RoleView,
  type SessionView,
  type TaskView,
  isServerErrorCode,
  parseBuildResponse,
  parseErrorEnvelope,
  parseKeyCheck,
  parseKeyStatus,
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
  // Both of these said what was wrong and stopped there. `EXPERIENCE.md`'s Voice
  // section asks for the next step too, and Story 2.3 owns error copy.
  turn_cap_reached:
    "This conversation has used all its turns. Build the team as it stands, or start a new conversation.",
  spec_invalid: "Those changes do not produce a valid team specification.",
  // Names where keys live without ever offering to take one — `EXPERIENCE.md:103`
  // bans key entry in the UI outright. The server's own message is more specific
  // (it names the provider and the Key Config entry) and is what normally shows;
  // this is the fallback for a missing or leak-flagged one.
  authoring_unavailable:
    "Composing needs a model provider with a usable key, and none is available. Keys live in your Key Config file.",
  compose_failed:
    "The team specification could not be created. Retry once; if the problem repeats, stop and report it.",
  // No longer an override — Story 2.3 fixed the server's own sentence, so this is
  // just the fallback for a missing or leak-flagged message, like every other row.
  // It phrases the remedy in this surface's terms, which the server cannot: the
  // destination is derived from the team name and pinned per conversation, so a
  // differently named team in a new conversation writes somewhere else.
  output_exists:
    "A directory already exists at the team's output path, so this build stopped rather than overwrite it. The destination is chosen by the server; start a new conversation to build a differently-named team.",
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
 * True when a message carries what looks like a stack trace, an exception name,
 * or an absolute filesystem path from the server's internals.
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
    // No leading `\n` requirement: a single-line JS frame such as
    // `at handler (/srv/app.js:12:9)` carries a path and a position and used to
    // pass because the pattern insisted on a preceding newline.
    /(?:^|\s)at .+:\d+:\d+/.test(message) ||
    // `[A-Za-z_.]` could not span a digit, so `urllib3.exceptions.MaxRetryError:`
    // slipped through — the class stopped at `urllib` and never reached `Error:`.
    /^[\w.]*(?:Error|Exception):\s/m.test(message) ||
    // An absolute filesystem path names server internals even without a frame
    // around it. The docstring claimed this was covered; nothing matched it.
    /(?:[A-Za-z]:\\|(?:^|\s)\/)(?:[\w.-]+[\\/]){2,}/.test(message)
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
  return { ok: false, code, message: usable, fields: scrubFields(fields) };
}

/**
 * The same leak check, applied to `fields[].message`.
 *
 * This is the field that most needs it. `api/errors.py`'s docstring promises
 * `message` is authored copy, and it is — but Story 2.0's own review recorded
 * that `fields[].message` is the `msg` half of a pydantic or `ComposerError`
 * string, forwarded verbatim. Pydantic routinely interpolates the offending
 * input, and here that input is LLM output derived from the user's intent. So
 * the one part of the envelope that is *not* authored was also the one part
 * reaching the screen unchecked.
 *
 * An entry that fails the check keeps its path — the client still needs to know
 * which row is wrong — and loses only the untrusted text.
 */
function scrubFields(fields: FieldIssue[]): FieldIssue[] {
  return fields.map((field) =>
    looksLikeLeakedInternals(field.message)
      ? { path: field.path, message: "This value was rejected by the server." }
      : field
  );
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

  // The timer is cleared in ONE place, after the body has been read. Clearing it
  // when the headers arrive left `response.json()` unbounded: a proxy that
  // flushes `200 OK` and then stalls mid-body could never be aborted, so the
  // caller's pending state lasted forever with no timeout and no recovery but a
  // page reload. The documented ceiling is a ceiling on the whole exchange.
  let payload: unknown;
  try {
    const response = await fetch(spec.path, {
      method: spec.method,
      headers: spec.body === undefined ? undefined : { "Content-Type": "application/json" },
      body: spec.body === undefined ? undefined : JSON.stringify(spec.body),
      signal: controller.signal,
    });

    try {
      payload = await response.json();
    } catch (error) {
      // An abort during the body read is a timeout, not an unreadable body —
      // otherwise a stalled response is reported as malformed JSON.
      if (isAbort(error)) return failure("timeout");
      // A proxy's HTML error page, or an empty body. Either way the envelope
      // promise is broken and there is nothing to read a code from.
      return failure("unreadable_response");
    }

    if (!response.ok) return toFailure(payload);
  } catch (error) {
    // Nothing from `error` reaches the caller: a DOMException's message is
    // browser-specific text, not product copy.
    return failure(isAbort(error) ? "timeout" : "unreachable");
  } finally {
    clearTimeout(timer);
  }

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
  // Every code now keeps the server's authored message, which is more specific
  // than anything this build could invent.
  //
  // Story 2.2 carried one narrow exception here: `output_exists`, whose server copy
  // told the user to "choose a different output path" — a remedy the UI is
  // forbidden to offer, because `output_path` is server-owned and read-only to the
  // browser (Story 2.0 AC 13). Story 2.3 owns error copy and fixed that sentence at
  // its source (`api/build.py`), so the client-side override has been removed
  // rather than left to mask a defect that no longer exists. Two places stating the
  // same fact is how they drift.
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
  if (llm && llm.model.length > MAX_MODEL_ID_LENGTH) {
    return tooLong("A model id", MAX_MODEL_ID_LENGTH);
  }
  return null;
}
