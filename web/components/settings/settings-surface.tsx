"use client"

import { useEffect, useState } from "react"
import type { KeyStatusView, ProviderKeyView } from "@/lib/api-types"
import { getKeyStatus } from "@/lib/api-client/keys"

/**
 * Settings surface component for Story 2.6.
 *
 * Renders the Key Config path and per-provider key status information.
 * Follows the same pattern as composer-surface.tsx with client-side fetching.
 */

/** The short word paired with a provider's status badge. */
const STATUS_WORD: Record<string, string> = {
  available: "key found",
  "keyless-local": "local",
  "via-openrouter": "via OpenRouter",
  missing: "key missing",
  "unsupported-by-runtime": "not supported",
  unrecognized: "unknown provider",
}

function statusWord(provider: ProviderKeyView): string {
  // Falls back to the server's own `detail` rather than a guess, so a status this
  // build has not heard of still renders something true (key-check.tsx precedent).
  return STATUS_WORD[provider.status] ?? provider.detail
}

/** Joins names with an Oxford "and" before the last item. */
function joinWithAnd(items: string[]): string {
  if (items.length <= 1) return items.join("")
  if (items.length === 2) return `${items[0]} and ${items[1]}`
  return `${items.slice(0, -1).join(", ")}, and ${items[items.length - 1]}`
}

/**
 * OpenRouter gateway explanation text.
 * One key unlocks many models — EXPERIENCE.md:127-128
 */
const OPENROUTER_EXPLANATION = "One key unlocks many models."

/**
 * Safe-key guidance copy in the established Voice register.
 * Plain, confident, helpful; no hype, no jargon.
 */
const SAFE_KEY_GUIDANCE = (
  <>
    <p className="text-sm text-muted-foreground mt-4">
      Keep your Key Config file out of version control. Never paste or share its
      contents in chat, tickets, or screenshots. If a key may have leaked, rotate it
      at the provider.
    </p>
  </>
)

export function SettingsSurface() {
  const [keyStatus, setKeyStatus] = useState<KeyStatusView | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    async function fetchKeyStatus() {
      try {
        const result = await getKeyStatus()
        if (cancelled) return

        if (result.ok) {
          setKeyStatus(result.data)
        } else {
          setError(`Failed to load key status: ${result.message}`)
        }
      } catch (err) {
        if (cancelled) return
        setError(`Failed to load key status: ${err instanceof Error ? err.message : String(err)}`)
      } finally {
        if (!cancelled) {
          setIsLoading(false)
        }
      }
    }

    fetchKeyStatus()

    return () => {
      cancelled = true
    }
  }, [])

  if (isLoading) {
    return (
      <div className="space-y-4" aria-busy="true">
        <p className="text-sm text-muted-foreground">Loading key status...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="space-y-4" role="status" aria-live="polite">
        <p className="text-sm text-destructive">{error}</p>
      </div>
    )
  }

  if (!keyStatus) {
    return (
      <div className="space-y-4" role="status">
        <p className="text-sm text-muted-foreground">No key status available.</p>
      </div>
    )
  }

  return (
    <div data-slot="settings-surface" className="space-y-6" role="status" aria-label="Key configuration status">
      {/* Key Config Path */}
      <div className="rounded-lg border bg-card px-4 py-3">
        <p className="text-sm font-medium">Key Config Path</p>
        <p className="mt-1 text-sm text-muted-foreground font-mono">
          {keyStatus.key_config_path}
        </p>
      </div>

      {/* Load Warnings — no role="alert": the outer surface's role="status" already
          owns this region, and two assertive live regions would talk over each
          other (key-check.tsx's Panel documents the same choice). */}
      {keyStatus.load_warnings.length > 0 && (
        <div className="rounded-lg border border-destructive/40 bg-card px-4 py-3">
          <p className="text-sm font-medium text-destructive">Load Warnings</p>
          <ul className="mt-2 space-y-1">
            {keyStatus.load_warnings.map((warning, index) => (
              <li key={index} className="text-sm text-destructive">
                {warning}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Needs Restart Notice */}
      {keyStatus.needs_restart_to_author.length > 0 && (
        <div className="rounded-lg border bg-card px-4 py-3">
          <p className="text-sm text-muted-foreground">
            {joinWithAnd(keyStatus.needs_restart_to_author)} {
              keyStatus.needs_restart_to_author.length === 1 ? "was" : "were"
            } changed in your Key Config after the API started. Running a built team
            picks that up, but composing needs the API restarted.
          </p>
        </div>
      )}

      {/* Provider Status List */}
      <div className="rounded-lg border bg-card px-4 py-3">
        <p className="text-sm font-medium">Provider Key Status</p>

        {keyStatus.providers.length === 0 ? (
          <p className="mt-2 text-sm text-muted-foreground">
            No providers configured.
          </p>
        ) : (
          <ul data-slot="settings-provider-list" className="mt-2 space-y-2">
            {keyStatus.providers.map((provider) => {
              const isOpenRouter = provider.name === "openrouter"
              const showFixHint = provider.fix_hint && provider.fix_hint.length > 0

              return (
                <li
                  key={provider.name}
                  data-slot="settings-provider-row"
                  data-provider={provider.name}
                  data-status={provider.status}
                  data-usable={provider.usable}
                  className="flex items-center justify-between rounded-md border px-3 py-2"
                >
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium">{provider.name}</span>
                    <span
                      data-slot="settings-provider-badge"
                      className={`text-xs rounded-full px-2 py-0.5 ${
                        provider.usable
                          ? "bg-muted text-foreground"
                          : "border border-destructive/40 text-destructive"
                      }`}
                    >
                      {statusWord(provider)}
                    </span>
                    {isOpenRouter && (
                      <span className="text-xs text-muted-foreground">
                        ({OPENROUTER_EXPLANATION})
                      </span>
                    )}
                  </div>

                  {showFixHint && (
                    <span className="text-xs text-muted-foreground">
                      {provider.fix_hint}
                    </span>
                  )}
                </li>
              )
            })}
          </ul>
        )}
      </div>

      {/* Safe Key Guidance */}
      <div className="rounded-lg border bg-card px-4 py-3">
        {SAFE_KEY_GUIDANCE}
      </div>
    </div>
  )
}
