import React from 'react'
import {
  fetchCausalEvidence,
  type CausalEvidenceResponse,
  type LagCorrelation,
} from '../../services/api'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import { spacing } from '../../theme'

type Props = { symbol: string }

function sortByAbsCorrDesc(rows: LagCorrelation[]): LagCorrelation[] {
  return [...rows].sort((a, b) => Math.abs(b.corr) - Math.abs(a.corr))
}

function Section({
  title,
  children,
  style,
}: {
  title: string
  children: React.ReactNode
  style?: React.CSSProperties
}) {
  return (
    <div
      style={{
        border: '1px solid #ddd',
        borderRadius: 8,
        padding: 12,
        ...style,
      }}
    >
      <div style={{ fontWeight: 700, marginBottom: 8 }}>{title}</div>
      {children}
    </div>
  )
}

function LagTable({ rows }: { rows: LagCorrelation[] }) {
  return (
    <table style={{ width: '100%', borderCollapse: 'collapse' }}>
      <thead>
        <tr>
          <th align="left">Lag</th>
          <th align="left">Corr</th>
          <th align="left">N</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={`${r.lag}`}>
            <td>{r.lag}</td>
            <td>{r.corr.toFixed(4)}</td>
            <td>{r.n}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function MetricTable({ rows }: { rows: { name: string; value: number }[] }) {
  return (
    <table style={{ width: '100%', borderCollapse: 'collapse' }}>
      <thead>
        <tr>
          <th align="left">Metric</th>
          <th align="left">Value</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.name}>
            <td>{r.name}</td>
            <td>
              {Number.isFinite(r.value) ? r.value.toFixed(4) : String(r.value)}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function LagChart({
  mentionRows,
  sentimentRows,
}: {
  mentionRows: LagCorrelation[]
  sentimentRows: LagCorrelation[]
}) {
  const byLag = new Map<
    number,
    { lag: number; mention: number; sentiment: number }
  >()
  for (const r of mentionRows) {
    byLag.set(r.lag, {
      lag: r.lag,
      mention: r.corr,
      sentiment: byLag.get(r.lag)?.sentiment ?? 0,
    })
  }
  for (const r of sentimentRows) {
    const existing = byLag.get(r.lag)
    if (existing) existing.sentiment = r.corr
    else byLag.set(r.lag, { lag: r.lag, mention: 0, sentiment: r.corr })
  }
  const data = [...byLag.values()].sort((a, b) => a.lag - b.lag)
  if (!data.length) return null
  return (
    <ResponsiveContainer width="100%" height={200}>
      <LineChart data={data} margin={{ top: 8, right: 8, bottom: 8, left: 8 }}>
        <XAxis dataKey="lag" tick={{ fontSize: 11 }} />
        <YAxis domain={[-1, 1]} tick={{ fontSize: 11 }} />
        <Tooltip
          formatter={(v: number) => v.toFixed(4)}
          labelFormatter={(l) => `Lag ${l}`}
        />
        <Line
          type="monotone"
          dataKey="mention"
          stroke="#6366f1"
          strokeWidth={2}
          dot={false}
          name="Mentions"
        />
        <Line
          type="monotone"
          dataKey="sentiment"
          stroke="#10b981"
          strokeWidth={2}
          dot={false}
          name="Sentiment"
        />
      </LineChart>
    </ResponsiveContainer>
  )
}

export function CausalPanel({ symbol }: Props) {
  const [days, setDays] = React.useState(90)
  const [freq, setFreq] = React.useState<string>('1h')
  const [maxLag, setMaxLag] = React.useState(12)
  const [includePlacebo, setIncludePlacebo] = React.useState(true)

  const [loading, setLoading] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const [data, setData] = React.useState<CausalEvidenceResponse | null>(null)

  const run = React.useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const resp = await fetchCausalEvidence({
        symbol,
        days,
        freq,
        maxLag,
        includePlacebo,
      })
      setData(resp)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
      setData(null)
    } finally {
      setLoading(false)
    }
  }, [symbol, days, freq, maxLag, includePlacebo])

  React.useEffect(() => {
    setData(null)
    setError(null)
    run()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [symbol])

  const isDark =
    typeof document !== 'undefined' &&
    document.documentElement.getAttribute('data-theme') === 'dark'
  const sectionBorder = isDark ? '1px solid #374151' : '1px solid #ddd'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.lg }}>
      <div
        style={{
          display: 'flex',
          gap: spacing.md,
          alignItems: 'flex-end',
          flexWrap: 'wrap',
        }}
      >
        <div>
          <label style={{ display: 'block', marginBottom: 4, fontSize: 14 }}>
            Days
          </label>
          <input
            type="number"
            min={7}
            max={730}
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            style={{
              padding: '6px 10px',
              border: sectionBorder,
              borderRadius: 6,
              fontSize: 14,
            }}
          />
        </div>

        <div>
          <label style={{ display: 'block', marginBottom: 4, fontSize: 14 }}>
            Frequency
          </label>
          <select
            value={freq}
            onChange={(e) => setFreq(e.target.value)}
            style={{
              padding: '6px 10px',
              border: sectionBorder,
              borderRadius: 6,
              fontSize: 14,
            }}
          >
            <option value="15min">15min</option>
            <option value="1h">1h</option>
            <option value="1d">1d</option>
          </select>
        </div>

        <div>
          <label style={{ display: 'block', marginBottom: 4, fontSize: 14 }}>
            Max lag
          </label>
          <input
            type="number"
            min={1}
            max={48}
            value={maxLag}
            onChange={(e) => setMaxLag(Number(e.target.value))}
            style={{
              padding: '6px 10px',
              border: sectionBorder,
              borderRadius: 6,
              fontSize: 14,
            }}
          />
        </div>

        <label
          style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: 14 }}
        >
          <input
            type="checkbox"
            checked={includePlacebo}
            onChange={(e) => setIncludePlacebo(e.target.checked)}
          />
          Include placebo
        </label>

        <button
          type="button"
          onClick={run}
          disabled={loading}
          style={{
            padding: '8px 16px',
            border: '1px solid #6366f1',
            borderRadius: 6,
            background: '#6366f1',
            color: '#fff',
            fontWeight: 600,
            cursor: loading ? 'not-allowed' : 'pointer',
          }}
        >
          {loading ? 'Running…' : 'Run'}
        </button>
      </div>

      <div style={{ fontSize: 13, opacity: 0.85 }}>
        <strong>Lead–lag evidence</strong> (not proof of causality). Positive lag
        means Reddit signal leads returns.
      </div>

      {error && (
        <div
          style={{
            border: '1px solid #f99',
            padding: 12,
            borderRadius: 8,
            color: '#b91c1c',
          }}
        >
          <strong>Error:</strong> {error}
        </div>
      )}

      {data?.status === 'insufficient_data' && (
        <div
          style={{
            border: sectionBorder,
            padding: 12,
            borderRadius: 8,
          }}
        >
          <div>
            <strong>INSUFFICIENT DATA</strong>
          </div>
          <div>Symbol: {data.symbol}</div>
          <div>Freq: {data.freq}</div>
          <div>Reason: {data.reason}</div>
          <div>Buckets available: {data.buckets_available}</div>
          <div>Min required: {data.min_required}</div>
          {data.notes?.length ? (
            <ul>
              {data.notes.map((n, i) => (
                <li key={i}>{n}</li>
              ))}
            </ul>
          ) : null}
        </div>
      )}

      {data && data.status !== 'insufficient_data' && (
        <>
          <div
            style={{ display: 'flex', gap: 24, flexWrap: 'wrap' }}
          >
            <div>
              <div>
                <strong>Sample size:</strong> {data.sample_size}
              </div>
              <div>
                <strong>Freq:</strong> {data.freq}
              </div>
              <div>
                <strong>Start:</strong> {data.start_utc}
              </div>
              <div>
                <strong>End:</strong> {data.end_utc}
              </div>
            </div>

            {data.notes?.length ? (
              <div>
                <div>
                  <strong>Notes</strong>
                </div>
                <ul>
                  {data.notes.map((n, i) => (
                    <li key={i}>{n}</li>
                  ))}
                </ul>
              </div>
            ) : null}
          </div>

          <Section title="Correlation vs lag" style={{ border: sectionBorder }}>
            <LagChart
              mentionRows={data.mention_xcorr}
              sentimentRows={data.sentiment_xcorr}
            />
          </Section>

          <Section title="Mentions ↔ Returns (xcorr)" style={{ border: sectionBorder }}>
            <LagTable
              rows={sortByAbsCorrDesc(data.mention_xcorr).slice(0, 12)}
            />
          </Section>

          <Section title="Sentiment ↔ Returns (xcorr)" style={{ border: sectionBorder }}>
            <LagTable
              rows={sortByAbsCorrDesc(data.sentiment_xcorr).slice(0, 12)}
            />
          </Section>

          <Section title="Predictive metrics" style={{ border: sectionBorder }}>
            <MetricTable
              rows={data.predictive.map((r) => ({
                name: r.metric,
                value: r.value,
              }))}
            />
          </Section>

          {includePlacebo ? (
            <Section title="Placebo metrics" style={{ border: sectionBorder }}>
              <MetricTable
                rows={data.placebo.map((r) => ({
                  name: r.metric,
                  value: r.value,
                }))}
              />
            </Section>
          ) : null}
        </>
      )}
    </div>
  )
}
