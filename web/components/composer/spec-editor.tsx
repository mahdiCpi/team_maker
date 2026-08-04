"use client"

import * as React from "react"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import type { SpecEditInput } from "@/lib/api-client"
import type { FieldIssue, SpecView } from "@/lib/api-types"
import {
  PROVIDER_IDS,
  draftIssues,
  groupIssues,
  toDraft,
  toEditInput,
  type SpecDraft,
} from "@/components/composer/spec-draft"

/**
 * The review-before-build editor (AC 4).
 *
 * Exposes exactly the three dimensions the spine names — roles, tasks, and
 * per-agent Provider/model (`EXPERIENCE.md:33,73`) — plus the team name and
 * purpose, which are the other two fields `PUT .../spec` accepts.
 *
 * **Modal depth is one.** This is the `Dialog`, and there is no second layer
 * inside it: the provider control is a native `<select>` and the model is a text
 * input, so no picker ever opens over this one (`EXPERIENCE.md:38-39,103`). That
 * is why the installed `popover` component is unused by this story — no picker
 * layer beats a correctly nested one.
 *
 * **It re-renders from the response, never from local state.** The parent mounts
 * this only while the editor is open, and a successful save closes it; the next
 * open seeds a fresh draft from the spec the *server* returned. That matters
 * because `_pre_process` rewrites input in five ways, so "edited JSON in" is not
 * "JSON out". A rejected save keeps this mounted with the user's draft intact so
 * they can fix it, while the parent's `spec` still holds the last good one.
 *
 * `Esc` closes it — Base UI's Dialog handles that, and it reaches `onClose`
 * through `onOpenChange`.
 */
