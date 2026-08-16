import { render } from "@testing-library/react";
import { axe } from "jest-axe";
import { describe, expect, it } from "vitest";

import StarterTeamsPage from "@/app/starter-teams/page";

/**
 * Stub routes accessibility smoke tests (AC 9)
 *
 * Starter Teams is still the Story 2.1 empty-state stub. My Teams stopped
 * being one in Story 2.8 — its axe coverage (both the empty and populated
 * states) moved to `tests/my-teams/a11y.test.tsx`, alongside the rest of its
 * feature-specific suite, per CLAUDE.md's reorg-on-growth rule.
 */
describe("Stub routes accessibility", () => {
  describe("Starter Teams", () => {
    it("should have no axe violations", async () => {
      const { container } = render(<StarterTeamsPage />);
      const results = await axe(container);
      expect(results).toHaveNoViolations();
    });
  });
});