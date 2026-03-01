/**
 * Color semantics (PRD §5.3): consistent green/red for P/L and sentiment,
 * severity-based colors for notifications.
 */

export const plPositive = '#166534'
export const plNegative = '#b91c1c'
export const severityHigh = '#b91c1c'
export const severityMedium = '#b45309'
export const severityLow = '#4b5563'

export function plColor(value: number): string {
  return value >= 0 ? plPositive : plNegative
}

export function severityColor(severity: string): string {
  const s = severity?.toLowerCase() ?? ''
  if (s === 'high') return severityHigh
  if (s === 'medium') return severityMedium
  return severityLow
}
