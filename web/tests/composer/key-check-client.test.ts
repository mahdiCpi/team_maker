import { afterEach, describe, expect, it, vi } from "vitest";

import { getKeyCheck, getKeyStatus, parseKeyCheck, parseKeyStatus } from "@/lib/api-client";

import {
  keyCheckAllGood,
  keyCheckMissingKey,
  keyStatusHasKeys,
  keyStatusNoKeys,
} from "./fixtures";
import { createFetchQueue } from "./harness";

/**
 * The client half of the key-status group (Story 2.3, AC 1 / AC 2).
 *
 * STUB: `fetch` is replaced by `createFetchQueue`. The bodies are **verbatim
 * captures from a live server** (see `fixtures/index.ts`), so this proves the real
 * parsers handle the real wire format — but the transport is fake and none of it
 * is evidence that a real provider is reachable (CLAUDE.md test transparency).
 */

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("parseKeyStatus", () => {
  it("narrows the captured provider report", () => {
    const parsed = parseKeyStatus(keyStatusHasKeys);

    expect(parsed).not.toBeNull();
    expect(parsed!.overall).toBe("has-keys");
    expect(parsed!.providers).toHaveLength(7);
    expect(parsed!.any_key_present).toBe(true);
  });

  it("keeps the five statuses verbatim rather than re-spelling them", () => {
    const parsed = parseKeyStatus(keyStatusNoKeys)!;
    const byName = new Map(parsed.providers.map((p) => [p.name, p]));

    expect(byName.get("anthropic")!.status).toBe("missing");
    expect(byName.get("ollama")!.status).toBe("keyless-local");
    expect(byName.get("groq")!.status).toBe("unsupported-by-runtime");
  });

  it("reads no-keys from the server rather than deriving it from usability", () => {
    // The captured proof of the trap: nothing is configured, yet a provider IS
    // usable. A client that recomputed this from `usable` would disagree with the
    // server it is rendering.
    const parsed = parseKeyStatus(keyStatusNoKeys)!;

    expect(parsed.overall).toBe("no-keys");
    expect(parsed.any_key_present).toBe(false);
    expect(parsed.providers.some((p) => p.usable)).toBe(true);
  });

  it("carries the Key Config path, which is what makes the hint actionable", () => {
    expect(parseKeyStatus(keyStatusHasKeys)!.key_config_path).toMatch(/team_maker\.keys$/);
  });

  it("defaults a malformed providers list instead of refusing the payload", () => {
    // Deliberately NOT a refusal. Returning null here propagated up and made the
    // whole check unreadable, which — via `keyCheck: null` — used to disable the
    // build gate. No consumer renders `providers`, so it must not be able to do
    // that. The fields the gate depends on are still refused (see below).
    const parsed = parseKeyStatus({
      ...(keyStatusHasKeys as object),
      providers: null,
    });

    expect(parsed).not.toBeNull();
    expect(parsed!.providers).toEqual([]);
    expect(parsed!.overall).toBe("has-keys");
  });

  it("refuses a payload with no overall verdict", () => {
    const { overall, ...rest } = keyStatusHasKeys as Record<string, unknown>;
    void overall;
    expect(parseKeyStatus(rest)).toBeNull();
  });

  it("accepts an overall value this build has never heard of", () => {
    // An earlier version closed this union, so one new server aggregate made the
    // parse fail — silently removing the panel AND the gate. The field the gate keys
    // on must never fail closed on an unrecognised value.
    const parsed = parseKeyStatus({
      ...(keyStatusHasKeys as object),
      overall: "some-future-aggregate",
    });

    expect(parsed).not.toBeNull();
    expect(parsed!.overall).toBe("some-future-aggregate");
  });

  it("reports where each credential actually came from", () => {
    const byName = new Map(
      parseKeyStatus(keyStatusHasKeys)!.providers.map((p) => [p.name, p])
    );

    expect(byName.get("anthropic")!.credential_source).toBe("key-config");
    // A keyless provider needs none.
    expect(byName.get("ollama")!.credential_source).toBe("none");
  });
});

describe("parseKeyCheck", () => {
  it("narrows the captured all-good check", () => {
    const parsed = parseKeyCheck(keyCheckAllGood)!;

    expect(parsed.overall).toBe("all-good");
    expect(parsed.blocked).toBe(false);
    expect(parsed.blocking_reason).toBeNull();
    expect(parsed.roles.map((r) => r.role)).toEqual(["researcher", "writer", "critic"]);
  });

  it("marks roles that inherited the server-side default", () => {
    // The browser cannot compute this: it does not know `default_llm`.
    const parsed = parseKeyCheck(keyCheckAllGood)!;

    expect(parsed.roles.every((r) => r.inherited_default)).toBe(true);
    expect(parsed.roles[0].provider).toBe("anthropic");
  });

  it("narrows the captured blocked check, keeping the reason and the hint", () => {
    const parsed = parseKeyCheck(keyCheckMissingKey)!;

    expect(parsed.overall).toBe("unsupported");
    expect(parsed.blocked).toBe(true);
    expect(parsed.blocking_reason).toContain("cannot run yet");
    const judge = parsed.roles.find((r) => r.role === "judge")!;
    expect(judge.usable).toBe(false);
    expect(judge.fix_hint).toContain("no native groq provider");
  });

  it("refuses a payload whose roles list is not an array", () => {
    expect(parseKeyCheck({ ...(keyCheckAllGood as object), roles: 0 })).toBeNull();
  });

  it("does not coerce a missing `blocked` into false", () => {
    // Reporting "not blocked" when the server never said so would let a build the
    // server considers unrunnable look fine.
    const { blocked, ...rest } = keyCheckAllGood as Record<string, unknown>;
    void blocked;
    expect(parseKeyCheck(rest)).toBeNull();
  });
});

describe("the two routes", () => {
  // The harness routes `/api/keys/*` through its own queue and log, so that suites
  // predating these routes keep `requests` meaning "compose calls".
  it("GETs the provider status from the same-origin path", async () => {
    const queue = createFetchQueue();
    queue.install();
    queue.queueKeyStatus(200, keyStatusHasKeys);

    const result = await getKeyStatus();

    expect(result.ok).toBe(true);
    expect(queue.keyRequests[0].url).toBe("/api/keys/status");
    expect(queue.keyRequests[0].method).toBe("GET");
    // AD-9: a status read sends nothing, least of all a key.
    expect(queue.keyRequests[0].body).toBeUndefined();
  });

  it("GETs the per-session check with the id encoded", async () => {
    const queue = createFetchQueue();
    queue.install();
    queue.queueKeyCheck(200, keyCheckAllGood);

    await getKeyCheck("a/b");

    expect(queue.keyRequests[0].url).toBe("/api/keys/check/a%2Fb");
  });

  it("reports an unreachable API as a failure value rather than throwing", async () => {
    const queue = createFetchQueue();
    queue.install();
    queue.queueKeyStatusReject(new TypeError("Failed to fetch"));

    const result = await getKeyStatus();

    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.code).toBe("unreachable");
  });

  it("maps a 404 on the check onto the session_not_found envelope", async () => {
    const queue = createFetchQueue();
    queue.install();
    queue.queueKeyCheck(404, {
      error: { code: "session_not_found", message: "That conversation is no longer available." },
    });

    const result = await getKeyCheck("gone");

    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.code).toBe("session_not_found");
  });
});
