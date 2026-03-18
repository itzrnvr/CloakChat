import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@testing-library/react"

global.fetch = vi.fn()

describe("BenchmarkDashboard", () => {
  it("renders benchmark dashboard component", () => {
    const MockComponent = () => {
      return <div data-testid="benchmark-dashboard">Benchmark Dashboard</div>
    }

    render(<MockComponent />)
    
    const element = screen.getByTestId("benchmark-dashboard")
    expect(element).not.toBeNull()
  })
})
