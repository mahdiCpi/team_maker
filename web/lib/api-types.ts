/**
 * The boundary between the API's wire payloads and what the Composer renders.
 *
 * Two rules hold here, both of them reactions to a defect class this codebase
 * has already produced (Story 2.2 Dev Notes, rule 3):
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

export type SessionView = {
  session_id: string;
  turn: number;
  turns_remaining: number;
  spec: SpecView;
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
// Key status (Story 2.3). Status only — the server never sends a key value, and
// nothing here would have anywhere to put one if it did.
// ---------------------------------------------------------------------------

/**
 * A `registry.STATUS_*` value, plus `unrecognized` for a role pinned to a
 * provider the catalog does not know.
 *
 * Deliberately a `string`, not a union of the five known values. The server
 * documents adding a status as a catalog change, and a union here would make an
 * unknown status a parse failure — turning a provider this build has not heard of
 * into "the whole check is unreadable". `KEY_STATUS_LABEL` handles the unknown
 * case by falling back to the server's own `detail`.
 */
export type ProviderKeyStatus = string;

/**
 * Which of the two documented credential sources answered — `key-config`,
 * `environment`, `startup-leftover`, or `none`. A bare `string` for the same reason
 * `status` is: a value this build has not heard of must not make the whole payload
 * unreadable.
 */
export type CredentialSource = string;

export type ProviderKeyView = {
  name: string;
  status: ProviderKeyStatus;
  /** The server's own words. Source-aware. Rendered, never re-authored. */
  detail: string;
  usable: boolean;
  /** The Key Config entry that would satisfy it — a variable *name*, never a value. */
  env_var: string | null;
  fix_hint: string | null;
  credential_source: CredentialSource;
};

export type RoleKeyView = {
  role: string;
  provider: string;
  model: string;
  status: ProviderKeyStatus;
  detail: string;
  usable: boolean;
  /**
   * The role named no `llm`, so its provider came from the server's resolution
   * order. The browser must not compute this — it does not know `default_llm`.
   */
  inherited_default: boolean;
  fix_hint: string | null;
  credential_source: CredentialSource;
  /**
   * The build cannot proceed without this role, so the UI must not offer to drop it
   * or route around it. The synthetic planner role is the only one today.
   */
  required: boolean;
};

/**
 * `no-keys` or `has-keys` today — the provider read has no team to judge.
 *
 * A bare `string`, not a union. An earlier version closed this union and the code
 * review found the consequence: one new server aggregate made `parseKeyStatus`
 * return `null`, which silently removed the whole panel *and* the build gate. The
 * field the gate keys on must never fail closed on an unrecognised value.
 */
export type KeyStatusOverall = string;

export type KeyStatusView = {
  overall: KeyStatusOverall;
  providers: ProviderKeyView[];
  key_config_path: string;
  load_warnings: string[];
  any_key_present: boolean;
  /** Present in the Key Config now, but not usable for *composing* until restart. */
  needs_restart_to_author: string[];
};

/**
 * `all-good` | `missing-key` | `unsupported` | `via-openrouter` | `unknown`.
 *
 * A bare `string` for the same reason as `KeyStatusOverall`. `missing-key` and
 * `unsupported` are distinct on purpose: the first is fixed by adding a key, the
 * second cannot be fixed by any key.
 */
export type KeyCheckOverall = string;

export type KeyCheckView = {
  overall: KeyCheckOverall;
  blocked: boolean;
  blocking_reason: string | null;
  roles: RoleKeyView[];
  providers: ProviderKeyView[];
  key_config_path: string;
  load_warnings: string[];
  any_key_present: boolean;
  needs_restart_to_author: string[];
};

// ---------------------------------------------------------------------------
// Error codes
// ---------------------------------------------------------------------------

/** Every code `api/errors.py` can emit, including the framework-level ones. */
export const SERVER_ERROR_CODES = [
  "session_not_found",
  "turn_cap_reached",
  "spec_invalid",
  "authoring_unavailable",
  "compose_failed",
  "output_exists",
  "build_failed",
  // Added by Story 2.0's code review; AC 8's original table predates it.
  "session_busy",
  // Framework-level: reachable via an unknown path, a 405, or a fault that
  // escapes the routes.
  "not_found",
  "method_not_allowed",
  "internal_error",
  "request_rejected",
] as const;

export type ServerErrorCode = (typeof SERVER_ERROR_CODES)[number];

/**
 * Codes this client originates. **These are additions, not part of Story 2.0's
 * contract** — the server never sends them. They exist because a browser has
 * failure modes an HTTP envelope cannot describe: the process is down, the
 * request was aborted, a proxy answered with HTML, or a future server sent a
 * code this build does not know. `EXPERIENCE.md:104` forbids a silent failure,
 * so each one gets authored copy rather than an empty state.
 */
export const CLIENT_ERROR_CODES = [
  "too_long",
  "unreachable",
  "timeout",
  "unreadable_response",
  "unknown_error",
] as const;

export type ClientErrorCode = (typeof CLIENT_ERROR_CODES)[number];
export type ApiErrorCode = ServerErrorCode | ClientErrorCode;

export type FieldIssue = { path: string; message: string };

export type ApiFailure = {
  ok: false;
  code: ApiErrorCode;
  message: string;
  /** Non-empty only for `spec_invalid`, matching `api/errors.py:93-94`. */
  fields: FieldIssue[];
};

export type ApiResult<T> = { ok: true; data: T } | ApiFailure;

