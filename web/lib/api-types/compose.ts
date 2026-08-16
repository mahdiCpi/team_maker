/**
 * The compose seam's view types (Story 2.0–2.3): what the Composer renders
 * from `/api/compose/*` and the pre-run key-status routes' `SpecView` shape.
 *
 * Two rules hold here, both reactions to a defect class this codebase has
 * already produced (Story 2.2 Dev Notes, rule 3):
 *
 * 1. **These view types are deliberately narrower than the server's spec.**
 *    They name only the fields the UI actually renders. `TeamCreationRequest`
 *    has nine fields on a role and eight more on the request; mirroring it here
 *    would create a second source of truth that drifts, and Story 2.0's
 *    `api/schemas.py` refuses to mirror it for exactly the same reason.
 * 2. **Everything arrives as `unknown` and is narrowed by a parser**, never by
 *    a cast. A `as SessionView` would make a missing `spec` a runtime crash in
 *    a component instead of a handled failure at the boundary.
 *
 * `output_path` is intentionally absent from `SpecView`. It is server-owned and
 * read-only to the browser (Story 2.0 AC 13), and the one place the UI shows it
 * is the build result — so the spec view has no field that could be threaded
 * back into an edit body by accident.
 */
import { asNumber, asString, asStringArray, isRecord } from "./primitives";

// ---------------------------------------------------------------------------
// Client-side bounds. These mirror `api/schemas.py:42-47` on purpose: enforcing
// them here means an over-long paste is a message in the composer rather than a
// 422 from the server (AC 8 / the Dependency section's fifth bullet).
// ---------------------------------------------------------------------------

export const MAX_MESSAGE_LENGTH = 8_000;
export const MAX_NAME_LENGTH = 120;
export const MAX_TEXT_LENGTH = 2_000;
/** `_MAX_MODEL_ID` in `api/schemas.py`. Named rather than inlined, because it
 *  is checked in two layers and a drifting literal is how one of them silently
 *  stopped matching the server. */
export const MAX_MODEL_ID_LENGTH = 200;

// ---------------------------------------------------------------------------
// View types
// ---------------------------------------------------------------------------

export type ProviderRoutingView = { provider: string; model: string };

export type RoleView = {
  name: string;
  description: string;
  /** Absent when the role inherits the request default — the real server
   *  omits the key entirely rather than sending null (`exclude_none=True`). */
  llm?: ProviderRoutingView;
};

export type TaskView = {
  name: string;
  description: string;
  agent_role: string;
  dependencies: string[];
};

export type SpecView = {
  team_name: string;
  purpose: string;
  desired_roles: RoleView[];
  desired_tasks: TaskView[];
};

/**
 * A discriminated union, not a flat object with an optional `spec`: this is
 * what lets the compiler narrow `spec` to non-null wherever `status` has
 * already been checked, instead of every consumer needing a `spec!` assertion
 * or a runtime null check the type system can't verify.
 */
export type SessionView =
  | {
      status: "complete";
      session_id: string;
      turn: number;
      turns_remaining: number;
      spec: SpecView;
      clarification: null;
    }
  | {
      status: "needs_clarification";
      session_id: string;
      turn: number;
      turns_remaining: number;
      spec: null;
      /** The message to show the user in place of a proposal. */
      clarification: string | null;
    };

export type ModelSubstitutionView = {
  role: string;
  /** Provider-qualified, e.g. `openai/gpt-4o-min` — not a bare model id. */
  requested: string;
  resolved: string;
};

export type ValidationSummaryView = {
  /**
   * `null` means the server did not report a usable verdict.
   *
   * Distinguished from `false` deliberately: coercing a missing or mis-typed
   * `passed` to `false` rendered a successful build as a red "Failed" with an
   * empty issue list — a failure claim the response never made.
   */
  passed: boolean | null;
  issues: string[];
  warnings: string[];
};

export type BuildResultView = {
  team_name: string;
  output_path: string;
  agent_count: number;
  task_count: number;
  written_file_count: number;
  model_substitutions: ModelSubstitutionView[];
  validation: ValidationSummaryView;
};

// ---------------------------------------------------------------------------
// Parsers
// ---------------------------------------------------------------------------

function parseRouting(value: unknown): ProviderRoutingView | undefined {
  if (!isRecord(value)) return undefined;
  const provider = asString(value.provider);
  const model = asString(value.model);
  if (provider === null || model === null) return undefined;
  return { provider, model };
}

