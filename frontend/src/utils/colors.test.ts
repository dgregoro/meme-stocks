import { describe, it, expect } from 'vitest'
import { plColor, severityColor, plPositive, plNegative, severityHigh, severityMedium, severityLow } from './colors'

describe('colors', () => {
  describe('plColor', () => {
    it('returns positive color for zero and positive values', () => {
      expect(plColor(0)).toBe(plPositive)
      expect(plColor(10)).toBe(plPositive)
    })
    it('returns negative color for negative values', () => {
      expect(plColor(-5)).toBe(plNegative)
    })
  })

  describe('severityColor', () => {
    it('returns high color for high severity', () => {
      expect(severityColor('high')).toBe(severityHigh)
      expect(severityColor('HIGH')).toBe(severityHigh)
    })
    it('returns medium color for medium severity', () => {
      expect(severityColor('medium')).toBe(severityMedium)
    })
    it('returns low color for low severity and unknown', () => {
      expect(severityColor('low')).toBe(severityLow)
      expect(severityColor('')).toBe(severityLow)
      expect(severityColor('other')).toBe(severityLow)
    })
  })
})
