/**
 * Fixtures for the `run` route suites.
 *
 * **Every fixture here is synthesised, not captured from a live server** —
 * unlike `tests/composer/fixtures/index.ts`'s convention of a provenance
 * table naming the exact `curl` command and branch. Capturing these needs a
 * two-terminal `uvicorn` + `next dev` topology, a built Team Package, and —
 * for a `complete`/`failed` capture — a real, paid crewai run, which this
 * task did not spend. Each shape below is instead hand-built to match
 * `api/schemas.py`'s `RunView` / `TeamPlanView` / `TranscriptView`
 * field-for-field, checked against the pydantic models directly rather than
 * against a mirror of them. Every test that consumes one says "synthesised"
 * in its own name or an adjacent comment, per this story's own instruction
 * for the case where a real capture is not taken.
 */

export const teamPlan = {
  team_name: "Haiku Team",
  agents: [
    {
      role: "poet",
      provider: "anthropic",
      model: "claude-sonnet-4-6",
      status: "available",
      detail: "key found",
      usable: true,
      fix_hint: null,
    },
  ],
  tasks: [{ name: "write_haiku", agent_role: "poet", dependencies: [] }],
};

export const teamPlanMissingKey = {
  team_name: "Haiku Team",
  agents: [
    {
      role: "poet",
      provider: "anthropic",
      model: "claude-sonnet-4-6",
      status: "missing",
      detail: "no key found",
      usable: false,
      fix_hint: "add ANTHROPIC_API_KEY to your Key Config",
    },
  ],
  tasks: [{ name: "write_haiku", agent_role: "poet", dependencies: [] }],
};

export const runRunning = {
  status: "running",
  run_id: "run-1",
  team_slug: "haiku_team",
  team_name: "Haiku Team",
  tasks: [{ name: "write_haiku", agent_role: "poet", dependencies: [] }],
  result: null,
  transcript_available: false,
  failure_reason: null,
};

export const runComplete = {
  status: "complete",
  run_id: "run-1",
  team_slug: "haiku_team",
  team_name: "Haiku Team",
  tasks: [{ name: "write_haiku", agent_role: "poet", dependencies: [] }],
  result: {
    final_output: "Autumn leaves falling / a quiet word in the wind / winter waits nearby",
    task_results: [
      {
        name: "write_haiku",
        agent_role: "poet",
        output: "Autumn leaves falling / a quiet word in the wind / winter waits nearby",
      },
    ],
  },
  transcript_available: true,
  failure_reason: null,
};

export const runFailed = {
  status: "failed",
  run_id: "run-1",
  team_slug: "haiku_team",
  team_name: "Haiku Team",
  tasks: [{ name: "write_haiku", agent_role: "poet", dependencies: [] }],
  result: null,
  transcript_available: false,
  failure_reason: "The run failed while in progress. Details have been logged on the server.",
};

export const transcriptAvailable = {
  available: true,
  entries: [
    {
      sequence: 2,
      kind: "task_started",
      agent_role: "poet",
      task_name: "write_haiku",
      content: "Write a haiku about autumn.",
      target_role: null,
    },
    {
      sequence: 13,
      kind: "task_completed",
      agent_role: "poet",
      task_name: "write_haiku",
      content: "Autumn leaves falling / a quiet word in the wind / winter waits nearby",
      target_role: null,
    },
    {
      sequence: 7,
      kind: "delegation",
      agent_role: "poet",
      task_name: "write_haiku",
      content: "please check the syllable count",
      target_role: "editor",
    },
  ],
};

export const transcriptUnavailable = {
  available: false,
  entries: [],
};

export const errorTeamNotFound = {
  error: { code: "team_not_found", message: "No such team, or its package could not be read." },
};

export const errorRunBlocked = {
  error: {
    code: "run_blocked",
    message:
      "This team cannot run yet: 'anthropic' (poet): add ANTHROPIC_API_KEY to your Key Config.",
  },
};

export const errorRunInProgress = {
  error: {
    code: "run_in_progress",
    message:
      "Another run is already in progress. Wait for it to finish before starting another — this server runs one at a time.",
  },
};

export const errorRunNotFound = {
  error: {
    code: "run_not_found",
    message:
      "That run is no longer available. It may have finished long enough ago to be cleared. Start a new run to see fresh results.",
  },
};
