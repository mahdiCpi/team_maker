import { render, screen, waitFor } from "@testing-library/react"
import { describe, expect, it, vi, beforeEach, afterEach, afterAll } from "vitest"

import {
  FirstVisitOrientation,
  ORIENTATION_COPY,
  markBuildCompleted,
  shouldShowOrientation,
} from "@/components/composer/first-visit-orientation"

// Mock localStorage
const mockLocalStorage = (() => {
  let store: Record<string, string> = {}
  return {
    getItem: vi.fn((key: string) => (key in store ? store[key] : null)),
    setItem: vi.fn((key: string, value: string) => {
      store[key] = value
    }),
    removeItem: vi.fn((key: string) => {
      delete store[key]
    }),
    clear: vi.fn(() => {
      store = {}
    }),
  }
})()

const originalLocalStorage = window.localStorage

Object.defineProperty(window, "localStorage", {
  value: mockLocalStorage,
  configurable: true,
})

afterAll(() => {
  Object.defineProperty(window, "localStorage", {
    value: originalLocalStorage,
    configurable: true,
  })
})

describe("FirstVisitOrientation", () => {
  beforeEach(() => {
    mockLocalStorage.clear()
    vi.clearAllMocks()
  })

  afterEach(() => {
    mockLocalStorage.clear()
    vi.clearAllMocks()
  })

  describe("shouldShowOrientation", () => {
    it("returns true when neither orientation shown nor build completed", () => {
      expect(shouldShowOrientation()).toBe(true)
    })

    it("returns false when orientation has been shown", () => {
      mockLocalStorage.setItem("team_maker_orientation_shown", "true")
      expect(shouldShowOrientation()).toBe(false)
    })

    it("returns false when build has been completed", () => {
      mockLocalStorage.setItem("team_maker_build_completed", "true")
      expect(shouldShowOrientation()).toBe(false)
    })

    it("returns false when both orientation shown and build completed", () => {
      mockLocalStorage.setItem("team_maker_orientation_shown", "true")
      mockLocalStorage.setItem("team_maker_build_completed", "true")
      expect(shouldShowOrientation()).toBe(false)
    })
  })

  describe("markBuildCompleted", () => {
    it("sets the build completed flag in localStorage", () => {
      markBuildCompleted()
      expect(mockLocalStorage.setItem).toHaveBeenCalledWith(
        "team_maker_build_completed",
        "true"
      )
    })

    it("does not throw when localStorage.setItem throws", () => {
      mockLocalStorage.setItem.mockImplementationOnce(() => {
        throw new Error("QuotaExceededError")
      })
      expect(() => markBuildCompleted()).not.toThrow()
    })
  })

  describe("FirstVisitOrientation component", () => {
    it("renders when neither flag is set", async () => {
      render(<FirstVisitOrientation />)
      expect(await screen.findByText("What team_maker does")).toBeInTheDocument()
    })

    it("does not render when orientation has been shown", () => {
      mockLocalStorage.setItem("team_maker_orientation_shown", "true")
      render(<FirstVisitOrientation />)
      expect(screen.queryByText("What team_maker does")).not.toBeInTheDocument()
    })

    it("does not render when build has been completed", () => {
      mockLocalStorage.setItem("team_maker_build_completed", "true")
      render(<FirstVisitOrientation />)
      expect(screen.queryByText("What team_maker does")).not.toBeInTheDocument()
    })

    it("renders the orientation description", async () => {
      render(<FirstVisitOrientation />)
      expect(await screen.findByText(ORIENTATION_COPY)).toBeInTheDocument()
    })

    it("renders a dismiss button", async () => {
      render(<FirstVisitOrientation />)
      expect(await screen.findByText("Dismiss")).toBeInTheDocument()
    })

    it("persists the dismissal and closes when dismissed", async () => {
      render(<FirstVisitOrientation />)

      const dismissButton = await screen.findByText("Dismiss")
      dismissButton.click()

      expect(mockLocalStorage.setItem).toHaveBeenCalledWith(
        "team_maker_orientation_shown",
        "true"
      )
      // Base UI's Dialog unmounts the popup after its exit transition, not
      // synchronously on click.
      await waitFor(() =>
        expect(screen.queryByText("What team_maker does")).not.toBeInTheDocument()
      )
    })
  })
})
