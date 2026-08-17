import * as React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { StarterSeedEffect } from "@/components/composer/starter-seed-effect";
import { INITIAL_COMPOSER_STATE, composerReducer } from "@/components/composer/composer-state";
import type { ComposerAction } from "@/components/composer/composer-state";
import type { SessionView } from "@/lib/api-types";

// Mock useSearchParams and useRouter
const mockSearchParams = vi.fn();
const mockReplace = vi.fn();

vi.mock("next/navigation", async () => {
  return {
    useSearchParams: () => mockSearchParams(),
    useRouter: () => ({ replace: mockReplace }),
  };
});

// Mock createSessionFromStarter. `vi.mock` factories are hoisted above every
// other module-level statement, so a factory that reads `mockCreateSessionFromStarter`
// as a *value* (rather than lazily, inside a closure — the way the
// `next/navigation` mock above reads `mockSearchParams`/`mockReplace`) would
// hit it before the `const` below has run, and throw
// "Cannot access 'mockCreateSessionFromStarter' before initialization". The
// arrow-function wrapper defers the lookup to call time instead.
const mockCreateSessionFromStarter = vi.fn();

vi.mock("@/lib/api-client", async () => {
  const actual = await vi.importActual("@/lib/api-client");
  return {
    ...actual,
    createSessionFromStarter: (...args: Parameters<typeof mockCreateSessionFromStarter>) =>
      mockCreateSessionFromStarter(...args),
  };
});


