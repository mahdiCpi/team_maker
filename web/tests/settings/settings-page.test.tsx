import { render, screen, waitFor } from "@testing-library/react"
import { describe, expect, it, vi, beforeEach } from "vitest"
import SettingsPage from "@/app/settings/page"
import { getKeyStatus } from "@/lib/api-client/keys"
import {
  mockKeyStatus,
  mockNoKeysStatus,
  mockWithWarnings,
  mockNeedsRestart,
  mockNeedsRestartMultiple,
} from "./fixtures"

// Mock the API client
vi.mock("@/lib/api-client/keys", () => ({
  getKeyStatus: vi.fn(),
}))

// Mock next-themes for ThemeToggle
vi.mock("next-themes", () => ({
  useTheme: () => ({ theme: "system", setTheme: vi.fn() }),
}))

function providerRows(container: HTMLElement): HTMLElement[] {
  return Array.from(container.querySelectorAll('[data-slot="settings-provider-row"]'))
}

describe("Settings Page - Story 2.6", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe("AC 1 - Per-provider status + Key Config path rendering", () => {
    it("renders Key Config path", async () => {
      vi.mocked(getKeyStatus).mockResolvedValue({ ok: true, data: mockKeyStatus })

      render(<SettingsPage />)

      await waitFor(() => {
        expect(screen.getByText("/path/to/key-config.yaml")).toBeInTheDocument()
      })
    })

    it("renders per-provider rows with status", async () => {
      vi.mocked(getKeyStatus).mockResolvedValue({ ok: true, data: mockKeyStatus })

      render(<SettingsPage />)

      await waitFor(() => {
        // Check that provider names are rendered
        expect(screen.getByText("anthropic")).toBeInTheDocument()
        expect(screen.getByText("openrouter")).toBeInTheDocument()
        expect(screen.getByText("openai")).toBeInTheDocument()
        expect(screen.getByText("ollama")).toBeInTheDocument()

        // Check that status words are rendered
        expect(screen.getAllByText("key found")).toHaveLength(2) // anthropic and openrouter
        expect(screen.getByText("key missing")).toBeInTheDocument()
        expect(screen.getByText("local")).toBeInTheDocument()
      })
    })

    it("renders provider rows with data-slot attributes", async () => {
      vi.mocked(getKeyStatus).mockResolvedValue({ ok: true, data: mockKeyStatus })

      const { container } = render(<SettingsPage />)

      await waitFor(() => {
        const rows = providerRows(container)
        expect(rows).toHaveLength(4)

        const anthropicRow = rows.find((row) => row.getAttribute("data-provider") === "anthropic")
        expect(anthropicRow).toBeDefined()
        expect(anthropicRow).toHaveAttribute("data-usable", "true")

        // The negative case matters too: a consumer relying on `data-usable` needs
        // both values proven, not just the happy path.
        const openaiRow = rows.find((row) => row.getAttribute("data-provider") === "openai")
        expect(openaiRow).toBeDefined()
        expect(openaiRow).toHaveAttribute("data-usable", "false")
      })
    })
  })

  describe("AC 2 - No overall/any_key_present verdict banner", () => {
    it("does not render a verdict banner when overall is no-keys but providers are usable", async () => {
      // This is the "true by construction" test case: a naive implementation
      // might show a "no keys" warning when overall is "no-keys", but AC 2 forbids this
      // because a user running only keyless-local ollama must not see a false warning.
      vi.mocked(getKeyStatus).mockResolvedValue({ ok: true, data: mockNoKeysStatus })

      render(<SettingsPage />)

      await waitFor(() => {
        // Should NOT show any warning about "no keys" or "all good"
        expect(screen.queryByText(/no keys/i)).not.toBeInTheDocument()
        expect(screen.queryByText(/all good/i)).not.toBeInTheDocument()
        expect(screen.queryByText(/you have no keys/i)).not.toBeInTheDocument()

        // But should still show the ollama provider as usable
        expect(screen.getByText("ollama")).toBeInTheDocument()
        expect(screen.getByText("local")).toBeInTheDocument()
      })
    })
  })

  describe("AC 3 - OpenRouter callout", () => {
    it("renders OpenRouter gateway explanation", async () => {
      vi.mocked(getKeyStatus).mockResolvedValue({ ok: true, data: mockKeyStatus })

      render(<SettingsPage />)

      await waitFor(() => {
        // Should show the OpenRouter explanation (rendered with parentheses)
        expect(screen.getByText("(One key unlocks many models.)")).toBeInTheDocument()
      })
    })

    it("OpenRouter explanation appears near the openrouter row", async () => {
      vi.mocked(getKeyStatus).mockResolvedValue({ ok: true, data: mockKeyStatus })

      const { container } = render(<SettingsPage />)

      await waitFor(() => {
        const openrouterRow = providerRows(container).find(
          (row) => row.getAttribute("data-provider") === "openrouter"
        )
        expect(openrouterRow).toBeDefined()
        expect(openrouterRow?.textContent).toContain("(One key unlocks many models.)")
      })
    })
  })

  describe("AC 4 - Safe-key guidance copy", () => {
    it("renders safe-key guidance text", async () => {
      vi.mocked(getKeyStatus).mockResolvedValue({ ok: true, data: mockKeyStatus })

      render(<SettingsPage />)

      await waitFor(() => {
        expect(screen.getByText(/Keep your Key Config file out of version control/i)).toBeInTheDocument()
        expect(screen.getByText(/Never paste or share its contents/i)).toBeInTheDocument()
        expect(screen.getByText(/rotate it at the provider/i)).toBeInTheDocument()
      })
    })
  })

  describe("AC 5 - No key entry invariant", () => {
    it("has no input, textarea, or editable controls capable of accepting key values", async () => {
      vi.mocked(getKeyStatus).mockResolvedValue({ ok: true, data: mockKeyStatus })

      const { container } = render(<SettingsPage />)

      await waitFor(() => {
        expect(screen.queryAllByRole("textbox")).toHaveLength(0)

        const inputElements = container.querySelectorAll("input")
        const textareaElements = container.querySelectorAll("textarea")

        // Filter out hidden inputs (like theme toggle might have)
        const visibleInputs = Array.from(inputElements).filter(
          (input: HTMLElement) =>
            input.getAttribute("type") !== "hidden" &&
            input.getAttribute("type") !== "button" &&
            input.getAttribute("type") !== "submit"
        )
        expect(visibleInputs).toHaveLength(0)
        expect(textareaElements).toHaveLength(0)
      })
    })
  })

  describe("AC 2 - Load warnings and restart notices", () => {
    it("renders load warnings when present", async () => {
      vi.mocked(getKeyStatus).mockResolvedValue({ ok: true, data: mockWithWarnings })

      render(<SettingsPage />)

      await waitFor(() => {
        expect(screen.getByText("Load Warnings")).toBeInTheDocument()
        expect(screen.getByText("Key Config file permissions are too open")).toBeInTheDocument()
      })
    })

    it("renders needs restart notice when present", async () => {
      vi.mocked(getKeyStatus).mockResolvedValue({ ok: true, data: mockNeedsRestart })

      render(<SettingsPage />)

      await waitFor(() => {
        expect(screen.getByText(/anthropic was changed in your Key Config after the API started/i)).toBeInTheDocument()
        expect(screen.getByText(/composing needs the API restarted/i)).toBeInTheDocument()
      })
    })

    it("renders a grammatical restart notice for more than one provider", async () => {
      vi.mocked(getKeyStatus).mockResolvedValue({ ok: true, data: mockNeedsRestartMultiple })

      render(<SettingsPage />)

      await waitFor(() => {
        expect(
          screen.getByText(/anthropic and openai were changed in your Key Config after the API started/i)
        ).toBeInTheDocument()
      })
    })

    it("does not render load warnings section when empty", async () => {
      vi.mocked(getKeyStatus).mockResolvedValue({ ok: true, data: mockKeyStatus })

      render(<SettingsPage />)

      await waitFor(() => {
        expect(screen.queryByText("Load Warnings")).not.toBeInTheDocument()
      })
    })

    it("does not render restart notice when empty", async () => {
      vi.mocked(getKeyStatus).mockResolvedValue({ ok: true, data: mockKeyStatus })

      render(<SettingsPage />)

      await waitFor(() => {
        expect(screen.queryByText(/was changed in your Key Config after the API started/i)).not.toBeInTheDocument()
      })
    })
  })

  describe("AC 9 - Color token usage", () => {
    it("does not use --signal or bg-signal tokens", async () => {
      vi.mocked(getKeyStatus).mockResolvedValue({ ok: true, data: mockKeyStatus })

      const { container } = render(<SettingsPage />)

      await waitFor(() => {
        const rows = providerRows(container)
        expect(rows.length).toBeGreaterThan(0)
        rows.forEach((row) => {
          expect(row.className).not.toContain("signal")
          expect(row.className).not.toContain("bg-signal")
          const badge = row.querySelector('[data-slot="settings-provider-badge"]')
          expect(badge?.className).not.toContain("signal")
          expect(badge?.className).not.toContain("bg-signal")
        })
      })
    })

    it("uses established badge color convention - usable providers are neutral", async () => {
      vi.mocked(getKeyStatus).mockResolvedValue({ ok: true, data: mockKeyStatus })

      const { container } = render(<SettingsPage />)

      await waitFor(() => {
        const anthropicRow = providerRows(container).find(
          (row) => row.getAttribute("data-provider") === "anthropic"
        )
        const badge = anthropicRow?.querySelector('[data-slot="settings-provider-badge"]')
        expect(badge?.className).toContain("bg-muted")
        expect(badge?.className).toContain("text-foreground")
      })
    })

    it("uses established badge color convention - unusable providers are destructive", async () => {
      vi.mocked(getKeyStatus).mockResolvedValue({ ok: true, data: mockKeyStatus })

      const { container } = render(<SettingsPage />)

      await waitFor(() => {
        const openaiRow = providerRows(container).find(
          (row) => row.getAttribute("data-provider") === "openai"
        )
        const badge = openaiRow?.querySelector('[data-slot="settings-provider-badge"]')
        expect(badge?.className).toContain("border-destructive")
        expect(badge?.className).toContain("text-destructive")
      })
    })
  })

  describe("Error handling", () => {
    it("renders error message when API call fails", async () => {
      vi.mocked(getKeyStatus).mockResolvedValue({
        ok: false,
        message: "Network error",
        code: "unreachable",
        fields: [],
      })

      render(<SettingsPage />)

      await waitFor(() => {
        expect(screen.getByText(/Failed to load key status: Network error/i)).toBeInTheDocument()
      })
    })

    it("renders error message when the request rejects instead of resolving", async () => {
      vi.mocked(getKeyStatus).mockRejectedValue(new Error("connection refused"))

      render(<SettingsPage />)

      await waitFor(() => {
        expect(screen.getByText(/Failed to load key status: connection refused/i)).toBeInTheDocument()
      })
    })
  })

  describe("Loading state", () => {
    it("renders loading state initially", () => {
      vi.mocked(getKeyStatus).mockImplementation(
        () => new Promise(() => {}) // Never resolves
      )

      render(<SettingsPage />)

      expect(screen.getByText("Loading key status...")).toBeInTheDocument()
    })
  })
})
