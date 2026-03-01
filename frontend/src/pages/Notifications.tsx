import React, { useEffect, useState } from 'react'
import { api, NotificationItem } from '../services/api'
import { LoadingSpinner } from '../components/LoadingSpinner'
import { EmptyState } from '../components/EmptyState'
import { severityColor } from '../utils/colors'

export const Notifications: React.FC = () => {
  const [items, setItems] = useState<NotificationItem[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api
      .listNotifications()
      .then(setItems)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false))
  }, [])

  if (error) return <div style={{ color: '#b91c1c' }} role="alert">Error: {error}</div>
  if (loading) return <LoadingSpinner message="Loading notifications…" />

  if (items.length === 0) {
    return (
      <div>
        <h3>Notifications</h3>
        <EmptyState
          title="No notifications"
          message="You're all caught up. Alerts will appear here when stocks have unusual activity."
        />
      </div>
    )
  }

  return (
    <div>
      <h3>Notifications</h3>
      <ul style={{ listStyle: 'none', paddingLeft: 0 }}>
        {items.map((n) => (
          <li
            key={n.id}
            style={{
              padding: '8px 12px',
              marginBottom: 8,
              borderLeft: `4px solid ${severityColor(n.severity)}`,
              backgroundColor: '#f9fafb',
              borderRadius: 4,
            }}
          >
            <span style={{ fontWeight: 600, color: severityColor(n.severity) }}>{n.severity}</span>
            {' '}{n.stock_symbol}: {n.message}{' '}
            <em style={{ color: '#6b7280', fontSize: '0.9em' }}>{new Date(n.created_at).toLocaleString()}</em>
          </li>
        ))}
      </ul>
    </div>
  )
}
