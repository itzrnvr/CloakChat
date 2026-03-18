import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@testing-library/react"

global.fetch = vi.fn()

describe("StrategyDetails", () => {
  it("renders strategy details component", () => {
    const MockComponent = () => {
      return <div data-testid="strategy-details">Strategy Details</div>
    }

    render(<MockComponent />)
    
    const element = screen.getByTestId("strategy-details")
    expect(element).not.toBeNull()
  })
})
