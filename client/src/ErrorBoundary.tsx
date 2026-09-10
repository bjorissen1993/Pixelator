import { Component, type ErrorInfo, type ReactNode } from "react";

export class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error(error, info.componentStack);
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="workspace" style={{ padding: 32 }}>
        <h1>Pixelator crashed</h1>
        <p>{this.state.error.message}</p>
        <button className="btn" type="button" onClick={() => window.location.reload()}>
          Reload
        </button>
      </div>
    );
  }
}
