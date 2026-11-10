import { Component, type ReactNode } from "react";

/** Replaces a blank page with a way out if something fails while rendering. */
export class ErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  render() {
    if (!this.state.failed) {
      return this.props.children;
    }
    return (
      <main className="grid h-full place-items-center p-6">
        <div role="alert" className="max-w-sm text-center">
          <h1 className="text-[2rem] leading-tight tracking-[-0.02em]">Something went wrong.</h1>
          <p className="mt-3 text-body text-ink-muted">Reload the page to plan the trip again.</p>
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="mt-6 h-12 cursor-pointer bg-ink px-6 font-mono text-sm tracking-[0.1em] text-ground uppercase transition-colors hover:bg-ink-hover"
          >
            Reload
          </button>
        </div>
      </main>
    );
  }
}
