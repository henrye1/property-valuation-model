import { Component, type ReactNode } from 'react'

interface Props {
  children: ReactNode
}

interface State {
  error: Error | null
}

/**
 * Catches render-time errors in the routed page so a component crash shows a
 * readable message instead of a blank screen. Key it by route path so it
 * resets automatically when the user navigates elsewhere.
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error) {
    // Surface it for debugging; the UI already shows the message.
    console.error('Render error:', error)
  }

  render() {
    if (this.state.error) {
      return (
        <div className="mx-auto max-w-lg rounded-md border border-destructive/30 bg-destructive/5 p-6">
          <h2 className="mb-2 text-lg font-semibold text-destructive">
            Something went wrong on this page
          </h2>
          <p className="mb-4 break-words text-sm text-muted-foreground">
            {this.state.error.message}
          </p>
          <button
            className="text-sm text-primary underline"
            onClick={() => this.setState({ error: null })}
          >
            Try again
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
