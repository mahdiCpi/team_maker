/**
 * All Composer state, as a pure reducer.
 *
 * It lives outside the component for two reasons. The transcript is UI-owned —
 * the API keeps no chat history at all (`ComposerSession` holds the intent and
 * the current spec, and intermediate turns are discarded) — so this reducer is
 * the only record of the conversation and deserves direct tests. And the
 * failure rules AC 8 states are easy to get subtly wrong: "a failed turn leaves
 * the transcript and the last good spec intact" is a property of state
 * transitions, not of rendering.
 */
import type {
  ApiFailure,
  BuildResultView,
  SessionView,
  SpecView,
} from "@/lib/api-types";
import { describeProposal } from "@/components/composer/proposal";

export type TranscriptEntry = {
  id: string;
  author: "user" | "assistant";
  text: string;
};

/** What the surface is waiting on. There is never more than one. */
export type PendingKind = "turn" | "build";

export type ComposerState = {
  sessionId: string | null;
  spec: SpecView | null;
  turn: number;
  turnsRemaining: number;
  transcript: TranscriptEntry[];
  pending: PendingKind | null;
  failure: ApiFailure | null;
  build: BuildResultView | null;
  reviewBeforeBuild: boolean;
  editorOpen: boolean;
  /** The session is gone server-side; only a restart can recover. */
  expired: boolean;
  /** Monotonic id source. A counter rather than a random or time-based id so
   *  the reducer stays pure and its tests stay deterministic. */
  nextEntryId: number;
  /** Bumped every time a server spec is adopted. The editor is keyed on it, so
   *  a saved edit remounts the form against the server's re-serialisation
   *  instead of leaving the user's local draft on screen. */
  specRevision: number;
};

export type ComposerAction =
  | { type: "turn_requested"; text: string }
  | { type: "turn_succeeded"; session: SessionView }
  | { type: "turn_failed"; failure: ApiFailure }
  | { type: "build_requested" }
  | { type: "build_succeeded"; result: BuildResultView }
  | { type: "build_failed"; failure: ApiFailure }
  | { type: "spec_replaced"; session: SessionView }
  | { type: "spec_edit_failed"; failure: ApiFailure }
  | { type: "review_toggled"; enabled: boolean }
  | { type: "editor_opened" }
  | { type: "editor_closed" }
  | { type: "failure_dismissed" }
  | { type: "conversation_restarted" };

export const INITIAL_COMPOSER_STATE: ComposerState = {
  sessionId: null,
  spec: null,
  turn: 0,
  turnsRemaining: 0,
  transcript: [],
  pending: null,
  failure: null,
  build: null,
  reviewBeforeBuild: false,
  editorOpen: false,
  expired: false,
  nextEntryId: 0,
  specRevision: 0,
};

function append(
  state: ComposerState,
  author: TranscriptEntry["author"],
  text: string
): Pick<ComposerState, "transcript" | "nextEntryId"> {
  return {
    transcript: [
      ...state.transcript,
      { id: `entry-${state.nextEntryId}`, author, text },
    ],
    nextEntryId: state.nextEntryId + 1,
  };
}

function adoptSession(state: ComposerState, session: SessionView) {
  return {
    sessionId: session.session_id,
    spec: session.spec,
    turn: session.turn,
    turnsRemaining: session.turns_remaining,
    specRevision: state.specRevision + 1,
  };
}

export function composerReducer(
  state: ComposerState,
  action: ComposerAction
): ComposerState {
  switch (action.type) {
    case "turn_requested":
      return {
        ...state,
        ...append(state, "user", action.text),
        pending: "turn",
        // Cleared on the new attempt, not on the old failure's dismissal: the
        // previous error must not sit above a request that has moved on.
        failure: null,
      };

    case "turn_succeeded": {
      const proposal = describeProposal(action.session.spec, action.session.turn);
      const withReply = append(
        state,
        "assistant",
        `${proposal.summary} ${proposal.followUp}`
      );
      return {
        ...state,
        ...withReply,
        ...adoptSession(state, action.session),
        pending: null,
        failure: null,
      };
    }

    case "turn_failed":
      return {
        ...state,
        pending: null,
        failure: action.failure,
        // `spec`, `sessionId` and `transcript` are deliberately untouched: the
        // server leaves `session.current` intact on a failed refine
        // (`api/routers/compose.py:88-90`), so the client must too.
        expired: action.failure.code === "session_not_found",
      };

    case "build_requested":
      return {
        ...state,
        pending: "build",
        failure: null,
        // A stale success panel beside a fresh spinner would claim a build this
        // attempt has not made.
        build: null,
        editorOpen: false,
      };

    case "build_succeeded":
      return { ...state, pending: null, failure: null, build: action.result };

    case "build_failed":
      return {
        ...state,
        pending: null,
        failure: action.failure,
        build: null,
        expired: action.failure.code === "session_not_found",
      };

    case "spec_replaced":
      return {
        ...state,
        ...adoptSession(state, action.session),
        pending: null,
        failure: null,
        // **Held open on purpose.** Closing it on success hid the one thing AC 4
        // requires the editor to show: the server's re-serialisation.
        // `_pre_process` rewrites input five ways, so a save that closed the
        // dialog would leave the user with no way to see what was actually
        // stored — and no confirmation that anything happened at all. The
        // parent keys this component on `specRevision`, so the form remounts
        // against the response rather than keeping the local draft.
        editorOpen: true,
        // No transcript entry: a direct edit consumes no turn
        // (`api/routers/compose.py:101`) and is not something the team "said".
      };

    case "spec_edit_failed":
      return {
        ...state,
        pending: null,
        failure: action.failure,
        // Held open so the inline `fields[]` reasons appear beside the inputs
        // that caused them, with the previous good spec still in `spec`.
        editorOpen: true,
        expired: action.failure.code === "session_not_found",
      };

    case "review_toggled":
      return { ...state, reviewBeforeBuild: action.enabled };

    case "editor_opened":
      return { ...state, editorOpen: true, failure: null };

    case "editor_closed":
      return { ...state, editorOpen: false };

    case "failure_dismissed":
      return { ...state, failure: null };

    case "conversation_restarted":
      return {
        ...INITIAL_COMPOSER_STATE,
        // Carried over: the user chose this, and a dropped session is not a
        // reason to silently un-choose it.
        reviewBeforeBuild: state.reviewBeforeBuild,
        // Never restarted from 0, or a restarted conversation would reuse ids
        // React has already keyed rows with.
        nextEntryId: state.nextEntryId,
        specRevision: state.specRevision,
      };
  }
}
