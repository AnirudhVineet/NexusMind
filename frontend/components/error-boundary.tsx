"use client";

import { Component, type ReactNode } from "react";

interface Props { children: ReactNode }
interface State { error: Error | null }

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  componentDidCatch(error: Error) {
    if (typeof window !== "undefined") {
      // eslint-disable-next-line no-console
      console.error("ErrorBoundary caught:", error);
    }
  }

  render() {
    if (this.state.error) {
      return (
        <div className="min-h-screen flex flex-col items-center justify-center p-6">
          <h1 className="text-xl font-semibold">Something went wrong</h1>
          <p className="text-muted-foreground mt-2">{this.state.error.message}</p>
          <button
            className="mt-4 rounded bg-accent text-white px-4 py-2"
            onClick={() => this.setState({ error: null })}
          >
            Try again
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
