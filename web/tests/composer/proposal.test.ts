import { describe, expect, it } from "vitest";

import type { SpecView } from "@/lib/api-types";
import {
  describeProposal,
  orderedTasks,
  rolesInPipelineOrder,
} from "@/components/composer/proposal";
import { parseSessionResponse } from "@/lib/api-client";

import { messageTurn2, sessionCreate } from "./fixtures";

/**
 * These are pure-function unit tests. No network, no mocks, no stubs — the
 * inputs are the captured API bytes narrowed by the production parser.
 */

function specFrom(payload: unknown): SpecView {
  const view = parseSessionResponse(payload);
  if (!view) throw new Error("fixture failed to parse");
  return view.spec;
}

const CAPTURED_SPEC = specFrom(sessionCreate);
const CAPTURED_TURN_2 = specFrom(messageTurn2);

function spec(partial: Partial<SpecView>): SpecView {
  return {
    team_name: "t",
    purpose: "p",
    desired_roles: [],
    desired_tasks: [],
    ...partial,
  };
}

describe("orderedTasks", () => {
  it("keeps the captured order, which already respects dependencies", () => {
    expect(orderedTasks(CAPTURED_SPEC).map((t) => t.name)).toEqual([
      "research_topic",
      "draft_article",
      "critique_and_revise",
    ]);
  });

  it("sorts a dependency-shuffled list back into pipeline order", () => {
    const shuffled = spec({
      desired_tasks: [
        { name: "c", description: "", agent_role: "z", dependencies: ["b"] },
        { name: "a", description: "", agent_role: "x", dependencies: [] },
        { name: "b", description: "", agent_role: "y", dependencies: ["a"] },
      ],
    });
    expect(orderedTasks(shuffled).map((t) => t.name)).toEqual(["a", "b", "c"]);
  });

  it("does not drop tasks when dependencies form a cycle", () => {
    const cyclic = spec({
      desired_tasks: [
        { name: "a", description: "", agent_role: "x", dependencies: ["b"] },
        { name: "b", description: "", agent_role: "y", dependencies: ["a"] },
      ],
    });
    // Asserted on the count, not on absence: an implementation that silently
    // returned [] would satisfy "no wrong order" and lose the whole team.
    expect(orderedTasks(cyclic)).toHaveLength(2);
  });

  it("ignores a dependency that names no task rather than stalling", () => {
    const dangling = spec({
      desired_tasks: [
        { name: "a", description: "", agent_role: "x", dependencies: ["ghost"] },
      ],
    });
    expect(orderedTasks(dangling).map((t) => t.name)).toEqual(["a"]);
  });
});

describe("rolesInPipelineOrder", () => {
  it("orders the captured roles by the task that first uses them", () => {
    expect(rolesInPipelineOrder(CAPTURED_SPEC).map((r) => r.name)).toEqual([
      "researcher",
      "writer",
      "critic",
    ]);
  });

  it("puts the refinement's new fact_checker in its pipeline position", () => {
    // The captured turn-2 response inserted fact_checker between writer and
    // critic and rewired the dependencies; declaration order alone would not
    // produce this.
    expect(rolesInPipelineOrder(CAPTURED_TURN_2).map((r) => r.name)).toEqual([
      "researcher",
      "writer",
      "fact_checker",
      "critic",
    ]);
  });

  it("appends a role that owns no task instead of dropping it", () => {
    const withIdleRole = spec({
      desired_roles: [
        { name: "idle", description: "" },
        { name: "worker", description: "" },
      ],
      desired_tasks: [
        { name: "a", description: "", agent_role: "worker", dependencies: [] },
      ],
    });
    expect(rolesInPipelineOrder(withIdleRole).map((r) => r.name)).toEqual([
      "worker",
      "idle",
    ]);
  });

  it("never invents a role from a task's agent_role", () => {
    const orphanTask = spec({
      desired_roles: [{ name: "worker", description: "" }],
      desired_tasks: [
        { name: "a", description: "", agent_role: "ghost", dependencies: [] },
      ],
    });
    expect(rolesInPipelineOrder(orphanTask).map((r) => r.name)).toEqual(["worker"]);
  });
});

describe("describeProposal", () => {
  it("names the captured roles in pipeline order", () => {
    const { summary } = describeProposal(CAPTURED_SPEC, 1);
    expect(summary).toContain("researcher");
    expect(summary).toContain("writer");
    expect(summary).toContain("critic");
    expect(summary.indexOf("researcher")).toBeLessThan(summary.indexOf("writer"));
    expect(summary.indexOf("writer")).toBeLessThan(summary.indexOf("critic"));
  });

  it("asks exactly one question, not a checklist", () => {
    for (const turn of [1, 2, 5]) {
      const { summary, followUp } = describeProposal(CAPTURED_SPEC, turn);
      const questionMarks = `${summary} ${followUp}`.match(/\?/g) ?? [];
      expect(questionMarks).toHaveLength(1);
    }
  });

  it("asks about models while any role has no explicit one", () => {
    // Every captured role omits `llm`, so this is the real first follow-up.
    expect(describeProposal(CAPTURED_SPEC, 1).followUp).toMatch(/model/i);
  });

  it("moves on once every role has a model", () => {
    const routed = spec({
      desired_roles: [
        {
          name: "worker",
          description: "",
          llm: { provider: "anthropic", model: "claude-sonnet-4-6" },
        },
      ],
      desired_tasks: [
        { name: "a", description: "", agent_role: "worker", dependencies: [] },
      ],
    });
    expect(describeProposal(routed, 2).followUp).not.toMatch(/model/i);
  });

  it("asks what an idle role should do when one owns no task", () => {
    const withIdleRole = spec({
      desired_roles: [
        {
          name: "loiterer",
          description: "",
          llm: { provider: "anthropic", model: "m" },
        },
        {
          name: "worker",
          description: "",
          llm: { provider: "anthropic", model: "m" },
        },
      ],
      desired_tasks: [
        { name: "a", description: "", agent_role: "worker", dependencies: [] },
      ],
    });
    expect(describeProposal(withIdleRole, 2).followUp).toContain("loiterer");
  });

  it("uses the product's voice: no emoji, no exclamation, no hype", () => {
    for (const turn of [1, 2, 3]) {
      const { summary, followUp } = describeProposal(CAPTURED_TURN_2, turn);
      const text = `${summary} ${followUp}`;
      expect(text).not.toMatch(/!/);
      expect(text).not.toMatch(/[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}]/u);
      expect(text).not.toMatch(/dream team|amazing|awesome|let's go/i);
    }
  });

  it("distinguishes the first proposal from a refinement", () => {
    const first = describeProposal(CAPTURED_SPEC, 1).summary;
    const later = describeProposal(CAPTURED_SPEC, 3).summary;
    expect(first).not.toBe(later);
  });

  it("says something usable even for a spec with no roles at all", () => {
    const { summary, followUp } = describeProposal(spec({}), 1);
    expect(summary.length).toBeGreaterThan(0);
    expect(followUp.length).toBeGreaterThan(0);
  });
});
