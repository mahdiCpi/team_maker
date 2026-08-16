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
import type {
  ApiFailure,
  FieldIssue,
  RoleKeyView,
  SpecView,
} from "@/lib/api-types"
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
 * per-agent Provider/model (`EXPERIENCE.md:33,73`) — plus `purpose`, the one
 * other field `PUT .../spec` accepts that carries no side effect. **`team_name`
 * is display-only**: renaming is Story 2.5's, and `api/output.py` pins
 * `output_path` from the *first* spec, so an editable name would show a renamed
 * team beside a path slugged from the old one (Open Question 5, settled at code
 * review: 2.2 displays the name and does not edit it).
 *
 * **Modal depth is one.** This is the `Dialog`, and there is no second layer
 * inside it: the provider control is a native `<select>` and the model is a text
 * input, so no picker ever opens over this one (`EXPERIENCE.md:38-39,103`). That
 * is why the installed `popover` component is unused by this story — no picker
 * layer beats a correctly nested one.
 *
 * **It re-renders from the response, never from local state.** A successful save
 * keeps the dialog *open* and the parent remounts this component by keying it on
 * `specRevision`, so the form is re-seeded from the spec the **server** returned
 * rather than from what was typed. That matters because `_pre_process` rewrites
 * input in five ways, so "edited JSON in" is not "JSON out". A rejected save
 * keeps this mounted with the user's draft intact so they can fix it, while the
 * parent's `spec` still holds the last good one.
 *
 * (An earlier version closed the dialog on success. That hid the server's
 * re-serialisation — the one thing this component exists to show — and left the
 * save with no confirmation at all.)
 *
 * **The editor owns every save failure while it is open**, not just
 * `spec_invalid`. The dialog is modal with a `fixed inset-0 z-50` backdrop, so a
 * message rendered by the parent would be painted underneath it: unreadable,
 * unfocusable, and indistinguishable from Save having done nothing.
 *
 * `Esc` closes it — Base UI's Dialog handles that, and it reaches `onClose`
 * through `onOpenChange`.
 */
