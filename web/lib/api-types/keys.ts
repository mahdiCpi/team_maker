/**
 * Key status (Story 2.3). Status only — the server never sends a key value,
 * and nothing here would have anywhere to put one if it did.
 */
import { asBoolean, asString, asStringArray, isRecord } from "./primitives";

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
// Parsers
// ---------------------------------------------------------------------------

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
