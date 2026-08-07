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
  KeyCheckView,
  KeyStatusView,
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
  /**
   * Provider-level key status (Story 2.3), read once on mount. `null` means "not
   * known yet" — never "fine": the surface renders nothing rather than claiming a
   * state it has not been told.
   */
  keyStatus: KeyStatusView | null;
  /**
   * This team's per-role key check. `null` until a spec exists, and re-read after
   * every adopted spec, because an edit can change which providers are required.
   */
  keyCheck: KeyCheckView | null;
  /**
   * Invalidates in-flight key checks, exactly like `saveEpoch` does for saves. A
   * check issued for an older spec must not overwrite the current one — that is
   * how a stale "all good" would end up authorising a build of a team whose
   * provider had since changed.
   */
  keyCheckEpoch: number;
  /**
   * Whether the key check has an answer, and if not, why not.
   *
   * This exists because `keyCheck === null` conflated three conditions — never
   * asked, in flight, and read failed — and the gate treated all three as
   * *permitting* a build. So the build was open for a round-trip after every turn,
   * and open forever if `/api/keys/*` ever 500'd. "Credential missing" and
   * "credential check failed" are different facts and neither may silently un-gate:
   * `checking` and `failed` both block, with their own copy.
   */
  keyCheckState: KeyCheckState;
};

/** `idle` = no team to check yet. `ready` = `keyCheck` holds the answer. */
export type KeyCheckState = "idle" | "checking" | "failed" | "ready";

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
  | { type: "conversation_restarted" }
  | { type: "key_status_loaded"; status: KeyStatusView }
  | { type: "key_check_requested"; epoch: number }
  | { type: "key_check_loaded"; check: KeyCheckView; epoch: number }
  | { type: "key_check_unavailable"; failure: ApiFailure; epoch: number };

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
  keyStatus: null,
  keyCheck: null,
  keyCheckEpoch: 0,
  keyCheckState: "idle",
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
    // A new spec can require different providers, so the previous check no longer
    // describes this team. Dropped rather than kept: a stale "All models reachable"
    // beside a team that now routes somewhere else is a false statement, and a
    // stale *pass* would be one that authorises a build. The epoch bump discards
    // any check already in flight for the old spec.
    keyCheck: null,
    keyCheckEpoch: state.keyCheckEpoch + 1,
    // Not yet checked. `idle` rather than `checking`: the effect that issues the
    // request sets that, so the flag and the request cannot disagree. Either way the
    // gate treats it as "no answer", which now blocks rather than permits.
    keyCheckState: "idle" as const,
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

    case "key_status_loaded":
      return { ...state, keyStatus: action.status };

    case "key_check_requested":
      if (action.epoch !== state.keyCheckEpoch) return state;
      return { ...state, keyCheckState: "checking" };

    case "key_check_loaded":
      // Same guard as `spec_replaced`: a check issued against a spec that has since
      // been replaced is discarded rather than applied.
      if (action.epoch !== state.keyCheckEpoch) return state;
      return { ...state, keyCheck: action.check, keyCheckState: "ready" };

    case "key_check_unavailable":
      if (action.epoch !== state.keyCheckEpoch) return state;
      return {
        ...state,
        keyCheck: null,
        keyCheckState: "failed",
        // The key check is the first request after every adopted spec, so it is
        // often the first to learn the session is gone. Every other failure path in
        // this reducer honours `session_not_found`; this one used to throw the code
        // away, leaving the conversation looking alive until the user clicked and
        // ate a 404.
        expired:
          action.failure.code === "session_not_found" ? true : state.expired,
      };

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
        // The provider-level report describes the machine, not the conversation, so
        // the last known value is carried across rather than blanking the banner
        // mid-restart. It is *also* re-fetched — see the effect in
        // `composer-surface.tsx` — because the user may have acted on the very fix
        // hint the banner gave them, and a value read once at mount would assert the
        // pre-edit truth for the life of the page. That is precisely the objection
        // this story raised against the server's boot-time snapshot.
        keyStatus: state.keyStatus,
        keyCheckEpoch: state.keyCheckEpoch + 1,
        keyCheckState: "idle",
      };
  }
}
