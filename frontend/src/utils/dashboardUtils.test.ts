import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { formatRelativeTime, sentimentClass } from './dashboardUtils'

describe('formatRelativeTime', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-02-28T12:00:00.000Z'))
  })
  afterEach(() => {
    vi.useRealTimers()
  })

  it('returns "just now" for times under 60 seconds ago', () => {
    expect(formatRelativeTime('2026-02-28T11:59:30.000Z')).toBe('just now')
  })

  it('returns "Nm ago" for minutes', () => {
    expect(formatRelativeTime('2026-02-28T11:58:00.000Z')).toBe('2m ago')
  })

  it('returns "Nh ago" for hours', () => {
    expect(formatRelativeTime('2026-02-28T10:00:00.000Z')).toBe('2h ago')
  })

  it('returns "Nd ago" for days', () => {
    expect(formatRelativeTime('2026-02-27T12:00:00.000Z')).toBe('1d ago')
  })

  it('returns empty string for invalid date', () => {
    expect(formatRelativeTime('not-a-date')).toBe('')
  })
})

describe('sentimentClass', () => {
  it('returns "positive" for score >= 0.3', () => {
    expect(sentimentClass(0.3)).toBe('positive')
    expect(sentimentClass(0.5)).toBe('positive')
  })

  it('returns "negative" for score <= -0.2', () => {
    expect(sentimentClass(-0.2)).toBe('negative')
    expect(sentimentClass(-0.5)).toBe('negative')
  })

  it('returns "neutral" for null or between -0.2 and 0.3', () => {
    expect(sentimentClass(null)).toBe('neutral')
    expect(sentimentClass(0)).toBe('neutral')
    expect(sentimentClass(0.1)).toBe('neutral')
    expect(sentimentClass(-0.1)).toBe('neutral')
  })
})
