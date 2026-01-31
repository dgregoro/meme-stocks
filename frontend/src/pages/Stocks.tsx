import React, { useEffect, useState } from 'react'
import { api, Stock, Sentiment, PricePoint } from '../services/api'

export const Stocks: React.FC = () => {
  const [stocks, setStocks] = useState<Stock[]>([])
  const [selected, setSelected] = useState<string | null>(null)
  const [sentiment, setSentiment] = useState<Sentiment | null>(null)
  const [prices, setPrices] = useState<PricePoint[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.listStocks().then(setStocks).catch((e) => setError(String(e)))
  }, [])

  useEffect(() => {
    if (!selected) return
    void Promise.resolve().then(() => {
      setSentiment(null)
      setPrices([])
      setError(null)
    })
    api.getSentiment(selected).then(setSentiment).catch((e) => setError(String(e)))
    api.getPrices(selected).then(setPrices).catch((e) => setError(String(e)))
  }, [selected])

  return (
    <div style={{ display: 'flex', gap: 24 }}>
      <div style={{ minWidth: 240 }}>
        <h3>Stocks</h3>
        <ul>
          {stocks.map((s) => (
            <li key={s.symbol}>
              <button onClick={() => setSelected(s.symbol)}>{s.symbol}</button>
            </li>
          ))}
        </ul>
      </div>
      <div style={{ flex: 1 }}>
        {error && <div style={{ color: 'red' }}>Error: {error}</div>}
        {!selected ? (
          <div>Select a stock…</div>
        ) : (
          <div>
            <h3>{selected}</h3>
            <div>
              <strong>Sentiment:</strong>{' '}
              {sentiment
                ? `${sentiment.classification} (${sentiment.score === null ? 'n/a' : sentiment.score.toFixed(2)})`
                : 'Loading…'}
            </div>
            <div style={{ marginTop: 12 }}>
              <strong>Recent Prices:</strong>
              <ul>
                {prices.slice(-10).map((p) => (
                  <li key={p.date}>
                    {p.date}: close {p.close} vol {p.volume}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
