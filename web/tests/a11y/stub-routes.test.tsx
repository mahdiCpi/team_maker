import { render } from "@testing-library/react";
import { axe } from "jest-axe";
import { describe, expect, it } from "vitest";

import MyTeamsPage from "@/app/my-teams/page";
import StarterTeamsPage from "@/app/starter-teams/page";

/**
 * Stub routes accessibility smoke tests (AC 9)
 *
 * Tests that the My Teams and Starter Teams placeholder routes
 * have no axe violations with their current empty-state stubs.
 */
describe("Stub routes accessibility", () => {
  describe("My Teams", () => {
    it("should have no axe violations", async () => {
      const { container } = render(<MyTeamsPage />);
      const results = await axe(container);
      expect(results).toHaveNoViolations();
    });
  });

  describe("Starter Teams", () => {
    it("should have no axe violations", async () => {
      const { container } = render(<StarterTeamsPage />);
      const results = await axe(container);
      expect(results).toHaveNoViolations();
    });
  });
});