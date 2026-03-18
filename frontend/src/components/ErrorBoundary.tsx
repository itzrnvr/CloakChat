import * as React from "react"
import { Button } from "@/components/ui/button"
import { AlertCircle } from "lucide-react"

interface ErrorBoundaryState {
  hasError: boolean
  error: Error | null
}

interface ErrorBoundaryProps {
  children: React.ReactNode
}

export class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error("Error caught by ErrorBoundary:", error, errorInfo)
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null })
    window.location.reload()
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex items-center justify-center min-h-screen bg-[var(--color-paper)] dark:bg-[var(--color-base-950)] p-8">
          <div className="max-w-md w-full space-y-6">
            <div className="flex items-center gap-3 text-[var(--color-red-400)]">
              <AlertCircle className="h-8 w-8" />
              <h1 className="text-2xl font-bold">Something went wrong</h1>
            </div>
            
            <div className="rounded-lg border border-[var(--color-base-200)] bg-[var(--color-base-50)] p-4 dark:border-[var(--color-base-800)] dark:bg-[var(--color-base-900)]">
              <p className="text-sm text-[var(--color-base-700)] dark:text-[var(--color-base-300)] mb-4">
                An unexpected error occurred. Please try refreshing the page.
              </p>
              
              {this.state.error && (
                <details className="group">
                  <summary className="cursor-pointer text-sm font-medium text-[var(--color-base-600)] dark:text-[var(--color-base-400)] select-none">
                    Show error details
                  </summary>
                  <pre className="mt-2 overflow-x-auto text-xs bg-[var(--color-base-100)] p-3 rounded dark:bg-[var(--color-base-950)]">
                    {this.state.error.toString()}
                  </pre>
                </details>
              )}
            </div>
            
            <Button onClick={this.handleReset} className="w-full">
              Refresh Page
            </Button>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}
