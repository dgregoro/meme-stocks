import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, type Stock } from '../services/api'
import { EmptyState } from '../components/EmptyState'
import { LoadingSpinner } from '../components/LoadingSpinner'

export const Stocks: React.FC = () => {
  const [stocks, setStocks] = useState<Stock[]>([])
  const [error, setError] = useState<string | null>(null)
  const [stocksLoading, setStocksLoading] = useState(true)

  useEffect(() => {
    api
      .listStocks()
      .then(setStocks)
      .catch((e) => setError(String(e)))
      .finally(() => setStocksLoading(false))
  }, [])

  if (stocksLoading) return <LoadingSpinner message="Loading stocks…" />
  if (stocks.length === 0 && !error) {
    return (
      <div>
        <h3>Stocks</h3>
        <EmptyState
          title="No stocks tracked"
          message="Stocks are added via the API, symbol universe refresh, or other workflows."
          action="Use the API or symbol universe tools to add tickers to track."
        />
      </div>
    )
  }

  return (
    <div>
      <h3>Stocks</h3>
      {error && (
        <div style={{ color: '#b91c1c', padding: '8px 12px', marginBottom: 12, backgroundColor: '#fef2f2', borderRadius: 6 }} role="alert">
          Error: {error}
        </div>
      )}
      <ul style={{ listStyle: 'none', paddingLeft: 0 }}>
        {stocks.map((s) => (
          <li key={s.symbol} style={{ marginBottom: 8 }}>
            <Link
              to={`/stocks/${s.symbol}`}
              style={{ display: 'inline-block', padding: '8px 12px', borderRadius: 6, textDecoration: 'none', color: '#6366f1', fontWeight: 600 }}
            >
              {s.symbol}
            </Link>
            {s.name && <span style={{ color: '#6b7280', marginLeft: 8 }}>{s.name}</span>}
          </li>
        ))}
      </ul>
    </div>
  )
}
