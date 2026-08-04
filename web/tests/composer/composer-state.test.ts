import { describe, expect, it } from "vitest";

import {
  INITIAL_COMPOSER_STATE,
  composerReducer,
  type ComposerState,
} from "@/components/composer/composer-state";
import { parseBuildResponse, parseSessionResponse } from "@/lib/api-client";
import type { ApiFailure, BuildResultView, SessionView } from "@/lib/api-types";

import {
  build,
  buildWithSubstitution,
  messageTurn2,
  sessionCreate,
} from "./fixtures";

/** Pure reducer unit tests. No network, no mocks, no component rendering. */

function session(payload: unknown): SessionView {
  const view = parseSessionResponse(payload);
  if (!view) throw new Error("fixture failed to parse");
  return view;
}

function buildResult(payload: unknown): BuildResultView {
  const view = parseBuildResponse(payload);
  if (!view) throw new Error("fixture failed to parse");
  return view;
}

const TURN_1 = session(sessionCreate);
const TURN_2 = session(messageTurn2);
const BUILD_OK = buildResult(build);
const BUILD_SUBBED = buildResult(buildWithSubstitution);

function failure(code: ApiFailure["code"], message = "nope"): ApiFailure {
  return { ok: false, code, message, fields: [] };
}

function run(actions: Parameters<typeof composerReducer>[1][]): ComposerState {
  return actions.reduce(composerReducer, INITIAL_COMPOSER_STATE);
}

/** The state after a successful first turn — the base for most cases below. */
const AFTER_FIRST_TURN = run([
  { type: "turn_requested", text: "research and write" },
  { type: "turn_succeeded", session: TURN_1 },
]);

describe("the initial state", () => {
  it("starts with no session, no spec, an empty transcript and review off", () => {
    expect(INITIAL_COMPOSER_STATE.sessionId).toBeNull();
    expect(INITIAL_COMPOSER_STATE.spec).toBeNull();
    expect(INITIAL_COMPOSER_STATE.transcript).toEqual([]);
    expect(INITIAL_COMPOSER_STATE.reviewBeforeBuild).toBe(false);
    expect(INITIAL_COMPOSER_STATE.pending).toBeNull();
  });
});

describe("a turn", () => {
  it("appends the user's words immediately and marks the turn pending", () => {
    const state = run([{ type: "turn_requested", text: "research and write" }]);
    expect(state.transcript).toHaveLength(1);
    expect(state.transcript[0]).toMatchObject({
      author: "user",
      text: "research and write",
    });
    expect(state.pending).toBe("turn");
  });

  it("appends an assistant reply naming the roles in pipeline order", () => {
    expect(AFTER_FIRST_TURN.transcript).toHaveLength(2);
    const reply = AFTER_FIRST_TURN.transcript[1];
    expect(reply.author).toBe("assistant");
    expect(reply.text).toContain("researcher");
    expect(reply.text).toContain("critic");
    expect(AFTER_FIRST_TURN.pending).toBeNull();
    expect(AFTER_FIRST_TURN.sessionId).toBe(TURN_1.session_id);
    expect(AFTER_FIRST_TURN.spec?.team_name).toBe("article_team");
  });

  it("gives every transcript entry a distinct id", () => {
    const state = run([
      { type: "turn_requested", text: "a" },
      { type: "turn_succeeded", session: TURN_1 },
      { type: "turn_requested", text: "a" },
      { type: "turn_succeeded", session: TURN_2 },
    ]);
    const ids = state.transcript.map((entry) => entry.id);
    expect(ids).toHaveLength(4);
    expect(new Set(ids).size).toBe(4);
  });

  it("allows a second turn after the first valid spec with review off (AC 4)", () => {
    const state = run([
      { type: "turn_requested", text: "research and write" },
      { type: "turn_succeeded", session: TURN_1 },
      { type: "turn_requested", text: "add a fact-checker" },
      { type: "turn_succeeded", session: TURN_2 },
    ]);
    expect(state.reviewBeforeBuild).toBe(false);
    expect(state.turn).toBe(2);
    expect(state.transcript).toHaveLength(4);
    // Nothing auto-built: `epics.md:321` governs what happens at build time,
    // not when a build is triggered.
    expect(state.build).toBeNull();
    expect(state.spec?.desired_roles.map((r) => r.name)).toContain("fact_checker");
  });

  it("tracks the turn counters the server reports", () => {
    expect(AFTER_FIRST_TURN.turn).toBe(1);
    expect(AFTER_FIRST_TURN.turnsRemaining).toBe(19);
  });
});

