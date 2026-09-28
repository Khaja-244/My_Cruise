import React from 'react';

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidUpdate(previousProps) {
    if (this.state.hasError && previousProps.resetKey !== this.props.resetKey) {
      this.setState({ hasError: false, error: null });
    }
  }

  componentDidCatch(error, info) {
    const route = typeof window !== 'undefined' ? `${window.location.pathname}${window.location.search}` : 'unknown-route';
    console.error(`[my_cruise UI error] ${route}`, error, info);
  }

  render() {
    if (!this.state.hasError) return this.props.children;

    const message = this.state.error?.message || 'Unknown rendering error';
    const route = typeof window !== 'undefined' ? `${window.location.pathname}${window.location.search}` : 'unknown-route';

    return (
      <main className="container-app py-16 lg:py-20">
        <div className="card max-w-2xl mx-auto p-8 sm:p-10 text-center">
          <div className="mx-auto h-14 w-14 rounded-2xl bg-error-soft text-error grid place-items-center font-black">!</div>
          <p className="eyebrow mt-6">Temporary page error</p>
          <h1 className="page-heading text-3xl font-extrabold mt-2">We hit an unexpected error</h1>
          <p className="muted mt-3 max-w-xl mx-auto">This page could not finish rendering. Refreshing is safe, and your saved booking progress is kept when possible.</p>
          <div className="flex flex-wrap justify-center gap-3 mt-7">
            <button className="btn btn-primary" onClick={() => window.location.reload()}>Refresh page</button>
            <button className="btn btn-outline" onClick={() => { this.setState({ hasError: false, error: null }); window.history.replaceState({}, '', '/'); window.location.assign('/'); }}>Go home</button>
          </div>
          <details className="mt-7 text-left rounded-2xl border border-default bg-surface-muted p-4">
            <summary className="cursor-pointer text-sm font-extrabold">Technical details</summary>
            <p className="text-xs muted mt-3 break-all">Route: {route}</p>
            <pre className="mt-2 whitespace-pre-wrap break-words text-xs text-error">{message}</pre>
          </details>
        </div>
      </main>
    );
  }
}
