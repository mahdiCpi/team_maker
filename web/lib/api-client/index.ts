/**
 * The single place in the frontend that talks to `/api`.
 *
 * Every request is same-origin: `web/next.config.ts` rewrites `/api/:path*` to
 * the FastAPI process, so there is no base URL to configure, no CORS, and no
 * credentials mode. Nothing here reads or sends an API key — AD-9 means the
 * request may *name* a provider and the server resolves the credential from the
 * Key Config, and `EXPERIENCE.md:103` bans key entry in the UI outright.
 *
 * The public surface is one function per route, each returning an `ApiResult`
 * the caller branches on by `code`. Nothing throws: a failure is a value,
 * because `EXPERIENCE.md:104` bans hiding a blocked action behind a silent
 * failure and an exception at a component boundary is exactly that.
 *
 * Split into one module per route group (Story 2.4's reorganisation, once
 * adding the `run` group pushed the former single `api-client.ts` to 599
 * lines — well past CLAUDE.md's ~400-line guideline). This barrel re-exports
 * everything so `@/lib/api-client` keeps resolving to the same public
 * surface and no importer needed to change.
 *
 * - `transport.ts` — the `fetch` wrapper and failure-shaping (internal).
 * - `compose.ts` — the compose seam's routes (Story 2.0–2.2).
 * - `keys.ts` — key-status routes (Story 2.3).
 * - `run.ts` — run/team-plan/transcript routes (Story 2.4).
 */
export * from "@/lib/api-types";
export * from "./compose";
export * from "./keys";
export * from "./run";
