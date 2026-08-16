import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { HelpButton } from "@/components/help/help-button"
import { SidebarProvider } from "@/components/ui/sidebar"
import {
  BUILD_ACTIONS_REVIEW_OFF_COPY,
  BUILD_ACTIONS_REVIEW_ON_COPY,
} from "@/components/composer/composer-actions"
import { ORIENTATION_COPY } from "@/components/composer/first-visit-orientation"

function renderHelpButton() {
  return render(
    <SidebarProvider>
      <table>
        <tbody>
          <tr>
            <td>
              <HelpButton />
            </td>
          </tr>
        </tbody>
      </table>
    </SidebarProvider>
  )
}

describe("HelpButton", () => {
  it("renders a help button in the sidebar", () => {
    renderHelpButton()
    expect(screen.getByText("Help")).toBeInTheDocument()
  })

  it("renders an icon inside the button", () => {
    renderHelpButton()
    const button = screen.getByRole("button", { name: /Help/i })
    expect(button.querySelector("svg")).toBeInTheDocument()
  })

  it("signals to assistive tech that it opens a dialog, not a navigation", () => {
    renderHelpButton()
    const button = screen.getByRole("button", { name: /Help/i })
    expect(button).toHaveAttribute("aria-haspopup", "dialog")
    expect(button).toHaveAttribute("aria-expanded", "false")
  })

  it("opens help dialog when clicked", async () => {
    renderHelpButton()
    const helpButton = screen.getByRole("button", { name: /Help/i })
    helpButton.click()

    expect(await screen.findByText("About team_maker")).toBeInTheDocument()
    expect(helpButton).toHaveAttribute("aria-expanded", "true")
  })

  it("renders help content with orientation questions", async () => {
    renderHelpButton()
    const helpButton = screen.getByRole("button", { name: /Help/i })
    helpButton.click()

    // Check for the main sections
    expect(await screen.findByText("What is a team?")).toBeInTheDocument()
    expect(screen.getByText("Build team vs Run it now")).toBeInTheDocument()
    expect(screen.getByText("Where do my teams go?")).toBeInTheDocument()
    expect(screen.getByText("How do I run a team again?")).toBeInTheDocument()
  })

  it("reuses the real composer-actions copy for both review-toggle variants", async () => {
    renderHelpButton()
    const helpButton = screen.getByRole("button", { name: /Help/i })
    helpButton.click()

    // Cross-references the same exported constants composer-actions.tsx
    // renders, so this fails the moment the two diverge instead of only
    // matching a second, independently hardcoded literal.
    expect(await screen.findByText(BUILD_ACTIONS_REVIEW_OFF_COPY)).toBeInTheDocument()
    expect(screen.getByText(BUILD_ACTIONS_REVIEW_ON_COPY)).toBeInTheDocument()
  })

  it("has a close button in the dialog", async () => {
    renderHelpButton()
    const helpButton = screen.getByRole("button", { name: /Help/i })
    helpButton.click()

    expect(await screen.findByText("Close")).toBeInTheDocument()
  })

  it("surfaces the same first-visit orientation copy on demand", async () => {
    renderHelpButton()
    const helpButton = screen.getByRole("button", { name: /Help/i })
    helpButton.click()

    expect(await screen.findByText(ORIENTATION_COPY)).toBeInTheDocument()
  })
})
