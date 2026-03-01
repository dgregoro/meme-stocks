import React, { useEffect, useState } from 'react'
import { api, Stock, Sentiment, PricePoint, RedditMention } from '../services/api'
import { EmptyState } from '../components/EmptyState'
import { LoadingSpinner } from '../components/LoadingSpinner'

function redditUrl(url: string): string {
  if (!url) return '#'
  if (url.startsWith('http')) return url
  return `https://www.reddit.com${url.startsWith('/') ? '' : '/'}${url}`
}

export const Stocks: React.FC = () => {
  const [stocks, setStocks] = useState<Stock[]>([])
  const [selected, setSelected] = useState<string | null>(null)
  const [sentiment, setSentiment] = useState<Sentiment | null>(null)
  const [prices, setPrices] = useState<PricePoint[]>([])
  const [mentions, setMentions] = useState<RedditMention[]>([])
  const [error, setError] = useState<string | null>(null)
  const [stocksLoading, setStocksLoading] = useState(true)

  useEffect(() => {
    api
      .listStocks()
      .then(setStocks)
      .catch((e) => setError(String(e)))
      .finally(() => setStocksLoading(false))
  }, [])

  useEffect(() => {
    if (!selected) return
    void Promise.resolve().then(() => {
      setSentiment(null)
      setPrices([])
      setMentions([])
      setError(null)
    })
    api.getSentiment(selected).then(setSentiment).catch((e) => setError(String(e)))
    api.getPrices(selected).then(setPrices).catch((e) => setError(String(e)))
    api.getMentions(selected).then(setMentions).catch(() => setMentions([]))
  }, [selected])

  if (stocksLoading) return <LoadingSpinner message="Loading stocks…" />
  if (stocks.length === 0 && !error) {
    return (
      <div>
        <h3>Stocks</h3>
        <EmptyState
          title="No stocks tracked"
          message="Stocks are added when they appear in Reddit mentions or via the API."
          action="Trigger Reddit collection or refresh symbol universe to discover stocks."
        />
      </div>
    )
  }

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
        {error && <div style={{ color: '#b91c1c', padding: '8px 12px', marginBottom: 12, backgroundColor: '#fef2f2', borderRadius: 6 }} role="alert">Error: {error}</div>}
        {!selected ? (
          <EmptyState title="Select a stock" message="Choose a symbol from the list to see sentiment, price history, and Reddit mentions." />
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
              <strong>Recent Reddit mentions (source)</strong>
              {mentions.length === 0 ? (
                <p style={{ margin: 0 }}>No recent mentions.</p>
              ) : (
                <ul style={{ listStyle: 'none', paddingLeft: 0 }}>
                  {mentions.map((m) => (
                    <li key={m.id} style={{ marginBottom: 8 }}>
                      <span style={{ fontWeight: 600 }}>r/{m.subreddit}</span>
                      {' — '}
                      <a href={redditUrl(m.url)} target="_blank" rel="noopener noreferrer">
                        {m.title.length > 60 ? `${m.title.slice(0, 60)}…` : m.title}
                      </a>
                      {' '}
                      <span style={{ color: '#666', fontSize: '0.9em' }}>
                        ({m.upvotes} ↑, {m.comments} comments)
                      </span>
                    </li>
                  ))}
                </ul>
              )}
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
