import React from 'react'

export type EmptyStateProps = {
  /** Short title (e.g. "No notifications") */
  title: string
  /** Guidance or explanation */
  message: string
  /** Optional call-to-action or hint */
  action?: string
}

/**
 * Empty state with title and guidance (PRD §5.3 Landing / empty states).
 */
export const EmptyState: React.FC<EmptyStateProps> = ({ title, message, action }) => (
  <div
    style={{
      padding: 32,
      textAlign: 'center',
      border: '1px dashed #ccc',
      borderRadius: 8,
      backgroundColor: '#fafafa',
      color: '#555',
    }}
    role="status"
  >
    <div style={{ fontSize: 18, fontWeight: 600, marginBottom: 8, color: '#333' }}>{title}</div>
    <p style={{ margin: '0 0 12px 0', maxWidth: 360, marginLeft: 'auto', marginRight: 'auto' }}>{message}</p>
    {action && <p style={{ margin: 0, fontSize: 14 }}>{action}</p>}
  </div>
)
