/**
 * Narrowing primitives shared by every parser in this package.
 *
 * Split out of the former single `api-types.ts` in Story 2.4, once adding the
 * `run` group's views and parsers pushed that file to 801 lines — well past
 * CLAUDE.md's ~400-line guideline. Internal to this package; nothing outside
 * `lib/api-types/` imports these directly.
 */

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function asString(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

export function asNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

export function asBoolean(value: unknown): boolean | null {
  return typeof value === "boolean" ? value : null;
}

export function asStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is string => typeof item === "string");
}