describe("a failed turn", () => {
  it("keeps the transcript and the last good spec, and clears pending", () => {
    const state = composerReducer(
      composerReducer(AFTER_FIRST_TURN, {
        type: "turn_requested",
        text: "break it",
      }),
      { type: "turn_failed", failure: failure("compose_failed") }
    );
    expect(state.pending).toBeNull();
    expect(state.failure?.code).toBe("compose_failed");
    // The user's words survive so the retry does not require retyping.
    expect(state.transcript).toHaveLength(3);
    expect(state.spec?.team_name).toBe("article_team");
    expect(state.spec?.desired_roles).toHaveLength(3);
  });

  it("leaves the session usable, so a retry is possible", () => {
    const failed = composerReducer(AFTER_FIRST_TURN, {
      type: "turn_failed",
      failure: failure("compose_failed"),
    });
    expect(failed.expired).toBe(false);
    const retried = composerReducer(failed, {
      type: "turn_requested",
      text: "again",
    });
    expect(retried.pending).toBe("turn");
    expect(retried.failure).toBeNull();
  });

  it("marks the conversation expired ONLY for session_not_found", () => {
    const gone = composerReducer(AFTER_FIRST_TURN, {
      type: "turn_failed",
      failure: failure("session_not_found"),
    });
    expect(gone.expired).toBe(true);

    for (const code of [
      "compose_failed",
      "turn_cap_reached",
      "session_busy",
      "spec_invalid",
      "authoring_unavailable",
      "unreachable",
      "timeout",
    ] as const) {
      const state = composerReducer(AFTER_FIRST_TURN, {
        type: "turn_failed",
        failure: failure(code),
      });
      expect(state.expired, `${code} must not expire the conversation`).toBe(false);
    }
  });

  it("leaves the first failed intent without a session, so the retry creates one", () => {
    const state = run([
      { type: "turn_requested", text: "hello" },
      { type: "turn_failed", failure: failure("authoring_unavailable") },
    ]);
    expect(state.sessionId).toBeNull();
    expect(state.spec).toBeNull();
    expect(state.transcript).toHaveLength(1);
  });
});

describe("building", () => {
  it("reports the outcome inline and does not clear the transcript", () => {
    const state = composerReducer(
      composerReducer(AFTER_FIRST_TURN, { type: "build_requested" }),
      { type: "build_succeeded", result: BUILD_OK }
    );
    expect(state.pending).toBeNull();
    expect(state.build?.team_name).toBe("article_team");
    expect(state.build?.written_file_count).toBe(17);
    expect(state.transcript).toHaveLength(2);
  });

  it("carries model substitutions through untouched", () => {
    const state = composerReducer(AFTER_FIRST_TURN, {
      type: "build_succeeded",
      result: BUILD_SUBBED,
    });
    expect(state.build?.model_substitutions).toHaveLength(1);
    expect(state.build?.model_substitutions[0].resolved).toBe("openai/gpt-4o-mini");
  });

  it("closes the review editor when a build starts", () => {
    const open = composerReducer(AFTER_FIRST_TURN, { type: "editor_opened" });
    expect(open.editorOpen).toBe(true);
    const building = composerReducer(open, { type: "build_requested" });
    expect(building.editorOpen).toBe(false);
    expect(building.pending).toBe("build");
  });

  it("discards a previous build result when a new build starts", () => {
    const built = composerReducer(AFTER_FIRST_TURN, {
      type: "build_succeeded",
      result: BUILD_OK,
    });
    const rebuilding = composerReducer(built, { type: "build_requested" });
    // Otherwise a stale success panel sits next to a spinner and then next to
    // an output_exists error, claiming a build that this attempt did not do.
    expect(rebuilding.build).toBeNull();
  });

  it("keeps the spec after a failed build so the user can edit and retry", () => {
    const state = composerReducer(
      composerReducer(AFTER_FIRST_TURN, { type: "build_requested" }),
      { type: "build_failed", failure: failure("output_exists") }
    );
    expect(state.failure?.code).toBe("output_exists");
    expect(state.spec?.team_name).toBe("article_team");
    expect(state.build).toBeNull();
  });
});

