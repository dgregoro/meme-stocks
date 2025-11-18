import React, { useEffect, useState } from 'react'
import { api, AnalysisRow } from '../services/api'

export const Dashboard: React.FC = () => {
  const [rows, setRows] = useState<AnalysisRow[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api
      .analysisDaily()
      .then(setRows)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div>Loading...</div>
  if (error) return <div style={{ color: 'red' }}>Error: {error}</div>

  return (
    <div>
      <h2>Daily Analysis</h2>
      <table cellPadding={8} style={{ borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            <th>Symbol</th>
            <th>Composite</th>
            <th>Trend</th>
            <th>Sentiment</th>
            <th>Mentions</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.symbol}>
              <td>{r.symbol}</td>
              <td>{r.composite_score.toFixed(2)}</td>
              <td>{r.price_trend}</td>
              <td>{r.sentiment_score === null ? 'n/a' : r.sentiment_score.toFixed(2)}</td>
              <td>{r.mention_count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
