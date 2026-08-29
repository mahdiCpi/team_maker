import { NextRequest } from "next/server";
import { afterEach, describe, expect, it } from "vitest";

import { middleware } from "../middleware";

describe("middleware (My Teams auth-wiring regression, story_4_8)", () => {
  const originalKey = process.env.TEAM_MAKER_API_KEY;

  afterEach(() => {
    if (originalKey === undefined) delete process.env.TEAM_MAKER_API_KEY;
    else process.env.TEAM_MAKER_API_KEY = originalKey;
  });

  it("attaches X-API-Key to proxied /api requests when the key is configured", () => {
    process.env.TEAM_MAKER_API_KEY = "test-key-123";

    const response = middleware(new NextRequest("http://localhost:3000/api/teams/browse"));

    expect(response.headers.get("x-middleware-request-x-api-key")).toBe("test-key-123");
  });

  it("does not fabricate a key when TEAM_MAKER_API_KEY is unset, matching the backend's fail-closed default", () => {
    delete process.env.TEAM_MAKER_API_KEY;

    const response = middleware(new NextRequest("http://localhost:3000/api/teams/browse"));

    expect(response.headers.get("x-middleware-request-x-api-key")).toBeNull();
  });
});