function parseRole(value: unknown): RoleView | null {
  if (!isRecord(value)) return null;
  const name = asString(value.name);
  if (name === null || name.length === 0) return null;
  const role: RoleView = {
    name,
    // Tolerated rather than required: the name is what identifies a role, and
    // refusing the whole spec over a blank description would take a usable
    // team away from the user to protect a label.
    description: asString(value.description) ?? "",
  };
  const llm = parseRouting(value.llm);
  if (llm) role.llm = llm;
  return role;
}

function parseTask(value: unknown): TaskView | null {
  if (!isRecord(value)) return null;
  const name = asString(value.name);
  const agentRole = asString(value.agent_role);
  if (name === null || agentRole === null) return null;
  return {
    name,
    description: asString(value.description) ?? "",
    agent_role: agentRole,
    dependencies: asStringArray(value.dependencies),
  };
}

export function parseSpec(value: unknown): SpecView | null {
  if (!isRecord(value)) return null;
  const teamName = asString(value.team_name);
  if (teamName === null) return null;
  // An array is mandatory: a string here means the contract moved, and
  // coercing it to [] would render an empty team as though it were real.
  if (!Array.isArray(value.desired_roles)) return null;

  const roles = value.desired_roles.map(parseRole);
  if (roles.some((role) => role === null)) return null;

  const rawTasks = Array.isArray(value.desired_tasks) ? value.desired_tasks : [];
  const tasks = rawTasks.map(parseTask);
  if (tasks.some((task) => task === null)) return null;

  return {
    team_name: teamName,
    purpose: asString(value.purpose) ?? "",
    desired_roles: roles as RoleView[],
    desired_tasks: tasks as TaskView[],
  };
}

export function parseSessionResponse(value: unknown): SessionView | null {
  if (!isRecord(value)) return null;
  const sessionId = asString(value.session_id);
  const turn = asNumber(value.turn);
  const turnsRemaining = asNumber(value.turns_remaining);
  if (sessionId === null || turn === null || turnsRemaining === null) return null;
  const status = asString(value.status);

  if (status === "needs_clarification") {
    return {
      status,
      session_id: sessionId,
      turn,
      turns_remaining: turnsRemaining,
      spec: null,
      clarification: asString(value.clarification),
    };
  }

  if (status === "complete") {
    const spec = parseSpec(value.spec);
    if (spec === null) return null;
    return {
      status,
      session_id: sessionId,
      turn,
      turns_remaining: turnsRemaining,
      spec,
      clarification: null,
    };
  }

  // Any other (or missing) status is refused rather than silently treated as
  // "complete" — a typo'd or future status string must not be trusted to mean
  // the spec is present.
  return null;
}

function parseSubstitution(value: unknown): ModelSubstitutionView | null {
  if (!isRecord(value)) return null;
  const role = asString(value.role);
  const requested = asString(value.requested);
  const resolved = asString(value.resolved);
  if (role === null || requested === null || resolved === null) return null;
  return { role, requested, resolved };
}

export function parseBuildResponse(value: unknown): BuildResultView | null {
  if (!isRecord(value)) return null;
  const teamName = asString(value.team_name);
  const outputPath = asString(value.output_path);
  const agentCount = asNumber(value.agent_count);
  const taskCount = asNumber(value.task_count);
  const writtenFileCount = asNumber(value.written_file_count);
  if (
    teamName === null ||
    outputPath === null ||
    agentCount === null ||
    taskCount === null ||
    writtenFileCount === null
  ) {
    return null;
  }

  // Refused, never coerced. A non-array `model_substitutions` — `null`, `{}`, a
  // string — used to become `[]`, which is exactly the "silently claim no
  // substitutions" outcome this field exists to prevent: the UI would report a
  // team built on the model the user asked for when the server had swapped it.
  // The same rule applies to an entry that fails to parse: the whole report is
  // refused rather than partially believed.
  if (!Array.isArray(value.model_substitutions)) return null;
  const substitutions = value.model_substitutions.map(parseSubstitution);
  if (substitutions.some((item) => item === null)) return null;

  const validationSource = isRecord(value.validation) ? value.validation : {};
  return {
    team_name: teamName,
    output_path: outputPath,
    agent_count: agentCount,
    task_count: taskCount,
    written_file_count: writtenFileCount,
    model_substitutions: substitutions as ModelSubstitutionView[],
    validation: {
      // Tri-state rather than `=== true`: a missing or mis-typed `passed` is
      // "not reported", not "failed". The build itself succeeded — refusing the
      // whole report over a bad verdict field would hide a package that was
      // genuinely written to disk.
      passed: typeof validationSource.passed === "boolean" ? validationSource.passed : null,
      issues: asStringArray(validationSource.issues),
      warnings: asStringArray(validationSource.warnings),
    },
  };
}
