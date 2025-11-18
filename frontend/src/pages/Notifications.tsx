import React, { useEffect, useState } from 'react'
import { api, NotificationItem } from '../services/api'

export const Notifications: React.FC = () => {
  const [items, setItems] = useState<NotificationItem[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.listNotifications().then(setItems).catch((e) => setError(String(e)))
  }, [])

  if (error) return <div style={{ color: 'red' }}>Error: {error}</div>

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
      {items.length === 0 && <div>No unread notifications.</div>}
    </div>
  )
}
