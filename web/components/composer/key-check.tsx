"use client"

import type { KeyCheckView, KeyStatusView, RoleKeyView } from "@/lib/api-types"

/**
 * The four UX-DR5 key-check states (Story 2.3, AC 4 / AC 5).
 *
 * Four rules hold here:
 *
 * 1. **Every state comes from the server.** `registry.classify()` is the single
 *    source of truth for availability and is shared with the runtime's credential
 *    resolution, so nothing is recomputed in the browser — not the statuses, not
 *    `no-keys`, and above all not each role's provider, because the browser does
 *    not know `default_llm` (`spec-draft.ts:9-31`).
 * 2. **Nothing is claimed before it is known.** No status and no check renders
 *    nothing; keys-but-no-team renders nothing, because "All models reachable" is
 *    a statement about a team's roles and there are none yet.
 * 3. **A missing key and an unsupported provider are different things.** Calling
 *    the second one a missing key tells a user who added the right key that they
 *    did not (`deferred-work.md:85`). The server authors the hint for it; this
 *    renders that hint rather than inventing one.
 * 4. **No key entry, ever, and no accent.** `EXPERIENCE.md:103` bans key entry
 *    outright; `EXPERIENCE.md:185` confirms a passing check is "accent-free,
 *    neutral badges", and the accent token belongs to Story 2.4 — which is why it
 *    is not named here either, since Guard B greps raw file text. Colour is always
 *    paired with a word (`EXPERIENCE.md:117`).
 *
 * On the deliberate copy deviation: `EXPERIENCE.md:87` asks the no-keys banner to
 * link to "Settings guidance", but Settings holds no key guidance until Story 2.6
 * and `EXPERIENCE.md:104`/`:172-174` ban dead affordances. The Key Config *path* is
 * named instead — truthful, actionable today, and the Story 1.6 precedent ("add
 * the key to your Key Config" is only actionable if the user knows which file).
 */

/** `EXPERIENCE.md:85-88`, verbatim. */
const ALL_GOOD = "All models reachable."
const VIA_OPENROUTER = "OpenRouter key found — routed models available."
const NO_KEYS =
  "You'll need at least one model key to run. Add one in your Key Config, or add an OpenRouter key to unlock many models."

/** The short word paired with a badge's provider name, per status. */
const STATUS_WORD: Record<string, string> = {
  available: "key found",
  "keyless-local": "local",
  "via-openrouter": "via OpenRouter",
  missing: "key missing",
  "unsupported-by-runtime": "not supported",
  unrecognized: "unknown provider",
}

function statusWord(role: RoleKeyView): string {
  // Falls back to the server's own `detail` rather than a guess, so a status this
  // build has not heard of still renders something true.
  return STATUS_WORD[role.status] ?? role.detail
}

/**
 * The banner's primary sentence.
 *
 * For a single missing key it is the spine's own wording (`EXPERIENCE.md:86`) with
 * the provider and the Key Config path substituted. For anything else — several
 * broken roles, or a provider no key can fix — it is the server's
 * `blocking_reason`, which is already plain language and already correct about
 * which of those two situations applies.
 */
function primaryMessage(check: KeyCheckView): string {
  // `blocked` is consulted before `overall`, so the banner and the build button can
  // never disagree. A payload saying `all-good` while `blocked` is true is not
  // producible by this server, but a proxy or a future one could send it, and
  // "All models reachable." above a disabled button is the worst of both.
  if (check.blocked) {
    const unusable = check.roles.filter((role) => !role.usable)
    if (unusable.length === 1 && unusable[0].status === "missing") {
      // `EXPERIENCE.md:86`, verbatim. The parenthetical stays "(Settings)" as the
      // spine wrote it; the Key Config path is shown on its own line below rather
      // than substituted into the sentence.
      return (
        `${unusable[0].provider} key missing — add it to your Key Config ` +
        "(Settings), or switch this agent to a model you have."
      )
    }
    return check.blocking_reason ?? "This team cannot run yet."
  }
  if (check.overall === "via-openrouter") return VIA_OPENROUTER
  if (check.overall === "unknown") {
    return "This team's models are chosen when the team is built, so there is nothing to check yet."
  }
  return ALL_GOOD
}

