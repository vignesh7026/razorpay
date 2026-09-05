import { describe, expect, it } from 'vitest'
import { formatInr, formatPct } from './constants'

describe('formatInr', () => {
  it('formats with the rupee sign and Indian digit grouping', () => {
    expect(formatInr(753124)).toBe('₹7,53,124')
  })

  it('rounds fractional amounts to the nearest rupee', () => {
    expect(formatInr(212407.69)).toBe('₹2,12,408')
  })

  it('handles zero', () => {
    expect(formatInr(0)).toBe('₹0')
  })
})

describe('formatPct', () => {
  it('converts a 0-1 rate to a percentage string with one decimal by default', () => {
    expect(formatPct(0.282)).toBe('28.2%')
  })

  it('respects a custom digit count', () => {
    expect(formatPct(0.28234, 2)).toBe('28.23%')
  })

  it('handles zero', () => {
    expect(formatPct(0)).toBe('0.0%')
  })
})
