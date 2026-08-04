import { describe, expect, it } from "vitest";

import {
  PROVIDER_IDS,
  draftIssues,
  groupIssues,
  toDraft,
  toEditInput,
  type SpecDraft,
} from "@/components/composer/spec-draft";
import { parseSessionResponse } from "@/lib/api-client";
import type { FieldIssue, SpecView } from "@/lib/api-types";

import { sessionCreate, specEdit } from "./fixtures";

/** Pure unit tests over the captured API bytes. No mocks, no rendering. */

function specFrom(payload: unknown): SpecView {
  const view = parseSessionResponse(payload);
  if (!view) throw new Error("fixture failed to parse");
  return view.spec;
}

const CAPTURED = specFrom(sessionCreate);
const CAPTURED_WITH_LLM = specFrom(specEdit);

describe("toDraft", () => {
  it("carries the captured roles and tasks across", () => {
    const draft = toDraft(CAPTURED);
    expect(draft.team_name).toBe("article_team");
    expect(draft.roles.map((r) => r.name)).toEqual([
      "researcher",
      "writer",
      "critic",
    ]);
    expect(draft.tasks.map((t) => t.name)).toEqual([
      "research_topic",
      "draft_article",
      "critique_and_revise",
    ]);
  });

  it("represents an absent llm as an empty provider, not as a fabricated default", () => {
    // Every captured role omits `llm`. Showing `anthropic/claude-sonnet-4-6`
    // here would be inventing a routing the spec does not state; the real
    // default is resolved server-side at build time.
    const draft = toDraft(CAPTURED);
    expect(draft.roles.every((r) => r.provider === "" && r.model === "")).toBe(true);
  });

  it("keeps an llm the server did send", () => {
    const critic = toDraft(CAPTURED_WITH_LLM).roles.find((r) => r.name === "critic");
    expect(critic?.provider).toBe("openai");
    expect(critic?.model).toBe("gpt-4o");
  });

  it("preserves dependencies verbatim", () => {
    const draft = toDraft(CAPTURED);
    expect(draft.tasks[1].dependencies).toEqual(["research_topic"]);
  });
});

describe("toEditInput", () => {
  it("round-trips a draft back into the four permitted dimensions", () => {
    const input = toEditInput(toDraft(CAPTURED));
    expect(Object.keys(input).sort()).toEqual([
      "desired_roles",
      "desired_tasks",
      "purpose",
      "team_name",
    ]);
  });

  it("omits llm entirely when the provider is blank", () => {
    const input = toEditInput(toDraft(CAPTURED));
    expect(input.desired_roles.every((role) => role.llm === undefined)).toBe(true);
  });

  it("emits llm when both provider and model are filled in", () => {
    const input = toEditInput(toDraft(CAPTURED_WITH_LLM));
    const critic = input.desired_roles.find((r) => r.name === "critic");
    expect(critic?.llm).toEqual({ provider: "openai", model: "gpt-4o" });
  });

  it("trims whitespace the user typed around a model id", () => {
    const draft = toDraft(CAPTURED);
    draft.roles[0].provider = "openai";
    draft.roles[0].model = "  gpt-4o  ";
    const input = toEditInput(draft);
    expect(input.desired_roles[0].llm).toEqual({
      provider: "openai",
      model: "gpt-4o",
    });
  });
});

describe("PROVIDER_IDS", () => {
  it("lists only ids `create_provider` resolves, and no model catalogue", () => {
    // Story 2.0 AC 10 / Dev Notes. There is deliberately no model list: the only
    // live one comes from per-provider network calls at build time, and AC 2
    // forbids an extra endpoint to expose it.
    expect([...PROVIDER_IDS]).toEqual([
      "anthropic",
      "openai",
      "xai",
      "google",
      "ollama",
      "openrouter",
    ]);
  });
});

function draft(partial: Partial<SpecDraft>): SpecDraft {
  return {
    team_name: "t",
    purpose: "p",
    roles: [{ name: "worker", description: "Works.", provider: "", model: "" }],
    tasks: [],
    ...partial,
  };
}

