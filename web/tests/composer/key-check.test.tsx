import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { KeyCheck } from "@/components/composer/key-check";
import { parseKeyCheck, parseKeyStatus } from "@/lib/api-client";

import {
  keyCheckAllGood,
  keyCheckMissingKey,
  keyStatusHasKeys,
  keyStatusNoKeys,
} from "./fixtures";

/**
 * The four UX-DR5 states as rendered (Story 2.3, AC 4 / AC 5).
 *
 * Every input is narrowed from a **captured** server body through the production
 * parser, so nothing here asserts against a hand-written shape.
 *
 * Copy is quoted verbatim from `EXPERIENCE.md:85-88`. One deliberate deviation:
 * the spine's "(Settings)" is replaced by the real Key Config path, because
 * Settings holds no key guidance until Story 2.6 and `EXPERIENCE.md:104` bans dead
 * affordances — see the story's AC 9.
 */

const noKeys = parseKeyStatus(keyStatusNoKeys)!;
const hasKeys = parseKeyStatus(keyStatusHasKeys)!;
const allGood = parseKeyCheck(keyCheckAllGood)!;
const missingKey = parseKeyCheck(keyCheckMissingKey)!;

function root(container: HTMLElement) {
  return container.querySelector('[data-slot="key-check"]');
}

function message(container: HTMLElement) {
  return container.querySelector('[data-slot="key-check-message"]')?.textContent ?? "";
}

function badges(container: HTMLElement) {
  return Array.from(container.querySelectorAll('[data-slot="key-check-badge"]'));
}

describe("nothing is claimed before anything is known", () => {
  it("renders nothing at all with no status and no check", () => {
    const { container } = render(<KeyCheck status={null} check={null} />);

    expect(root(container)).toBeNull();
  });

  it("stays silent when keys exist but no team does yet", () => {
    // "All models reachable" is a claim about a *team*. With no roles there is
    // nothing to have checked, so saying it would be fabricated reassurance.
    const { container } = render(<KeyCheck status={hasKeys} check={null} />);

    expect(root(container)).toBeNull();
  });
});

describe("no keys at all", () => {
  it("renders the spine's sentence before any team exists", () => {
    const { container } = render(<KeyCheck status={noKeys} check={null} />);

    expect(root(container)).not.toBeNull();
    expect(root(container)!.getAttribute("data-state")).toBe("no-keys");
    expect(message(container)).toBe(
      "You'll need at least one model key to run. Add one in your Key Config, or add an OpenRouter key to unlock many models."
    );
  });

  it("names the Key Config file instead of linking to a Settings page with nothing on it", () => {
    const { container } = render(<KeyCheck status={noKeys} check={null} />);

    expect(
      container.querySelector('[data-slot="key-check-path"]')?.textContent
    ).toContain(noKeys.key_config_path);
    // AC 9: the link is deliberately not built, and Settings stays Story 2.6's.
    expect(container.querySelectorAll("a")).toHaveLength(0);
  });
});

describe("all good", () => {
  it("renders the spine's sentence", () => {
    const { container } = render(<KeyCheck status={hasKeys} check={allGood} />);

    expect(root(container)!.getAttribute("data-state")).toBe("all-good");
    expect(message(container)).toBe("All models reachable.");
  });

  it("badges every role neutrally, pairing the provider with a status word", () => {
    const { container } = render(<KeyCheck status={hasKeys} check={allGood} />);

    const rendered = badges(container);
    expect(rendered).toHaveLength(3);
    // UX-DR9 / `EXPERIENCE.md:117`: colour is never the only carrier, so the state
    // must be present as *words*.
    //
    // The earlier assertion was `textContent.length > "anthropic".length`, which the
    // role name alone already satisfied — it would have passed with no status word
    // rendered at all, i.e. with the property under test absent.
    for (const badge of rendered) {
      expect(badge.textContent).toContain("anthropic");
      expect(badge.textContent).toContain("key found");
      expect(badge.getAttribute("data-usable")).toBe("true");
    }
  });

  it("spells out each of the five statuses as words, not colour alone", () => {
    const everyStatus = {
      ...allGood,
      roles: [
        { ...allGood.roles[0], role: "a", status: "available", usable: true },
        { ...allGood.roles[0], role: "b", status: "keyless-local", usable: true },
        { ...allGood.roles[0], role: "c", status: "via-openrouter", usable: true },
      ],
    };

    const { container } = render(<KeyCheck status={hasKeys} check={everyStatus} />);
    const words = badges(container).map((badge) => badge.textContent ?? "");

    expect(words[0]).toContain("key found");
    expect(words[1]).toContain("local");
    expect(words[2]).toContain("via OpenRouter");
  });
});

