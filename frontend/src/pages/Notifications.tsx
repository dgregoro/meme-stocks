import React, { useEffect, useState } from 'react'
import { api, NotificationItem } from '../services/api'
import { LoadingSpinner } from '../components/LoadingSpinner'
import { EmptyState } from '../components/EmptyState'

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

  if (error) return <div style={{ color: 'red' }}>Error: {error}</div>
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
      <ul>
        {items.map((n) => (
          <li key={n.id}>
            [{n.severity}] {n.stock_symbol}: {n.message} <em>{new Date(n.created_at).toLocaleString()}</em>
          </li>
        ))}
      </ul>
    </div>
  )
}
