import { render, screen, waitFor } from "@testing-library/react";
import { axe } from "jest-axe";
import { describe, expect, it, vi } from "vitest";

import SettingsPage from "@/app/settings/page";
import { getKeyStatus } from "@/lib/api-client/keys";

import { mockKeyStatus } from "../settings/fixtures";

/**
 * Settings surface accessibility smoke tests (AC 9)
 *
 * `getKeyStatus` is mocked to a settled, real key-status response (the same
 * pattern `tests/settings/settings-page.test.tsx` uses) so the axe check
 * runs against the actual rendered provider list, not a transient loading
 * state that never resolves in a jsdom render.
 */

vi.mock("@/lib/api-client/keys", () => ({
  getKeyStatus: vi.fn(),
}));

vi.mock("next-themes", () => ({
  useTheme: () => ({ theme: "system", setTheme: vi.fn() }),
}));

describe("Settings surface accessibility", () => {
  it("should have no axe violations", async () => {
    vi.mocked(getKeyStatus).mockResolvedValue({ ok: true, data: mockKeyStatus });

    const { container } = render(<SettingsPage />);
    await waitFor(() => {
      expect(screen.getByText(mockKeyStatus.key_config_path)).toBeInTheDocument();
    });

    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});
