import React from 'react'
import { LineChart, Line, ResponsiveContainer } from 'recharts'
import type { PricePoint } from '../services/api'

export type SparklineProps = {
  data: PricePoint[]
  width?: number
  height?: number
  /** Line color; default #6366f1 */
  stroke?: string
}

/**
 * Minimal sparkline for price close series (e.g. Dashboard table).
 */
export const Sparkline: React.FC<SparklineProps> = ({
  data,
  width = 80,
  height = 28,
  stroke = '#6366f1',
}) => {
  if (!data.length) return <span style={{ fontSize: 10, color: '#9ca3af' }}>—</span>

  const chartData = data.map((p) => ({ date: p.date, close: p.close }))

  return (
    <div style={{ width, height }} aria-hidden>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={chartData} margin={{ top: 2, right: 2, bottom: 2, left: 2 }}>
          <Line type="monotone" dataKey="close" stroke={stroke} strokeWidth={1.5} dot={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
