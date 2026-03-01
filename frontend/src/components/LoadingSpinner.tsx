import React from 'react'

const spinnerStyle: React.CSSProperties = {
  width: 32,
  height: 32,
  border: '3px solid #e0e0e0',
  borderTopColor: '#1a1a2e',
  borderRadius: '50%',
  animation: 'spin 0.8s linear infinite',
}

const containerStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 12,
  padding: 24,
}

export type LoadingSpinnerProps = {
  /** Optional message for screen readers and visible text; default "Loading..." */
  message?: string
}

/**
 * Accessible loading indicator (PRD §5.3 Loading states).
 * Uses role="status" and aria-live so assistive tech announces the state.
 */
export const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({ message = 'Loading...' }) => (
  <div style={containerStyle} role="status" aria-live="polite" aria-busy="true">
    <span style={spinnerStyle} aria-hidden />
    <span>{message}</span>
    <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
  </div>
)