export function KeyCheck({
  status,
  check,
}: {
  status: KeyStatusView | null
  check: KeyCheckView | null
}) {
  // The no-keys state outranks everything the per-team check can say, and is
  // checked *before* `check === null`. The first version consulted `status` only
  // while no check existed, so the moment a spec appeared the banner was replaced —
  // on the planner path, by reassuring copy — and a user with an empty Key Config
  // lost the one message that told them what to do. AC 4 puts `no-keys` first in the
  // precedence for exactly this reason.
  const noKeys = status !== null && status.overall === "no-keys"
  if (noKeys) {
    return (
      <Panel state="no-keys" tone="warn">
        <Message>{NO_KEYS}</Message>
        <Warnings warnings={warningsOf(status, check)} />
        <ConfigPath path={status.key_config_path} />
      </Panel>
    )
  }

  // Before a team exists there is still one thing worth saying: that a key the user
  // has just added cannot be used for composing until the API restarts. This is the
  // only moment it can be acted on *before* spending a turn and getting a 503, and
  // the first version returned early here and so never showed it.
  if (check === null) {
    const pending = status?.needs_restart_to_author ?? []
    const warnings = status?.load_warnings ?? []
    if (pending.length === 0 && warnings.length === 0) return null
    return (
      <Panel state="provider-notice" tone="neutral">
        <Warnings warnings={warnings} />
        <RestartNote providers={pending} />
        <ConfigPath path={status!.key_config_path} />
      </Panel>
    )
  }

  const blocked = check.blocked
  const unusable = check.roles.filter((role) => !role.usable)
  // The check's value wins, because it is read per request while the provider
  // report is a snapshot. `??` was wrong here: it only falls through on
  // null/undefined, and `[]` is neither — so a successful mount read permanently
  // shadowed the fresh list and the whole restart warning was dead in the one flow
  // it exists for.
  const restarting =
    check.needs_restart_to_author.length > 0
      ? check.needs_restart_to_author
      : (status?.needs_restart_to_author ?? [])

  return (
    <Panel state={check.overall} tone={blocked ? "warn" : "neutral"}>
      <Message>{primaryMessage(check)}</Message>

      {check.roles.length > 0 ? (
        <ul
          data-slot="key-check-badges"
          className="mt-2 flex flex-wrap items-center gap-1.5"
        >
          {check.roles.map((role) => (
            <li
              key={role.role}
              data-slot="key-check-badge"
              data-role={role.role}
              data-status={role.status}
              data-usable={role.usable}
              className={
                "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs " +
                (role.usable
                  ? "bg-muted text-foreground"
                  : "border-destructive/40 text-destructive")
              }
            >
              <span className="font-medium">{role.role}</span>
              <span className="text-muted-foreground">·</span>
              <span>{role.provider}</span>
              <span className="text-muted-foreground">·</span>
              {/* Colour is never the only carrier (`EXPERIENCE.md:117`). */}
              <span>{statusWord(role)}</span>
            </li>
          ))}
        </ul>
      ) : null}

      {/* The per-role remedy, in the server's words. Only for roles that need one,
          and only once per provider — two roles on the same missing key do not
          need the same sentence twice. */}
      {unusable.length > 0 ? (
        <ul data-slot="key-check-hints" className="mt-2 flex flex-col gap-1">
          {dedupeByProvider(unusable).map((role) => (
            <li key={role.provider} data-slot="key-check-hint" className="text-xs">
              <span className="font-medium">{role.provider}</span> — {role.fix_hint}
            </li>
          ))}
        </ul>
      ) : null}

      <Warnings warnings={warningsOf(status, check)} />
      <RestartNote providers={restarting} />

      {blocked ? <ConfigPath path={check.key_config_path} /> : null}
    </Panel>
  )
}

function dedupeByProvider(roles: RoleKeyView[]): RoleKeyView[] {
  const seen = new Set<string>()
  return roles.filter((role) => {
    if (seen.has(role.provider)) return false
    seen.add(role.provider)
    return true
  })
}

/** The check's warnings if it has any, else the provider report's. */
function warningsOf(
  status: KeyStatusView | null,
  check: KeyCheckView | null
): string[] {
  if (check && check.load_warnings.length > 0) return check.load_warnings
  return status?.load_warnings ?? []
}

/**
 * Problems the server hit while *reading* the Key Config.
 *
 * Rendered because the alternative is advice the user can prove wrong: a
 * permission-denied or locked file makes every provider classify as `missing`, so
 * the banner says "add it to your Key Config" about a file that already contains the
 * key. `load_warnings` is the one sentence that explains it, and the first version
 * plumbed it end to end and then dropped it at the render boundary — the same
 * "field that exists, looks load-bearing, and is never read" pattern this story
 * criticised elsewhere.
 *
 * The strings are catalog and path text; they carry no key value.
 */
function Warnings({ warnings }: { warnings: string[] }) {
  if (warnings.length === 0) return null
  return (
    <ul data-slot="key-check-warnings" className="mt-2 flex flex-col gap-1">
      {warnings.map((warning) => (
        <li key={warning} className="text-xs text-destructive">
          {warning}
        </li>
      ))}
    </ul>
  )
}

function RestartNote({ providers }: { providers: string[] }) {
  if (providers.length === 0) return null
  return (
    <p data-slot="key-check-restart" className="mt-2 text-xs text-muted-foreground">
      {providers.join(", ")} {providers.length === 1 ? "was" : "were"} changed in
      your Key Config after the API started. Running a built team picks that up, but
      composing needs the API restarted.
    </p>
  )
}

function Panel({
  state,
  tone,
  children,
}: {
  state: string
  tone: "warn" | "neutral"
  children: React.ReactNode
}) {
  return (
    <div
      data-slot="key-check"
      data-state={state}
      // `role="status"` rather than `"alert"`: this is standing information about a
      // setup, not an error that just happened. The failure alert beside it owns
      // `role="alert"`, and two assertive regions would talk over each other.
      role="status"
      className={
        "mb-3 rounded-lg border px-3 py-2 " +
        (tone === "warn" ? "border-destructive/40 bg-card" : "bg-card")
      }
    >
      {children}
    </div>
  )
}

function Message({ children }: { children: React.ReactNode }) {
  return (
    <p data-slot="key-check-message" className="text-sm">
      {children}
    </p>
  )
}

function ConfigPath({ path }: { path: string }) {
  return (
    <p data-slot="key-check-path" className="mt-2 text-xs text-muted-foreground">
      Key Config: <span className="font-mono">{path}</span>
    </p>
  )
}
