import React, { useEffect, useState, useMemo } from 'react'
import { api, type AnalysisRow, type JobRun } from '../services/api'
import { formatRelativeTime, sentimentClass } from '../utils/dashboardUtils'
import { LoadingSpinner } from '../components/LoadingSpinner'
import { EmptyState } from '../components/EmptyState'

type SortKey = 'symbol' | 'composite_score' | 'price_trend' | 'sentiment_score' | 'mention_count'
type SortDir = 'asc' | 'desc'

export const Dashboard: React.FC = () => {
  const [rows, setRows] = useState<AnalysisRow[]>([])
  const [unreadCount, setUnreadCount] = useState<number | null>(null)
  const [lastRun, setLastRun] = useState<JobRun | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [sortKey, setSortKey] = useState<SortKey>('composite_score')
  const [sortDir, setSortDir] = useState<SortDir>('desc')
  const [lastUpdated, setLastUpdated] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([
      api.analysisDaily().then(setRows),
      api.listNotifications().then((n) => setUnreadCount(n.filter((x) => !x.read).length)),
      api.getJobRuns('reddit-collection').then((runs) => setLastRun(runs[0] ?? null)),
    ])
      .catch((e) => setError(String(e)))
      .finally(() => {
        setLoading(false)
        setLastUpdated(new Date().toISOString())
      })
  }, [])

  const sortedRows = useMemo(() => {
    const copy = [...rows]
    copy.sort((a, b) => {
      let aVal: string | number = a[sortKey]
      let bVal: string | number = b[sortKey]
      if (sortKey === 'sentiment_score') {
        aVal = a.sentiment_score ?? -999
        bVal = b.sentiment_score ?? -999
      }
      if (typeof aVal === 'number' && typeof bVal === 'number') {
        return sortDir === 'asc' ? aVal - bVal : bVal - aVal
      }
      const aStr = String(aVal)
      const bStr = String(bVal)
      return sortDir === 'asc'
        ? aStr.localeCompare(bStr)
        : bStr.localeCompare(aStr)
    })
    return copy
  }, [rows, sortKey, sortDir])

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortKey(key)
      setSortDir(key === 'symbol' || key === 'price_trend' ? 'asc' : 'desc')
    }
  }

  if (loading) return <LoadingSpinner message="Loading..." />
  if (error) return <div style={{ color: '#b91c1c', padding: '8px 12px', backgroundColor: '#fef2f2', borderRadius: 6 }} role="alert">Error: {error}</div>

  if (rows.length === 0) {
    return (
      <div>
        <h2>Daily Analysis</h2>
        <EmptyState
          title="No analysis yet"
          message="Daily analysis ranks stocks by sentiment and price trend."
          action="Trigger Reddit collection and daily analysis jobs to populate this view."
        />
      </div>
    )
  }

  return (
    <div>
      <h2>Daily Analysis</h2>
      {lastUpdated && (
        <p style={{ margin: '0 0 16px 0', fontSize: 14, color: '#6b7280' }}>
          Last updated: {formatRelativeTime(lastUpdated)}
        </p>
      )}
      <div style={{ display: 'flex', gap: 16, marginBottom: 24, flexWrap: 'wrap' }}>
        <div
          style={{
            padding: '12px 16px',
            border: '1px solid #ddd',
            borderRadius: 8,
            minWidth: 140,
          }}
        >
          <div style={{ fontSize: 12, color: '#666', marginBottom: 4 }}>Stocks in analysis</div>
          <div style={{ fontSize: 20, fontWeight: 600 }}>{rows.length}</div>
        </div>
        <div
          style={{
            padding: '12px 16px',
            border: '1px solid #ddd',
            borderRadius: 8,
            minWidth: 140,
          }}
        >
          <div style={{ fontSize: 12, color: '#666', marginBottom: 4 }}>Unread notifications</div>
          <div style={{ fontSize: 20, fontWeight: 600 }}>{unreadCount ?? 0}</div>
        </div>
        {lastRun && (
          <div
            style={{
              padding: '12px 16px',
              border: '1px solid #ddd',
              borderRadius: 8,
              minWidth: 140,
            }}
          >
            <div style={{ fontSize: 12, color: '#666', marginBottom: 4 }}>Last Reddit run</div>
            <div style={{ fontSize: 14 }} title={lastRun.run_at}>
              {formatRelativeTime(lastRun.run_at)}
            </div>
          </div>
        )}
      </div>

      <table cellPadding={8} style={{ borderCollapse: 'collapse', width: '100%' }}>
        <thead>
          <tr style={{ borderBottom: '2px solid #333' }}>
            <th
              style={{ textAlign: 'left', cursor: 'pointer', userSelect: 'none' }}
              onClick={() => handleSort('symbol')}
            >
              Symbol {sortKey === 'symbol' && (sortDir === 'asc' ? '↑' : '↓')}
            </th>
            <th
              style={{ textAlign: 'right', cursor: 'pointer', userSelect: 'none' }}
              onClick={() => handleSort('composite_score')}
            >
              Composite {sortKey === 'composite_score' && (sortDir === 'asc' ? '↑' : '↓')}
            </th>
            <th
              style={{ textAlign: 'left', cursor: 'pointer', userSelect: 'none' }}
              onClick={() => handleSort('price_trend')}
            >
              Trend {sortKey === 'price_trend' && (sortDir === 'asc' ? '↑' : '↓')}
            </th>
            <th
              style={{ textAlign: 'right', cursor: 'pointer', userSelect: 'none' }}
              onClick={() => handleSort('sentiment_score')}
            >
              Sentiment {sortKey === 'sentiment_score' && (sortDir === 'asc' ? '↑' : '↓')}
            </th>
            <th
              style={{ textAlign: 'right', cursor: 'pointer', userSelect: 'none' }}
              onClick={() => handleSort('mention_count')}
            >
              Mentions {sortKey === 'mention_count' && (sortDir === 'asc' ? '↑' : '↓')}
            </th>
          </tr>
        </thead>
        <tbody>
          {sortedRows.map((r) => {
            const sentClass = sentimentClass(r.sentiment_score)
            return (
              <tr key={r.symbol} style={{ borderBottom: '1px solid #eee' }}>
                <td style={{ fontWeight: 600 }}>{r.symbol}</td>
                <td style={{ textAlign: 'right' }}>{r.composite_score.toFixed(2)}</td>
                <td>{r.price_trend}</td>
                <td style={{ textAlign: 'right' }}>
                  <span
                    style={{
                      padding: '2px 8px',
                      borderRadius: 4,
                      fontSize: 12,
                      fontWeight: 500,
                      backgroundColor:
                        sentClass === 'positive'
                          ? '#d4edda'
                          : sentClass === 'negative'
                            ? '#f8d7da'
                            : '#e2e3e5',
                      color:
                        sentClass === 'positive'
                          ? '#155724'
                          : sentClass === 'negative'
                            ? '#721c24'
                            : '#383d41',
                    }}
                  >
                    {r.sentiment_score === null ? 'n/a' : r.sentiment_score.toFixed(2)}
                  </span>
                </td>
                <td style={{ textAlign: 'right' }}>{r.mention_count}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
