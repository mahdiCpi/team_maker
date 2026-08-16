import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest"

import {
  FirstVisitOrientation,
  markBuildCompleted,
  resetOrientationState,
  shouldShowOrientation,
} from "@/components/composer/first-visit-orientation"

// Mock localStorage
const mockLocalStorage = (() => {
  let store: Record<string, string> = {}
  return {
    getItem: vi.fn((key: string) => store[key] || null),
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

Object.defineProperty(window, "localStorage", {
  value: mockLocalStorage,
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
  })

  describe("resetOrientationState", () => {
    it("removes both orientation flags from localStorage", () => {
      mockLocalStorage.setItem("team_maker_orientation_shown", "true")
      mockLocalStorage.setItem("team_maker_build_completed", "true")
      
      resetOrientationState()
      
      expect(mockLocalStorage.removeItem).toHaveBeenCalledWith(
        "team_maker_orientation_shown"
      )
      expect(mockLocalStorage.removeItem).toHaveBeenCalledWith(
        "team_maker_build_completed"
      )
    })
  })

  describe("FirstVisitOrientation component", () => {
    it("renders when neither flag is set", () => {
      render(<FirstVisitOrientation onDismiss={() => {}} />)
      expect(screen.getByText("What team_maker does")).toBeInTheDocument()
    })

    it("does not render when orientation has been shown", () => {
      mockLocalStorage.setItem("team_maker_orientation_shown", "true")
      render(<FirstVisitOrientation onDismiss={() => {}} />)
      expect(screen.queryByText("What team_maker does")).not.toBeInTheDocument()
    })

    it("does not render when build has been completed", () => {
      mockLocalStorage.setItem("team_maker_build_completed", "true")
      render(<FirstVisitOrientation onDismiss={() => {}} />)
      expect(screen.queryByText("What team_maker does")).not.toBeInTheDocument()
    })

    it("renders the orientation description", () => {
      render(<FirstVisitOrientation onDismiss={() => {}} />)
      expect(
        screen.getByText(
          /team_maker turns a description into a runnable team of AI agents./
        )
      ).toBeInTheDocument()
    })

    it("renders a dismiss button", () => {
      render(<FirstVisitOrientation onDismiss={() => {}} />)
      expect(screen.getByText("Dismiss")).toBeInTheDocument()
    })

    it("calls onDismiss when dismissed", () => {
      const onDismiss = vi.fn()
      render(<FirstVisitOrientation onDismiss={onDismiss} />)
      
      const dismissButton = screen.getByText("Dismiss")
      dismissButton.click()
      
      expect(onDismiss).toHaveBeenCalled()
      expect(mockLocalStorage.setItem).toHaveBeenCalledWith(
        "team_maker_orientation_shown",
        "true"
      )
    })
  })
})