export function SpecEditor({
  spec,
  serverIssues,
  saving,
  savedNotice,
  onSave,
  onBuild,
  onClose,
}: {
  spec: SpecView
  /** `fields[]` from a rejected save. */
  serverIssues: FieldIssue[]
  saving: boolean
  /** Set after a save succeeded, so the reopened form confirms it happened. */
  savedNotice: string | null
  onSave: (edit: SpecEditInput) => void
  onBuild: () => void
  onClose: () => void
}) {
  const pristine = React.useMemo(() => toDraft(spec), [spec])
  const [draft, setDraft] = React.useState<SpecDraft>(pristine)
  const [clientIssues, setClientIssues] = React.useState<FieldIssue[]>([])

  const dirty =
    JSON.stringify(toEditInput(draft)) !== JSON.stringify(toEditInput(pristine))
  const issues = [...clientIssues, ...serverIssues]
  const grouped = groupIssues(issues)

  function update(next: (current: SpecDraft) => SpecDraft) {
    setDraft(next)
    // Stale reasons must not outlive the edit that caused them.
    setClientIssues([])
  }

  function handleSave() {
    const found = draftIssues(draft)
    setClientIssues(found)
    if (found.length === 0) onSave(toEditInput(draft))
  }

  // `Build team` here must not build something other than what is on screen: an
  // unsaved edit is not in the session's spec, so building would silently
  // discard it. Stated as a reason rather than a dead control.
  const buildBlockedReason = saving
    ? "Saving your changes…"
    : dirty
      ? "Save your changes first, then build."
      : null

  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) onClose()
      }}
    >
      <DialogContent
        data-slot="spec-editor"
        className="max-h-[85vh] overflow-y-auto sm:max-w-2xl"
      >
        <DialogHeader>
          <DialogTitle>Review before build</DialogTitle>
          <DialogDescription>
            Change the roles, the tasks, or which model each role uses. Saving
            re-validates the whole team.
          </DialogDescription>
        </DialogHeader>

        {savedNotice && !dirty ? (
          <p
            data-slot="spec-editor-saved"
            role="status"
            className="text-xs text-muted-foreground"
          >
            {savedNotice}
          </p>
        ) : null}

        <IssueList issues={grouped.other} slot="spec-editor-general-issues" />

        <Field label="Team name">
          <Input
            aria-label="Team name"
            value={draft.team_name}
            onChange={(event) =>
              update((current) => ({ ...current, team_name: event.target.value }))
            }
          />
        </Field>
        <Field label="Purpose">
          <Textarea
            aria-label="Purpose"
            rows={2}
            value={draft.purpose}
            onChange={(event) =>
              update((current) => ({ ...current, purpose: event.target.value }))
            }
          />
        </Field>

        <section data-slot="spec-editor-roles" className="flex flex-col gap-3">
          <h3 className="text-sm font-medium">Roles</h3>
          <IssueList issues={grouped.roleSection} slot="spec-editor-role-issues" />
          {draft.roles.map((role, index) => (
            <div
              key={index}
              data-slot="spec-editor-role"
              className="flex flex-col gap-2 rounded-lg border p-3"
            >
              <Input
                aria-label={`Role ${index + 1} name`}
                value={role.name}
                onChange={(event) =>
                  update((current) => ({
                    ...current,
                    roles: current.roles.map((item, at) =>
                      at === index ? { ...item, name: event.target.value } : item
                    ),
                  }))
                }
              />
              <Textarea
                aria-label={`Role ${index + 1} description`}
                rows={2}
                value={role.description}
                onChange={(event) =>
                  update((current) => ({
                    ...current,
                    roles: current.roles.map((item, at) =>
                      at === index
                        ? { ...item, description: event.target.value }
                        : item
                    ),
                  }))
                }
              />
              <div className="flex flex-wrap items-center gap-2">
                {/* A native select is a `SELECT`, which `nav-shortcuts.tsx:11`
                    already treats as a typing target, and it opens no second
                    modal layer. */}
                <select
                  aria-label={`Role ${index + 1} provider`}
                  className="h-9 rounded-lg border border-input bg-transparent px-2 text-sm"
                  value={role.provider}
                  onChange={(event) =>
                    update((current) => ({
                      ...current,
                      roles: current.roles.map((item, at) =>
                        at === index
                          ? { ...item, provider: event.target.value }
                          : item
                      ),
                    }))
                  }
                >
                  <option value="">Server default</option>
                  {PROVIDER_IDS.map((provider) => (
                    <option key={provider} value={provider}>
                      {provider}
                    </option>
                  ))}
                </select>
                <Input
                  aria-label={`Role ${index + 1} model`}
                  // Free text on purpose: there is no model catalogue to offer.
                  placeholder="model id"
                  className="max-w-56"
                  value={role.model}
                  onChange={(event) =>
                    update((current) => ({
                      ...current,
                      roles: current.roles.map((item, at) =>
                        at === index ? { ...item, model: event.target.value } : item
                      ),
                    }))
                  }
                />
              </div>
              <IssueList
                issues={grouped.roleRows.get(index) ?? []}
                slot="spec-editor-role-row-issues"
              />
            </div>
          ))}
        </section>

        <section data-slot="spec-editor-tasks" className="flex flex-col gap-3">
          <h3 className="text-sm font-medium">Tasks</h3>
          <IssueList issues={grouped.taskSection} slot="spec-editor-task-issues" />
          {draft.tasks.map((task, index) => (
            <div
              key={index}
              data-slot="spec-editor-task"
              className="flex flex-col gap-2 rounded-lg border p-3"
            >
              <Input
                aria-label={`Task ${index + 1} name`}
                value={task.name}
                onChange={(event) =>
                  update((current) => ({
                    ...current,
                    tasks: current.tasks.map((item, at) =>
                      at === index ? { ...item, name: event.target.value } : item
                    ),
                  }))
                }
              />
              <Textarea
                aria-label={`Task ${index + 1} description`}
                rows={2}
                value={task.description}
                onChange={(event) =>
                  update((current) => ({
                    ...current,
                    tasks: current.tasks.map((item, at) =>
                      at === index
                        ? { ...item, description: event.target.value }
                        : item
                    ),
                  }))
                }
              />
              <select
                aria-label={`Task ${index + 1} role`}
                className="h-9 w-fit rounded-lg border border-input bg-transparent px-2 text-sm"
                value={task.agent_role}
                onChange={(event) =>
                  update((current) => ({
                    ...current,
                    tasks: current.tasks.map((item, at) =>
                      at === index
                        ? { ...item, agent_role: event.target.value }
                        : item
                    ),
                  }))
                }
              >
                {/* The current value is offered even when it names no role, so
                    an orphaned task shows what it is actually assigned to
                    rather than silently reading as the first role. */}
                {!draft.roles.some((role) => role.name === task.agent_role) ? (
                  <option value={task.agent_role}>{task.agent_role}</option>
                ) : null}
                {draft.roles.map((role, at) => (
                  <option key={at} value={role.name}>
                    {role.name}
                  </option>
                ))}
              </select>
              {task.dependencies.length > 0 ? (
                <p className="text-xs text-muted-foreground">
                  Runs after {task.dependencies.join(", ")}.
                </p>
              ) : null}
              <IssueList
                issues={grouped.taskRows.get(index) ?? []}
                slot="spec-editor-task-row-issues"
              />
            </div>
          ))}
        </section>

        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose}>
            Close
          </Button>
          <Button
            type="button"
            variant="outline"
            onClick={handleSave}
            aria-disabled={saving}
            data-slot="spec-editor-save"
          >
            Save
          </Button>
          <Button
            type="button"
            onClick={() => {
              if (!buildBlockedReason) onBuild()
            }}
            aria-disabled={buildBlockedReason !== null}
            data-slot="spec-editor-build"
          >
            Build team
          </Button>
        </DialogFooter>
        {buildBlockedReason ? (
          <p
            data-slot="spec-editor-build-reason"
            className="text-xs text-muted-foreground"
          >
            {buildBlockedReason}
          </p>
        ) : null}
      </DialogContent>
    </Dialog>
  )
}

function Field({
  label,
  children,
}: {
  label: string
  children: React.ReactNode
}) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-xs text-muted-foreground">{label}</span>
      {children}
    </div>
  )
}

function IssueList({ issues, slot }: { issues: FieldIssue[]; slot: string }) {
  if (issues.length === 0) return null
  return (
    <ul data-slot={slot} className="flex flex-col gap-1">
      {issues.map((issue) => (
        <li key={`${issue.path}:${issue.message}`} className="text-xs text-destructive">
          {issue.message}
        </li>
      ))}
    </ul>
  )
}
