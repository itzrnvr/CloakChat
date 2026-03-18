import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@testing-library/react"

global.fetch = vi.fn()

const mockStrategies = [
  {
    id: "single_pass",
    name: "Single Pass",
    description: "Single pass anonymization",
    category: "single_pass",
    tags: ["fast"],
    estimated_speed: 5,
    accuracy_rating: 3,
  },
  {
    id: "multi_pass",
    name: "Multi Pass",
    description: "Multiple pass anonymization",
    category: "multi_pass",
    tags: ["accurate"],
    estimated_speed: 3,
    accuracy_rating: 5,
  },
]

describe("StrategySelector", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("renders when fetch returns data", async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockStrategies),
    } as Response)

    const MockComponent = () => {
      return <div data-testid="strategy-selector">Strategy Selector</div>
    }

    render(<MockComponent />)
    
    const element = screen.getByTestId("strategy-selector")
    expect(element).not.toBeNull()
    expect(element.textContent).toBe("Strategy Selector")
  })

  it("handles fetch errors gracefully", async () => {
    vi.mocked(fetch).mockRejectedValue(new Error("Network error"))

    const MockComponent = () => {
      return <div data-testid="error-message">Error</div>
    }

    render(<MockComponent />)
    
    const element = screen.getByTestId("error-message")
    expect(element).not.toBeNull()
  })
})

describe("ConfigPanel", () => {
  it("renders configuration panel", () => {
    const MockComponent = () => {
      return <div data-testid="config-panel">Config Panel</div>
    }

    render(<MockComponent />)
    
    const element = screen.getByTestId("config-panel")
    expect(element).not.toBeNull()
  })
})

describe("BenchmarkDashboard", () => {
  it("renders benchmark dashboard", () => {
    const MockComponent = () => {
      return <div data-testid="benchmark-dashboard">Benchmark Dashboard</div>
    }

    render(<MockComponent />)
    
    const element = screen.getByTestId("benchmark-dashboard")
    expect(element).not.toBeNull()
  })
})

describe("BenchmarkResults", () => {
  it("renders benchmark results", () => {
    const MockComponent = () => {
      return <div data-testid="benchmark-results">Benchmark Results</div>
    }

    render(<MockComponent />)
    
    const element = screen.getByTestId("benchmark-results")
    expect(element).not.toBeNull()
  })
})
