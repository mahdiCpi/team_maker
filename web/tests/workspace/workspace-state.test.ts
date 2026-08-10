import { describe, expect, it } from "vitest";

import {
  INITIAL_WORKSPACE_STATE,
  currentTurn,
  isRunInFlight,
  workspaceReducer,
  type WorkspaceState,
} from "@/components/workspace/workspace-state";
import type { RunView } from "@/lib/api-types";

function run(overrides: Partial<RunView> = {}): RunView {
  return {
    status: "running",
    run_id: "run-1",
    team_slug: "haiku-team",
    team_name: "Haiku Team",
    tasks: [{ name: "draft", agent_role: "writer", dependencies: [] }],
    result: null,
    transcript_available: false,
    failure_reason: null,
    ...overrides,
  };
}

describe("workspaceReducer", () => {
  it("loads a plan", () => {
    const plan = { team_name: "Haiku Team", agents: [], tasks: [] };
    const state = workspaceReducer(INITIAL_WORKSPACE_STATE, {
      type: "plan_loaded",
      plan,
    });
    expect(state.plan).toBe(plan);
    expect(state.planFailed).toBe(false);
  });

  it("marks the plan as failed without touching a previously loaded plan", () => {
    const plan = { team_name: "Haiku Team", agents: [], tasks: [] };
    const loaded = workspaceReducer(INITIAL_WORKSPACE_STATE, { type: "plan_loaded", plan });
    const state = workspaceReducer(loaded, { type: "plan_load_failed" });
    expect(state.planFailed).toBe(true);
    expect(state.plan).toBe(plan);
  });

  it("attaches a document and clears any previous attach error", () => {
    const withError = workspaceReducer(INITIAL_WORKSPACE_STATE, {
      type: "document_attach_failed",
      reason: "not text",
    });
    const state = workspaceReducer(withError, {
      type: "document_attached",
      document: { name: "brief.txt", text: "Ship it." },
    });
    expect(state.documents).toEqual([{ id: "doc-0", name: "brief.txt", text: "Ship it." }]);
    expect(state.documentError).toBeNull();
  });

  it("removes a document by id, leaving a same-named sibling in place", () => {
    const attached = workspaceReducer(INITIAL_WORKSPACE_STATE, {
      type: "document_attached",
      document: { name: "brief.txt", text: "Ship it." },
    });
    // A second file with the *same basename* — picked from another directory.
    // Removing by name deleted both, and React saw duplicate keys.
    const twice = workspaceReducer(attached, {
      type: "document_attached",
      document: { name: "brief.txt", text: "A different brief." },
    });
    expect(twice.documents.map((document) => document.id)).toEqual(["doc-0", "doc-1"]);

    const state = workspaceReducer(twice, { type: "document_removed", id: "doc-0" });
    expect(state.documents).toEqual([
      { id: "doc-1", name: "brief.txt", text: "A different brief." },
    ]);
  });

  it("starts a run: appends a turn, clears documents, bumps the poll epoch", () => {
    const withDocs = workspaceReducer(INITIAL_WORKSPACE_STATE, {
      type: "document_attached",
      document: { name: "brief.txt", text: "Ship it." },
    });
    const state = workspaceReducer(withDocs, {
      type: "run_started",
      runId: "run-1",
      goal: "ship a v1",
      run: run(),
      sentDocumentIds: withDocs.documents.map((document) => document.id),
    });
    expect(state.turns).toEqual([{ runId: "run-1", goal: "ship a v1", run: run() }]);
    expect(state.documents).toEqual([]);
    expect(state.pollEpoch).toBe(INITIAL_WORKSPACE_STATE.pollEpoch + 1);
    expect(state.transcript).toBeNull();
    expect(state.transcriptDialogOpen).toBe(false);
  });

  it("records a run request failure without starting a turn, and bumps failureRevision", () => {
    const failure = { ok: false as const, code: "run_blocked" as const, message: "no", fields: [] };
    const state = workspaceReducer(INITIAL_WORKSPACE_STATE, {
      type: "run_request_failed",
      failure,
    });
    expect(state.runRequestFailure).toBe(failure);
    expect(state.turns).toEqual([]);
    expect(state.failureRevision).toBe(INITIAL_WORKSPACE_STATE.failureRevision + 1);
  });

  it("updates the matching turn's run on a poll response with the current epoch", () => {
    const started = workspaceReducer(INITIAL_WORKSPACE_STATE, {
      type: "run_started",
      runId: "run-1",
      goal: "ship a v1",
      run: run(),
      sentDocumentIds: [],
    });
    const completed = run({ status: "complete", result: { final_output: "done", task_results: [] } });
    const state = workspaceReducer(started, {
      type: "run_updated",
      run: completed,
      epoch: started.pollEpoch,
    });
    expect(currentTurn(state)?.run).toEqual(completed);
  });

  it("discards a poll response carrying a stale epoch", () => {
    const started = workspaceReducer(INITIAL_WORKSPACE_STATE, {
      type: "run_started",
      runId: "run-1",
      goal: "ship a v1",
      run: run(),
      sentDocumentIds: [],
    });
    const state = workspaceReducer(started, {
      type: "run_updated",
      run: run({ status: "complete" }),
      epoch: started.pollEpoch - 1, // a poll issued for a run since superseded
    });
    expect(currentTurn(state)?.run.status).toBe("running");
  });

  it("supports more than one run in a session, each its own turn", () => {
    const first = workspaceReducer(INITIAL_WORKSPACE_STATE, {
      type: "run_started",
      runId: "run-1",
      goal: "first goal",
      run: run({ run_id: "run-1" }),
      sentDocumentIds: [],
    });
    const second = workspaceReducer(first, {
      type: "run_started",
      runId: "run-2",
      goal: "second goal",
      run: run({ run_id: "run-2" }),
      sentDocumentIds: [],
    });
    expect(second.turns.map((turn) => turn.goal)).toEqual(["first goal", "second goal"]);
    expect(currentTurn(second)?.runId).toBe("run-2");
  });

  it("opens and closes the transcript dialog", () => {
    const opened = workspaceReducer(INITIAL_WORKSPACE_STATE, { type: "transcript_dialog_opened" });
    expect(opened.transcriptDialogOpen).toBe(true);
    const closed = workspaceReducer(opened, { type: "transcript_dialog_closed" });
    expect(closed.transcriptDialogOpen).toBe(false);
  });

  it("loads a transcript", () => {
    const transcript = { available: true, entries: [] };
    const state = workspaceReducer(INITIAL_WORKSPACE_STATE, {
      type: "transcript_loaded",
      transcript,
    });
    expect(state.transcript).toBe(transcript);
  });
});

