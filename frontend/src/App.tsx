import React, { useEffect, useState } from 'react'
import { api } from './services/api'
import { fontFamily, spacing } from './theme'
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

const THEME_STORAGE_KEY = 'meme-stocks-theme'

function getInitialTheme(): 'light' | 'dark' {
  if (typeof window === 'undefined') return 'light'
  const stored = window.localStorage.getItem(THEME_STORAGE_KEY) as 'light' | 'dark' | null
  if (stored === 'light' || stored === 'dark') return stored
  return 'light'
}

export const App: React.FC = () => {
  const [tab, setTab] = useState<Tab>('dashboard')
  const [error, setError] = useState<string | null>(null)
  const [theme, setTheme] = useState<'light' | 'dark'>(getInitialTheme)

  useEffect(() => {
    api.health().catch((e) => setError(String(e)))
  }, [])

  useEffect(() => {
    window.localStorage.setItem(THEME_STORAGE_KEY, theme)
  }, [theme])

  const isDark = theme === 'dark'
  const rootStyle: React.CSSProperties = {
    fontFamily,
    minHeight: '100vh',
    backgroundColor: isDark ? '#1a1a2e' : '#fff',
    color: isDark ? '#e5e7eb' : '#111',
  }
  const headerStyle: React.CSSProperties = {
    borderBottom: isDark ? '1px solid #374151' : '1px solid #e0e0e0',
    marginBottom: spacing.xl,
  }
  const baseNavButton: React.CSSProperties = {
    padding: '8px 14px',
    fontSize: '1rem',
    fontFamily: 'inherit',
    border: isDark ? '1px solid #4b5563' : '1px solid #ccc',
    borderRadius: 6,
    background: isDark ? '#374151' : '#fff',
    color: isDark ? '#e5e7eb' : '#111',
    cursor: 'pointer',
  }
  const activeNavButton: React.CSSProperties = {
    ...baseNavButton,
    background: isDark ? '#6366f1' : '#1a1a2e',
    color: '#fff',
    border: isDark ? '1px solid #6366f1' : '1px solid #1a1a2e',
    fontWeight: 600,
  }

  return (
    <div style={rootStyle} data-theme={theme}>
      <header style={headerStyle}>
        <div style={{ maxWidth: 960, margin: '0 auto', padding: `${spacing.lg}px ${spacing.xl}px`, display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: spacing.md }}>
          <div>
            <h1 style={{ margin: `0 0 ${spacing.md}px 0`, fontSize: '1.5rem' }}>Meme Stocks</h1>
            <nav aria-label="Main navigation" style={{ display: 'flex', gap: spacing.sm, flexWrap: 'wrap' }}>
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
          <button
            type="button"
            onClick={() => setTheme((t) => (t === 'light' ? 'dark' : 'light'))}
            style={baseNavButton}
            title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
            aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
          >
            {isDark ? '☀️ Light' : '🌙 Dark'}
          </button>
        </div>
      </header>
      <main style={{ maxWidth: 960, margin: '0 auto', padding: `0 ${spacing.xl}px ${spacing.xl}px` }}>
        {error ? (
          <div style={{ color: isDark ? '#f87171' : '#b91c1c' }} role="alert">Error: {error}</div>
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
