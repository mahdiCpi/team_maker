/**
 * All Workspace state, as a pure reducer — the same reason
 * `composer-state.ts` is one: the failure and epoch rules are properties of
 * state transitions, not of rendering, and deserve direct tests.
 *
 * `RunView` never carries the goal back (AD-11: transient to the run, never a
 * durable record of it), so the goal the user typed is remembered here,
 * client-side, alongside the run it started — that pairing is what lets the
 * surface render "the user's turn is a goal, the system's turn is the run's
 * outcome" (Task 6's FR-23 reading) across more than one run in a session.
 */
import type { ApiFailure, RunView, TeamPlanView, TranscriptView } from "@/lib/api-types";

export type AttachedDocument = { name: string; text: string };

/** One run, paired with the goal that started it. `run` is replaced in place
 *  as polling reports its progress — never appended as a second turn. */
export type ChatTurn = {
  runId: string;
  goal: string;
  run: RunView;
};

export type WorkspaceState = {
  plan: TeamPlanView | null;
  /** `plan` failing to load is distinct from "not yet loaded" (`null`, both
   *  fields) — mirrors `keyCheckState`'s "checking vs failed" distinction. */
  planFailed: boolean;
  documents: AttachedDocument[];
  /** The reason the most recent attach attempt was refused, if any. */
  documentError: string | null;
  turns: ChatTurn[];
  /** A run request that never reached `running` at all — `team_not_found`,
   *  `run_blocked`, `run_in_progress`, or a client-side validation failure. */
  runRequestFailure: ApiFailure | null;
  transcript: TranscriptView | null;
  transcriptDialogOpen: boolean;
  /**
   * Invalidates in-flight polls, exactly like `composer-state.ts`'s
   * `keyCheckEpoch`. Bumped on every new run, so a poll response for a run
   * the user has since superseded is discarded rather than applied.
   */
  pollEpoch: number;
  /** Bumped on every `run_request_failed`, mirroring `buildRevision`: a run
   *  request failure appends no chat entry of its own, so `Transcript`'s
   *  autoscroll effect needs its own signal to notice it appeared. */
  failureRevision: number;
};

export type WorkspaceAction =
  | { type: "plan_loaded"; plan: TeamPlanView }
  | { type: "plan_load_failed" }
  | { type: "document_attached"; document: AttachedDocument }
  | { type: "document_removed"; name: string }
  | { type: "document_attach_failed"; reason: string }
  | { type: "run_requested" }
  | { type: "run_started"; runId: string; goal: string; run: RunView }
  | { type: "run_request_failed"; failure: ApiFailure }
  | { type: "run_updated"; run: RunView; epoch: number }
  | { type: "transcript_loaded"; transcript: TranscriptView }
  | { type: "transcript_dialog_opened" }
  | { type: "transcript_dialog_closed" };

export const INITIAL_WORKSPACE_STATE: WorkspaceState = {
  plan: null,
  planFailed: false,
  documents: [],
  documentError: null,
  turns: [],
  runRequestFailure: null,
  transcript: null,
  transcriptDialogOpen: false,
  pollEpoch: 0,
  failureRevision: 0,
};

export function workspaceReducer(
  state: WorkspaceState,
  action: WorkspaceAction
): WorkspaceState {
  switch (action.type) {
    case "plan_loaded":
      return { ...state, plan: action.plan, planFailed: false };

    case "plan_load_failed":
      return { ...state, planFailed: true };

    case "document_attached":
      return {
        ...state,
        documents: [...state.documents, action.document],
        documentError: null,
      };

    case "document_removed":
      return {
        ...state,
        documents: state.documents.filter((document) => document.name !== action.name),
      };

    case "document_attach_failed":
      return { ...state, documentError: action.reason };

    case "run_requested":
      return { ...state, runRequestFailure: null };

    case "run_started":
      return {
        ...state,
        turns: [...state.turns, { runId: action.runId, goal: action.goal, run: action.run }],
        runRequestFailure: null,
        // Documents are transient to the run they were sent with — cleared
        // once genuinely used, not merely attempted (AD-11).
        documents: [],
        // A fresh run has no transcript of its own yet.
        transcript: null,
        transcriptDialogOpen: false,
        pollEpoch: state.pollEpoch + 1,
      };

    case "run_request_failed":
      return {
        ...state,
        runRequestFailure: action.failure,
        failureRevision: state.failureRevision + 1,
      };

    case "run_updated": {
      if (action.epoch !== state.pollEpoch) return state;
      return {
        ...state,
        turns: state.turns.map((turn) =>
          turn.runId === action.run.run_id ? { ...turn, run: action.run } : turn
        ),
      };
    }

    case "transcript_loaded":
      return { ...state, transcript: action.transcript };

    case "transcript_dialog_opened":
      return { ...state, transcriptDialogOpen: true };

    case "transcript_dialog_closed":
      return { ...state, transcriptDialogOpen: false };
  }
}

/** The most recent run, if any — what the task list, run status, and results
 *  panel all render against. */
export function currentTurn(state: WorkspaceState): ChatTurn | null {
  return state.turns.length > 0 ? state.turns[state.turns.length - 1] : null;
}
