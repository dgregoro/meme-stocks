import React, { useEffect, useState } from 'react'
import { api } from './services/api'
import { Dashboard } from './pages/Dashboard'
import { Stocks } from './pages/Stocks'
import { Notifications } from './pages/Notifications'
import { PaperTrading } from './pages/PaperTrading'

export type Tab = 'dashboard' | 'stocks' | 'notifications' | 'paper'

const NAV_SECTIONS: { id: Tab; label: string }[] = [
  { id: 'dashboard', label: 'Dashboard' },
  { id: 'stocks', label: 'Stocks' },
  { id: 'notifications', label: 'Notifications' },
  { id: 'paper', label: 'Paper Trading' },
]

const baseNavButton: React.CSSProperties = {
  padding: '8px 14px',
  fontSize: '1rem',
  fontFamily: 'inherit',
  border: '1px solid #ccc',
  borderRadius: 6,
  background: '#fff',
  cursor: 'pointer',
}
const activeNavButton: React.CSSProperties = {
  ...baseNavButton,
  background: '#1a1a2e',
  color: '#fff',
  border: '1px solid #1a1a2e',
  fontWeight: 600,
}

export const App: React.FC = () => {
  const [tab, setTab] = useState<Tab>('dashboard')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.health().catch((e) => setError(String(e)))
  }, [])

  return (
    <div style={{ fontFamily: 'system-ui, sans-serif', minHeight: '100vh' }}>
      <header style={{ borderBottom: '1px solid #e0e0e0', marginBottom: 24 }}>
        <div style={{ maxWidth: 960, margin: '0 auto', padding: '16px 20px' }}>
          <h1 style={{ margin: '0 0 12px 0', fontSize: '1.5rem' }}>Meme Stocks</h1>
          <nav aria-label="Main navigation" style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {NAV_SECTIONS.map(({ id, label }) => {
              const isActive = tab === id
              return (
                <button
                  key={id}
                  type="button"
                  onClick={() => setTab(id)}
                  style={isActive ? activeNavButton : baseNavButton}
                  aria-current={isActive ? 'page' : undefined}
                >
                  {label}
                </button>
              )
            })}
          </nav>
        </div>
      </header>
      <main style={{ maxWidth: 960, margin: '0 auto', padding: '0 20px 24px' }}>
        {error ? (
          <div style={{ color: '#c00' }} role="alert">Error: {error}</div>
        ) : tab === 'dashboard' ? (
          <Dashboard />
        ) : tab === 'stocks' ? (
          <Stocks />
        ) : tab === 'notifications' ? (
          <Notifications />
        ) : (
          <PaperTrading />
        )}
      </main>
    </div>
  )
}
