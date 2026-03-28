import React, { useEffect, useState } from 'react'
import { useParams, Link, useSearchParams } from 'react-router-dom'
import { api, type Sentiment, type PricePoint, type RedditMention } from '../services/api'
import { LoadingSpinner } from '../components/LoadingSpinner'
import { PriceChart } from '../components/PriceChart'
import { CausalPanel } from '../components/symbols/CausalPanel'
import { sentimentClass } from '../utils/dashboardUtils'
import { spacing } from '../theme'

type StockDetailTab = 'overview' | 'causal'

function redditUrl(url: string): string {
  if (!url) return '#'
  if (url.startsWith('http')) return url
  return `https://www.reddit.com${url.startsWith('/') ? '' : '/'}${url}`
}

export const StockDetail: React.FC = () => {
  const { symbol } = useParams<{ symbol: string }>()
  const [searchParams] = useSearchParams()
  const tab = (searchParams.get('tab') as StockDetailTab) ?? 'overview'
  const [sentiment, setSentiment] = useState<Sentiment | null>(null)
  const [prices, setPrices] = useState<PricePoint[]>([])
  const [mentions, setMentions] = useState<RedditMention[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!symbol) return
    let cancelled = false
    const completedRef = { current: false }
    const tick = (): void => {
      if (!cancelled && !completedRef.current) setLoading(true)
      setError(null)
    }
    const id = requestAnimationFrame(tick)
    Promise.all([
      api.getSentiment(symbol).then(setSentiment).catch((e) => setError(String(e))),
      api.getPrices(symbol).then(setPrices).catch(() => setPrices([])),
      api.getMentions(symbol).then(setMentions).catch(() => setMentions([])),
    ]).finally(() => {
      if (!cancelled) {
        completedRef.current = true
        setLoading(false)
      }
    })
    return () => {
      cancelled = true
      cancelAnimationFrame(id)
    }
  }, [symbol])

  if (!symbol) {
    return <div>Missing symbol.</div>
  }

  if (loading) return <LoadingSpinner message={`Loading ${symbol}…`} />
  if (error) {
    return (
      <div>
        <Link to="/stocks" style={{ display: 'inline-block', marginBottom: 12 }}>← Back to list</Link>
        <div style={{ color: '#b91c1c', padding: '8px 12px', backgroundColor: '#fef2f2', borderRadius: 6 }} role="alert">Error: {error}</div>
      </div>
    )
  }

  const sentClass = sentiment ? sentimentClass(sentiment.score) : null
  const isDark =
    typeof document !== 'undefined' &&
    document.documentElement.getAttribute('data-theme') === 'dark'

  const baseTabStyle: React.CSSProperties = {
    padding: '8px 14px',
    fontSize: '1rem',
    fontFamily: 'inherit',
    border: isDark ? '1px solid #4b5563' : '1px solid #ccc',
    borderRadius: 6,
    background: isDark ? '#374151' : '#fff',
    color: isDark ? '#e5e7eb' : '#111',
    cursor: 'pointer',
    textDecoration: 'none',
  }
  const activeTabStyle: React.CSSProperties = {
    ...baseTabStyle,
    background: isDark ? '#6366f1' : '#1a1a2e',
    color: '#fff',
    border: isDark ? '1px solid #6366f1' : '1px solid #1a1a2e',
    fontWeight: 600,
  }

  return (
    <div>
      <Link to="/stocks" style={{ display: 'inline-block', marginBottom: 16, color: '#6366f1' }}>← Back to list</Link>
      <h2 style={{ marginTop: 0 }}>{symbol}</h2>

      <div style={{ display: 'flex', gap: spacing.sm, marginBottom: spacing.lg }}>
        <Link
          to={`/stocks/${symbol}`}
          style={tab === 'overview' ? activeTabStyle : baseTabStyle}
        >
          Overview
        </Link>
        <Link
          to={`/stocks/${symbol}?tab=causal`}
          style={tab === 'causal' ? activeTabStyle : baseTabStyle}
        >
          Causal
        </Link>
      </div>

      {tab === 'causal' ? (
        <CausalPanel symbol={symbol} />
      ) : (
        <>
          <section style={{ marginBottom: 24 }}>
            <h3 style={{ marginBottom: 8 }}>Price</h3>
            <PriceChart data={prices} height={280} />
          </section>

          {sentiment && (
            <section style={{ marginBottom: 24 }}>
              <h3 style={{ marginBottom: 8 }}>Sentiment</h3>
              <p style={{ margin: 0 }}>
                <strong>{sentiment.classification}</strong>
                {sentiment.score != null && (
                  <span
                    style={{
                      marginLeft: 8,
                      padding: '2px 8px',
                      borderRadius: 4,
                      fontSize: 14,
                      fontWeight: 500,
                      backgroundColor:
                        sentClass === 'positive' ? '#d4edda' : sentClass === 'negative' ? '#f8d7da' : '#e2e3e5',
                      color: sentClass === 'positive' ? '#155724' : sentClass === 'negative' ? '#721c24' : '#383d41',
                    }}
                  >
                    {sentiment.score.toFixed(2)}
                  </span>
                )}
                {' '}({sentiment.mention_count} mentions, {sentiment.window_hours}h window)
              </p>
            </section>
          )}

          <section>
            <h3 style={{ marginBottom: 8 }}>Recent Reddit mentions</h3>
            {mentions.length === 0 ? (
              <p style={{ color: '#6b7280' }}>No recent mentions.</p>
            ) : (
              <ul style={{ listStyle: 'none', paddingLeft: 0 }}>
                {mentions.map((m) => (
                  <li key={m.id} style={{ marginBottom: 12, padding: 12, border: '1px solid #e5e7eb', borderRadius: 8 }}>
                    <span style={{ fontWeight: 600 }}>r/{m.subreddit}</span>
                    {' — '}
                    <a href={redditUrl(m.url)} target="_blank" rel="noopener noreferrer">
                      {m.title.length > 80 ? `${m.title.slice(0, 80)}…` : m.title}
                    </a>
                    <span style={{ color: '#6b7280', fontSize: 14, display: 'block', marginTop: 4 }}>
                      {m.upvotes} ↑ · {m.comments} comments
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      )}
    </div>
  )
}
