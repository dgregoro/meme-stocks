import React, { useEffect, useState } from 'react'
import { api } from './services/api'
import { Dashboard } from './pages/Dashboard'
import { Stocks } from './pages/Stocks'
import { Notifications } from './pages/Notifications'
import { PaperTrading } from './pages/PaperTrading'

type Tab = 'dashboard' | 'stocks' | 'notifications' | 'paper'

export const App: React.FC = () => {
  const [tab, setTab] = useState<Tab>('dashboard')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    // Simple connectivity check
    api.health().catch((e) => setError(String(e)))
  }, [])

  return (
    <div style={{ fontFamily: 'system-ui, sans-serif', padding: 16 }}>
      <h1>Meme Stocks</h1>
      <nav style={{ display: 'flex', gap: 12, marginBottom: 16 }}>
        <button onClick={() => setTab('dashboard')}>Dashboard</button>
        <button onClick={() => setTab('stocks')}>Stocks</button>
        <button onClick={() => setTab('notifications')}>Notifications</button>
        <button onClick={() => setTab('paper')}>Paper Trading</button>
      </nav>
      {error ? (
        <div style={{ color: 'red' }}>Error: {error}</div>
      ) : tab === 'dashboard' ? (
        <Dashboard />
      ) : tab === 'stocks' ? (
        <Stocks />
      ) : tab === 'notifications' ? (
        <Notifications />
      ) : (
        <PaperTrading />
      )}
    </div>
  )
}

