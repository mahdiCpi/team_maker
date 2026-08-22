import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/**
 * Story 4.1 (api/deps.py) made every /api/teams/* route fail closed without a
 * matching X-API-Key header, but nothing ever attached that header to the
 * browser's same-origin fetch calls (lib/api-client/transport.ts) — so the
 * local web app locked itself out of its own backend (Epic 4 regression,
 * story_4_8).
 *
 * Middleware runs server-side, before next.config.ts's rewrite forwards the
 * request to FastAPI, so it is the one place that can attach the key without
 * ever exposing it to browser JS. TEAM_MAKER_API_KEY must be set in the Next
 * process's own environment (e.g. web/.env.local) to the same value the
 * FastAPI process uses.
 */
export function middleware(request: NextRequest) {
  const apiKey = process.env.TEAM_MAKER_API_KEY;
  if (!apiKey) return NextResponse.next();

  const headers = new Headers(request.headers);
  headers.set("X-API-Key", apiKey);
  return NextResponse.next({ request: { headers } });
}

export const config = {
  matcher: "/api/:path*",
};