describe("via OpenRouter", () => {
  it("labels the route on the badge and in the message", () => {
    // Derived from the captured all-good check by moving its roles onto the
    // gateway, which is the one state no capture could pin deterministically:
    // it depends on which keys the capturing machine has.
    const viaOpenRouter = {
      ...allGood,
      overall: "via-openrouter" as const,
      roles: allGood.roles.map((role) => ({
        ...role,
        status: "via-openrouter",
        detail: "reachable via OpenRouter key",
      })),
    };

    const { container } = render(<KeyCheck status={hasKeys} check={viaOpenRouter} />);

    expect(message(container)).toBe("OpenRouter key found — routed models available.");
    expect(badges(container)[0].textContent).toContain("via OpenRouter");
  });
});

describe("missing key", () => {
  it("uses the spine's sentence when a single role is short a key", () => {
    const oneMissing = {
      ...missingKey,
      // Set explicitly, not inherited: the captured body pins its role to `groq`, so
      // its aggregate is `unsupported`. This case is the other one — a key that is
      // genuinely absent and genuinely addable.
      overall: "missing-key",
      roles: [
        missingKey.roles[0],
        {
          ...missingKey.roles[1],
          provider: "openai",
          status: "missing",
          detail: "no key found",
          usable: false,
          fix_hint: "add OPENAI_API_KEY to your Key Config.",
        },
      ],
    };

    const { container } = render(<KeyCheck status={hasKeys} check={oneMissing} />);

    // `EXPERIENCE.md:86`, verbatim — including the "(Settings)" parenthetical. An
    // earlier version substituted the Key Config path into the sentence; AC 9
    // authorised that for the *no-keys* banner only, so it was an undeclared
    // deviation from AC 4's "verbatim" requirement. Better Settings key guidance is
    // tracked for Story 2.6 instead.
    expect(root(container)!.getAttribute("data-state")).toBe("missing-key");
    expect(message(container)).toBe(
      "openai key missing — add it to your Key Config (Settings), or switch this agent to a model you have."
    );
    // The path is still shown, on its own line rather than inside the sentence.
    expect(
      container.querySelector('[data-slot="key-check-path"]')?.textContent
    ).toContain(oneMissing.key_config_path);
  });

  it("does not call an unsupported provider a missing key", () => {
    // The captured check pins a role to `groq`, whose key is not missing: the
    // engine simply cannot use it. `deferred-work.md:85` records a user adding the
    // right key and the run breaking anyway.
    const { container } = render(<KeyCheck status={hasKeys} check={missingKey} />);

    expect(message(container)).not.toContain("key missing");
    expect(message(container)).toContain("cannot run yet");
  });

  it("shows the server's hint for the affected role, and never asks for a groq key", () => {
    const { container } = render(<KeyCheck status={hasKeys} check={missingKey} />);
    const text = container.textContent ?? "";

    expect(text).toContain("no native groq provider");
    expect(text).not.toContain("GROQ_API_KEY");
  });

  it("flags the affected role's badge and leaves the healthy one alone", () => {
    const { container } = render(<KeyCheck status={hasKeys} check={missingKey} />);
    const [writer, judge] = badges(container);

    expect(writer.getAttribute("data-usable")).toBe("true");
    expect(judge.getAttribute("data-usable")).toBe("false");
    expect(judge.textContent).toContain("groq");
  });

  it("offers no way to enter a key", () => {
    const { container } = render(<KeyCheck status={hasKeys} check={missingKey} />);

    // `EXPERIENCE.md:103` bans key entry in the UI outright.
    expect(container.querySelectorAll("input")).toHaveLength(0);
    expect(container.querySelectorAll("textarea")).toHaveLength(0);
  });
});

describe("the planner path", () => {
  it("says the models are not chosen yet rather than badging nothing", () => {
    const planner = { ...allGood, overall: "unknown" as const, roles: [] };

    const { container } = render(<KeyCheck status={hasKeys} check={planner} />);

    expect(root(container)!.getAttribute("data-state")).toBe("unknown");
    expect(badges(container)).toHaveLength(0);
    expect(message(container)).toContain("when the team is built");
  });
});

