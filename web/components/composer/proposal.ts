/**
 * The assistant's side of the conversation.
 *
 * **This copy is authored in the browser, and that is a declared addition, not
 * an oversight.** The API returns no assistant prose: `ComposerSession` keeps
 * only the intent and the current spec, and a turn's response is a
 * `TeamCreationRequest` and nothing else (`api/schemas.py:125-133`). AC 1 still
 * requires the assistant to "name the roles in pipeline order and ask one
 * targeted follow-up", so that sentence has to be derived from the spec here.
 *
 * Everything below is a pure function of the spec the server sent. Nothing is
 * invented: no model names, no capabilities, no counts that are not in the data.
 * The only authored content is the sentence frame and the follow-up question.
 */
import type { RoleView, SpecView, TaskView } from "@/lib/api-types";

/**
 * Tasks in dependency order.
 *
 * The server's order already respects dependencies in practice, but nothing in
 * the contract promises it — `desired_tasks` is whatever the LLM emitted — so
 * the order the user is shown is computed rather than trusted. Kahn's algorithm,
 * stable on the declared order so equal-depth tasks keep the author's sequence.
 */
export function orderedTasks(spec: SpecView): TaskView[] {
  const tasks = spec.desired_tasks;
  const known = new Set(tasks.map((task) => task.name));
  const remaining = new Map(tasks.map((task, index) => [index, task]));
  const emitted = new Set<string>();
  const ordered: TaskView[] = [];

  let progressed = true;
  while (remaining.size > 0 && progressed) {
    progressed = false;
    for (const [index, task] of [...remaining.entries()]) {
      // A dependency naming no task is ignored rather than treated as unmet:
      // the core prunes dangling dependencies at build time, and treating one
      // as a blocker here would stall the whole list on a typo.
      const blocked = task.dependencies.some(
        (dep) => known.has(dep) && !emitted.has(dep)
      );
      if (blocked) continue;
      ordered.push(task);
      emitted.add(task.name);
      remaining.delete(index);
      progressed = true;
    }
  }

  // A dependency cycle leaves entries that can never unblock. They are appended
  // in declared order rather than dropped — losing a task silently is worse
  // than showing it out of order, and `orderedTasks` must be total.
  for (const task of remaining.values()) ordered.push(task);
  return ordered;
}

/**
 * Roles ordered by the first task that uses them, with task-less roles last.
 *
 * Declaration order is not pipeline order: the captured turn-2 response inserted
 * `fact_checker` and rewired dependencies, and only the task graph shows where
 * it belongs.
 */
export function rolesInPipelineOrder(spec: SpecView): RoleView[] {
  const byName = new Map(spec.desired_roles.map((role) => [role.name, role]));
  const ordered: RoleView[] = [];
  const seen = new Set<string>();

  for (const task of orderedTasks(spec)) {
    const role = byName.get(task.agent_role);
    // No synthesised role for an orphaned `agent_role`: the roles list is the
    // only authority on which roles exist.
    if (!role || seen.has(role.name)) continue;
    seen.add(role.name);
    ordered.push(role);
  }
  for (const role of spec.desired_roles) {
    if (!seen.has(role.name)) ordered.push(role);
  }
  return ordered;
}

/**
 * A stable identifier for *which* follow-up was asked, so it can be asked once.
 *
 * The question text varies with the spec (it names a role), so the caller cannot
 * dedupe on the string. `null` means "nothing was asked that should be
 * remembered" — the generic closing question is repeatable by design.
 */
export type FollowUpKind = "routing" | "idle_role" | null;

export type Proposal = {
  summary: string;
  followUp: string;
  kind: FollowUpKind;
};

/**
 * One proposal sentence plus exactly one follow-up question.
 *
 * `EXPERIENCE.md:184` shows the shape ("proposes researcher → writer → editor →
 * critic and asks one follow-up"), and Story 1.3's Dev Notes require one
 * targeted question rather than a checklist — so the follow-ups below are a
 * precedence list, and only the first applicable one is asked.
 */
export function describeProposal(
  spec: SpecView,
  turn: number,
  /**
   * Follow-up kinds already asked in this conversation.
   *
   * Required for correctness, not politeness: the server never writes `llm` from
   * a conversational reply, so "use what I have" leaves the routing condition
   * permanently true. Without this the same question was re-asked on every turn,
   * forever — the opposite of the converging conversation AC 1 describes.
   */
  askedFollowUps: readonly string[] = []
): Proposal {
  const roles = rolesInPipelineOrder(spec);
  const names = roles.map((role) => role.name);

  const summary =
    names.length === 0
      ? turn <= 1
        ? "I could not settle on a set of roles from that description."
        : "That leaves the team with no roles."
      : turn <= 1
        ? `Here is a team for that: ${names.join(" → ")}.`
        : `Updated: ${names.join(" → ")}.`;

  return { summary, ...followUpFor(spec, roles, askedFollowUps) };
}

function followUpFor(
  spec: SpecView,
  roles: RoleView[],
  asked: readonly string[]
): { followUp: string; kind: FollowUpKind } {
  if (roles.length === 0) {
    return {
      followUp: "Could you describe the work you want done, in a sentence or two?",
      kind: null,
    };
  }

  // 1. Routing is the question EXPERIENCE.md:184 actually names, and it is the
  //    one the captured responses always provoke — every role came back with no
  //    `llm` at all. Asked at most once.
  if (!asked.includes("routing") && roles.some((role) => !role.llm)) {
    return {
      followUp: "Any model preferences, or should I pick from the keys you have?",
      kind: "routing",
    };
  }

  // 2. A role with no task will contribute nothing to the built package. Also
  //    asked at most once, for the same reason: the user may deliberately leave
  //    it, and re-asking would stall the conversation on their answer.
  const owners = new Set(spec.desired_tasks.map((task) => task.agent_role));
  const idle = roles.find((role) => !owners.has(role.name));
  if (idle && !asked.includes("idle_role")) {
    return { followUp: `What should ${idle.name} do?`, kind: "idle_role" };
  }

  // 3. Nothing specific is left to ask, so invite a change rather than assert the
  //    team is finished — the user decides when it is ready. Repeatable, and
  //    therefore carries no kind.
  const last = roles[roles.length - 1].name;
  return {
    followUp: `Anything you would change about ${last}, or is this ready to build?`,
    kind: null,
  };
}
