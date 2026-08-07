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
 * | `error-authoring-unavailable.json` | `curl -X POST /api/compose/sessions -d '{…,"authoring":{"provider":"ollama","model":"llama3"}}'` | 503 |
 *
 * **`error-output-exists.json` was RE-captured on 2026-08-04**, not on the date
 * above: Story 2.3 changed that error's server copy, so the 2.2 body no longer
 * matches what the server sends. Re-captured with the same command
 * (`curl -X POST …/build` a second time, 409) against a live server on that date.
 * Recorded here rather than left under the 2.2 heading, because a capture attributed
 * to the wrong session is the stale-provenance trap this table exists to prevent.
 *
 * ### Story 2.3 — the key-status group
 *
 * Captured **2026-08-04** on branch `story_2_3`, and **re-captured the same day**
 * after the code review changed the contract: the aggregate now distinguishes
 * `unsupported` from `missing-key`, and every provider row carries
 * `credential_source` and `status_detail`. The pre-review bodies are gone rather
 * than kept, because a fixture is only worth anything if it is what the server
 * actually sends.
 *
 * The two `key-check-*` files came from the same real topology as above (real
 * uvicorn, real Claude authoring turn, genuine key from `team_maker.keys`). The two
 * `key-status-*` files were captured against a server pointed at a **throwaway Key
 * Config holding fake values**, so the reported status set is controlled rather than
 * a function of whichever keys the capturing machine happened to have:
 *
 * ```
 * # key-status-has-keys.json  (ANTHROPIC_API_KEY + OPENROUTER_API_KEY, both fake)
 * TEAM_MAKER_KEYS=C:\tm-capture\team_maker.keys uvicorn api.main:app --port 8200
 * # key-status-no-keys.json   (a file containing only a comment)
 * TEAM_MAKER_KEYS=C:\tm-capture\empty.keys      uvicorn api.main:app --port 8201
 * ```
 *
 * That capture path is deliberately outside a home directory: the first capture
 * embedded the developer's OS username in `key_config_path`, which the code review
 * flagged, and a fixture is committed forever.
 *
 * | File | Command | Status |
 * |---|---|---|
 * | `key-status-has-keys.json` | `curl /api/keys/status` | 200 |
 * | `key-status-no-keys.json` | `curl /api/keys/status` against the empty config | 200 |
 * | `key-check-all-good.json` | `curl /api/keys/check/{id}` after a real authoring turn | 200 |
 * | `key-check-missing-key.json` | same, after `PUT …/spec` pinned a role to `groq` | 200 |
 *
 * `key-status-no-keys.json` is the load-bearing one: it is real server evidence
 * that `any_key_present` is `false` and `overall` is `no-keys` **while
 * `ollama.usable` is `true`** — the "any usable provider" trap, proven against the
 * running server rather than argued about.
 *
 * `key-check-missing-key.json` pins a role to `groq` because that is unusable
 * regardless of which keys the capturing machine has, so the capture is
 * deterministic; it is also the provider whose fix hint must NOT say "add
 * GROQ_API_KEY". Note its aggregate is **`unsupported`**, not `missing-key` — groq's
 * key is not missing, and no key would help.
 *
 * These four carry a real `key_config_path`. It is a path, not a credential — no key
 * value appears in any captured body, which is the AD-9 guarantee
 * `tests/api/test_key_status.py` asserts directly.
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
import keyCheckAllGood from "./key-check-all-good.json";
import keyCheckMissingKey from "./key-check-missing-key.json";
import keyStatusHasKeys from "./key-status-has-keys.json";
import keyStatusNoKeys from "./key-status-no-keys.json";
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
  keyStatusHasKeys,
  keyStatusNoKeys,
  keyCheckAllGood,
  keyCheckMissingKey,
};

export {
  build,
  buildWithSubstitution,
  errorAuthoringUnavailable,
  errorOutputExists,
  errorSessionNotFound,
  errorSpecInvalid,
  keyCheckAllGood,
  keyCheckMissingKey,
  keyStatusHasKeys,
  keyStatusNoKeys,
  messageTurn2,
  sessionCreate,
  specEdit,
};