describe("the review editor", () => {
  it("re-renders from the server's response, never from the local edit", () => {
    const state = composerReducer(AFTER_FIRST_TURN, {
      type: "spec_replaced",
      session: TURN_2,
    });
    expect(state.spec?.desired_roles.map((r) => r.name)).toEqual([
      "researcher",
      "writer",
      "fact_checker",
      "critic",
    ]);
  });

  it("stays open after a save, and bumps the revision the form is keyed on", () => {
    const open = composerReducer(AFTER_FIRST_TURN, { type: "editor_opened" });
    const saved = composerReducer(open, {
      type: "spec_replaced",
      session: TURN_2,
    });
    // Closing on success would hide the server's re-serialisation, which is the
    // one thing AC 4 requires the editor to render, and would leave the save
    // with no visible confirmation at all.
    expect(saved.editorOpen).toBe(true);
    expect(saved.specRevision).toBeGreaterThan(open.specRevision);
  });

  it("adds no transcript entry — an edit is not a conversational turn", () => {
    const before = AFTER_FIRST_TURN.transcript.length;
    const state = composerReducer(AFTER_FIRST_TURN, {
      type: "spec_replaced",
      session: TURN_2,
    });
    expect(state.transcript).toHaveLength(before);
  });

  it("keeps the editor open and preserves the good spec when an edit is invalid", () => {
    const open = composerReducer(AFTER_FIRST_TURN, { type: "editor_opened" });
    const rejected = composerReducer(open, {
      type: "spec_edit_failed",
      failure: {
        ok: false,
        code: "spec_invalid",
        message: "Those changes leave the task list inconsistent.",
        fields: [
          { path: "desired_tasks.1.agent_role", message: "Not one of the roles." },
        ],
      },
    });
    expect(rejected.editorOpen).toBe(true);
    expect(rejected.failure?.fields).toHaveLength(1);
    expect(rejected.spec?.desired_roles).toHaveLength(3);
    expect(rejected.spec?.desired_roles.map((r) => r.name)).not.toContain(
      "fact_checker"
    );
  });

  it("toggles review independently of everything else", () => {
    const on = composerReducer(AFTER_FIRST_TURN, {
      type: "review_toggled",
      enabled: true,
    });
    expect(on.reviewBeforeBuild).toBe(true);
    expect(on.editorOpen).toBe(false);
    expect(composerReducer(on, { type: "review_toggled", enabled: false })
      .reviewBeforeBuild).toBe(false);
  });
});

describe("starting over", () => {
  it("returns to the initial state but keeps the review preference", () => {
    const used = composerReducer(
      composerReducer(AFTER_FIRST_TURN, { type: "review_toggled", enabled: true }),
      { type: "turn_failed", failure: failure("session_not_found") }
    );
    const fresh = composerReducer(used, { type: "conversation_restarted" });
    expect(fresh.transcript).toEqual([]);
    expect(fresh.sessionId).toBeNull();
    expect(fresh.spec).toBeNull();
    expect(fresh.expired).toBe(false);
    expect(fresh.failure).toBeNull();
    expect(fresh.build).toBeNull();
    // A preference the user set is not a symptom of the dropped session.
    expect(fresh.reviewBeforeBuild).toBe(true);
  });

  it("does not reuse ids after a restart", () => {
    const fresh = composerReducer(AFTER_FIRST_TURN, {
      type: "conversation_restarted",
    });
    const reused = composerReducer(fresh, { type: "turn_requested", text: "x" });
    expect(AFTER_FIRST_TURN.transcript.map((e) => e.id)).not.toContain(
      reused.transcript[0].id
    );
  });
});

describe("dismissing a failure", () => {
  it("clears the message without touching the spec or transcript", () => {
    const failed = composerReducer(AFTER_FIRST_TURN, {
      type: "turn_failed",
      failure: failure("compose_failed"),
    });
    const cleared = composerReducer(failed, { type: "failure_dismissed" });
    expect(cleared.failure).toBeNull();
    expect(cleared.spec?.team_name).toBe("article_team");
    expect(cleared.transcript).toHaveLength(2);
  });
});
