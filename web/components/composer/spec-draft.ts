/**
 * The editable form of a spec, and every check that can be made without the
 * server.
 *
 * Kept pure and separate from the editor component for two reasons: the checks
 * below encode real knowledge about what the core silently discards, which
 * deserves direct tests; and the component stays small enough to read.
 *
 * **Nothing here invents a default.** A role with no `llm` becomes a blank
 * provider, not `anthropic/claude-sonnet-4-6` — the real default is resolved
 * server-side at build time (`role.llm → request.default_llm → anthropic`), and
 * pre-filling a guess would put a routing on screen that the spec does not state
 * and that a Save would then make real.
 */
import type { FieldIssue, SpecView } from "@/lib/api-types";
import type { SpecEditInput } from "@/lib/api-client";
import {
  MAX_MODEL_ID_LENGTH,
  MAX_NAME_LENGTH,
  MAX_TEXT_LENGTH,
} from "@/lib/api-types";

/**
 * The provider ids the schema accepts — whatever `create_provider` resolves
 * (Story 2.0 Dev Notes / AC 10).
 *
 * There is deliberately **no model catalogue** to go with it. The only live
 * model list in the system comes from `normalize_team_routings`' per-provider
 * network calls at build time, and Story 2.0's AC 2 forbids an extra endpoint to
 * expose it — so the model is a free-text field. A hard-coded list here would be
 * fabricated data of exactly the class Story 2.1 rejected.
 */
export const PROVIDER_IDS = [
  "anthropic",
  "openai",
  "xai",
  "google",
  "ollama",
  "openrouter",
] as const;

/** `""` in `provider`/`model` means "inherit the server's default". */
export type RoleDraft = {
  name: string;
  description: string;
  provider: string;
  model: string;
};

export type TaskDraft = {
  name: string;
  description: string;
  agent_role: string;
  /** Displayed but not editable in this story; sent back unchanged. */
  dependencies: string[];
};

export type SpecDraft = {
  team_name: string;
  purpose: string;
  roles: RoleDraft[];
  tasks: TaskDraft[];
};

export function toDraft(spec: SpecView): SpecDraft {
  return {
    team_name: spec.team_name,
    purpose: spec.purpose,
    roles: spec.desired_roles.map((role) => ({
      name: role.name,
      description: role.description,
      provider: role.llm?.provider ?? "",
      model: role.llm?.model ?? "",
    })),
    tasks: spec.desired_tasks.map((task) => ({
      name: task.name,
      description: task.description,
      agent_role: task.agent_role,
      dependencies: [...task.dependencies],
    })),
  };
}

export function toEditInput(draft: SpecDraft): SpecEditInput {
  return {
    team_name: draft.team_name.trim(),
    purpose: draft.purpose.trim(),
    desired_roles: draft.roles.map((role) => {
      const provider = role.provider.trim();
      const model = role.model.trim();
      return {
        name: role.name.trim(),
        description: role.description.trim(),
        // Both or neither: `ProviderSelection` requires each field when the
        // object is present, so a half-filled routing is a 422.
        ...(provider && model ? { llm: { provider, model } } : {}),
      };
    }),
    desired_tasks: draft.tasks.map((task) => ({
      name: task.name.trim(),
      description: task.description.trim(),
      agent_role: task.agent_role.trim(),
      dependencies: task.dependencies,
    })),
  };
}

/** `request.py`'s role-name rule, checked here so it lands beside the field. */
const SNAKE_CASE = /^[a-z][a-z0-9_]*$/;

/**
 * Client-side pre-flight.
 *
 * Some of these duplicate a server check so the reason appears next to the input
 * instead of arriving as a 422. Three of them are checks the server does **not**
 * make, and each one corresponds to something the core discards in silence:
 *
 * - an empty roles list flips the build into a second LLM call through
 *   `planning_llm` — a different provider config, and unasked-for spend;
 * - two tasks with the same name collapse onto one manifest key, so one file is
 *   written while `task_count` reports two;
 * - a dependency naming no task is pruned by the template without a word, so
 *   renaming a task quietly breaks the DAG. `_check_task_integrity` checks
 *   duplicate task names and orphaned `agent_role` — it does not check this.
 */
