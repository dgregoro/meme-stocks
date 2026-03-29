import React, { useCallback, useEffect, useMemo, useState } from 'react'

import {
  api,
  type CollectionStatus,
  type IntradayStatusResponse,
  type JobRunHistoryItem,
  type JobStatus,
  type RunOnceResponse,
  type StaleSymbolStatus,
} from '../services/api'
import { LoadingSpinner } from '../components/LoadingSpinner'
import { spacing } from '../theme'

type StatusFilter = 'all' | 'bad'

export const DataCollection: React.FC = () => {
  const [status, setStatus] = useState<CollectionStatus | null>(null)
  const [intradayStatus, setIntradayStatus] = useState<IntradayStatusResponse | null>(null)
  const [intradayRunResult, setIntradayRunResult] = useState<RunOnceResponse | null>(null)
  const [intradayRunError, setIntradayRunError] = useState<string | null>(null)
  const [intradayRunning, setIntradayRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [lastUpdatedIso, setLastUpdatedIso] = useState<string | null>(null)
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [jobsFilter, setJobsFilter] = useState<StatusFilter>('bad')
  const [staleSymbols, setStaleSymbols] = useState<StaleSymbolStatus[] | null>(null)
  const [jobRunsHistory, setJobRunsHistory] = useState<JobRunHistoryItem[] | null>(null)
  const [currentTime, setCurrentTime] = useState(() => Date.now())
  const [expandedRunIds, setExpandedRunIds] = useState<Set<number | null>>(new Set())

  useEffect(() => {
    const id = setInterval(() => setCurrentTime(Date.now()), 1000)
    return () => clearInterval(id)
  }, [])

  const fetchStatus = () => {
    setError(null)
    setIntradayRunError(null)
    Promise.all([
      api.getCollectionStatus(),
      api.getStaleSymbols(25),
      api.getJobRunsHistory(200),
      api.getIntradayStatus().catch(() => null),
    ])
      .then(([collection, stale, runs, intraday]) => {
        setStatus(collection)
        setStaleSymbols(stale)
        setJobRunsHistory(runs)
        setIntradayStatus(intraday ?? null)
        setLastUpdatedIso(new Date().toISOString())
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false))
  }

  const runIntradayOnce = () => {
    setIntradayRunning(true)
    setIntradayRunError(null)
    setIntradayRunResult(null)
    api
      .runIntradayOnce()
      .then((res) => {
        setIntradayRunResult(res)
        fetchStatus()
      })
      .catch((e) => setIntradayRunError(String(e)))
      .finally(() => setIntradayRunning(false))
  }

  useEffect(() => {
    queueMicrotask(() => fetchStatus())
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
        if (s === 'never') return 0
        return 1
      }
      const diff = order(a.last_status) - order(b.last_status)
      if (diff !== 0) return diff
      return a.job_id.localeCompare(b.job_id)
    })
    if (jobsFilter === 'bad') {
      return copy.filter((j) => j.last_status === 'never')
    }
    return copy
  }, [status, jobsFilter])

  const formatTime = (iso: string | null | undefined) => {
    if (!iso) return '—'
    const d = new Date(iso)
    return d.toLocaleString()
  }

  const toggleExpanded = useCallback((id: number | null) => {
    setExpandedRunIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }, [])

  const formatRelative = (iso: string | null | undefined) => {
    if (!iso) return 'never'
    const then = new Date(iso).getTime()
    const now = currentTime
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

  if (loading) {
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

  const jobPill = (statusValue: JobStatus['last_status']) => {
    let bg = '#e5e7eb'
    let color = '#111827'
    if (statusValue === 'never') {
      bg = '#fef3c7'
      color = '#92400e'
    } else if (statusValue === 'ran') {
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

  const healthPill = (value: 'ok' | 'stale' | 'empty') => {
    let bg = '#e5e7eb'
    let color = '#111827'
    if (value === 'ok') {
      bg = '#dcfce7'
      color = '#166534'
    } else if (value === 'stale') {
      bg = '#fef3c7'
      color = '#92400e'
    } else if (value === 'empty') {
      bg = '#fee2e2'
      color = '#b91c1c'
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
          <h3 style={{ marginTop: 0, marginBottom: 4 }}>Price data</h3>
          <div style={{ marginBottom: 6 }}>
            <span style={healthPill(status.health.prices)}>
              {status.health.prices.toUpperCase()}
            </span>
          </div>
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
          <h3 style={{ marginTop: 0, marginBottom: 4 }}>Scheduled jobs</h3>
          <div style={{ marginBottom: 6 }}>
            <span style={healthPill(status.health.jobs === 'ok' ? 'ok' : 'stale')}>
              {status.health.jobs.toUpperCase()}
            </span>
          </div>
          <p style={{ fontSize: 13, color: '#6b7280', margin: 0 }}>
            Derived from recent job runs. Warnings usually mean a job has not completed since startup or is behind schedule.
          </p>
        </div>

        {intradayStatus && (
          <div style={{ ...cardStyle, minWidth: 280 }}>
            <h3 style={{ marginTop: 0, marginBottom: 4 }}>Intraday ingestion</h3>
            <div style={{ fontSize: 14, marginBottom: 8 }}>
              <div>
                Feed: <strong>{intradayStatus.alpaca_feed}</strong>
                {intradayStatus.free_plan_mode && (
                  <span style={{ marginLeft: 8, color: '#6b7280' }}>
                    (free plan, lag {intradayStatus.effective_data_lag_minutes}m)
                  </span>
                )}
              </div>
              <div>
                Newest last_ts: <strong>{formatTime(intradayStatus.newest_last_ts) ?? '—'}</strong>
              </div>
              <div>
                Oldest last_ts: <strong>{formatTime(intradayStatus.oldest_last_ts) ?? '—'}</strong>
              </div>
              {intradayStatus.latest_run && (
                <div style={{ marginTop: 4 }}>
                  Latest run: <strong>{intradayStatus.latest_run.bars_written ?? 0}</strong> bars,{' '}
                  <strong>{intradayStatus.latest_run.errors_count ?? 0}</strong> errors
                </div>
              )}
              {Object.keys(intradayStatus.counts_by_status ?? {}).length > 0 && (
                <div style={{ marginTop: 4, fontSize: 12, color: '#6b7280' }}>
                  {Object.entries(intradayStatus.counts_by_status).map(([k, v]) => (
                    <span key={k} style={{ marginRight: 8 }}>
                      {k}: {v}
                    </span>
                  ))}
                </div>
              )}
            </div>
            <button
              type="button"
              onClick={runIntradayOnce}
              disabled={intradayRunning || intradayStatus.lock?.held}
              style={{
                padding: '6px 12px',
                borderRadius: 6,
                border: '1px solid #6366f1',
                background: '#6366f1',
                color: '#fff',
                fontWeight: 500,
                cursor: intradayRunning || intradayStatus.lock?.held ? 'not-allowed' : 'pointer',
              }}
            >
              {intradayRunning
                ? 'Running…'
                : intradayStatus.lock?.held
                  ? 'Running'
                  : 'Run intraday ingestion once'}
            </button>
            {intradayRunResult && (
              <div style={{ marginTop: 8, fontSize: 13, padding: 8, backgroundColor: '#f0fdf4', borderRadius: 6 }}>
                Bars written: <strong>{intradayRunResult.bars_written}</strong>, symbols:{' '}
                {intradayRunResult.symbols_processed}, errors: {intradayRunResult.errors_count}
              </div>
            )}
            {intradayRunError && (
              <div
                style={{
                  marginTop: 8,
                  fontSize: 13,
                  padding: 8,
                  backgroundColor: '#fef2f2',
                  color: '#b91c1c',
                  borderRadius: 6,
                }}
              >
                {intradayRunError}
              </div>
            )}
          </div>
        )}
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
              <th style={{ textAlign: 'left' }}>Last result</th>
            </tr>
          </thead>
          <tbody>
            {sortedJobs.map((j) => (
              <tr key={j.job_id} style={{ borderBottom: '1px solid #f3f4f6' }}>
                <td style={{ fontWeight: 500 }}>{j.job_id}</td>
                <td>{j.schedule ?? '—'}</td>
                <td>
                  <span style={jobPill(j.last_status)}>{j.last_status}</span>
                </td>
                <td title={j.last_run_utc ?? undefined}>{formatRelative(j.last_run_utc)}</td>
                <td title={j.last_success_utc ?? undefined}>
                  {j.last_success_utc ? formatRelative(j.last_success_utc) : '—'}
                </td>
                <td
                  title={j.last_success_summary ?? j.last_run_summary ?? undefined}
                  style={{
                    maxWidth: 280,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {j.last_success_summary ?? j.last_run_summary ?? '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section aria-label="Job run history" style={{ marginTop: spacing.lg }}>
        <h3 style={{ marginBottom: 8 }}>Job run history</h3>
        <p style={{ fontSize: 12, color: '#6b7280', marginTop: 0, marginBottom: 8 }}>
          Recent job executions across all scheduled jobs.
        </p>
        {jobRunsHistory && jobRunsHistory.length > 0 ? (
          <table
            cellPadding={6}
            style={{ borderCollapse: 'collapse', width: '100%', fontSize: 14 }}
          >
            <thead>
              <tr style={{ borderBottom: '2px solid #e5e7eb' }}>
                <th style={{ textAlign: 'left' }}>Time</th>
                <th style={{ textAlign: 'left' }}>Job</th>
                <th style={{ textAlign: 'left' }}>Success</th>
                <th style={{ textAlign: 'left' }}>Duration</th>
                <th style={{ textAlign: 'left' }}>Summary</th>
                <th style={{ textAlign: 'left' }}>Error</th>
                <th style={{ width: 28 }} />
              </tr>
            </thead>
            <tbody>
              {jobRunsHistory.map((r, idx) => {
                const runKey = r.id ?? idx
                const hasDetails = r.metrics && Object.keys(r.metrics).length > 0
                const isExpanded = expandedRunIds.has(runKey as number)
                return (
                  <React.Fragment key={runKey}>
                    <tr style={{ borderBottom: '1px solid #f3f4f6' }}>
                      <td title={r.finished_at_utc ?? undefined}>
                        {r.finished_at_utc
                          ? formatRelative(r.finished_at_utc)
                          : '—'}
                      </td>
                      <td style={{ fontWeight: 500 }}>{r.job_name}</td>
                      <td>
                        {r.success === true ? (
                          <span aria-label="success">✅</span>
                        ) : r.success === false ? (
                          <span aria-label="failed">❌</span>
                        ) : (
                          '—'
                        )}
                      </td>
                      <td>
                        {r.duration_seconds != null
                          ? `${r.duration_seconds.toFixed(1)}s`
                          : '—'}
                      </td>
                      <td
                        title={r.summary ?? undefined}
                        style={{
                          maxWidth: 240,
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {r.summary ?? '—'}
                      </td>
                      <td
                        title={r.error_message ?? undefined}
                        style={{
                          maxWidth: 200,
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {r.error_message
                          ? r.error_message.length > 120
                            ? `${r.error_message.slice(0, 120)}…`
                            : r.error_message
                          : '—'}
                      </td>
                      <td>
                        {hasDetails ? (
                          <button
                            type="button"
                            onClick={() => toggleExpanded(runKey as number)}
                            aria-expanded={isExpanded}
                            style={{
                              padding: 0,
                              border: 'none',
                              background: 'none',
                              cursor: 'pointer',
                              fontSize: 12,
                            }}
                          >
                            {isExpanded ? '▼' : '▶'}
                          </button>
                        ) : (
                          ''
                        )}
                      </td>
                    </tr>
                    {hasDetails && isExpanded && (
                      <tr style={{ borderBottom: '1px solid #f3f4f6' }}>
                        <td colSpan={7} style={{ padding: '4px 8px', verticalAlign: 'top' }}>
                          <pre
                            style={{
                              margin: 0,
                              padding: 8,
                              fontSize: 12,
                              backgroundColor: '#f9fafb',
                              borderRadius: 4,
                              overflow: 'auto',
                              maxHeight: 200,
                            }}
                          >
                            {JSON.stringify(r.metrics, null, 2)}
                          </pre>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                )
              })}
            </tbody>
          </table>
        ) : (
          <p style={{ fontSize: 14, color: '#6b7280' }}>No run history yet.</p>
        )}
      </section>
      {staleSymbols && staleSymbols.length > 0 && (
        <section aria-label="Stalest symbols" style={{ marginTop: spacing.lg }}>
          <h3 style={{ marginBottom: 8 }}>Stalest symbols</h3>
          <p style={{ fontSize: 12, color: '#6b7280', marginTop: 0, marginBottom: 8 }}>
            Top {Math.min(staleSymbols.length, 25)} symbols with missing or stale data across
            Reddit, prices, and daily features.
          </p>
          <table
            cellPadding={6}
            style={{ borderCollapse: 'collapse', width: '100%', fontSize: 14 }}
          >
            <thead>
              <tr style={{ borderBottom: '2px solid #e5e7eb' }}>
                <th style={{ textAlign: 'left' }}>Symbol</th>
                <th style={{ textAlign: 'left' }}>Last price</th>
                <th style={{ textAlign: 'left' }}>Reasons</th>
              </tr>
            </thead>
            <tbody>
              {staleSymbols.map((s) => (
                <tr key={s.symbol} style={{ borderBottom: '1px solid #f3f4f6' }}>
                  <td style={{ fontWeight: 500 }}>{s.symbol}</td>
                  <td>{s.last_price_date ?? 'n/a'}</td>
                  <td>{s.stale_reasons.join(', ')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </div>
  )
}
