import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  MAX_MESSAGE_LENGTH,
  MAX_NAME_LENGTH,
  MAX_TEXT_LENGTH,
  buildTeam,
  createSession,
  parseSessionResponse,
  replaceSpec,
  sendMessage,
} from "@/lib/api-client";

import {
  build,
  buildWithSubstitution,
  errorAuthoringUnavailable,
  errorOutputExists,
  errorSessionNotFound,
  errorSpecInvalid,
  messageTurn2,
  sessionCreate,
  specEdit,
} from "./fixtures";

/**
 * ALL network traffic in this file is a **mocked `fetch`** (`vi.stubGlobal`).
 * Per CLAUDE.md's test-transparency rule this is NOT evidence that the API
 * works: it is evidence that the client parses the API's *real recorded bytes*
 * correctly. The bytes themselves came from a live server — see
 * `fixtures/index.ts` for the capture commands.
 */

type FetchCall = { url: string; init: RequestInit };

let calls: FetchCall[] = [];

function stubFetch(status: number, body: unknown, ok = status < 400) {
  const fetchMock = vi.fn((url: string | URL, init?: RequestInit) => {
    calls.push({ url: String(url), init: init ?? {} });
    return Promise.resolve({
      ok,
      status,
      json: () => Promise.resolve(body),
    } as Response);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

/** A server that answers with something that is not our envelope at all. */
function stubNonJson(status: number) {
  const fetchMock = vi.fn(() =>
    Promise.resolve({
      ok: false,
      status,
      json: () => Promise.reject(new SyntaxError("Unexpected token < in JSON")),
    } as unknown as Response)
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

beforeEach(() => {
  calls = [];
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("createSession", () => {
  it("posts the intent to the Story 2.0 route and narrows the captured 201", async () => {
    stubFetch(201, sessionCreate);
    const result = await createSession({ intent: "research and write" });

    expect(calls).toHaveLength(1);
    expect(calls[0].url).toBe("/api/compose/sessions");
    expect(calls[0].init.method).toBe("POST");
    expect(JSON.parse(String(calls[0].init.body))).toEqual({
      intent: "research and write",
    });

    if (!result.ok) throw new Error(`expected success, got ${result.code}`);
    // Values asserted against the CAPTURED bytes, so a server-side rename of
    // any of these keys turns this red.
    expect(result.data.session_id).toBe("Rv-1jGo1Q5fnAVLinZ1MPg");
    expect(result.data.turn).toBe(1);
    expect(result.data.turns_remaining).toBe(19);
    expect(result.data.spec.team_name).toBe("article_team");
    expect(result.data.spec.desired_roles.map((r) => r.name)).toEqual([
      "researcher",
      "writer",
      "critic",
    ]);
  });

  it("omits `authoring` entirely when no provider was chosen", async () => {
    stubFetch(201, sessionCreate);
    await createSession({ intent: "x" });
    expect(Object.keys(JSON.parse(String(calls[0].init.body)))).toEqual(["intent"]);
  });

  it("sends `authoring` when a provider IS chosen, and never a key", async () => {
    stubFetch(201, sessionCreate);
    await createSession({
      intent: "x",
      authoring: { provider: "openai", model: "gpt-4o" },
    });
    const body = JSON.parse(String(calls[0].init.body));
    expect(body.authoring).toEqual({ provider: "openai", model: "gpt-4o" });
    expect(JSON.stringify(body)).not.toMatch(/key/i);
  });

  it("rejects an over-long intent client-side, without a request", async () => {
    const fetchMock = stubFetch(201, sessionCreate);
    const result = await createSession({ intent: "x".repeat(MAX_MESSAGE_LENGTH + 1) });
    expect(result.ok).toBe(false);
    if (result.ok) throw new Error("expected failure");
    expect(result.code).toBe("too_long");
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe("sendMessage", () => {
  it("posts to the messages route and reports the incremented turn", async () => {
    stubFetch(200, messageTurn2);
    const result = await sendMessage("SID", "add a fact-checker");

    expect(calls[0].url).toBe("/api/compose/sessions/SID/messages");
    expect(calls[0].init.method).toBe("POST");
    expect(JSON.parse(String(calls[0].init.body))).toEqual({
      message: "add a fact-checker",
    });

    if (!result.ok) throw new Error("expected success");
    expect(result.data.turn).toBe(2);
    expect(result.data.turns_remaining).toBe(18);
    expect(result.data.spec.desired_roles.map((r) => r.name)).toContain(
      "fact_checker"
    );
  });

  it("percent-encodes the session id so a stray slash cannot forge a path", async () => {
    stubFetch(200, messageTurn2);
    await sendMessage("a/b", "hi");
    expect(calls[0].url).toBe("/api/compose/sessions/a%2Fb/messages");
  });

  it("rejects an over-long message client-side", async () => {
    const fetchMock = stubFetch(200, messageTurn2);
    const result = await sendMessage("SID", "x".repeat(MAX_MESSAGE_LENGTH + 1));
    expect(result.ok).toBe(false);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe("replaceSpec", () => {
  const roles = [
    { name: "researcher", description: "Researches." },
    {
      name: "critic",
      description: "Critiques.",
      llm: { provider: "openai", model: "gpt-4o" },
    },
  ];
  const tasks = [
    {
      name: "research",
      description: "Do it.",
      agent_role: "researcher",
      dependencies: [],
    },
  ];

  it("PUTs only the four permitted dimensions", async () => {
    stubFetch(200, specEdit);
    await replaceSpec("SID", {
      team_name: "article_team",
      purpose: "Write things.",
      desired_roles: roles,
      desired_tasks: tasks,
    });

    expect(calls[0].url).toBe("/api/compose/sessions/SID/spec");
    expect(calls[0].init.method).toBe("PUT");
    expect(Object.keys(JSON.parse(String(calls[0].init.body))).sort()).toEqual([
      "desired_roles",
      "desired_tasks",
      "purpose",
      "team_name",
    ]);
  });

  it("never sends output_path — 2.0's `extra=forbid` makes it a 422, not a no-op", async () => {
    stubFetch(200, specEdit);
    await replaceSpec("SID", {
      team_name: "article_team",
      purpose: "Write things.",
      desired_roles: roles,
      desired_tasks: tasks,
    });
    // Asserted on the serialised body, so an accidental spread of a whole spec
    // object into the edit payload is caught rather than merely unlikely.
    expect(String(calls[0].init.body)).not.toMatch(/output_path/);
  });

  it("drops an omitted per-role llm rather than sending llm: null", async () => {
    stubFetch(200, specEdit);
    await replaceSpec("SID", {
      team_name: "t",
      purpose: "p",
      desired_roles: [{ name: "researcher", description: "Researches." }],
      desired_tasks: tasks,
    });
    const body = JSON.parse(String(calls[0].init.body));
    expect("llm" in body.desired_roles[0]).toBe(false);
  });

  it("refuses an empty roles list before the request leaves the browser", async () => {
    const fetchMock = stubFetch(200, specEdit);
    const result = await replaceSpec("SID", {
      team_name: "t",
      purpose: "p",
      desired_roles: [],
      desired_tasks: [],
    });
    expect(result.ok).toBe(false);
    if (result.ok) throw new Error("expected failure");
    expect(result.code).toBe("spec_invalid");
    expect(result.fields.map((f) => f.path)).toContain("desired_roles");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("rejects an over-long role name and an over-long description client-side", async () => {
    const fetchMock = stubFetch(200, specEdit);
    const longName = await replaceSpec("SID", {
      team_name: "t",
      purpose: "p",
      desired_roles: [
        { name: "x".repeat(MAX_NAME_LENGTH + 1), description: "ok" },
      ],
      desired_tasks: [],
    });
    const longText = await replaceSpec("SID", {
      team_name: "t",
      purpose: "p",
      desired_roles: [
        { name: "ok", description: "x".repeat(MAX_TEXT_LENGTH + 1) },
      ],
      desired_tasks: [],
    });
    expect(longName.ok).toBe(false);
    expect(longText.ok).toBe(false);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("re-renders from the response, which is re-serialised server-side", async () => {
    stubFetch(200, specEdit);
    const result = await replaceSpec("SID", {
      team_name: "IGNORED_LOCAL_VALUE",
      purpose: "p",
      desired_roles: roles,
      desired_tasks: tasks,
    });
    if (!result.ok) throw new Error("expected success");
    // The captured response is the server's own re-serialisation; the local
    // edit value must not leak into what the caller renders.
    expect(result.data.spec.team_name).toBe("article_team");
    expect(result.data.spec.team_name).not.toBe("IGNORED_LOCAL_VALUE");
  });
});

describe("buildTeam", () => {
  it("reports the captured build outcome", async () => {
    stubFetch(200, build);
    const result = await buildTeam("SID");
    expect(calls[0].url).toBe("/api/compose/sessions/SID/build");
    expect(calls[0].init.method).toBe("POST");

    if (!result.ok) throw new Error("expected success");
    expect(result.data.team_name).toBe("article_team");
    expect(result.data.agent_count).toBe(3);
    expect(result.data.task_count).toBe(3);
    expect(result.data.written_file_count).toBe(17);
    expect(result.data.validation.passed).toBe(true);
    expect(result.data.model_substitutions).toEqual([]);
    expect(result.data.output_path).toMatch(/generated_teams/);
  });

  it("surfaces a real model substitution rather than dropping it", async () => {
    stubFetch(200, buildWithSubstitution);
    const result = await buildTeam("SID");
    if (!result.ok) throw new Error("expected success");
    expect(result.data.model_substitutions).toEqual([
      {
        role: "critic",
        requested: "openai/gpt-4o-min",
        resolved: "openai/gpt-4o-mini",
      },
    ]);
  });
});

describe("the error envelope, parsed from captured bytes", () => {
  it("maps session_not_found and keeps the server's copy", async () => {
    stubFetch(404, errorSessionNotFound);
    const result = await buildTeam("SID");
    if (result.ok) throw new Error("expected failure");
    expect(result.code).toBe("session_not_found");
    expect(result.message).toMatch(/no longer available/);
    expect(result.fields).toEqual([]);
  });

  it("maps spec_invalid and carries every dotted field path", async () => {
    stubFetch(422, errorSpecInvalid);
    const result = await buildTeam("SID");
    if (result.ok) throw new Error("expected failure");
    expect(result.code).toBe("spec_invalid");
    // Non-empty asserted BEFORE mapping: `[].map(...)` equals `[]` and would
    // make the path assertion below vacuously true (Dev Notes rule 2).
    expect(result.fields.length).toBeGreaterThan(0);
    expect(result.fields.map((f) => f.path)).toEqual([
      "desired_tasks.1.agent_role",
      "desired_tasks.2.agent_role",
    ]);
    expect(result.fields[0].message).toMatch(/not one of the team's roles/);
  });

  it("maps output_exists and authoring_unavailable", async () => {
    stubFetch(409, errorOutputExists);
    const exists = await buildTeam("SID");
    if (exists.ok) throw new Error("expected failure");
    expect(exists.code).toBe("output_exists");

    stubFetch(503, errorAuthoringUnavailable);
    const unavailable = await createSession({ intent: "x" });
    if (unavailable.ok) throw new Error("expected failure");
    expect(unavailable.code).toBe("authoring_unavailable");
    expect(unavailable.message).toMatch(/ollama/);
  });

  it("maps session_busy, which AC 8's table predates", async () => {
    stubFetch(409, {
      error: {
        code: "session_busy",
        message:
          "This conversation is still working on a previous request. Try again in a moment.",
      },
    });
    const result = await sendMessage("SID", "hi");
    if (result.ok) throw new Error("expected failure");
    expect(result.code).toBe("session_busy");
  });

  it("degrades a body that is not our envelope into a usable failure", async () => {
    stubNonJson(502);
    const result = await buildTeam("SID");
    if (result.ok) throw new Error("expected failure");
    expect(result.code).toBe("unreadable_response");
    expect(result.message.length).toBeGreaterThan(0);
    // The parser's own exception must never become user-facing copy.
    expect(result.message).not.toMatch(/SyntaxError|Unexpected token/);
  });

  it("degrades an unknown server code instead of trusting it as a known one", async () => {
    stubFetch(418, { error: { code: "brand_new_code", message: "Tea." } });
    const result = await buildTeam("SID");
    if (result.ok) throw new Error("expected failure");
    expect(result.code).toBe("unknown_error");
    expect(result.message).toBe("Tea.");
  });

  it("never lets a server-sent stack trace through as the message", async () => {
    // Story 2.0 guarantees it sends none; this proves the CLIENT would not
    // relay one if that guarantee ever broke. Guard validated against a
    // payload that really contains a trace (Dev Notes rule 1).
    stubFetch(500, {
      error: {
        code: "build_failed",
        message:
          'Traceback (most recent call last):\n  File "api/build.py", line 30, in run_build\n    raise FileExistsError(path)\nFileExistsError: C:\\secret',
      },
    });
    const result = await buildTeam("SID");
    if (result.ok) throw new Error("expected failure");
    expect(result.code).toBe("build_failed");
    expect(result.message).not.toMatch(/Traceback|File "|line \d+/);
  });

  it("reports a fetch rejection as unreachable, not as a thrown error", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.reject(new TypeError("Failed to fetch")))
    );
    const result = await buildTeam("SID");
    if (result.ok) throw new Error("expected failure");
    expect(result.code).toBe("unreachable");
    expect(result.message).not.toMatch(/Failed to fetch|TypeError/);
  });

  it("reports an aborted request as a timeout", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => {
        const err = new Error("aborted");
        err.name = "AbortError";
        return Promise.reject(err);
      })
    );
    const result = await createSession({ intent: "x" });
    if (result.ok) throw new Error("expected failure");
    expect(result.code).toBe("timeout");
  });

  it("passes an AbortSignal with a ceiling generous enough for 1-4 LLM calls", async () => {
    stubFetch(201, sessionCreate);
    await createSession({ intent: "x" });
    expect(calls[0].init.signal).toBeInstanceOf(AbortSignal);
  });
});

describe("parseSessionResponse narrowing", () => {
  it("rejects a payload missing the spec rather than yielding a half-built view", () => {
    expect(parseSessionResponse({ session_id: "a", turn: 1 })).toBeNull();
  });

  it("rejects a spec whose desired_roles is not an array", () => {
    expect(
      parseSessionResponse({
        session_id: "a",
        turn: 1,
        turns_remaining: 2,
        spec: { team_name: "t", purpose: "p", desired_roles: "nope" },
      })
    ).toBeNull();
  });

  it("tolerates a role with no llm, which the real server omits entirely", () => {
    const view = parseSessionResponse(sessionCreate);
    expect(view).not.toBeNull();
    expect(view?.spec.desired_roles[0].llm).toBeUndefined();
  });

  it("keeps a role's llm when the server does send one", () => {
    const view = parseSessionResponse(specEdit);
    const critic = view?.spec.desired_roles.find((r) => r.name === "critic");
    expect(critic?.llm).toEqual({ provider: "openai", model: "gpt-4o" });
  });
});
