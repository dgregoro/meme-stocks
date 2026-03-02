import React, { useEffect, useMemo, useState } from 'react'

import { api, type CollectionStatus, type JobStatus } from '../services/api'
import { LoadingSpinner } from '../components/LoadingSpinner'
import { spacing } from '../theme'

type StatusFilter = 'all' | 'bad'

export const DataCollection: React.FC = () => {
  const [status, setStatus] = useState<CollectionStatus | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [lastUpdatedIso, setLastUpdatedIso] = useState<string | null>(null)
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [jobsFilter, setJobsFilter] = useState<StatusFilter>('bad')

  const fetchStatus = () => {
    setError(null)
    api
      .getCollectionStatus()
      .then((data) => {
        setStatus(data)
        setLastUpdatedIso(new Date().toISOString())
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    fetchStatus()
  }, [])

  useEffect(() => {
    if (!autoRefresh) return
    const intervalMs = 30_000
    const id = setInterval(fetchStatus, intervalMs)
    return () => clearInterval(id)
  }, [autoRefresh])

  const sortedJobs: JobStatus[] = useMemo(() => {
    if (!status) return []
    const copy = [...status.jobs]
    copy.sort((a, b) => {
      const order = (s: JobStatus['last_status']) => {
        if (s === 'failure') return 0
        if (s === 'never') return 1
        if (s === 'running') return 2
        return 3
      }
      const diff = order(a.last_status) - order(b.last_status)
      if (diff !== 0) return diff
      return a.job_id.localeCompare(b.job_id)
    })
    if (jobsFilter === 'bad') {
      return copy.filter((j) => j.last_status !== 'success')
    }
    return copy
  }, [status, jobsFilter])

  const formatTime = (iso: string | null | undefined) => {
    if (!iso) return '—'
    const d = new Date(iso)
    return d.toLocaleString()
  }

  const formatRelative = (iso: string | null | undefined) => {
    if (!iso) return 'never'
    const then = new Date(iso).getTime()
    const now = Date.now()
    const diffMs = Math.max(0, now - then)
    const diffMin = Math.round(diffMs / 60000)
    if (diffMin === 0) return 'just now'
    if (diffMin === 1) return '1 min ago'
    if (diffMin < 60) return `${diffMin} min ago`
    const diffH = Math.round(diffMin / 60)
    if (diffH === 1) return '1 hour ago'
    if (diffH < 48) return `${diffH} hours ago`
    const diffD = Math.round(diffH / 24)
    return `${diffD} days ago`
  }

  if (loading && !status) {
    return <LoadingSpinner message="Loading data collection status..." />
  }

  if (error) {
    return (
      <div
        style={{
          padding: '12px 16px',
          marginBottom: 16,
          borderRadius: 6,
          backgroundColor: '#fef2f2',
          color: '#b91c1c',
        }}
        role="alert"
      >
        Error loading collection status: {error}
      </div>
    )
  }

  if (!status) {
    return <div>No status available.</div>
  }

  const headerRowStyle: React.CSSProperties = {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.lg,
    gap: spacing.md,
    flexWrap: 'wrap',
  }

  const cardStyle: React.CSSProperties = {
    padding: '12px 16px',
    border: '1px solid #e5e7eb',
    borderRadius: 8,
    minWidth: 220,
    flex: 1,
  }

  const pill = (statusValue: JobStatus['last_status']) => {
    let bg = '#e5e7eb'
    let color = '#111827'
    if (statusValue === 'failure') {
      bg = '#fee2e2'
      color = '#b91c1c'
    } else if (statusValue === 'never') {
      bg = '#fef3c7'
      color = '#92400e'
    } else if (statusValue === 'running') {
      bg = '#d1fae5'
      color = '#065f46'
    } else if (statusValue === 'success') {
      bg = '#dcfce7'
      color = '#166534'
    }
    return {
      backgroundColor: bg,
      color,
      padding: '2px 8px',
      borderRadius: 999,
      fontSize: 12,
      fontWeight: 500,
      whiteSpace: 'nowrap' as const,
    }
  }

  return (
    <div>
      <div style={headerRowStyle}>
        <div>
          <h2 style={{ marginBottom: 4 }}>Data Collection</h2>
          <div style={{ fontSize: 14, color: '#6b7280' }}>
            Server UTC: {formatTime(status.server_time_utc)} · Market local:{' '}
            {formatTime(status.market_time_local)}
          </div>
          {lastUpdatedIso && (
            <div style={{ fontSize: 12, color: '#9ca3af' }}>
              Last refreshed: {formatRelative(lastUpdatedIso)}
            </div>
          )}
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <button
            type="button"
            onClick={fetchStatus}
            style={{
              padding: '6px 12px',
              borderRadius: 6,
              border: '1px solid #d1d5db',
              backgroundColor: '#fff',
              cursor: 'pointer',
            }}
          >
            Refresh
          </button>
          <label style={{ fontSize: 14, display: 'flex', alignItems: 'center', gap: 4 }}>
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
            />
            Auto-refresh (30s)
          </label>
        </div>
      </div>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: spacing.md, marginBottom: spacing.lg }}>
        <div style={cardStyle}>
          <h3 style={{ marginTop: 0, marginBottom: 8 }}>Reddit ingestion</h3>
          <div style={{ fontSize: 14 }}>
            <div>
              Posts: <strong>{status.reddit.posts_last_1h}</strong> (1h) ·{' '}
              <strong>{status.reddit.posts_last_24h}</strong> (24h)
            </div>
            <div>
              Mentions: <strong>{status.reddit.mentions_last_1h}</strong> (1h) ·{' '}
              <strong>{status.reddit.mentions_last_24h}</strong> (24h)
            </div>
            <div style={{ marginTop: 6, fontSize: 12, color: '#6b7280' }}>
              Newest post collected: {formatRelative(status.reddit.newest_post_collected_at_utc)}
            </div>
          </div>
        </div>

        <div style={cardStyle}>
          <h3 style={{ marginTop: 0, marginBottom: 8 }}>Price ingestion</h3>
          <div style={{ fontSize: 14 }}>
            <div>
              Newest price date: <strong>{status.prices.newest_price_date ?? 'n/a'}</strong>
            </div>
            <div>
              Rows: <strong>{status.prices.price_rows_last_7d}</strong> (7d) ·{' '}
              <strong>{status.prices.price_rows_last_30d}</strong> (30d)
            </div>
          </div>
        </div>

        <div style={cardStyle}>
          <h3 style={{ marginTop: 0, marginBottom: 8 }}>Daily Reddit features</h3>
          <div style={{ fontSize: 14 }}>
            <div>
              Newest trading day:{' '}
              <strong>{status.daily_features.newest_trading_day ?? 'n/a'}</strong>
            </div>
            <div>
              Rows: <strong>{status.daily_features.rows_last_7d}</strong> (7d) ·{' '}
              <strong>{status.daily_features.rows_last_30d}</strong> (30d)
            </div>
          </div>
        </div>
      </div>

      <section aria-label="Job execution status">
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: 8,
          }}
        >
          <h3 style={{ margin: 0 }}>Scheduled jobs</h3>
          <div style={{ fontSize: 14, display: 'flex', gap: 8 }}>
            <button
              type="button"
              onClick={() => setJobsFilter('bad')}
              style={{
                padding: '4px 8px',
                borderRadius: 6,
                border: jobsFilter === 'bad' ? '2px solid #111827' : '1px solid #d1d5db',
                backgroundColor: jobsFilter === 'bad' ? '#e5e7eb' : '#fff',
                cursor: 'pointer',
              }}
            >
              Show issues
            </button>
            <button
              type="button"
              onClick={() => setJobsFilter('all')}
              style={{
                padding: '4px 8px',
                borderRadius: 6,
                border: jobsFilter === 'all' ? '2px solid #111827' : '1px solid #d1d5db',
                backgroundColor: jobsFilter === 'all' ? '#e5e7eb' : '#fff',
                cursor: 'pointer',
              }}
            >
              Show all
            </button>
          </div>
        </div>
        <table
          cellPadding={6}
          style={{ borderCollapse: 'collapse', width: '100%', fontSize: 14, marginTop: 4 }}
        >
          <thead>
            <tr style={{ borderBottom: '2px solid #e5e7eb' }}>
              <th style={{ textAlign: 'left' }}>Job</th>
              <th style={{ textAlign: 'left' }}>Schedule</th>
              <th style={{ textAlign: 'left' }}>Last status</th>
              <th style={{ textAlign: 'left' }}>Last run</th>
              <th style={{ textAlign: 'left' }}>Last success</th>
            </tr>
          </thead>
          <tbody>
            {sortedJobs.map((j) => (
              <tr key={j.job_id} style={{ borderBottom: '1px solid #f3f4f6' }}>
                <td style={{ fontWeight: 500 }}>{j.job_id}</td>
                <td>{j.schedule ?? '—'}</td>
                <td>
                  <span style={pill(j.last_status)}>{j.last_status}</span>
                </td>
                <td title={j.last_start_utc ?? undefined}>{formatRelative(j.last_start_utc)}</td>
                <td title={j.last_success_utc ?? undefined}>{formatRelative(j.last_success_utc)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  )
}