describe("draftIssues", () => {
  it("passes a clean captured draft", () => {
    expect(draftIssues(toDraft(CAPTURED))).toEqual([]);
  });

  it("refuses an empty roles list, which the server would not reject", () => {
    // An empty `desired_roles` flips the build into a second LLM call through
    // `planning_llm` — a different provider config, and silent cost.
    const issues = draftIssues(draft({ roles: [] }));
    expect(issues.map((i) => i.path)).toContain("desired_roles");
  });

  it("catches a blank role name and a blank description", () => {
    const issues = draftIssues(
      draft({ roles: [{ name: "  ", description: "", provider: "", model: "" }] })
    );
    expect(issues.length).toBeGreaterThan(0);
    expect(issues.map((i) => i.path)).toContain("desired_roles.0.name");
  });

  it("catches a role name that is not snake_case", () => {
    // `request.py` enforces `^[a-z][a-z0-9_]*$`; catching it here turns a 422
    // into an inline reason next to the field.
    const issues = draftIssues(
      draft({ roles: [{ name: "Bad Name", description: "x", provider: "", model: "" }] })
    );
    expect(issues.map((i) => i.path)).toContain("desired_roles.0.name");
  });

  it("catches duplicate role names", () => {
    const issues = draftIssues(
      draft({
        roles: [
          { name: "dup", description: "a", provider: "", model: "" },
          { name: "dup", description: "b", provider: "", model: "" },
        ],
      })
    );
    expect(issues.some((i) => /unique|already/i.test(i.message))).toBe(true);
  });

  it("catches a provider chosen with no model, and a model with no provider", () => {
    const noModel = draftIssues(
      draft({
        roles: [{ name: "worker", description: "x", provider: "openai", model: "" }],
      })
    );
    const noProvider = draftIssues(
      draft({
        roles: [{ name: "worker", description: "x", provider: "", model: "gpt-4o" }],
      })
    );
    // `ProviderSelection` requires both fields, so half a routing is a 422.
    expect(noModel.map((i) => i.path)).toContain("desired_roles.0.llm.model");
    expect(noProvider.map((i) => i.path)).toContain("desired_roles.0.llm.provider");
  });

  it("catches a task assigned to a role that no longer exists", () => {
    const issues = draftIssues(
      draft({
        tasks: [
          { name: "a", description: "x", agent_role: "ghost", dependencies: [] },
        ],
      })
    );
    expect(issues.map((i) => i.path)).toContain("desired_tasks.0.agent_role");
  });

  it("catches duplicate task names, which collapse onto one file at build time", () => {
    const issues = draftIssues(
      draft({
        tasks: [
          { name: "dup", description: "x", agent_role: "worker", dependencies: [] },
          { name: "dup", description: "y", agent_role: "worker", dependencies: [] },
        ],
      })
    );
    expect(issues.filter((i) => i.path.startsWith("desired_tasks")).length)
      .toBeGreaterThan(0);
  });

  it("catches a dependency that names no task — the server does NOT", () => {
    // `_check_task_integrity` checks duplicate names and orphan agent_role only.
    // A dangling dependency is pruned silently by the template, so renaming a
    // task would quietly break the DAG with no error anywhere.
    const issues = draftIssues(
      draft({
        tasks: [
          {
            name: "second",
            description: "x",
            agent_role: "worker",
            dependencies: ["renamed_away"],
          },
        ],
      })
    );
    expect(issues.map((i) => i.path)).toContain("desired_tasks.0.dependencies");
  });

  it("accepts a dependency that does name a task", () => {
    const issues = draftIssues(
      draft({
        tasks: [
          { name: "first", description: "x", agent_role: "worker", dependencies: [] },
          {
            name: "second",
            description: "y",
            agent_role: "worker",
            dependencies: ["first"],
          },
        ],
      })
    );
    expect(issues).toEqual([]);
  });
});

describe("groupIssues", () => {
  const fields: FieldIssue[] = [
    { path: "desired_roles.1.name", message: "role one" },
    { path: "desired_tasks.0.agent_role", message: "task zero" },
    { path: "desired_roles", message: "roles section" },
    { path: "desired_tasks", message: "tasks section" },
    { path: "(root)", message: "root level" },
    { path: "team_name", message: "name level" },
  ];

  it("routes indexed paths to their row", () => {
    const grouped = groupIssues(fields);
    expect(grouped.roleRows.get(1)?.map((i) => i.message)).toEqual(["role one"]);
    expect(grouped.taskRows.get(0)?.map((i) => i.message)).toEqual(["task zero"]);
  });

  it("routes section paths to their section", () => {
    const grouped = groupIssues(fields);
    expect(grouped.roleSection.map((i) => i.message)).toEqual(["roles section"]);
    expect(grouped.taskSection.map((i) => i.message)).toEqual(["tasks section"]);
  });

  it("loses nothing: every issue lands in exactly one bucket", () => {
    const grouped = groupIssues(fields);
    const placed = [
      ...[...grouped.roleRows.values()].flat(),
      ...[...grouped.taskRows.values()].flat(),
      ...grouped.roleSection,
      ...grouped.taskSection,
      ...grouped.other,
    ];
    // Counted rather than checked for absence: an implementation that dropped
    // an unrecognised path would still satisfy every assertion above.
    expect(placed).toHaveLength(fields.length);
    expect(new Set(placed.map((i) => i.message)).size).toBe(fields.length);
  });

  it("keeps an unrecognised path rather than discarding it", () => {
    const grouped = groupIssues([{ path: "planning_llm.provider", message: "odd" }]);
    expect(grouped.other.map((i) => i.message)).toEqual(["odd"]);
  });
});
