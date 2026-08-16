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

/** An attached document, keyed by a client-assigned `id`.
 *
 *  Not keyed by `name`: two files picked from different directories can share
 *  a basename, and keying on it gave duplicate React keys *and* made "Remove"
 *  delete every document sharing that name. `id` is assigned by the reducer
 *  (`documentSeq`) so it stays pure and the ids stay stable across renders.
 *  Only `name` and `text` are ever sent to the server. */
export type AttachedDocument = { id: string; name: string; text: string };

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
  /**
   * Set when polling a run returns `run_not_found` — the one poll failure that
   * is permanent rather than transient. The record was evicted (30-minute idle
   * TTL) or the server restarted, so retrying can only 404 forever. Kept
   * distinct from `runRequestFailure`, which describes a run that never
   * started: this one *did* start, and its outcome is now unknowable.
   */
  runLost: { runId: string; message: string } | null;
  transcript: TranscriptView | null;
  /** The transcript GET failed. Distinct from `transcript.available === false`,
   *  which is the server saying "nothing was captured" — a claim it never made
   *  if the request never arrived. */
  transcriptFailed: boolean;
  transcriptDialogOpen: boolean;
  /** Bumped every time the dialog is opened, so a transcript that failed to
   *  load is retried on reopen — which is what the failure copy tells the user
   *  to do, and a promise the UI has to actually keep. */
  transcriptAttempt: number;
  /** Monotonic source of `AttachedDocument.id`. */
  documentSeq: number;
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
  | { type: "document_attached"; document: { name: string; text: string } }
  | { type: "document_removed"; id: string }
  | { type: "document_attach_failed"; reason: string }
  | { type: "run_requested" }
  | {
      type: "run_started";
      runId: string;
      goal: string;
      run: RunView;
      /** Exactly the documents that went with this request. Anything attached
       *  while the POST was in flight is kept for the next run rather than
       *  discarded unsent. */
      sentDocumentIds: string[];
    }
  | { type: "run_request_failed"; failure: ApiFailure }
  | { type: "run_updated"; run: RunView; epoch: number }
  | { type: "run_lost"; runId: string; message: string }
  | { type: "transcript_loaded"; transcript: TranscriptView }
  | { type: "transcript_load_failed" }
  | { type: "transcript_dialog_opened" }
  | { type: "transcript_dialog_closed" };

export const INITIAL_WORKSPACE_STATE: WorkspaceState = {
  plan: null,
  planFailed: false,
  documents: [],
  documentError: null,
  turns: [],
  runRequestFailure: null,
  runLost: null,
  transcript: null,
  transcriptFailed: false,
  transcriptDialogOpen: false,
  transcriptAttempt: 0,
  documentSeq: 0,
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
        documents: [
          ...state.documents,
          { id: `doc-${state.documentSeq}`, ...action.document },
        ],
        documentSeq: state.documentSeq + 1,
        documentError: null,
      };

    case "document_removed":
      return {
        ...state,
        documents: state.documents.filter((document) => document.id !== action.id),
      };

    case "document_attach_failed":
      return { ...state, documentError: action.reason };

    case "run_requested":
      return { ...state, runRequestFailure: null, runLost: null };

    case "run_started": {
      const sent = new Set(action.sentDocumentIds);
      return {
        ...state,
        turns: [...state.turns, { runId: action.runId, goal: action.goal, run: action.run }],
        runRequestFailure: null,
        runLost: null,
        // Documents are transient to the run they were sent with — cleared
        // once genuinely used, not merely attempted (AD-11). Only the ones
        // actually sent: attaching is not blocked while the POST is in flight,
        // so clearing the whole tray would silently destroy a document that
        // was neither used nor attempted.
        documents: state.documents.filter((document) => !sent.has(document.id)),
        // A fresh run has no transcript of its own yet.
        transcript: null,
        transcriptFailed: false,
        transcriptDialogOpen: false,
        pollEpoch: state.pollEpoch + 1,
      };
    }

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

    case "run_lost":
      return {
        ...state,
        runLost: { runId: action.runId, message: action.message },
        failureRevision: state.failureRevision + 1,
      };

    case "transcript_loaded":
      return { ...state, transcript: action.transcript, transcriptFailed: false };

    case "transcript_load_failed":
      return { ...state, transcriptFailed: true };

    case "transcript_dialog_opened":
      // The attempt counter is what makes the failure copy's "open it again
      // to retry" true rather than merely encouraging.
      return {
        ...state,
        transcriptDialogOpen: true,
        transcriptAttempt: state.transcriptAttempt + 1,
      };

    case "transcript_dialog_closed":
      return { ...state, transcriptDialogOpen: false };
  }
}

/** The most recent run, if any — what the task list, run status, and results
 *  panel all render against. */
export function currentTurn(state: WorkspaceState): ChatTurn | null {
  return state.turns.length > 0 ? state.turns[state.turns.length - 1] : null;
}

/**
 * Whether the current run is still genuinely in flight — what decides both
 * whether to keep polling and whether the `Run` control stays blocked.
 *
 * A run whose record has gone (`run_not_found`) is **not** in flight, even
 * though its last known `status` is still `"running"`: nothing will ever
 * update it. Deriving this from `status` alone meant a poll 404 left the tab
 * polling every two seconds forever and the `Run` button permanently blocked
 * on "A run is already in progress", with a page reload the only escape.
 */
export function isRunInFlight(state: WorkspaceState): boolean {
  const turn = currentTurn(state);
  if (turn === null) return false;
  if (state.runLost?.runId === turn.runId) return false;
  return turn.run.status === "running";
}
