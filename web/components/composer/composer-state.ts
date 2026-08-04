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
  /**
   * A user entry whose turn failed. Without this a message that never reached
   * the model looks identical to one that did — which matters most at the turn
   * cap, where every further attempt appends a bubble and changes nothing.
   */
  undelivered?: boolean;
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
  /** Bumped on every build outcome, so the transcript can autoscroll to a panel
   *  that appends no transcript entry of its own. */
  buildRevision: number;
  /**
   * Invalidates in-flight saves.
   *
   * Closing the editor, or starting another save, bumps this; a save result
   * carrying a stale epoch is discarded. Without it, closing the editor mid-save
   * let the late `spec_replaced` reopen the dialog by itself *and* reset
   * `pending` from `"build"` to `null`, re-enabling both build controls while a
   * build was still running.
   */
  saveEpoch: number;
  /**
   * True once a turn's result may no longer reflect the session's real spec —
   * set by a `timeout`, where the server may well have completed the turn we
   * stopped waiting for. Editing or building on a spec that may be stale would
   * either write something the user never saw or silently revert the server.
   */
  specMayBeStale: boolean;
  /**
   * Which follow-up questions have already been asked, so the assistant does not
   * repeat one the user has answered. The server never writes `llm` from a
   * conversational reply, so without this the model question recurred forever.
   */
  askedFollowUps: string[];
};

export type ComposerAction =
  | { type: "turn_requested"; text: string }
  | { type: "turn_succeeded"; session: SessionView }
  | { type: "turn_failed"; failure: ApiFailure }
  | { type: "build_requested" }
  | { type: "build_succeeded"; result: BuildResultView }
  | { type: "build_failed"; failure: ApiFailure }
  | { type: "save_requested" }
  | { type: "spec_replaced"; session: SessionView; epoch: number }
  | { type: "spec_edit_failed"; failure: ApiFailure; epoch: number }
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
  buildRevision: 0,
  saveEpoch: 0,
  specMayBeStale: false,
  askedFollowUps: [],
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

/**
 * Flags the most recent user entry as never delivered.
 *
 * Only the last one: an earlier failed turn was already marked, and a turn that
 * succeeded must not be retroactively doubted.
 */
function markLastUserEntryUndelivered(
  transcript: TranscriptEntry[]
): TranscriptEntry[] {
  for (let index = transcript.length - 1; index >= 0; index -= 1) {
    if (transcript[index].author !== "user") continue;
    if (transcript[index].undelivered) return transcript;
    const copy = [...transcript];
    copy[index] = { ...copy[index], undelivered: true };
    return copy;
  }
  return transcript;
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
        // The previous build described a spec this turn is about to change, and
        // the panel renders as the newest thing that happened. Leaving it would
        // claim the team on disk matches the team on screen.
        build: null,
      };

    case "turn_succeeded": {
      const proposal = describeProposal(
        action.session.spec,
        action.session.turn,
        state.askedFollowUps
      );
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
        // A successful turn re-establishes what the session holds.
        specMayBeStale: false,
        askedFollowUps: proposal.kind
          ? [...state.askedFollowUps, proposal.kind]
          : state.askedFollowUps,
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
        // A timeout is the one failure where the server may have *succeeded*
        // after we stopped listening, so our spec and turn counter may now be
        // behind the session's.
        specMayBeStale:
          action.failure.code === "timeout" ? true : state.specMayBeStale,
        // Marked so a message that never reached the model is distinguishable
        // from one that did.
        transcript: markLastUserEntryUndelivered(state.transcript),
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
      return {
        ...state,
        pending: null,
        failure: null,
        build: action.result,
        buildRevision: state.buildRevision + 1,
      };

    case "build_failed":
      return {
        ...state,
        pending: null,
        failure: action.failure,
        build: null,
        buildRevision: state.buildRevision + 1,
        expired: action.failure.code === "session_not_found",
      };

    case "save_requested":
      // Bumping the epoch here is what makes a double-submitted save safe: only
      // the most recent one can still apply.
      return { ...state, saveEpoch: state.saveEpoch + 1, failure: null };

    case "spec_replaced":
      // Discarded if the editor was closed, or another save started, while this
      // one was in flight. Applying it would reopen a dialog the user dismissed
      // and reset `pending` out from under a running build.
      if (action.epoch !== state.saveEpoch) return state;
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

    case "spec_edit_failed": {
      if (action.epoch !== state.saveEpoch) return state;
      const gone = action.failure.code === "session_not_found";
      return {
        ...state,
        pending: null,
        failure: action.failure,
        // Held open so the inline reasons appear beside the inputs that caused
        // them, with the previous good spec still in `spec` — EXCEPT when the
        // session is gone. The only recovery control ("Start a new
        // conversation") lives on the surface, outside the modal's focus scope,
        // so holding the dialog open would trap the user with a dead session and
        // a Save button they can press forever.
        editorOpen: !gone,
        expired: gone,
      };
    }

    case "review_toggled":
      return { ...state, reviewBeforeBuild: action.enabled };

    case "editor_opened":
      return { ...state, editorOpen: true, failure: null };

    case "editor_closed":
      // Epoch bumped so a save still in flight cannot reopen this.
      return { ...state, editorOpen: false, saveEpoch: state.saveEpoch + 1 };

    case "failure_dismissed":
      return { ...state, failure: null };

    case "conversation_restarted":
      return {
        ...INITIAL_COMPOSER_STATE,
        // Carried over: the user chose this, and a dropped session is not a
        // reason to silently un-choose it.
        reviewBeforeBuild: state.reviewBeforeBuild,
        // Never restarted from 0, or a restarted conversation would reuse ids
        // React has already keyed rows with — and a stale in-flight save could
        // land in the fresh conversation.
        nextEntryId: state.nextEntryId,
        specRevision: state.specRevision,
        buildRevision: state.buildRevision,
        saveEpoch: state.saveEpoch + 1,
      };
  }
}