describe("a key added while the server was running", () => {
  it("says composing needs a restart, without contradicting the status", () => {
    const restarting = { ...hasKeys, needs_restart_to_author: ["openai"] };

    const { container } = render(<KeyCheck status={restarting} check={allGood} />);
    const note = container.querySelector('[data-slot="key-check-restart"]')?.textContent ?? "";

    expect(note).toContain("openai");
    expect(note).toMatch(/restart/i);
  });

  it("prefers the check's list, which is the only one read per request", () => {
    // The AC 3 flow, and the one the first version could not render. The provider
    // status is fetched and reports nothing pending; the per-team check — issued
    // after it — reports that a key was just changed. The check has to win.
    //
    // `??` was the bug: it falls through only on null/undefined, and `[]` is neither,
    // so a successful status read permanently shadowed the fresh list. The previous
    // test injected the flag through `status`, i.e. through the branch that worked,
    // which is why it could not fail.
    const stale = { ...hasKeys, needs_restart_to_author: [] };
    const fresh = { ...allGood, needs_restart_to_author: ["openai"] };

    const { container } = render(<KeyCheck status={stale} check={fresh} />);
    const note =
      container.querySelector('[data-slot="key-check-restart"]')?.textContent ?? "";

    expect(note).toContain("openai");
    expect(note).toMatch(/restart/i);
  });

  it("omits the note when nothing was added late", () => {
    const { container } = render(<KeyCheck status={hasKeys} check={allGood} />);

    expect(container.querySelector('[data-slot="key-check-restart"]')).toBeNull();
  });
});

describe("the editor's per-row key note", () => {
  it("shows the checked status beside the row it describes", async () => {
    const { SpecEditor } = await import("@/components/composer/spec-editor");
    const spec = {
      team_name: "Docs",
      purpose: "Write docs.",
      // Pinned to the same provider the captured check ran against, or the row
      // would legitimately have nothing to say (see the next test).
      desired_roles: [
        {
          name: "judge",
          description: "Judges.",
          llm: { provider: "groq", model: "llama-3.1-70b" },
        },
      ],
      desired_tasks: [],
    };
    const judge = { ...missingKey.roles[1], role: "judge" };

    render(
      <SpecEditor
        spec={spec}
        failure={null}
        saving={false}
        savedNotice={null}
        keyRoles={[judge]}
        blockedReason={null}
        onSave={() => {}}
        onBuild={() => {}}
        onClose={() => {}}
        onEdit={() => {}}
      />
    );

    // `document`, not `container`: the Dialog renders through a portal, so a
    // container query would find nothing and every assertion below would pass
    // vacuously.
    await screen.findByRole("textbox", { name: "Role 1 name" });
    const note = document.querySelector('[data-slot="spec-editor-role-key"]');
    // The dialog's backdrop hides the surface banner, so this row has to say it.
    expect(note).not.toBeNull();
    expect(note!.getAttribute("data-usable")).toBe("false");
    expect(note!.textContent).toContain("no native groq provider");
  });

  it("drops the note once the row's provider no longer matches what was checked", async () => {
    const { SpecEditor } = await import("@/components/composer/spec-editor");
    const spec = {
      team_name: "Docs",
      purpose: "Write docs.",
      desired_roles: [
        {
          name: "judge",
          description: "Judges.",
          // The user has switched away from the provider the check ran against.
          llm: { provider: "anthropic", model: "claude-sonnet-4-6" },
        },
      ],
      desired_tasks: [],
    };
    const judge = { ...missingKey.roles[1], role: "judge" };

    render(
      <SpecEditor
        spec={spec}
        failure={null}
        saving={false}
        savedNotice={null}
        keyRoles={[judge]}
        blockedReason={null}
        onSave={() => {}}
        onBuild={() => {}}
        onClose={() => {}}
        onEdit={() => {}}
      />
    );

    // Positive control first: the editor really rendered, so the absence below is
    // the note being withheld rather than the portal never being queried.
    await screen.findByRole("textbox", { name: "Role 1 name" });
    expect(document.querySelector('[data-slot="spec-editor-role"]')).not.toBeNull();
    // Saying "groq is not supported" beside a row that now reads `anthropic` would
    // be a stale claim about a provider nobody checked.
    expect(document.querySelector('[data-slot="spec-editor-role-key"]')).toBeNull();
  });
});
