import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { HelpButton } from "@/components/help/help-button"
import { SidebarProvider } from "@/components/ui/sidebar"

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

  it("renders the HelpCircle icon", () => {
    renderHelpButton()
    const icon = screen.getByRole("img", { hidden: true })
    expect(icon).toBeInTheDocument()
  })

  it("has a button with Help text", () => {
    renderHelpButton()
    expect(screen.getByRole("button", { name: /Help/i })).toBeInTheDocument()
  })

  it("opens help dialog when clicked", async () => {
    renderHelpButton()
    const helpButton = screen.getByRole("button", { name: /Help/i })
    helpButton.click()
    
    expect(await screen.findByText("About team_maker")).toBeInTheDocument()
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

  it("reuses existing copy for Build team/Run it now explanation", async () => {
    renderHelpButton()
    const helpButton = screen.getByRole("button", { name: /Help/i })
    helpButton.click()
    
    expect(
      await screen.findByText("Build team writes the package. Run it now does the same, skipping review.")
    ).toBeInTheDocument()
  })

  it("has a close button in the dialog", async () => {
    renderHelpButton()
    const helpButton = screen.getByRole("button", { name: /Help/i })
    helpButton.click()
    
    expect(await screen.findByText("Close")).toBeInTheDocument()
  })

  it("includes first visit orientation content", async () => {
    renderHelpButton()
    const helpButton = screen.getByRole("button", { name: /Help/i })
    helpButton.click()
    
    expect(await screen.findByText("First visit orientation")).toBeInTheDocument()
    expect(
      screen.getByText(
        /team_maker turns a description into a runnable team of AI agents./
      )
    ).toBeInTheDocument()
  })
})
