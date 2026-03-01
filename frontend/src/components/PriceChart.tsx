import React from 'react'
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import type { PricePoint } from '../services/api'

export type PriceChartProps = {
  data: PricePoint[]
  height?: number
}

function formatDate(iso: string): string {
  try {
    const d = new Date(iso)
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: '2-digit' })
  } catch {
    return iso
  }
}

/**
 * Full price chart (close) for stock detail view.
 */
export const PriceChart: React.FC<PriceChartProps> = ({ data, height = 280 }) => {
  if (!data.length) {
    return (
      <div style={{ height, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#6b7280' }}>
        No price data
      </div>
    )
  }

  const chartData = data.map((p) => ({ ...p, dateLabel: formatDate(p.date) }))

  return (
    <div style={{ width: '100%', height }} role="img" aria-label="Price chart">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={chartData} margin={{ top: 8, right: 8, bottom: 8, left: 8 }}>
          <defs>
            <linearGradient id="priceGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#6366f1" stopOpacity={0.3} />
              <stop offset="100%" stopColor="#6366f1" stopOpacity={0} />
            </linearGradient>
          </defs>
          <XAxis dataKey="dateLabel" tick={{ fontSize: 11 }} />
          <YAxis domain={['auto', 'auto']} tick={{ fontSize: 11 }} tickFormatter={(v) => `$${v}`} />
          <Tooltip formatter={(v: number) => [`$${v.toFixed(2)}`, 'Close']} labelFormatter={(l) => l} />
          <Area type="monotone" dataKey="close" stroke="#6366f1" strokeWidth={2} fill="url(#priceGradient)" />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}