export function draftIssues(draft: SpecDraft): FieldIssue[] {
  const issues: FieldIssue[] = [];

  if (draft.team_name.trim().length === 0) {
    issues.push({ path: "team_name", message: "Give the team a name." });
  } else if (draft.team_name.length > MAX_NAME_LENGTH) {
    issues.push({
      path: "team_name",
      message: `Use ${MAX_NAME_LENGTH} characters or fewer.`,
    });
  }

  // Every bound `api/schemas.py` enforces is checked here, not just some of them.
  // The gap mattered more than it looks: an unchecked bound reaches the server,
  // comes back as `too_long` with an empty `fields[]`, and lands in the one
  // failure shape the editor had no row to attach a reason to.
  if (draft.purpose.length > MAX_TEXT_LENGTH) {
    issues.push({
      path: "purpose",
      message: `Use ${MAX_TEXT_LENGTH} characters or fewer.`,
    });
  }

  if (draft.roles.length === 0) {
    issues.push({
      path: "desired_roles",
      message: "Add at least one role. A team with no roles cannot be built.",
    });
  }

  const roleNames = new Map<string, number>();
  draft.roles.forEach((role, index) => {
    const name = role.name.trim();
    if (name.length === 0) {
      issues.push({
        path: `desired_roles.${index}.name`,
        message: "Give the role a name.",
      });
    } else if (!SNAKE_CASE.test(name)) {
      issues.push({
        path: `desired_roles.${index}.name`,
        message:
          "Use lowercase letters, digits and underscores, starting with a letter.",
      });
    } else if (name.length > MAX_NAME_LENGTH) {
      issues.push({
        path: `desired_roles.${index}.name`,
        message: `Use ${MAX_NAME_LENGTH} characters or fewer.`,
      });
    } else if (roleNames.has(name)) {
      issues.push({
        path: `desired_roles.${index}.name`,
        message: `'${name}' is already used by another role; names must be unique.`,
      });
    }
    if (name.length > 0) roleNames.set(name, index);

    if (role.description.trim().length === 0) {
      issues.push({
        path: `desired_roles.${index}.description`,
        message: "Say what this role does.",
      });
    } else if (role.description.length > MAX_TEXT_LENGTH) {
      issues.push({
        path: `desired_roles.${index}.description`,
        message: `Use ${MAX_TEXT_LENGTH} characters or fewer.`,
      });
    }

    const provider = role.provider.trim();
    const model = role.model.trim();
    if (model.length > MAX_MODEL_ID_LENGTH) {
      issues.push({
        path: `desired_roles.${index}.llm.model`,
        message: `Use ${MAX_MODEL_ID_LENGTH} characters or fewer.`,
      });
    }
    if (provider && !model) {
      issues.push({
        path: `desired_roles.${index}.llm.model`,
        message: `Name a model for ${provider}, or clear the provider to use the default.`,
      });
    }
    if (!provider && model) {
      issues.push({
        path: `desired_roles.${index}.llm.provider`,
        message: "Choose a provider for that model, or clear the model.",
      });
    }
  });

  const taskNames = new Map<string, number>();
  draft.tasks.forEach((task, index) => {
    const name = task.name.trim();
    if (name.length === 0) {
      issues.push({
        path: `desired_tasks.${index}.name`,
        message: "Give the task a name.",
      });
    } else if (name.length > MAX_NAME_LENGTH) {
      issues.push({
        path: `desired_tasks.${index}.name`,
        message: `Use ${MAX_NAME_LENGTH} characters or fewer.`,
      });
    } else if (taskNames.has(name)) {
      issues.push({
        path: `desired_tasks.${index}.name`,
        message: `Two tasks are both named '${name}'; only one would be written.`,
      });
    }
    if (name.length > 0) taskNames.set(name, index);

    if (task.description.trim().length === 0) {
      issues.push({
        path: `desired_tasks.${index}.description`,
        message: "Say what this task does.",
      });
    } else if (task.description.length > MAX_TEXT_LENGTH) {
      issues.push({
        path: `desired_tasks.${index}.description`,
        message: `Use ${MAX_TEXT_LENGTH} characters or fewer.`,
      });
    }

    if (!roleNames.has(task.agent_role.trim())) {
      issues.push({
        path: `desired_tasks.${index}.agent_role`,
        message: `'${task.agent_role}' is not one of the team's roles.`,
      });
    }
  });

  const declaredTasks = new Set(
    draft.tasks.map((task) => task.name.trim()).filter((name) => name.length > 0)
  );
  draft.tasks.forEach((task, index) => {
    const dangling = task.dependencies.filter((dep) => !declaredTasks.has(dep));
    if (dangling.length > 0) {
      issues.push({
        path: `desired_tasks.${index}.dependencies`,
        message: `Depends on ${dangling.join(", ")}, which is not a task on this team. It would be dropped silently.`,
      });
    }
  });

  return issues;
}

export type GroupedIssues = {
  roleRows: Map<number, FieldIssue[]>;
  taskRows: Map<number, FieldIssue[]>;
  roleSection: FieldIssue[];
  taskSection: FieldIssue[];
  /** Anything that could not be placed. Rendered, never dropped. */
  other: FieldIssue[];
};

const ROW_PATH = /^desired_(roles|tasks)\.(\d+)(?:\.|$)/;

/**
 * Sorts `fields[]` into the rows they belong to.
 *
 * Total by construction: an unrecognised path lands in `other` and is still
 * rendered. A grouping that silently discarded a path the server sent would
 * block a build with no visible reason — which is exactly what
 * `EXPERIENCE.md:104` forbids.
 */
export function groupIssues(fields: FieldIssue[]): GroupedIssues {
  const grouped: GroupedIssues = {
    roleRows: new Map(),
    taskRows: new Map(),
    roleSection: [],
    taskSection: [],
    other: [],
  };

  for (const issue of fields) {
    const match = ROW_PATH.exec(issue.path);
    if (match) {
      const bucket = match[1] === "roles" ? grouped.roleRows : grouped.taskRows;
      const index = Number(match[2]);
      const existing = bucket.get(index);
      if (existing) existing.push(issue);
      else bucket.set(index, [issue]);
      continue;
    }
    if (issue.path === "desired_roles") {
      grouped.roleSection.push(issue);
      continue;
    }
    if (issue.path === "desired_tasks") {
      grouped.taskSection.push(issue);
      continue;
    }
    grouped.other.push(issue);
  }

  return grouped;
}
