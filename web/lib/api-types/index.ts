/**
 * The boundary between the API's wire payloads and what the frontend renders.
 *
 * Split into one module per domain (Story 2.4's reorganisation, once adding
 * the `run` group pushed the former single `api-types.ts` to 801 lines — well
 * past CLAUDE.md's ~400-line guideline, mirroring `api/schemas.py`'s own
 * split-if-crossed-400 rule on the Python side). This barrel re-exports
 * everything so `@/lib/api-types` keeps resolving to the same public surface
 * and no importer needed to change.
 *
 * - `primitives.ts` — narrowing helpers shared by every parser.
 * - `errors.ts` — the error envelope's codes and shape.
 * - `compose.ts` — the compose seam's spec/session/build views (Story 2.0–2.2).
 * - `keys.ts` — key-status views (Story 2.3).
 * - `run.ts` — run/team-plan/transcript views (Story 2.4).
 */
export * from "./compose";
export * from "./errors";
export * from "./keys";
export * from "./run";