export function isServerErrorCode(value: unknown): value is ServerErrorCode {
  return (
    typeof value === "string" &&
    (SERVER_ERROR_CODES as readonly string[]).includes(value)
  );
}

// ---------------------------------------------------------------------------
// Narrowing primitives
// ---------------------------------------------------------------------------

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function asString(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

function asNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function asStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is string => typeof item === "string");
}

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
  const spec = parseSpec(value.spec);
  if (spec === null) return null;
  return {
    session_id: sessionId,
    turn,
    turns_remaining: turnsRemaining,
    spec,
  };
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

// ---------------------------------------------------------------------------
// Key-status parsers
// ---------------------------------------------------------------------------

function asBoolean(value: unknown): boolean | null {
  return typeof value === "boolean" ? value : null;
}

function parseProviderKey(value: unknown): ProviderKeyView | null {
  if (!isRecord(value)) return null;
  const name = asString(value.name);
  const status = asString(value.status);
  const usable = asBoolean(value.usable);
  if (name === null || status === null || usable === null) return null;
  return {
    name,
    status,
    detail: asString(value.detail) ?? status,
    usable,
    env_var: asString(value.env_var),
    fix_hint: asString(value.fix_hint),
    credential_source: asString(value.credential_source) ?? "none",
  };
}

function parseRoleKey(value: unknown): RoleKeyView | null {
  if (!isRecord(value)) return null;
  const role = asString(value.role);
  const provider = asString(value.provider);
  const status = asString(value.status);
  const usable = asBoolean(value.usable);
  // `inherited_default` is refused rather than defaulted: guessing `false` would
  // claim the user chose a provider the server actually supplied for them.
  const inherited = asBoolean(value.inherited_default);
  if (
    role === null ||
    provider === null ||
    status === null ||
    usable === null ||
    inherited === null
  ) {
    return null;
  }
  return {
    role,
    provider,
    model: asString(value.model) ?? "",
    status,
    detail: asString(value.detail) ?? status,
    usable,
    inherited_default: inherited,
    fix_hint: asString(value.fix_hint),
    credential_source: asString(value.credential_source) ?? "none",
    // Defaults to `false`: a role the server did not mark required is not required,
    // and unlike `usable` this only ever *removes* an affordance, so a permissive
    // default cannot un-gate anything.
    required: asBoolean(value.required) ?? false,
  };
}

/**
 * The provider list, defaulted rather than refused.
 *
 * An earlier version returned `null` for a non-array, which propagated up and made
 * the whole check unreadable — and therefore, via `keyCheck: null`, disabled the
 * build gate. A field no consumer renders must not be able to do that.
 */
function parseProviderList(value: unknown): ProviderKeyView[] {
  if (!Array.isArray(value)) return [];
  return value
    .map(parseProviderKey)
    .filter((entry): entry is ProviderKeyView => entry !== null);
}

function parseKeyCommon(value: Record<string, unknown>) {
  const path = asString(value.key_config_path);
  const anyKey = asBoolean(value.any_key_present);
  if (path === null || anyKey === null) return null;
  return {
    providers: parseProviderList(value.providers),
    key_config_path: path,
    load_warnings: asStringArray(value.load_warnings),
    any_key_present: anyKey,
    needs_restart_to_author: asStringArray(value.needs_restart_to_author),
  };
}

export function parseKeyStatus(value: unknown): KeyStatusView | null {
  if (!isRecord(value)) return null;
  // Any non-empty string is accepted. Only `no-keys` changes what renders; anything
  // else means "the user has some credential", which is what every other value the
  // server can send amounts to.
  const overall = asString(value.overall);
  if (overall === null || overall.length === 0) return null;
  const common = parseKeyCommon(value);
  if (common === null) return null;
  return { overall, ...common };
}

export function parseKeyCheck(value: unknown): KeyCheckView | null {
  if (!isRecord(value)) return null;
  const overall = asString(value.overall);
  if (overall === null || overall.length === 0) return null;
  // Refused rather than coerced. `blocked` is the one field that gates a build, so
  // a missing or mis-typed value must not become a permissive `false`.
  const blocked = asBoolean(value.blocked);
  if (blocked === null) return null;
  if (!Array.isArray(value.roles)) return null;
  const roles = value.roles.map(parseRoleKey);
  if (roles.some((entry) => entry === null)) return null;
  const common = parseKeyCommon(value);
  if (common === null) return null;
  return {
    overall,
    blocked,
    blocking_reason: asString(value.blocking_reason),
    roles: roles as RoleKeyView[],
    ...common,
  };
}

export function parseFieldIssues(value: unknown): FieldIssue[] {
  if (!Array.isArray(value)) return [];
  const issues: FieldIssue[] = [];
  for (const entry of value) {
    if (!isRecord(entry)) continue;
    const path = asString(entry.path);
    const message = asString(entry.message);
    if (path === null || message === null) continue;
    issues.push({ path, message });
  }
  return issues;
}

/** Reads `{ error: { code, message, fields? } }` without trusting any of it. */
export function parseErrorEnvelope(
  value: unknown
): { code: string; message: string; fields: FieldIssue[] } | null {
  if (!isRecord(value)) return null;
  if (!isRecord(value.error)) return null;
  const code = asString(value.error.code);
  const message = asString(value.error.message);
  if (code === null || message === null) return null;
  return { code, message, fields: parseFieldIssues(value.error.fields) };
}