export function SpecEditor({
  spec,
  failure,
  saving,
  savedNotice,
  keyRoles,
  blockedReason,
  onSave,
  onBuild,
  onClose,
  onEdit,
}: {
  spec: SpecView
  /** The whole save failure, not just `spec_invalid`'s `fields[]`. */
  failure: ApiFailure | null
  saving: boolean
  /** Set after a save succeeded, so the reopened form confirms it happened. */
  savedNotice: string | null
  /**
   * The key check for the *saved* spec (Story 2.3).
   *
   * Needed here and not only on the surface: this dialog has a `z-50` backdrop, so
   * the key-check banner behind it is invisible — the same reason the editor owns
   * its own failures. Without it, changing a role to a provider with no key would
   * get no feedback at all, on the one surface where that choice is made.
   */
  keyRoles: RoleKeyView[]
  /**
   * The surface's build gate, or `null` when it permits a build.
   *
   * Threaded in rather than recomputed: this dialog holds the fourth of four ways
   * to start a build, and its own reasons only know about saving and unsaved edits.
   */
  blockedReason: string | null
  onSave: (edit: SpecEditInput) => void
  onBuild: () => void
  onClose: () => void
  /** Lets an edit clear a server failure the editor cannot clear itself. */
  onEdit: () => void
}) {
  const pristine = React.useMemo(() => toDraft(spec), [spec])
  const [draft, setDraft] = React.useState<SpecDraft>(pristine)
  const [clientIssues, setClientIssues] = React.useState<FieldIssue[]>([])

  const serverIssues = failure?.code === "spec_invalid" ? failure.fields : []
  const dirty =
    JSON.stringify(toEditInput(draft)) !== JSON.stringify(toEditInput(pristine))
  const issues = [...clientIssues, ...serverIssues]
  const grouped = groupIssues(issues)

  function update(next: (current: SpecDraft) => SpecDraft) {
    setDraft(next)
    // Stale reasons must not outlive the edit that caused them — including the
    // server's, which live in the parent's `failure` and which the editor could
    // not previously clear, so a fixed row kept its 422 reason.
    setClientIssues([])
    if (failure) onEdit()
  }

  function handleSave() {
    // Guarded, like every other control. Without this, `aria-disabled` was
    // decorative and a double-click issued two concurrent PUTs — the later one
    // able to re-write the session spec back to the pre-remount draft.
    if (saving) return
    const found = draftIssues(draft)
    setClientIssues(found)
    if (found.length === 0) onSave(toEditInput(draft))
  }

  // `Build team` here must not build something other than what is on screen: an
  // unsaved edit is not in the session's spec, so building would silently
  // discard it. Stated as a reason rather than a dead control.
  //
  // `blockedReason` is the surface's own gate, threaded in so this control cannot
  // route around it. It is the fourth of four ways to start a build, and it was the
  // one that bypassed the Story 2.3 key check — the local reasons below are about
  // *this dialog's* state and would never have known about a missing key.
  // Editor-local reasons come first: they are the more immediate thing to fix.
  const buildBlockedReason = saving
    ? "Saving your changes…"
    : dirty
      ? "Save your changes first, then build."
      : blockedReason

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

        {savedNotice && !dirty && !failure ? (
          <p
            data-slot="spec-editor-saved"
            role="status"
            className="text-xs text-muted-foreground"
          >
            {savedNotice}
          </p>
        ) : null}

        {/* Every save failure surfaces here, inside the modal. `spec_invalid`
            additionally distributes its `fields[]` to the rows below. */}
        {failure ? (
          <p
            data-slot="spec-editor-failure"
            data-code={failure.code}
            role="alert"
            className="rounded-lg border border-destructive/40 px-3 py-2 text-sm"
          >
            {failure.message}
          </p>
        ) : null}

        {saving ? (
          <p
            data-slot="spec-editor-saving"
            role="status"
            className="text-xs text-muted-foreground"
          >
            Saving — the fields are locked until the server answers, because it
            re-serialises the team and this form re-renders from its reply.
          </p>
        ) : null}

        <IssueList issues={grouped.other} slot="spec-editor-general-issues" />

        {/* Display-only, decided at code review. AC 4 names exactly three
            editable dimensions, renaming is Story 2.5's, and `api/output.py`
            pins `output_path` from the FIRST spec — so an editable name would
            show a renamed team beside a path slugged from the old one. */}
        <Field label="Team name">
          <p data-slot="spec-editor-team-name" className="text-sm">
            {draft.team_name}
          </p>
        </Field>
        <Field label="Purpose">
          <Textarea
            aria-label="Purpose"
            rows={2}
            readOnly={saving}
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
                readOnly={saving}
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
                readOnly={saving}
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
                  disabled={saving}
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
                  readOnly={saving}
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
              <RoleKeyNote note={keyNoteFor(keyRoles, role)} />
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
                readOnly={saving}
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
                readOnly={saving}
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
                disabled={saving}
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
            // Without this the control announces as unavailable and the reason —
            // which is only adjacent text — is never announced with it.
            aria-describedby={
              buildBlockedReason ? EDITOR_BUILD_REASON_ID : undefined
            }
            data-slot="spec-editor-build"
          >
            Build team
          </Button>
        </DialogFooter>
        {buildBlockedReason ? (
          <p
            id={EDITOR_BUILD_REASON_ID}
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

const EDITOR_BUILD_REASON_ID = "spec-editor-build-reason"

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

/**
 * The key note for one editor row, or `null` when there is nothing honest to say.
 *
 * The check describes the **saved** spec, so it is only shown while the row still
 * matches what was checked. Change the provider and the note disappears rather than
 * asserting a status for a provider nobody has checked — a stale "key found" beside
 * a freshly typed provider is exactly the kind of claim this story exists to stop.
 *
 * An empty `provider` in the draft means "server default", which corresponds to the
 * checked role having inherited its routing.
 */
function keyNoteFor(
  keyRoles: RoleKeyView[],
  role: { name: string; provider: string }
): RoleKeyView | null {
  const checked = keyRoles.find((entry) => entry.role === role.name)
  if (!checked) return null
  const stillMatches =
    role.provider === ""
      ? checked.inherited_default
      : role.provider === checked.provider
  return stillMatches ? checked : null
}

function RoleKeyNote({ note }: { note: RoleKeyView | null }) {
  if (note === null) return null
  return (
    <p
      data-slot="spec-editor-role-key"
      data-status={note.status}
      data-usable={note.usable}
      className={
        "text-xs " + (note.usable ? "text-muted-foreground" : "text-destructive")
      }
    >
      {/* Colour is never the only carrier (`EXPERIENCE.md:117`), and an unusable
          row carries the server's own remedy rather than a re-authored one.
          `fix_hint` is guarded: interpolating a null into a template string printed
          the literal "null", where the JSX interpolation in `key-check.tsx` renders
          nothing — two sites behaving differently on the same input. */}
      {note.usable || !note.fix_hint
        ? note.detail
        : `${note.detail} — ${note.fix_hint}`}
    </p>
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
