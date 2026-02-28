/**
 * Pure helpers for Dashboard data presentation. Exported for unit testing.
 */
export function formatRelativeTime(iso: string): string {
  try {
    const d = new Date(iso)
    const now = new Date()
    const sec = Math.floor((now.getTime() - d.getTime()) / 1000)
    if (Number.isNaN(sec) || sec < 0) return ''
    if (sec < 60) return 'just now'
    if (sec < 3600) return `${Math.floor(sec / 60)}m ago`
    if (sec < 86400) return `${Math.floor(sec / 3600)}h ago`
    return `${Math.floor(sec / 86400)}d ago`
  } catch {
    return ''
  }
}

export function sentimentClass(
  score: number | null,
): 'positive' | 'negative' | 'neutral' {
  if (score === null) return 'neutral'
  if (score >= 0.3) return 'positive'
  if (score <= -0.2) return 'negative'
  return 'neutral'
}
