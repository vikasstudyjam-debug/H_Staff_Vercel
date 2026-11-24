import React from 'react';

// Shows the error instead of a blank white screen when something throws during render.
export default class ErrorBoundary extends React.Component {
  state = { error: null };
  static getDerivedStateFromError(error) { return { error }; }
  componentDidCatch(error, info) { console.error('UI crashed:', error, info?.componentStack); }
  render() {
    if (!this.state.error) return this.props.children;
    return <div style={{ padding: 32, fontFamily: 'system-ui, sans-serif', maxWidth: 720, margin: '40px auto', color: '#172554' }}>
      <h2 style={{ color: '#172554' }}>Something went wrong</h2>
      <pre style={{ whiteSpace: 'pre-wrap', background: '#F2EEFF', border: '1px solid #E5DDF5', color: '#dc2626', padding: 16, borderRadius: 8 }}>{String(this.state.error?.stack || this.state.error)}</pre>
      <button className="btn primary" onClick={() => this.setState({ error: null })}>Try again</button>{' '}
      <button className="btn secondary" onClick={() => location.reload()}>Reload</button>
    </div>;
  }
}