describe("currentTurn", () => {
  it("is null with no turns", () => {
    expect(currentTurn(INITIAL_WORKSPACE_STATE)).toBeNull();
  });

  it("is the last turn when several exist", () => {
    const state: WorkspaceState = {
      ...INITIAL_WORKSPACE_STATE,
      turns: [
        { runId: "run-1", goal: "a", run: run({ run_id: "run-1" }) },
        { runId: "run-2", goal: "b", run: run({ run_id: "run-2" }) },
      ],
    };
    expect(currentTurn(state)?.runId).toBe("run-2");
  });
});


// ---------------------------------------------------------------------------
// Story 2.4 review patches
// ---------------------------------------------------------------------------

describe("documents attached while a run request is in flight", () => {
  it("keeps a document that was not part of the request that just started", () => {
    const first = workspaceReducer(INITIAL_WORKSPACE_STATE, {
      type: "document_attached",
      document: { name: "sent.txt", text: "Went with the run." },
    });
    // Attaching is not blocked while the POST is in flight, so this one is
    // added *after* `submitGoal` snapshotted what it would send.
    const alsoAttached = workspaceReducer(first, {
      type: "document_attached",
      document: { name: "late.txt", text: "Attached mid-request." },
    });

    const state = workspaceReducer(alsoAttached, {
      type: "run_started",
      runId: "run-1",
      goal: "ship a v1",
      run: run(),
      sentDocumentIds: ["doc-0"], // only the first was actually sent
    });

    expect(state.documents).toEqual([
      { id: "doc-1", name: "late.txt", text: "Attached mid-request." },
    ]);
  });
});

describe("a run whose record has gone", () => {
  function startedState() {
    return workspaceReducer(INITIAL_WORKSPACE_STATE, {
      type: "run_started",
      runId: "run-1",
      goal: "ship a v1",
      run: run(),
      sentDocumentIds: [],
    });
  }

  it("is no longer in flight, so polling stops and the Run control releases", () => {
    const started = startedState();
    expect(isRunInFlight(started)).toBe(true);

    const lost = workspaceReducer(started, {
      type: "run_lost",
      runId: "run-1",
      message: "That run is no longer available.",
    });

    // The last known status is still "running" — nothing will ever update it,
    // which is exactly why `isRunInFlight` must not be derived from it alone.
    expect(currentTurn(lost)?.run.status).toBe("running");
    expect(isRunInFlight(lost)).toBe(false);
    expect(lost.runLost?.message).toBe("That run is no longer available.");
  });

  it("does not release a different run that is still going", () => {
    const started = startedState();
    const lost = workspaceReducer(started, {
      type: "run_lost",
      runId: "some-older-run",
      message: "gone",
    });
    expect(isRunInFlight(lost)).toBe(true);
  });

  it("is cleared when the user starts another run", () => {
    const lost = workspaceReducer(startedState(), {
      type: "run_lost",
      runId: "run-1",
      message: "gone",
    });
    expect(workspaceReducer(lost, { type: "run_requested" }).runLost).toBeNull();
  });
});

describe("a transcript that could not be fetched", () => {
  it("is distinct from the server reporting none, and is retried on reopen", () => {
    const failed = workspaceReducer(INITIAL_WORKSPACE_STATE, {
      type: "transcript_load_failed",
    });
    expect(failed.transcriptFailed).toBe(true);
    expect(failed.transcript).toBeNull();

    // Reopening bumps the attempt counter, which is what makes the failure
    // copy's "open it again to retry" a promise the surface actually keeps.
    const reopened = workspaceReducer(failed, { type: "transcript_dialog_opened" });
    expect(reopened.transcriptAttempt).toBe(failed.transcriptAttempt + 1);

    const loaded = workspaceReducer(reopened, {
      type: "transcript_loaded",
      transcript: { available: true, entries: [] },
    });
    expect(loaded.transcriptFailed).toBe(false);
  });
});
