/**
 * Captured API responses — the real bytes, not a hand-written mirror.
 *
 * Story 2.2 Dev Notes, rule 3 ("measuring a mirror"): Story 2.1 tested a
 * hand-maintained TypeScript copy of the tokens instead of the shipped CSS, and
 * the copy drifted. The same trap applies to `TeamCreationRequest`'s shape, so
 * the `.json` files beside this module are **verbatim response bodies** written
 * by `curl -o` against a live `api/` process. Nothing in them is authored, and
 * they must never be hand-edited — re-capture instead.
 *
 * ## Provenance
 *
 * Captured **2026-08-03** on branch `story_2_2`, against a live server started
 * with:
 *
 * ```
 * .venv/Scripts/python.exe -m uvicorn api.main:app --port 8000
 * ```
 *
 * The authoring provider was the real server default (`anthropic` /
 * `claude-sonnet-4-6`) reading a genuine key from `team_maker.keys`, so the
 * three `spec` payloads below are the output of real Claude authoring turns —
 * not a stubbed provider.
 *
 * | File | Command | Status |
 * |---|---|---|
 * | `session-create.json` | `curl -X POST /api/compose/sessions -d '{"intent":"a team that researches a topic, drafts an article, and critiques it"}'` | 201 |
 * | `message-turn-2.json` | `curl -X POST /api/compose/sessions/{id}/messages -d '{"message":"add a fact-checker between the writer and the critic"}'` | 200 |
 * | `spec-edit.json` | `curl -X PUT /api/compose/sessions/{id}/spec -d '{"team_name":…,"desired_roles":[…]}'` | 200 |
 * | `build.json` | `curl -X POST /api/compose/sessions/{id}/build` | 200 |
 * | `build-with-substitution.json` | same, after editing the critic's model to `gpt-4o-min` | 200 |
 * | `error-session-not-found.json` | `curl -X POST /api/compose/sessions/nope/messages -d '{"message":"hi"}'` | 404 |
 * | `error-spec-invalid.json` | `curl -X PUT …/spec -d '{"desired_roles":[{"name":"researcher",…}]}'` (orphans the other tasks) | 422 |
 * | `error-output-exists.json` | `curl -X POST …/build` a second time | 409 |
 * | `error-authoring-unavailable.json` | `curl -X POST /api/compose/sessions -d '{…,"authoring":{"provider":"ollama","model":"llama3"}}'` | 503 |
 *
 * ## What is NOT captured, and why
 *
 * Four of the server's error codes are **not** represented by a captured file:
 *
 * - `turn_cap_reached` — needs 20 real authoring turns to provoke.
 * - `compose_failed` — could not be provoked. A deliberately bogus model id
 *   (`claude-not-a-real-model`) returned **201**, not a fault, so the adapter
 *   evidently does not reject it.
 * - `build_failed` and `session_busy` — need an induced internal fault and a
 *   race respectively.
 *
 * Tests that exercise those four build the envelope inline from the copy in
 * `api/sessions.py:206-216`, `api/build.py:39-42` and
 * `api/routers/compose.py:218-223`. Those are **synthesised from the server's
 * own source strings, not captured** — stated plainly here because the envelope
 * *shape* is what the captures prove, and that shape is identical for every
 * code (`api/errors.py:101-105`).
 */
import buildWithSubstitution from "./build-with-substitution.json";
import build from "./build.json";
import errorAuthoringUnavailable from "./error-authoring-unavailable.json";
import errorOutputExists from "./error-output-exists.json";
import errorSessionNotFound from "./error-session-not-found.json";
import errorSpecInvalid from "./error-spec-invalid.json";
import messageTurn2 from "./message-turn-2.json";
import sessionCreate from "./session-create.json";
import specEdit from "./spec-edit.json";

/**
 * Typed as `unknown` on purpose. These are wire payloads; giving them a
 * TypeScript shape here would recreate the very mirror this module exists to
 * avoid, and would let a test assert against the mirror rather than the bytes.
 * Every consumer must narrow through the production parser.
 */
export const CAPTURED: Record<string, unknown> = {
  sessionCreate,
  messageTurn2,
  specEdit,
  build,
  buildWithSubstitution,
  errorSessionNotFound,
  errorSpecInvalid,
  errorOutputExists,
  errorAuthoringUnavailable,
};

export {
  build,
  buildWithSubstitution,
  errorAuthoringUnavailable,
  errorOutputExists,
  errorSessionNotFound,
  errorSpecInvalid,
  messageTurn2,
  sessionCreate,
  specEdit,
};
