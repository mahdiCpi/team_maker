/**
 * The `fetch` wrapper and failure-shaping shared by every route module in
 * this package.
 *
 * Split out of the former single `api-client.ts` in Story 2.4, once adding
 * the `run` group's routes pushed that file to 599 lines — well past
 * CLAUDE.md's ~400-line guideline. Internal to `lib/api-client/`: route
 * modules import from here, but nothing outside this package does.
 */
import {
  type ApiErrorCode,
  type ApiFailure,
  type ApiResult,
  type FieldIssue,
  isServerErrorCode,
  parseErrorEnvelope,
} from "@/lib/api-types";

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
  // Story 2.4's run group. The server's own message is usually more specific
  // (it names the provider and the fix, or the inconsistency); these are the
  // fallback for a missing or leak-flagged one.
  team_not_found:
    "That team could not be found. It may have been removed, or the link may be out of date.",
  run_blocked: "This run could not start. See the reason above, or check your Key Config.",
  run_in_progress:
    "Another run is already in progress. Wait for it to finish before starting another.",
  run_not_found:
    "That run is no longer available. It may have finished long enough ago to be cleared.",
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

export function failure(
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

export function tooLong(what: string, limit: number): ApiFailure {
  return failure("too_long", `${what} must be ${limit} characters or fewer.`);
}

export type RequestSpec = {
  path: string;
  method: "GET" | "POST" | "PUT" | "DELETE";
  body?: unknown;
  timeoutMs: number;
};

export async function request<T>(
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