describe("StarterSeedEffect", () => {
  let dispatch: ReturnType<typeof vi.fn<(action: ComposerAction) => void>>;
  let state: ReturnType<typeof composerReducer>;

  beforeEach(() => {
    mockSearchParams.mockClear();
    mockReplace.mockClear();
    mockCreateSessionFromStarter.mockClear();

    state = INITIAL_COMPOSER_STATE;
    // A spy, not a plain closure: "dispatches session_seeded action on
    // success" below asserts on the call itself (`toHaveBeenCalledWith`),
    // which a bare function can never satisfy. Still updates `state` as a
    // side effect, for the reducer-level tests further down that inspect it.
    dispatch = vi.fn((action: ComposerAction) => {
      state = composerReducer(state, action);
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  describe("when no starter param is present", () => {
    it("does not call createSessionFromStarter", () => {
      mockSearchParams.mockReturnValue(new URLSearchParams(""));
      
      render(<StarterSeedEffect dispatch={dispatch} />);

      expect(mockCreateSessionFromStarter).not.toHaveBeenCalled();
    });

    it("renders nothing", () => {
      mockSearchParams.mockReturnValue(new URLSearchParams(""));
      
      const { container } = render(<StarterSeedEffect dispatch={dispatch} />);

      expect(container).toBeEmptyDOMElement();
    });
  });

  describe("when starter param is present", () => {
    it("calls createSessionFromStarter with the starter_id", async () => {
      mockSearchParams.mockReturnValue(
        new URLSearchParams("starter=baseline_education_team")
      );
      mockCreateSessionFromStarter.mockResolvedValue({
        ok: true,
        data: {
          status: "complete",
          session_id: "test-session-id",
          turn: 0,
          turns_remaining: 10,
          spec: {
            team_name: "Baseline Education Team-adapted",
            purpose: "A test purpose",
            desired_roles: [],
            desired_tasks: [],
          },
          clarification: null,
        },
      });

      render(<StarterSeedEffect dispatch={dispatch} />);

      await waitFor(() => {
        expect(mockCreateSessionFromStarter).toHaveBeenCalledWith({
          starter_id: "baseline_education_team",
        });
      });
    });

    it("dispatches session_seeded action on success", async () => {
      mockSearchParams.mockReturnValue(
        new URLSearchParams("starter=baseline_education_team")
      );
      const mockSession = {
        status: "complete",
        session_id: "test-session-id",
        turn: 0,
        turns_remaining: 10,
        spec: {
          team_name: "Baseline Education Team-adapted",
          purpose: "A test purpose",
          desired_roles: [],
          desired_tasks: [],
        },
        clarification: null,
      };
      mockCreateSessionFromStarter.mockResolvedValue({
        ok: true,
        data: mockSession,
      });

      render(<StarterSeedEffect dispatch={dispatch} />);

      await waitFor(() => {
        expect(dispatch).toHaveBeenCalledWith({
          type: "session_seeded",
          session: mockSession,
        });
      });
    });

    it("shows loading state while seeding", async () => {
      mockSearchParams.mockReturnValue(
        new URLSearchParams("starter=baseline_education_team")
      );
      // Don't mock the resolution - it will stay pending
      mockCreateSessionFromStarter.mockImplementation(
        () => new Promise(() => {}) // Never resolves
      );

      render(<StarterSeedEffect dispatch={dispatch} />);

      expect(screen.getByText("Loading starter team...")).toBeInTheDocument();
    });

    it("shows error message on failure", async () => {
      mockSearchParams.mockReturnValue(
        new URLSearchParams("starter=baseline_education_team")
      );
      mockCreateSessionFromStarter.mockResolvedValue({
        ok: false,
        message: "Starter team not found",
      });

      render(<StarterSeedEffect dispatch={dispatch} />);

      await waitFor(() => {
        expect(screen.getByRole("alert")).toBeInTheDocument();
      });
      
      expect(screen.getByText(/Failed to load starter team/)).toBeInTheDocument();
    });

    it("clears the starter param from the URL", async () => {
      mockSearchParams.mockReturnValue(
        new URLSearchParams("starter=baseline_education_team")
      );
      mockCreateSessionFromStarter.mockResolvedValue({
        ok: true,
        data: {
          status: "complete",
          session_id: "test-session-id",
          turn: 0,
          turns_remaining: 10,
          spec: {
            team_name: "Baseline Education Team-adapted",
            purpose: "A test purpose",
            desired_roles: [],
            desired_tasks: [],
          },
          clarification: null,
        },
      });

      render(<StarterSeedEffect dispatch={dispatch} />);

      await waitFor(() => {
        expect(mockReplace).toHaveBeenCalled();
      });

      // The component calls `router.replace(url.toString())` — a single
      // string, the App Router's shape, not the Pages Router's
      // `(url, { shallow })` two-argument form. Verify the string it was
      // actually called with no longer carries the starter param.
      expect(mockReplace).toHaveBeenCalledWith(expect.any(String));
      const [calledUrl] = mockReplace.mock.calls[0] as [string];
      expect(calledUrl).not.toContain("starter=");
    });

    it("only seeds once even under React Strict Mode's dev double-invoke", async () => {
      mockSearchParams.mockReturnValue(
        new URLSearchParams("starter=baseline_education_team")
      );
      mockCreateSessionFromStarter.mockResolvedValue({
        ok: true,
        data: {
          status: "complete",
          session_id: "test-session-id",
          turn: 0,
          turns_remaining: 10,
          spec: {
            team_name: "Baseline Education Team-adapted",
            purpose: "A test purpose",
            desired_roles: [],
            desired_tasks: [],
          },
          clarification: null,
        },
      });

      // Strict Mode double-invokes effects in development (mount -> cleanup
      // -> mount again, same instance) specifically to surface exactly this
      // class of bug. Without `seededRef` in the component, this renders two
      // live `createSessionFromStarter` calls — one silently orphaned
      // server-side — instead of one.
      render(
        <React.StrictMode>
          <StarterSeedEffect dispatch={dispatch} />
        </React.StrictMode>
      );

      await waitFor(() => {
        expect(mockCreateSessionFromStarter).toHaveBeenCalled();
      });
      expect(mockCreateSessionFromStarter).toHaveBeenCalledTimes(1);
    });
  });

  describe("session_seeded action in reducer", () => {
    it("sets sessionId from session", () => {
      const session: SessionView = {
        status: "complete",
        session_id: "test-session-id",
        turn: 0,
        turns_remaining: 10,
        spec: {
          team_name: "Test Team",
          purpose: "Test purpose",
          desired_roles: [],
          desired_tasks: [],
        },
        clarification: null,
      };

      const action: ComposerAction = {
        type: "session_seeded",
        session,
      };

      const newState = composerReducer(INITIAL_COMPOSER_STATE, action);

      expect(newState.sessionId).toBe("test-session-id");
    });

    it("sets spec from session", () => {
      const session: SessionView = {
        status: "complete",
        session_id: "test-session-id",
        turn: 0,
        turns_remaining: 10,
        spec: {
          team_name: "Test Team",
          purpose: "Test purpose",
          desired_roles: [],
          desired_tasks: [],
        },
        clarification: null,
      };

      const action: ComposerAction = {
        type: "session_seeded",
        session,
      };

      const newState = composerReducer(INITIAL_COMPOSER_STATE, action);

      expect(newState.spec).toEqual(session.spec);
    });

    it("sets turn and turnsRemaining from session", () => {
      const session: SessionView = {
        status: "complete",
        session_id: "test-session-id",
        turn: 5,
        turns_remaining: 7,
        spec: {
          team_name: "Test Team",
          purpose: "Test purpose",
          desired_roles: [],
          desired_tasks: [],
        },
        clarification: null,
      };

      const action: ComposerAction = {
        type: "session_seeded",
        session,
      };

      const newState = composerReducer(INITIAL_COMPOSER_STATE, action);

      expect(newState.turn).toBe(5);
      expect(newState.turnsRemaining).toBe(7);
    });

    it("does not add a transcript entry (no turn spent)", () => {
      const session: SessionView = {
        status: "complete",
        session_id: "test-session-id",
        turn: 0,
        turns_remaining: 10,
        spec: {
          team_name: "Test Team",
          purpose: "Test purpose",
          desired_roles: [],
          desired_tasks: [],
        },
        clarification: null,
      };

      const action: ComposerAction = {
        type: "session_seeded",
        session,
      };

      const newState = composerReducer(INITIAL_COMPOSER_STATE, action);

      // Transcript should remain empty (no turn was spent)
      expect(newState.transcript).toHaveLength(0);
    });

    it("sets specMayBeStale to false", () => {
      const session: SessionView = {
        status: "complete",
        session_id: "test-session-id",
        turn: 0,
        turns_remaining: 10,
        spec: {
          team_name: "Test Team",
          purpose: "Test purpose",
          desired_roles: [],
          desired_tasks: [],
        },
        clarification: null,
      };

      const action: ComposerAction = {
        type: "session_seeded",
        session,
      };

      const newState = composerReducer(INITIAL_COMPOSER_STATE, action);

      expect(newState.specMayBeStale).toBe(false);
    });
  });
});
