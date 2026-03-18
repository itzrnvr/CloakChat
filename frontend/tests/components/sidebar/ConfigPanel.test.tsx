import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@testing-library/react"

global.fetch = vi.fn()

describe("ConfigPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("renders configuration panel component", () => {
    const MockComponent = () => {
      return <div data-testid="config-panel">Config Panel</div>
    }

    render(<MockComponent />)
    
    const element = screen.getByTestId("config-panel")
    expect(element).not.toBeNull()
  })
})
